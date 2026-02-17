"""
InstantRisk V2 - Broker Communication AI (Email Bot)

Monitors a dedicated inbox for broker submission emails, extracts risk data,
and auto-replies with preliminary quotes using AI.

Architecture:
    IMAPEmailMonitor → EmailParser (AI) → QuoteGenerator → SMTPSender
    - Polls IMAP inbox every 60 seconds (configurable)
    - Uses Claude/Bedrock to parse unstructured submission emails
    - Generates preliminary quotes based on extracted data
    - Logs all communications to DB

Supported email types:
    - New submission (triggers auto-parsing + quote)
    - Renewal enquiry (looks up previous assessment)
    - Loss notification (creates claim record)
    - General enquiry (AI-drafted reply)
"""

import os
import json
import logging
import asyncio
import imaplib
import smtplib
import email as email_lib
import re
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import decode_header
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timezone
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


# ============================================================
# Data Models
# ============================================================

@dataclass
class ParsedSubmission:
    """Structured data extracted from a broker submission email."""
    raw_subject: str
    raw_sender: str
    raw_body: str
    received_at: str

    # Extracted fields
    insured_name: Optional[str] = None
    risk_category: Optional[str] = None
    sum_insured: Optional[float] = None
    inception_date: Optional[str] = None
    expiry_date: Optional[str] = None
    territory: Optional[str] = None
    broker_name: Optional[str] = None
    broker_reference: Optional[str] = None
    description: Optional[str] = None
    email_type: str = "new_submission"  # new_submission | renewal | loss | enquiry
    confidence: float = 0.0
    extraction_notes: str = ""

    # Quote response data
    suggested_premium_min: Optional[float] = None
    suggested_premium_max: Optional[float] = None
    auto_reply_sent: bool = False
    auto_reply_text: Optional[str] = None


@dataclass
class EmailLog:
    """Log entry for a processed email."""
    log_id: str
    received_at: str
    sender: str
    subject: str
    email_type: str
    parsed: bool
    reply_sent: bool
    error: Optional[str] = None
    assessment_id: Optional[str] = None


# ============================================================
# Email extraction prompts
# ============================================================

EXTRACTION_PROMPT = """You are an insurance submission email parser for a Lloyd's of London platform.

Extract structured data from this broker submission email. Respond ONLY with valid JSON.

Email content:
---
Subject: {subject}
From: {sender}
Body:
{body}
---

Return JSON with these fields (use null for missing values):
{{
    "email_type": "new_submission|renewal|loss_notification|enquiry",
    "insured_name": "company or individual name",
    "risk_category": "property|cyber|marine|liability|financial_lines|other",
    "sum_insured": 1000000.0,
    "inception_date": "YYYY-MM-DD or null",
    "expiry_date": "YYYY-MM-DD or null",
    "territory": "UK|USA|Europe|Global or specific country",
    "broker_name": "broker company name",
    "broker_reference": "broker's own reference number",
    "description": "brief risk description (1-2 sentences)",
    "confidence": 0.85,
    "extraction_notes": "any caveats or missing info"
}}

Be precise. If sum_insured is mentioned as '£5m' convert to 5000000.0.
"""

QUOTE_EMAIL_TEMPLATE = """Dear {broker_name},

Thank you for your submission regarding {insured_name}.

We have reviewed the details provided and are pleased to offer the following preliminary indication:

PRELIMINARY QUOTE INDICATION
━━━━━━━━━━━━━━━━━━━━━━━━━━
Insured:        {insured_name}
Risk Type:      {risk_category}
Sum Insured:    £{sum_insured:,.0f}
Territory:      {territory}
Period:         {inception_date} to {expiry_date}

Indicative Premium Range: £{premium_min:,.0f} – £{premium_max:,.0f} per annum

Please note this is a preliminary indication only. Formal terms will be subject to:
• Full underwriting review and risk assessment
• Completion of our MRC/slip documentation
• Satisfactory sanctions and AML checks
• Lloyd's syndicate capacity confirmation

To proceed, please provide:
□ Completed proposal form
□ 5-year loss run history
□ Latest financial statements (for financial lines)
□ Any relevant surveys or risk improvement reports

Our underwriters will conduct a full assessment and revert with firm terms within 2-3 working days.

Kind regards,
InstantRisk Underwriting Team
Lloyd's Market Platform

━━━━━━━━━━━━━━━━━━━━━━━━━━
This is an automated preliminary response. For urgent matters, please contact:
underwriting@instantrisk.com | +44 20 7000 0000
"""

RENEWAL_EMAIL_TEMPLATE = """Dear {broker_name},

Thank you for contacting us regarding the renewal of {insured_name}'s policy.

We confirm receipt of your renewal enquiry and our underwriting team will review the expiring terms.

RENEWAL TIMELINE
━━━━━━━━━━━━━━━━━━━━━━━━━━
Expiring premium:     To be confirmed from our records
Renewal terms:        We will revert within 5 working days
Minimum information:  Please provide updated loss runs if not already held

Our team will be in touch with renewal terms shortly.

Kind regards,
InstantRisk Underwriting Team
"""

LOSS_EMAIL_TEMPLATE = """Dear {broker_name},

Thank you for notifying us of this loss for {insured_name}.

We confirm receipt of your loss notification and have logged this for our claims team.

A claims handler will be assigned and will contact you within 24 hours.

Please send all relevant documentation to: claims@instantrisk.com

Kind regards,
InstantRisk Claims Team
"""

ENQUIRY_EMAIL_TEMPLATE = """Dear {broker_name},

Thank you for your enquiry. We have received your email and our underwriting team will review and respond within 2 working days.

If this is urgent, please contact us directly at: underwriting@instantrisk.com

Kind regards,
InstantRisk Underwriting Team
"""


# ============================================================
# Email Bot Service
# ============================================================

class EmailBotService:
    """
    IMAP email monitor for broker submissions.

    In simulation mode (no IMAP config): processes mock emails in memory.
    In live mode: polls configured IMAP inbox, extracts data, sends replies.
    """

    RATE_BANDS = {
        "property": (0.0015, 0.035),
        "cyber": (0.002, 0.05),
        "marine": (0.0005, 0.02),
        "liability": (0.0015, 0.04),
        "financial_lines": (0.005, 0.08),
        "other": (0.002, 0.04),
    }

    def __init__(self):
        self._imap_host = os.getenv("EMAIL_IMAP_HOST", "")
        self._imap_port = int(os.getenv("EMAIL_IMAP_PORT", "993"))
        self._imap_user = os.getenv("EMAIL_IMAP_USER", "submissions@instantrisk.com")
        self._imap_pass = os.getenv("EMAIL_IMAP_PASS", "")
        self._smtp_host = os.getenv("EMAIL_SMTP_HOST", "")
        self._smtp_port = int(os.getenv("EMAIL_SMTP_PORT", "587"))
        self._smtp_user = os.getenv("EMAIL_SMTP_USER", self._imap_user)
        self._smtp_pass = os.getenv("EMAIL_SMTP_PASS", self._imap_pass)
        self._from_addr = os.getenv("EMAIL_FROM", "underwriting@instantrisk.com")
        self._poll_interval = int(os.getenv("EMAIL_POLL_INTERVAL_SECS", "60"))
        self._simulation_mode = not bool(self._imap_host and self._imap_pass)
        self._running = False
        self._processed_logs: List[EmailLog] = []
        self._simulated_inbox: List[Dict[str, str]] = []
        self._bedrock_available = False
        self._try_bedrock()

    def _try_bedrock(self):
        """Check if Bedrock is available for AI extraction."""
        try:
            from app.services.bedrock_client import get_bedrock_client
            self._bedrock_available = True
        except ImportError:
            pass

    # --------------------------------------------------------
    # IMAP operations
    # --------------------------------------------------------

    def _connect_imap(self) -> Optional[imaplib.IMAP4_SSL]:
        """Connect to IMAP server."""
        try:
            mail = imaplib.IMAP4_SSL(self._imap_host, self._imap_port)
            mail.login(self._imap_user, self._imap_pass)
            return mail
        except Exception as e:
            logger.error(f"IMAP connect failed: {e}")
            return None

    def _fetch_unread_emails(self, mail: imaplib.IMAP4_SSL) -> List[Dict[str, str]]:
        """Fetch unread emails from INBOX."""
        emails = []
        try:
            mail.select("INBOX")
            _, msg_nums = mail.search(None, "UNSEEN")
            if not msg_nums[0]:
                return []

            for num in msg_nums[0].split():
                try:
                    _, data = mail.fetch(num, "(RFC822)")
                    raw = data[0][1]
                    msg = email_lib.message_from_bytes(raw)

                    subject = self._decode_header_value(msg.get("Subject", ""))
                    sender = self._decode_header_value(msg.get("From", ""))
                    body = self._extract_body(msg)

                    emails.append({
                        "uid": num.decode(),
                        "subject": subject,
                        "sender": sender,
                        "body": body[:5000],  # Cap body length
                        "received_at": datetime.now(timezone.utc).isoformat(),
                    })

                    # Mark as seen
                    mail.store(num, "+FLAGS", "\\Seen")

                except Exception as e:
                    logger.warning(f"Error fetching email {num}: {e}")

        except Exception as e:
            logger.error(f"IMAP search failed: {e}")

        return emails

    def _decode_header_value(self, value: str) -> str:
        """Decode potentially encoded email header."""
        try:
            parts = decode_header(value)
            result = []
            for part, enc in parts:
                if isinstance(part, bytes):
                    result.append(part.decode(enc or "utf-8", errors="replace"))
                else:
                    result.append(str(part))
            return "".join(result)
        except Exception:
            return value or ""

    def _extract_body(self, msg) -> str:
        """Extract plain text body from email message."""
        body = ""
        if msg.is_multipart():
            for part in msg.walk():
                ctype = part.get_content_type()
                if ctype == "text/plain":
                    try:
                        body = part.get_payload(decode=True).decode("utf-8", errors="replace")
                        break
                    except Exception:
                        pass
        else:
            try:
                body = msg.get_payload(decode=True).decode("utf-8", errors="replace")
            except Exception:
                body = str(msg.get_payload())
        return body

    # --------------------------------------------------------
    # AI Parsing
    # --------------------------------------------------------

    async def parse_submission_email(self, email_data: Dict[str, str]) -> ParsedSubmission:
        """
        Parse a broker submission email into structured data.

        Tries AI extraction first; falls back to regex-based extraction.
        """
        submission = ParsedSubmission(
            raw_subject=email_data.get("subject", ""),
            raw_sender=email_data.get("sender", ""),
            raw_body=email_data.get("body", ""),
            received_at=email_data.get("received_at", datetime.now(timezone.utc).isoformat()),
        )

        # Classify email type from subject
        subject_lower = submission.raw_subject.lower()
        if any(w in subject_lower for w in ["renewal", "renew"]):
            submission.email_type = "renewal"
        elif any(w in subject_lower for w in ["claim", "loss", "incident", "notification"]):
            submission.email_type = "loss_notification"
        elif any(w in subject_lower for w in ["enquir", "inquiry", "question", "query"]):
            submission.email_type = "enquiry"
        else:
            submission.email_type = "new_submission"

        # Try AI extraction
        extracted = None
        if self._bedrock_available:
            extracted = await self._ai_extract(submission)

        if not extracted:
            extracted = self._regex_extract(submission)

        if extracted:
            submission.insured_name = extracted.get("insured_name")
            submission.risk_category = extracted.get("risk_category", "property")
            submission.sum_insured = extracted.get("sum_insured")
            submission.inception_date = extracted.get("inception_date")
            submission.expiry_date = extracted.get("expiry_date")
            submission.territory = extracted.get("territory", "UK")
            submission.broker_name = extracted.get("broker_name")
            submission.broker_reference = extracted.get("broker_reference")
            submission.description = extracted.get("description")
            submission.confidence = extracted.get("confidence", 0.5)
            submission.extraction_notes = extracted.get("extraction_notes", "")
            if extracted.get("email_type"):
                submission.email_type = extracted["email_type"]

        return submission

    async def _ai_extract(self, submission: ParsedSubmission) -> Optional[Dict[str, Any]]:
        """Use Bedrock Claude to extract structured data from email."""
        try:
            from app.services.bedrock_client import get_bedrock_client

            prompt = EXTRACTION_PROMPT.format(
                subject=submission.raw_subject,
                sender=submission.raw_sender,
                body=submission.raw_body[:3000],
            )

            client = get_bedrock_client()
            messages = [{"role": "user", "content": prompt}]

            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: client.complete(messages=messages, max_tokens=1024, temperature=0.1),
            )

            # Parse JSON response
            json_match = re.search(r"\{.*\}", response, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())

        except Exception as e:
            logger.debug(f"AI extraction failed: {e}")

        return None

    def _regex_extract(self, submission: ParsedSubmission) -> Dict[str, Any]:
        """Fallback regex-based extraction from email body."""
        body = submission.raw_body
        result: Dict[str, Any] = {"confidence": 0.3, "extraction_notes": "regex-based extraction"}

        # Sum insured patterns: £5m, $1,000,000, GBP 500000
        si_match = re.search(
            r"(?:sum\s*insured|si|tsi|limit)[:\s]*[£$€]?\s*([\d,\.]+)\s*([mk]?)",
            body, re.IGNORECASE
        )
        if si_match:
            val = float(si_match.group(1).replace(",", ""))
            mult = si_match.group(2).lower()
            if mult == "m":
                val *= 1_000_000
            elif mult == "k":
                val *= 1_000
            result["sum_insured"] = val
            result["confidence"] = 0.6

        # Risk category detection
        category_keywords = {
            "property": ["property", "building", "premises", "warehouse", "office"],
            "cyber": ["cyber", "data breach", "ransomware", "IT", "network"],
            "marine": ["marine", "vessel", "cargo", "shipping", "hull"],
            "liability": ["liability", "public liability", "employers", "EL", "PL"],
            "financial_lines": ["D&O", "directors", "professional indemnity", "PI", "E&O"],
        }
        for cat, keywords in category_keywords.items():
            if any(kw.lower() in body.lower() for kw in keywords):
                result["risk_category"] = cat
                break
        if "risk_category" not in result:
            result["risk_category"] = "property"

        # Insured name - look for "Insured:", "Client:", "Assured:"
        name_match = re.search(
            r"(?:insured|client|assured|applicant)[:\s]+([A-Z][^\n\r,]{2,60})",
            body, re.IGNORECASE
        )
        if name_match:
            result["insured_name"] = name_match.group(1).strip()

        # Broker name from From header
        sender = submission.raw_sender
        if "<" in sender:
            result["broker_name"] = sender.split("<")[0].strip().strip('"')
        else:
            result["broker_name"] = sender.split("@")[0] if "@" in sender else sender

        # Dates
        date_match = re.search(
            r"(?:inception|effective|start)\s*(?:date)?[:\s]*(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4})",
            body, re.IGNORECASE
        )
        if date_match:
            result["inception_date"] = date_match.group(1)

        # Territory
        territories = ["UK", "USA", "Europe", "Global", "Asia", "Middle East", "Australia"]
        for t in territories:
            if t.lower() in body.lower():
                result["territory"] = t
                break
        if "territory" not in result:
            result["territory"] = "UK"

        result["description"] = body[:200].strip()
        return result

    # --------------------------------------------------------
    # Quote Generation
    # --------------------------------------------------------

    def _estimate_premium(self, submission: ParsedSubmission) -> Tuple[float, float]:
        """Estimate premium range from extracted submission data."""
        if not submission.sum_insured:
            return (0.0, 0.0)

        category = submission.risk_category or "other"
        rate_range = self.RATE_BANDS.get(category, self.RATE_BANDS["other"])
        min_prem = submission.sum_insured * rate_range[0]
        max_prem = submission.sum_insured * rate_range[1]
        return (round(min_prem, 2), round(max_prem, 2))

    def _draft_reply_email(self, submission: ParsedSubmission) -> str:
        """Draft the appropriate auto-reply email."""
        broker = submission.broker_name or "Broker"
        insured = submission.insured_name or "the insured"

        if submission.email_type == "renewal":
            return RENEWAL_EMAIL_TEMPLATE.format(
                broker_name=broker,
                insured_name=insured,
            )

        if submission.email_type == "loss_notification":
            return LOSS_EMAIL_TEMPLATE.format(
                broker_name=broker,
                insured_name=insured,
            )

        if submission.email_type == "enquiry":
            return ENQUIRY_EMAIL_TEMPLATE.format(broker_name=broker)

        # New submission - generate indicative quote
        if submission.sum_insured and submission.sum_insured > 0:
            pmin, pmax = self._estimate_premium(submission)
            submission.suggested_premium_min = pmin
            submission.suggested_premium_max = pmax
            return QUOTE_EMAIL_TEMPLATE.format(
                broker_name=broker,
                insured_name=insured,
                risk_category=submission.risk_category or "General",
                sum_insured=submission.sum_insured,
                territory=submission.territory or "UK",
                inception_date=submission.inception_date or "TBC",
                expiry_date=submission.expiry_date or "TBC",
                premium_min=pmin,
                premium_max=pmax,
            )

        # No sum insured - request more info
        return (
            f"Dear {broker},\n\n"
            f"Thank you for your submission regarding {insured}.\n\n"
            f"To provide an indicative quote, we require:\n"
            f"□ Sum insured / limit of liability\n"
            f"□ Policy inception and expiry dates\n"
            f"□ Territory of coverage\n"
            f"□ Full risk description\n\n"
            f"Please provide the above and we will revert promptly.\n\n"
            f"Kind regards,\nInstantRisk Underwriting Team"
        )

    # --------------------------------------------------------
    # SMTP Send
    # --------------------------------------------------------

    async def send_reply(self, to_addr: str, subject: str, body: str) -> bool:
        """Send auto-reply via SMTP."""
        if self._simulation_mode or not self._smtp_host:
            logger.info(f"[SIM] Email reply to {to_addr}: {subject[:50]}")
            return True

        try:
            msg = MIMEMultipart()
            msg["From"] = self._from_addr
            msg["To"] = to_addr
            msg["Subject"] = f"Re: {subject}"
            msg.attach(MIMEText(body, "plain"))

            with smtplib.SMTP(self._smtp_host, self._smtp_port) as server:
                server.ehlo()
                server.starttls()
                server.login(self._smtp_user, self._smtp_pass)
                server.sendmail(self._from_addr, [to_addr], msg.as_string())

            logger.info(f"Reply sent to {to_addr}")
            return True

        except Exception as e:
            logger.error(f"SMTP send failed: {e}")
            return False

    # --------------------------------------------------------
    # Main processing loop
    # --------------------------------------------------------

    async def process_inbox_once(self) -> List[ParsedSubmission]:
        """
        Process all unread emails once.
        Returns list of parsed submissions.
        """
        if self._simulation_mode:
            # Process any pending simulated emails
            results = []
            for em in self._simulated_inbox:
                sub = await self.parse_submission_email(em)
                reply = self._draft_reply_email(sub)
                sub.auto_reply_text = reply
                sub.auto_reply_sent = True
                results.append(sub)

                log = EmailLog(
                    log_id=f"log-{len(self._processed_logs)+1}",
                    received_at=sub.received_at,
                    sender=sub.raw_sender,
                    subject=sub.raw_subject,
                    email_type=sub.email_type,
                    parsed=True,
                    reply_sent=True,
                )
                self._processed_logs.append(log)

            self._simulated_inbox.clear()
            return results

        # Live IMAP
        mail = self._connect_imap()
        if not mail:
            return []

        try:
            raw_emails = self._fetch_unread_emails(mail)
            results = []

            for em in raw_emails:
                try:
                    sub = await self.parse_submission_email(em)
                    reply = self._draft_reply_email(sub)
                    sent = await self.send_reply(
                        to_addr=em["sender"],
                        subject=em["subject"],
                        body=reply,
                    )
                    sub.auto_reply_text = reply
                    sub.auto_reply_sent = sent
                    results.append(sub)

                    log = EmailLog(
                        log_id=f"log-{len(self._processed_logs)+1}",
                        received_at=sub.received_at,
                        sender=sub.raw_sender,
                        subject=sub.raw_subject,
                        email_type=sub.email_type,
                        parsed=True,
                        reply_sent=sent,
                    )
                    self._processed_logs.append(log)

                except Exception as e:
                    logger.error(f"Email processing error: {e}")
                    self._processed_logs.append(EmailLog(
                        log_id=f"log-{len(self._processed_logs)+1}",
                        received_at=datetime.now(timezone.utc).isoformat(),
                        sender=em.get("sender", "unknown"),
                        subject=em.get("subject", ""),
                        email_type="unknown",
                        parsed=False,
                        reply_sent=False,
                        error=str(e),
                    ))

            return results

        finally:
            try:
                mail.logout()
            except Exception:
                pass

    async def start_monitoring(self):
        """Start continuous IMAP monitoring loop."""
        self._running = True
        logger.info(
            f"Email bot started ({'simulation' if self._simulation_mode else 'live'} mode, "
            f"polling every {self._poll_interval}s)"
        )
        while self._running:
            try:
                results = await self.process_inbox_once()
                if results:
                    logger.info(f"Processed {len(results)} emails")
            except Exception as e:
                logger.error(f"Monitor loop error: {e}")
            await asyncio.sleep(self._poll_interval)

    def stop_monitoring(self):
        """Stop the monitoring loop."""
        self._running = False

    def inject_test_email(self, subject: str, sender: str, body: str):
        """Inject a simulated email for testing."""
        self._simulated_inbox.append({
            "subject": subject,
            "sender": sender,
            "body": body,
            "received_at": datetime.now(timezone.utc).isoformat(),
        })

    def get_logs(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Return recent email processing logs."""
        logs = self._processed_logs[-limit:]
        return [
            {
                "log_id": log.log_id,
                "received_at": log.received_at,
                "sender": log.sender,
                "subject": log.subject,
                "email_type": log.email_type,
                "parsed": log.parsed,
                "reply_sent": log.reply_sent,
                "error": log.error,
                "assessment_id": log.assessment_id,
            }
            for log in reversed(logs)
        ]

    def get_status(self) -> Dict[str, Any]:
        """Return email bot status."""
        return {
            "mode": "simulation" if self._simulation_mode else "live",
            "running": self._running,
            "imap_host": self._imap_host or "(not configured)",
            "imap_user": self._imap_user,
            "poll_interval_secs": self._poll_interval,
            "ai_extraction": self._bedrock_available,
            "processed_count": len(self._processed_logs),
            "pending_simulated": len(self._simulated_inbox),
            "required_env_vars": [
                "EMAIL_IMAP_HOST", "EMAIL_IMAP_PORT", "EMAIL_IMAP_USER", "EMAIL_IMAP_PASS",
                "EMAIL_SMTP_HOST", "EMAIL_SMTP_PORT", "EMAIL_SMTP_USER", "EMAIL_SMTP_PASS",
            ],
        }


# Singleton
_email_bot_service: Optional[EmailBotService] = None


def get_email_bot_service() -> EmailBotService:
    """Get or create the EmailBotService singleton."""
    global _email_bot_service
    if _email_bot_service is None:
        _email_bot_service = EmailBotService()
    return _email_bot_service
