"""
Loss Run Parser Service

Parses loss run documents from PDF, Excel, and CSV formats.
Uses Bedrock Claude for PDF table extraction.
"""
import io
import re
import json
from datetime import datetime, date
from decimal import Decimal, InvalidOperation
from typing import Optional, List, Dict, Any, Tuple, BinaryIO
from enum import Enum
import logging

import pandas as pd
from pydantic import BaseModel, Field, validator

from app.config import settings
from app.services.bedrock_client import get_bedrock_client
from app.services.s3_client import get_documents_client, generate_loss_run_key

logger = logging.getLogger(__name__)


class ParsedClaim(BaseModel):
    """Structured claim data extracted from loss run."""
    claim_number: Optional[str] = None
    claim_date: Optional[date] = None
    report_date: Optional[date] = None
    close_date: Optional[date] = None
    policy_year: Optional[int] = None
    policy_effective_date: Optional[date] = None
    policy_expiration_date: Optional[date] = None
    claim_type: Optional[str] = None
    claim_description: Optional[str] = None
    claimant_name: Optional[str] = None
    status: Optional[str] = None
    amount_paid: Optional[Decimal] = Field(default=Decimal(0))
    amount_reserved: Optional[Decimal] = Field(default=Decimal(0))
    expense_paid: Optional[Decimal] = Field(default=Decimal(0))
    expense_reserved: Optional[Decimal] = Field(default=Decimal(0))
    subrogation_amount: Optional[Decimal] = Field(default=Decimal(0))
    deductible_applied: Optional[Decimal] = Field(default=Decimal(0))
    row_number: Optional[int] = None
    parsing_confidence: float = 1.0
    parsing_notes: Optional[str] = None

    class Config:
        json_encoders = {
            Decimal: lambda v: float(v) if v else 0.0,
            date: lambda v: v.isoformat() if v else None,
        }


class ParseResult(BaseModel):
    """Result of parsing a loss run document."""
    success: bool
    claims: List[ParsedClaim] = []
    file_type: str
    total_rows: int = 0
    parsed_rows: int = 0
    error_rows: int = 0
    overall_confidence: float = 1.0
    errors: List[str] = []
    warnings: List[str] = []
    metadata: Dict[str, Any] = {}


class LossRunParser:
    """Parser for loss run documents."""

    # Common column name mappings
    COLUMN_MAPPINGS = {
        "claim_number": [
            "claim_number", "claim_no", "claim #", "claim id", "claimid",
            "claim ref", "reference", "ref no", "file number"
        ],
        "claim_date": [
            "claim_date", "date of loss", "loss date", "accident date",
            "date of occurrence", "occurrence date", "incident date", "dol"
        ],
        "report_date": [
            "report_date", "reported date", "date reported", "notice date"
        ],
        "close_date": [
            "close_date", "closed date", "date closed", "closure date"
        ],
        "policy_year": [
            "policy_year", "policy year", "year", "pol year"
        ],
        "claim_type": [
            "claim_type", "type", "loss type", "coverage", "claim category",
            "injury type", "cause"
        ],
        "claim_description": [
            "description", "claim_description", "loss description", "narrative",
            "details", "summary", "notes", "claim summary"
        ],
        "claimant_name": [
            "claimant", "claimant_name", "injured party", "plaintiff", "name"
        ],
        "status": [
            "status", "claim status", "state", "disposition"
        ],
        "amount_paid": [
            "paid", "amount_paid", "indemnity paid", "loss paid",
            "paid amount", "total paid", "paid loss"
        ],
        "amount_reserved": [
            "reserved", "amount_reserved", "outstanding", "reserve",
            "case reserve", "loss reserve", "open reserve"
        ],
        "expense_paid": [
            "expense_paid", "alae paid", "expense", "legal expense",
            "defense paid", "allocated expense"
        ],
        "expense_reserved": [
            "expense_reserved", "alae reserve", "expense reserve",
            "defense reserve"
        ],
    }

    def __init__(self):
        self.bedrock = get_bedrock_client()
        self.s3 = get_documents_client()

    async def parse_file(
        self,
        file_obj: BinaryIO,
        filename: str,
        assessment_id: str,
    ) -> ParseResult:
        """Parse a loss run file.

        Args:
            file_obj: File-like object
            filename: Original filename
            assessment_id: Assessment UUID

        Returns:
            ParseResult with extracted claims
        """
        ext = filename.lower().split(".")[-1]

        # Store raw file to S3
        s3_key = generate_loss_run_key(assessment_id, filename)
        file_obj.seek(0)
        self.s3.upload_file(
            file_obj,
            s3_key,
            content_type=self._get_content_type(ext),
            metadata={"assessment_id": assessment_id, "original_filename": filename},
        )
        file_obj.seek(0)

        # Parse based on file type
        if ext == "csv":
            result = await self._parse_csv(file_obj, filename)
        elif ext in ("xlsx", "xls"):
            result = await self._parse_excel(file_obj, filename)
        elif ext == "pdf":
            result = await self._parse_pdf(file_obj, filename)
        else:
            return ParseResult(
                success=False,
                file_type=ext,
                errors=[f"Unsupported file type: {ext}"],
            )

        # Add S3 path to metadata
        result.metadata["s3_key"] = s3_key
        result.metadata["original_filename"] = filename

        return result

    async def _parse_csv(self, file_obj: BinaryIO, filename: str) -> ParseResult:
        """Parse CSV loss run file."""
        try:
            # Try different encodings
            file_obj.seek(0)
            content = file_obj.read()

            for encoding in ["utf-8", "latin-1", "cp1252"]:
                try:
                    df = pd.read_csv(io.BytesIO(content), encoding=encoding)
                    break
                except UnicodeDecodeError:
                    continue
            else:
                return ParseResult(
                    success=False,
                    file_type="csv",
                    errors=["Could not decode CSV file with common encodings"],
                )

            return self._parse_dataframe(df, "csv")

        except Exception as e:
            logger.error(f"CSV parsing error: {e}")
            return ParseResult(
                success=False,
                file_type="csv",
                errors=[f"Failed to parse CSV: {str(e)}"],
            )

    async def _parse_excel(self, file_obj: BinaryIO, filename: str) -> ParseResult:
        """Parse Excel loss run file."""
        try:
            file_obj.seek(0)
            # Try to read all sheets
            xlsx = pd.ExcelFile(file_obj)

            # Find the sheet most likely to contain loss run data
            best_sheet = None
            best_score = 0

            for sheet_name in xlsx.sheet_names:
                df = pd.read_excel(xlsx, sheet_name=sheet_name)
                score = self._score_sheet(df)
                if score > best_score:
                    best_score = score
                    best_sheet = sheet_name

            if best_sheet is None:
                return ParseResult(
                    success=False,
                    file_type="excel",
                    errors=["No suitable sheet found in Excel file"],
                )

            df = pd.read_excel(xlsx, sheet_name=best_sheet)
            result = self._parse_dataframe(df, "excel")
            result.metadata["sheet_name"] = best_sheet

            return result

        except Exception as e:
            logger.error(f"Excel parsing error: {e}")
            return ParseResult(
                success=False,
                file_type="excel",
                errors=[f"Failed to parse Excel: {str(e)}"],
            )

    async def _parse_pdf(self, file_obj: BinaryIO, filename: str) -> ParseResult:
        """Parse PDF loss run using Bedrock Claude for table extraction."""
        try:
            import base64
            file_obj.seek(0)
            pdf_bytes = file_obj.read()
            pdf_base64 = base64.b64encode(pdf_bytes).decode("utf-8")

            # Use Claude to extract tabular data
            extraction_prompt = """Analyze this PDF document which contains insurance loss run data (claims history).

Extract ALL claims from the document into a structured JSON format. For each claim, extract:
- claim_number: The claim or file reference number
- claim_date: Date of loss/accident (format: YYYY-MM-DD)
- report_date: Date claim was reported (format: YYYY-MM-DD)
- close_date: Date claim was closed, if applicable (format: YYYY-MM-DD)
- policy_year: Policy year (integer)
- claim_type: Type of claim (bodily injury, property damage, etc.)
- claim_description: Brief description of the claim
- claimant_name: Name of claimant if available
- status: open, closed, or other status
- amount_paid: Amount paid to date (number, no currency symbols)
- amount_reserved: Outstanding reserve amount (number)
- expense_paid: Legal/adjustment expenses paid (number)
- expense_reserved: Legal/adjustment expenses reserved (number)

Return ONLY valid JSON in this format:
{
  "claims": [
    {
      "claim_number": "...",
      "claim_date": "YYYY-MM-DD",
      ...
    }
  ],
  "metadata": {
    "policy_holder": "Company name if found",
    "policy_number": "Policy number if found",
    "valuation_date": "Report valuation date if found",
    "total_rows_found": number
  }
}

If no claims are found, return {"claims": [], "metadata": {"error": "No claims found"}}
Parse ALL claims visible in the document - do not truncate."""

            # Call Bedrock with PDF
            response = await self.bedrock.chat(
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "document",
                                "source": {
                                    "type": "base64",
                                    "media_type": "application/pdf",
                                    "data": pdf_base64,
                                },
                            },
                            {"type": "text", "text": extraction_prompt},
                        ],
                    }
                ],
                max_tokens=8192,
                temperature=0.1,  # Low temperature for structured extraction
            )

            # Parse response
            response_text = response.get("content", [{}])[0].get("text", "")

            # Extract JSON from response
            json_match = re.search(r"\{[\s\S]*\}", response_text)
            if not json_match:
                return ParseResult(
                    success=False,
                    file_type="pdf",
                    errors=["Could not extract structured data from PDF"],
                )

            extracted = json.loads(json_match.group())
            claims_data = extracted.get("claims", [])

            if not claims_data:
                return ParseResult(
                    success=True,
                    file_type="pdf",
                    claims=[],
                    total_rows=0,
                    parsed_rows=0,
                    overall_confidence=0.5,
                    warnings=["No claims found in PDF"],
                    metadata=extracted.get("metadata", {}),
                )

            # Convert to ParsedClaim objects
            claims = []
            errors = []

            for i, claim_data in enumerate(claims_data):
                try:
                    claim = self._dict_to_claim(claim_data, row_number=i + 1)
                    claim.parsing_confidence = 0.85  # PDF extraction confidence
                    claims.append(claim)
                except Exception as e:
                    errors.append(f"Row {i + 1}: {str(e)}")

            return ParseResult(
                success=True,
                file_type="pdf",
                claims=claims,
                total_rows=len(claims_data),
                parsed_rows=len(claims),
                error_rows=len(errors),
                overall_confidence=0.85,
                errors=errors,
                metadata=extracted.get("metadata", {}),
            )

        except json.JSONDecodeError as e:
            logger.error(f"PDF JSON parsing error: {e}")
            return ParseResult(
                success=False,
                file_type="pdf",
                errors=[f"Failed to parse extracted data: {str(e)}"],
            )
        except Exception as e:
            logger.error(f"PDF parsing error: {e}")
            return ParseResult(
                success=False,
                file_type="pdf",
                errors=[f"Failed to parse PDF: {str(e)}"],
            )

    def _parse_dataframe(self, df: pd.DataFrame, file_type: str) -> ParseResult:
        """Parse a pandas DataFrame into claims."""
        if df.empty:
            return ParseResult(
                success=True,
                file_type=file_type,
                claims=[],
                warnings=["File contains no data rows"],
            )

        # Normalize column names
        df.columns = [str(c).lower().strip() for c in df.columns]

        # Map columns
        column_map = self._map_columns(df.columns.tolist())

        # Parse rows
        claims = []
        errors = []
        warnings = []

        for idx, row in df.iterrows():
            try:
                claim = self._row_to_claim(row, column_map, row_number=idx + 2)  # +2 for header
                if claim:
                    claims.append(claim)
            except Exception as e:
                errors.append(f"Row {idx + 2}: {str(e)}")

        # Calculate confidence based on mapping quality
        mapped_count = len([k for k, v in column_map.items() if v])
        total_important = len(["claim_date", "amount_paid", "amount_reserved", "status"])
        confidence = min(1.0, (mapped_count / 8) + 0.2)  # Base confidence on columns mapped

        if not column_map.get("claim_date") and not column_map.get("claim_number"):
            warnings.append("Could not identify claim date or claim number column")
            confidence *= 0.7

        return ParseResult(
            success=True,
            file_type=file_type,
            claims=claims,
            total_rows=len(df),
            parsed_rows=len(claims),
            error_rows=len(errors),
            overall_confidence=confidence,
            errors=errors,
            warnings=warnings,
            metadata={"columns_mapped": column_map},
        )

    def _map_columns(self, columns: List[str]) -> Dict[str, Optional[str]]:
        """Map DataFrame columns to claim fields."""
        column_map = {}

        for field, aliases in self.COLUMN_MAPPINGS.items():
            column_map[field] = None
            for col in columns:
                col_clean = col.lower().strip().replace("_", " ").replace("-", " ")
                for alias in aliases:
                    if alias in col_clean or col_clean in alias:
                        column_map[field] = col
                        break
                if column_map[field]:
                    break

        return column_map

    def _row_to_claim(
        self,
        row: pd.Series,
        column_map: Dict[str, Optional[str]],
        row_number: int,
    ) -> Optional[ParsedClaim]:
        """Convert a DataFrame row to a ParsedClaim."""
        def get_value(field: str) -> Any:
            col = column_map.get(field)
            if col and col in row:
                val = row[col]
                if pd.isna(val):
                    return None
                return val
            return None

        # Skip rows with no meaningful data
        paid = get_value("amount_paid")
        reserved = get_value("amount_reserved")
        claim_date = get_value("claim_date")
        claim_num = get_value("claim_number")

        if paid is None and reserved is None and claim_date is None and claim_num is None:
            return None

        return ParsedClaim(
            claim_number=str(get_value("claim_number")) if get_value("claim_number") else None,
            claim_date=self._parse_date(get_value("claim_date")),
            report_date=self._parse_date(get_value("report_date")),
            close_date=self._parse_date(get_value("close_date")),
            policy_year=self._parse_int(get_value("policy_year")),
            claim_type=str(get_value("claim_type")) if get_value("claim_type") else None,
            claim_description=str(get_value("claim_description")) if get_value("claim_description") else None,
            claimant_name=str(get_value("claimant_name")) if get_value("claimant_name") else None,
            status=str(get_value("status")).lower() if get_value("status") else None,
            amount_paid=self._parse_decimal(get_value("amount_paid")),
            amount_reserved=self._parse_decimal(get_value("amount_reserved")),
            expense_paid=self._parse_decimal(get_value("expense_paid")),
            expense_reserved=self._parse_decimal(get_value("expense_reserved")),
            row_number=row_number,
        )

    def _dict_to_claim(self, data: Dict[str, Any], row_number: int) -> ParsedClaim:
        """Convert a dictionary to a ParsedClaim."""
        return ParsedClaim(
            claim_number=data.get("claim_number"),
            claim_date=self._parse_date(data.get("claim_date")),
            report_date=self._parse_date(data.get("report_date")),
            close_date=self._parse_date(data.get("close_date")),
            policy_year=self._parse_int(data.get("policy_year")),
            claim_type=data.get("claim_type"),
            claim_description=data.get("claim_description"),
            claimant_name=data.get("claimant_name"),
            status=data.get("status"),
            amount_paid=self._parse_decimal(data.get("amount_paid")),
            amount_reserved=self._parse_decimal(data.get("amount_reserved")),
            expense_paid=self._parse_decimal(data.get("expense_paid")),
            expense_reserved=self._parse_decimal(data.get("expense_reserved")),
            row_number=row_number,
        )

    def _parse_date(self, value: Any) -> Optional[date]:
        """Parse various date formats."""
        if value is None or (isinstance(value, float) and pd.isna(value)):
            return None

        if isinstance(value, (datetime, date)):
            return value if isinstance(value, date) else value.date()

        if isinstance(value, pd.Timestamp):
            return value.date()

        str_value = str(value).strip()
        if not str_value:
            return None

        # Try common formats
        formats = [
            "%Y-%m-%d", "%m/%d/%Y", "%m-%d-%Y",
            "%d/%m/%Y", "%d-%m-%Y",
            "%Y/%m/%d", "%m/%d/%y", "%d/%m/%y",
        ]

        for fmt in formats:
            try:
                return datetime.strptime(str_value, fmt).date()
            except ValueError:
                continue

        return None

    def _parse_decimal(self, value: Any) -> Decimal:
        """Parse monetary values to Decimal."""
        if value is None or (isinstance(value, float) and pd.isna(value)):
            return Decimal(0)

        if isinstance(value, Decimal):
            return value

        if isinstance(value, (int, float)):
            return Decimal(str(value))

        # Clean string value
        str_value = str(value).strip()
        str_value = re.sub(r"[,$\s]", "", str_value)  # Remove currency symbols and commas
        str_value = str_value.replace("(", "-").replace(")", "")  # Handle accounting format

        if not str_value or str_value == "-":
            return Decimal(0)

        try:
            return Decimal(str_value)
        except InvalidOperation:
            return Decimal(0)

    def _parse_int(self, value: Any) -> Optional[int]:
        """Parse integer value."""
        if value is None or (isinstance(value, float) and pd.isna(value)):
            return None

        try:
            return int(float(value))
        except (ValueError, TypeError):
            return None

    def _score_sheet(self, df: pd.DataFrame) -> int:
        """Score how likely a sheet contains loss run data."""
        if df.empty:
            return 0

        score = 0
        columns = [str(c).lower() for c in df.columns]
        col_text = " ".join(columns)

        # Keywords that suggest loss run data
        keywords = [
            "claim", "loss", "paid", "reserve", "incurred",
            "date", "status", "claimant", "injury", "occurrence"
        ]

        for keyword in keywords:
            if keyword in col_text:
                score += 1

        # Bonus for having monetary columns
        if any(kw in col_text for kw in ["paid", "reserve", "amount"]):
            score += 2

        # Bonus for having date columns
        if "date" in col_text:
            score += 1

        return score

    def _get_content_type(self, ext: str) -> str:
        """Get MIME type for file extension."""
        types = {
            "csv": "text/csv",
            "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "xls": "application/vnd.ms-excel",
            "pdf": "application/pdf",
        }
        return types.get(ext, "application/octet-stream")


# Singleton instance
_parser: Optional[LossRunParser] = None


def get_loss_run_parser() -> LossRunParser:
    """Get singleton parser instance."""
    global _parser
    if _parser is None:
        _parser = LossRunParser()
    return _parser
