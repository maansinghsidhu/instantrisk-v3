"""
Document Generation Router - AI-Powered Insurance Document Generation

Endpoints for generating insurance documents from assessments
using the 5-agent AutoGen pipeline.
"""

import asyncio
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import List, Optional

logger = logging.getLogger(__name__)

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from app.core.database import get_db, AsyncSessionLocal
from app.core.security import get_current_user
from app.models.user import User
from app.models.assessment import Assessment
from app.models.template import Template
from app.models.generated_document import GeneratedDocument, DocumentGenerationJob
from app.schemas.generated_document import (
    DocumentSuggestion,
    DocumentSuggestionResponse,
    LMAClauseSuggestion,
    GenerationJobCreate,
    GenerationJobProgress,
    GenerationStepProgress,
    GenerationJobResponse,
    GeneratedDocumentResponse,
    GeneratedDocumentListResponse,
    GeneratedDocumentUpdate,
    PrefillRequest,
    PrefillResponse,
    FinalizeRequest,
    FinalizeResponse,
)
from app.services.document_generator import document_generator
from app.services.reference_document_service import reference_document_service
from app.services.insurance_templates import get_all_templates, get_template
from app.services.lma_clauses_service import LMAClausesService
from app.services.translation_service import translation_service
from app.data.clause_service import get_clause_service
from app.services.qdrant_service import qdrant_service
from app.models.user import SupportedLanguage
from app.config import settings

# Initialize clause services
lma_clauses_service = LMAClausesService()
clause_service = get_clause_service()  # Full 33k+ clause library

router = APIRouter()


# =============================================================================
# INLINE CLAUSE DEFINITIONS — always available regardless of library/pgvector
# =============================================================================

INLINE_MANDATORY_CLAUSES: dict = {
    # ── Core LMA mandatory clauses (ALL Lloyd's policies) ──
    "LMA5021": {
        "id": "LMA5021",
        "name": "War & Civil War Exclusion",
        "category": "exclusion",
        "source": "lma",
        "is_mandatory": True,
        "text": (
            "This insurance excludes:\n\n"
            "1. Loss, damage, liability or expense directly or indirectly caused by, "
            "contributed to by, resulting from, or arising out of or in connection with:\n"
            "(a) war, invasion, acts of foreign enemies, hostilities or warlike operations "
            "(whether war be declared or not), civil war, rebellion, revolution, insurrection, "
            "civil commotion assuming the proportions of or amounting to an uprising, "
            "military or usurped power; or\n"
            "(b) any act of terrorism being an act of any person acting on behalf of, or in "
            "connection with, any organisation which carries out activities directed towards "
            "the overthrowing or influencing, by force or violence, of any government whether "
            "or not legally constituted; or\n"
            "(c) any action taken in controlling, preventing, suppressing or in any way "
            "relating to (a) and/or (b) above.\n\n"
            "2. If the Underwriters allege that by reason of this exclusion, any loss, damage, "
            "liability or expense is not covered by this insurance the burden of proving the "
            "contrary shall be upon the Assured.\n\n"
            "3. In the event any portion of this exclusion is found to be invalid or "
            "unenforceable, the remainder shall remain in full force and effect."
        ),
    },
    "LMA3100": {
        "id": "LMA3100",
        "name": "Sanctions Limitation & Exclusion Clause",
        "category": "exclusion",
        "source": "lma",
        "is_mandatory": True,
        "text": (
            "No (re)insurer shall be deemed to provide cover and no (re)insurer shall be "
            "liable to pay any claim or provide any benefit hereunder to the extent that "
            "the provision of such cover, payment of such claim or provision of such benefit "
            "would expose that (re)insurer to any sanction, prohibition or restriction under "
            "United Nations resolutions or the trade or economic sanctions, laws or regulations "
            "of the European Union, United Kingdom or United States of America.\n\n"
            "If any such sanction, prohibition or restriction takes effect during the currency "
            "of this insurance, the (re)insurer affected shall have the right to cancel this "
            "insurance by giving 30 days' written notice. Premium shall be adjusted pro rata "
            "for the unexpired period.\n\n"
            "It is understood and agreed that the Insured shall not knowingly engage in any "
            "transaction or activity that would cause the (re)insurer to be in breach of "
            "any applicable sanctions regime."
        ),
    },
    "LMA5390": {
        "id": "LMA5390",
        "name": "Sanctions Limitation & Exclusion Clause",
        "category": "exclusion",
        "source": "lma",
        "is_mandatory": True,
        "text": (
            "No (re)insurer shall be deemed to provide cover and no (re)insurer shall be "
            "liable to pay any claim or provide any benefit hereunder to the extent that "
            "the provision of such cover, payment of such claim or provision of such benefit "
            "would expose that (re)insurer to any sanction, prohibition or restriction under "
            "United Nations resolutions or the trade or economic sanctions, laws or regulations "
            "of the European Union, United Kingdom or United States of America."
        ),
    },
    "LMA5400": {
        "id": "LMA5400",
        "name": "Several Liability Clause",
        "category": "condition",
        "source": "lma",
        "is_mandatory": True,
        "text": (
            "The liability of an insurer under this contract is several and not joint with "
            "other insurers party to this contract. An insurer is liable only for the "
            "proportion of liability it has underwritten. An insurer is not jointly liable "
            "for the proportion of liability underwritten by any other insurer. Nor is an "
            "insurer otherwise responsible for any liability of any other insurer that may "
            "underwrite this contract.\n\n"
            "The proportion of liability under this contract underwritten by an insurer "
            "(or, in the case of a Lloyd's syndicate, the total of the proportions "
            "underwritten by all the members of the syndicate taken together) is shown in "
            "this contract.\n\n"
            "In the case of a Lloyd's syndicate, each member of the syndicate (rather than "
            "the syndicate itself) is an insurer. Each member has underwritten a proportion "
            "of the total shown for the syndicate (that total itself being the total of the "
            "proportions underwritten by all the members of the syndicate taken together). "
            "The liability of each member of the syndicate is several and not joint with "
            "other members. A member is liable only for that member's proportion. A member "
            "is not jointly liable for any other member's proportion."
        ),
    },
    "LMA5027": {
        "id": "LMA5027",
        "name": "Market Reform Contract (MRC) Standard",
        "category": "condition",
        "source": "lma",
        "is_mandatory": True,
        "text": (
            "This insurance is subject to the Market Reform Contract (MRC) provisions as "
            "agreed by the Lloyd's Market Association and the International Underwriting "
            "Association of London.\n\n"
            "The MRC sets out the standard framework for placing insurance and reinsurance "
            "business in the London Market. It provides the structure for the slip and the "
            "policy, ensuring that all necessary commercial and contractual information is "
            "clearly presented.\n\n"
            "All parties agree that the terms and conditions of this insurance are as set "
            "out in this MRC slip, which constitutes the contract of insurance between the "
            "Insured and Underwriters."
        ),
    },
    "LMA5515": {
        "id": "LMA5515",
        "name": "Law & Jurisdiction (England & Wales)",
        "category": "condition",
        "source": "lma",
        "is_mandatory": True,
        "text": (
            "This insurance shall be governed by and construed in accordance with the law "
            "of England and Wales.\n\n"
            "Each party agrees to submit to the exclusive jurisdiction of the courts of "
            "England and Wales in respect of any dispute arising out of or in connection "
            "with this insurance.\n\n"
            "For the avoidance of doubt, any arbitration or alternative dispute resolution "
            "provisions contained herein shall take precedence over this jurisdiction clause "
            "to the extent of any inconsistency."
        ),
    },
    "LMA5406": {
        "id": "LMA5406",
        "name": "Claims Cooperation Clause",
        "category": "condition",
        "source": "lma",
        "is_mandatory": True,
        "text": (
            "The Insured shall:\n\n"
            "(a) give notice to Underwriters as soon as reasonably practicable and in any "
            "event within 30 days of becoming aware of any occurrence which may give rise "
            "to a claim under this insurance;\n\n"
            "(b) cooperate fully with Underwriters and their appointed representatives in "
            "the investigation, defence and settlement of any claim;\n\n"
            "(c) not admit liability, make any payment, settle any claim, incur any cost "
            "or expense, or assume any obligation without the prior written consent of "
            "Underwriters;\n\n"
            "(d) take all reasonable steps to preserve any rights of recovery against third "
            "parties and to minimise any loss, damage, liability or expense;\n\n"
            "(e) provide Underwriters with all information, documentation and assistance as "
            "may be reasonably required in connection with any claim or potential claim;\n\n"
            "(f) not prejudice the position of Underwriters in any way.\n\n"
            "Failure to comply with the above requirements may prejudice the Insured's right "
            "to indemnity under this insurance to the extent that Underwriters have been "
            "prejudiced by such failure."
        ),
    },
    # ── Line-specific mandatory clauses ──
    "LMA5567": {
        "id": "LMA5567",
        "name": "Terrorism Exclusion (Property)",
        "category": "exclusion",
        "source": "lma",
        "is_mandatory": True,
        "text": (
            "This insurance excludes loss, damage, cost or expense of whatsoever nature "
            "directly or indirectly caused by, resulting from or in connection with any "
            "act of terrorism regardless of any other cause or event contributing concurrently "
            "or in any other sequence to the loss.\n\n"
            "For the purposes of this exclusion, 'act of terrorism' means an act, including "
            "but not limited to the use of force or violence and/or the threat thereof, of "
            "any person or group(s) of persons, whether acting alone or on behalf of or in "
            "connection with any organisation(s) or government(s), committed for political, "
            "religious, ideological or similar purposes including the intention to influence "
            "any government and/or to put the public, or any section of the public, in fear.\n\n"
            "This exclusion also excludes loss, damage, cost or expense of whatsoever nature "
            "directly or indirectly caused by, resulting from or in connection with any action "
            "taken in controlling, preventing, suppressing or in any way relating to any act "
            "of terrorism.\n\n"
            "If Underwriters allege that by reason of this exclusion any loss, damage, cost "
            "or expense is not covered by this insurance, the burden of proving the contrary "
            "shall be upon the Insured."
        ),
    },
    "ICC-A": {
        "id": "ICC-A",
        "name": "Institute Cargo Clauses (A) - All Risks",
        "category": "coverage",
        "source": "lma",
        "is_mandatory": True,
        "text": (
            "RISKS COVERED\n\n"
            "1. This insurance covers all risks of loss of or damage to the subject-matter "
            "insured except as excluded by the provisions of Clauses 4, 5, 6 and 7 below.\n\n"
            "GENERAL AVERAGE\n\n"
            "2. This insurance covers general average and salvage charges, adjusted or "
            "determined according to the contract of carriage and/or the governing law and "
            "practice, incurred to avoid or in connection with the avoidance of loss from "
            "any cause except those excluded in Clauses 4, 5, 6 and 7 below.\n\n"
            "BOTH TO BLAME COLLISION CLAUSE\n\n"
            "3. This insurance indemnifies the Assured, in respect of any risk insured herein, "
            "against liability incurred under any Both to Blame Collision Clause in the "
            "contract of carriage.\n\n"
            "GENERAL EXCLUSIONS\n\n"
            "4. In no case shall this insurance cover:\n"
            "4.1 loss damage or expense attributable to wilful misconduct of the Assured\n"
            "4.2 ordinary leakage, ordinary loss in weight or volume, or ordinary wear and tear\n"
            "4.3 loss damage or expense caused by insufficiency or unsuitability of packing\n"
            "4.4 loss damage or expense caused by inherent vice or nature of the subject-matter\n"
            "4.5 loss damage or expense caused by delay\n"
            "4.6 loss damage or expense caused by insolvency or financial default of the "
            "owners managers charterers or operators of the vessel\n"
            "4.7 deliberate damage to or deliberate destruction of the subject-matter insured "
            "by the wrongful act of any person\n\n"
            "DURATION\n\n"
            "8. This insurance attaches from the time the subject-matter insured is first "
            "moved in the warehouse for the purpose of the immediate loading into or onto "
            "the carrying vehicle and continues during the ordinary course of transit until "
            "delivered to the final warehouse at the destination named, or until the expiry "
            "of 60 days after completion of discharge from the oversea vessel, whichever "
            "first occurs."
        ),
    },
    "LMA5401": {
        "id": "LMA5401",
        "name": "Cyber Attack Exclusion",
        "category": "exclusion",
        "source": "lma",
        "is_mandatory": True,
        "text": (
            "1. Notwithstanding any provision to the contrary within this insurance or any "
            "endorsement thereto, this insurance excludes any loss, damage, liability, claim, "
            "cost or expense of whatsoever nature directly or indirectly caused by, contributed "
            "to by, resulting from, arising out of or in connection with any Cyber Act or "
            "Cyber Incident including, but not limited to, any action taken in controlling, "
            "preventing, suppressing or remediating any Cyber Act or Cyber Incident.\n\n"
            "2. Where, solely and directly as a result of a Cyber Act or Cyber Incident, "
            "a physical peril insured under this policy ensues, this policy will cover the "
            "ensuing physical loss or damage only. This does not extend to cover any loss, "
            "damage, liability, claim, cost or expense directly or indirectly arising from "
            "the Cyber Act or Cyber Incident itself.\n\n"
            "3. For the purposes of this exclusion:\n"
            "3.1 'Cyber Act' means an unauthorised, malicious or criminal act or series of "
            "related unauthorised, malicious or criminal acts, regardless of time and place, "
            "involving access to, processing of, use of, or operation of any Computer System.\n"
            "3.2 'Cyber Incident' means any error or omission or series of related errors or "
            "omissions involving access to, processing of, use of or operation of any "
            "Computer System.\n"
            "3.3 'Computer System' means any computer, hardware, software, communications "
            "system, electronic device, server, cloud or microcontroller including any similar "
            "system or any configuration of the aforementioned and including any associated "
            "input, output, data storage device, networking equipment or back-up facility."
        ),
    },
    "AVN48B": {
        "id": "AVN48B",
        "name": "War, Hi-jacking and Other Perils Exclusion (Aviation)",
        "category": "exclusion",
        "source": "lma",
        "is_mandatory": True,
        "text": (
            "This policy does not cover claims caused by:\n\n"
            "(a) War, invasion, acts of foreign enemies, hostilities (whether war be declared "
            "or not), civil war, rebellion, revolution, insurrection, martial law, military "
            "or usurped power or attempts at usurpation of power.\n\n"
            "(b) Any hostile detonation of any weapon of war employing atomic or nuclear "
            "fission and/or fusion or other like reaction or radioactive force or matter.\n\n"
            "(c) Strikes, riots, civil commotions or labour disturbances.\n\n"
            "(d) Any act of one or more persons, whether or not agents of a sovereign Power, "
            "for political or terrorist purposes and whether the loss or damage resulting "
            "therefrom is accidental or intentional.\n\n"
            "(e) Any malicious act or act of sabotage.\n\n"
            "(f) Confiscation, nationalisation, seizure, restraint, detention, appropriation, "
            "requisition for title or use by or under the order of any Government (whether "
            "civil, military or de facto) or public or local authority.\n\n"
            "(g) Hi-jacking or any unlawful seizure or wrongful exercise of control of the "
            "aircraft or crew in flight (including any attempt at such seizure or control) "
            "made by any person or persons on board the aircraft acting without the consent "
            "of the Insured.\n\n"
            "Furthermore, this policy does not cover claims arising whilst the aircraft is "
            "outside the control of the Insured by reason of any of the above perils. The "
            "aircraft shall be deemed to have been restored to the control of the Insured "
            "on the safe return of the aircraft to the Insured at an airfield not excluded "
            "by the geographical limits of this policy."
        ),
    },
    # ── Recommended clauses ──
    "NMA2914": {
        "id": "NMA2914",
        "name": "Joint Excess Loss Clause",
        "category": "condition",
        "source": "lma",
        "is_mandatory": False,
        "text": (
            "If other insurance covers the same loss or any part thereof, the Company shall "
            "not be liable under this insurance for more than its rateable proportion of the "
            "amount exceeding the total of all deductibles, excesses and retentions applicable "
            "to such other insurance.\n\n"
            "The Insured undertakes to maintain such other insurance in force throughout the "
            "currency of this Policy and to advise Underwriters of any changes thereto."
        ),
    },
    "LMA5014": {
        "id": "LMA5014",
        "name": "Duty of Fair Presentation",
        "category": "condition",
        "source": "lma",
        "is_mandatory": False,
        "text": (
            "The Insured shall make a fair presentation of the risk to Underwriters in "
            "accordance with Section 3 of the Insurance Act 2015.\n\n"
            "A fair presentation means:\n"
            "(a) disclosure of every material circumstance which the Insured knows or ought "
            "to know, or failing that, disclosure which gives Underwriters sufficient "
            "information to put a prudent insurer on notice that it needs to make further "
            "enquiries;\n"
            "(b) that the disclosure is made in a manner which would be reasonably clear and "
            "accessible to a prudent insurer;\n"
            "(c) in which every material representation as to a matter of fact is substantially "
            "correct, and every material representation as to a matter of expectation or "
            "belief is made in good faith.\n\n"
            "If the Insured fails to make a fair presentation, Underwriters shall have the "
            "remedies set out in the Insurance Act 2015, which may include avoidance of the "
            "contract, imposition of different terms, or a proportionate reduction in the "
            "amount paid on a claim."
        ),
    },
    "LMA5096": {
        "id": "LMA5096",
        "name": "Premium Payment Clause",
        "category": "condition",
        "source": "lma",
        "is_mandatory": False,
        "text": (
            "The Insured undertakes that premium will be paid in full to Underwriters within "
            "60 days of inception of this insurance (or, in respect of instalments, within "
            "60 days of the instalment due date).\n\n"
            "If the premium due under this insurance has not been so paid to Underwriters "
            "by the 60th day from the inception of this insurance (or, in respect of "
            "instalments, by the 60th day of the instalment due date), Underwriters shall "
            "have the right to cancel this insurance by notifying the Insured via the broker "
            "in writing.\n\n"
            "In the event of cancellation, premium is due to Underwriters on a pro rata "
            "basis for the period that Underwriters are on risk but the full policy premium "
            "shall be payable if a loss has occurred prior to the date of cancellation.\n\n"
            "It is agreed that Underwriters shall give not less than 15 days prior notice "
            "of cancellation to the Insured via the broker."
        ),
    },
    "ICC-B": {
        "id": "ICC-B",
        "name": "Institute Cargo Clauses (B) - Named Perils",
        "category": "coverage",
        "source": "lma",
        "is_mandatory": False,
        "text": (
            "RISKS COVERED\n\n"
            "1. This insurance covers, except as excluded by the provisions of Clauses 4, "
            "5, 6 and 7 below:\n"
            "1.1 loss of or damage to the subject-matter insured reasonably attributable to:\n"
            "1.1.1 fire or explosion\n"
            "1.1.2 vessel or craft being stranded grounded sunk or capsized\n"
            "1.1.3 overturning or derailment of land conveyance\n"
            "1.1.4 collision or contact of vessel craft or conveyance with any external object\n"
            "1.1.5 discharge of cargo at a port of distress\n"
            "1.1.6 earthquake volcanic eruption or lightning\n"
            "1.2 loss of or damage to the subject-matter insured caused by:\n"
            "1.2.1 general average sacrifice\n"
            "1.2.2 jettison or washing overboard\n"
            "1.2.3 entry of sea lake or river water into vessel craft hold conveyance "
            "container or place of storage\n"
            "1.3 total loss of any package lost overboard or dropped whilst loading on to, "
            "or unloading from, vessel or craft."
        ),
    },
    "IWC-CARGO": {
        "id": "IWC-CARGO",
        "name": "Institute War Clauses (Cargo)",
        "category": "coverage",
        "source": "lma",
        "is_mandatory": False,
        "text": (
            "RISKS COVERED\n\n"
            "1. This insurance covers, except as excluded by the provisions of Clauses 3 "
            "and 4 below, loss of or damage to the subject-matter insured caused by:\n"
            "1.1 war civil war revolution rebellion insurrection, or civil strife arising "
            "therefrom, or any hostile act by or against a belligerent power\n"
            "1.2 capture seizure arrest restraint or detainment, arising from risks covered "
            "under 1.1 above, and the consequences thereof or any attempt thereat\n"
            "1.3 derelict mines torpedoes bombs or other derelict weapons of war.\n\n"
            "GENERAL AVERAGE\n\n"
            "2. This insurance covers general average and salvage charges, adjusted or "
            "determined according to the contract of carriage and/or the governing law and "
            "practice, incurred to avoid or in connection with the avoidance of loss from a "
            "risk covered under these clauses."
        ),
    },
    "LMA5402": {
        "id": "LMA5402",
        "name": "Cyber Act War Exclusion",
        "category": "exclusion",
        "source": "lma",
        "is_mandatory": False,
        "text": (
            "Notwithstanding any provision to the contrary within this insurance:\n\n"
            "This insurance excludes any loss, damage, liability, cost or expense of "
            "whatsoever nature directly or indirectly caused by, contributed to by, resulting "
            "from, arising out of or in connection with a Cyber Operation that is carried out "
            "in the course of war, or the use of a Computer System by any party to the war.\n\n"
            "For the purposes of this exclusion:\n"
            "(a) 'War' means war, whether declared or not, or any armed conflict between two "
            "or more States; or cyber operations between two or more States which are "
            "sufficiently disruptive, destructive, or destabilising to amount to armed conflict.\n"
            "(b) 'Cyber Operation' means the use of a Computer System by or on behalf of a "
            "State to disrupt, deny, degrade, manipulate or destroy information in, or the "
            "infrastructure of, a Computer System of another State."
        ),
    },
    "LMA5394": {
        "id": "LMA5394",
        "name": "Pandemic Exclusion",
        "category": "exclusion",
        "source": "lma",
        "is_mandatory": False,
        "text": (
            "Notwithstanding any provision to the contrary within this insurance or any "
            "endorsement thereto, this insurance excludes any loss, damage, liability, claim, "
            "cost or expense of whatsoever nature directly or indirectly caused by, contributed "
            "to by, resulting from, arising out of, or in connection with:\n\n"
            "(a) a pandemic or epidemic as declared or recognised by the World Health "
            "Organisation or any governmental or statutory authority;\n\n"
            "(b) the fear or threat (whether actual or perceived) of a pandemic or epidemic;\n\n"
            "(c) any action taken in controlling, preventing, suppressing, mitigating, or in "
            "any way relating to any pandemic or epidemic.\n\n"
            "For the avoidance of doubt, this exclusion applies regardless of any other "
            "cause or event contributing concurrently or in any other sequence to the loss."
        ),
    },
    "AVN52E": {
        "id": "AVN52E",
        "name": "War and Allied Perils Extension (Aviation)",
        "category": "coverage",
        "source": "lma",
        "is_mandatory": False,
        "text": (
            "In consideration of an additional premium, the cover excluded by AVN48B is "
            "reinstated subject to the following:\n\n"
            "This extension covers claims caused by:\n"
            "(a) War, invasion, acts of foreign enemies, hostilities, civil war, rebellion, "
            "revolution, insurrection, martial law, military or usurped power;\n"
            "(b) Strikes, riots, civil commotions or labour disturbances;\n"
            "(c) Any act of one or more persons, whether or not agents of a sovereign Power, "
            "for political or terrorist purposes;\n"
            "(d) Any malicious act or act of sabotage;\n"
            "(e) Confiscation, nationalisation, seizure, restraint, detention;\n"
            "(f) Hi-jacking or any unlawful seizure of the aircraft.\n\n"
            "This extension is subject to 7 days' notice of cancellation by either party, "
            "except in the event of hostile detonation of a nuclear weapon, in which case "
            "the cover shall terminate automatically."
        ),
    },
    "LMA3200": {
        "id": "LMA3200",
        "name": "Employer's Liability Clause",
        "category": "coverage",
        "source": "lma",
        "is_mandatory": False,
        "text": (
            "This insurance covers the Insured's legal liability to pay compensation and "
            "claimant's costs and expenses in respect of bodily injury or disease sustained "
            "by any Employee of the Insured arising out of and in the course of employment "
            "by the Insured in connection with the Insured's business.\n\n"
            "For the purposes of this section:\n"
            "'Employee' means any person under a contract of service or apprenticeship with "
            "the Insured, including:\n"
            "(a) any person employed by labour-only sub-contractors;\n"
            "(b) any person hired to or borrowed by the Insured;\n"
            "(c) any self-employed person performing work under the supervision and control "
            "of the Insured;\n"
            "(d) any person supplied to the Insured under a contract or agreement the terms "
            "of which deem such persons to be employees of the Insured.\n\n"
            "The indemnity includes costs and expenses incurred with Underwriters' written "
            "consent in the defence or settlement of any claim."
        ),
    },
}


def _resolve_clause_full_text(clause_id: str) -> dict | None:
    """Resolve a clause ID to a full clause dict with text.

    Priority:
      1. clauses_library_service (102K+ file-based / pgvector)
      2. _get_clause_by_id (V3 template files)
      3. INLINE_MANDATORY_CLAUSES (always-available fallback)
    """
    if not clause_id:
        return None

    # 1. Try comprehensive library
    try:
        from app.services.clauses_library_service import clauses_library_service

        result = clauses_library_service.get_clause_by_id(clause_id)
        if result and result.get("text") and len(result["text"]) >= 30:
            return result
    except Exception:
        pass

    # 2. Try V3 template lookup
    try:
        result = _get_clause_by_id(clause_id)
        if result and result.get("text") and len(result["text"]) >= 30:
            return result
    except Exception:
        pass

    # 3. Inline fallback
    inline = INLINE_MANDATORY_CLAUSES.get(clause_id)
    if inline:
        return inline

    return None


def _resolve_clauses_batch(items) -> list:
    """Resolve a mixed bag of clause IDs/dicts/grouped-by-doc into fully resolved clause dicts.

    Accepts:
      - list of str (plain clause IDs)
      - list of dicts ({clause_id, name, content_preview, ...})
      - dict keyed by doc_type ({"policy_wording": [clause_dicts], ...})

    Returns: deduplicated list of {clause_id, name, selected_text, source, is_mandatory}
    """
    if not items:
        return []

    flat: list = []

    if isinstance(items, dict):
        # Dict keyed by doc type — flatten all clause lists
        for _doc_type, clause_list in items.items():
            if isinstance(clause_list, list):
                flat.extend(clause_list)
    elif isinstance(items, list):
        flat = list(items)
    else:
        return []

    resolved: list = []
    seen_ids: set = set()

    for item in flat:
        cid = None
        name = None
        existing_text = ""
        source = "user_selected"
        is_mandatory = False

        if isinstance(item, str):
            cid = item
            name = item
        elif isinstance(item, dict):
            cid = item.get("clause_id") or item.get("id")
            name = item.get("name", cid)
            existing_text = (
                item.get("selected_text")
                or item.get("full_text")
                or item.get("text")
                or ""
            )
            source = item.get("source", "user_selected")
            is_mandatory = item.get("is_mandatory", False)
        else:
            continue

        if not cid or cid in seen_ids:
            continue
        seen_ids.add(cid)

        # Resolve full text if what we have is too short (< 50 chars)
        full_text = existing_text
        if len(full_text.strip()) < 50:
            resolved_clause = _resolve_clause_full_text(cid)
            if resolved_clause:
                full_text = resolved_clause.get("text", "") or full_text
                if not name or name == cid:
                    name = resolved_clause.get("name", name)
                source = resolved_clause.get("source", source)
                is_mandatory = resolved_clause.get("is_mandatory", is_mandatory)

        resolved.append(
            {
                "clause_id": cid,
                "name": name or cid,
                "selected_text": full_text,
                "source": source,
                "is_mandatory": is_mandatory,
            }
        )

    return resolved


def _parse_doc_id(doc_id: str) -> int | None:
    """Parse a document ID from the frontend.

    The frontend may send string IDs like "gen_1770850906225" or plain
    integer strings like "42".  This helper strips the "gen_" prefix
    (if present) and converts the remainder to an integer suitable for
    the DB lookup.  Returns None when the value cannot be parsed.
    """
    if doc_id is None:
        return None
    raw = doc_id
    # Strip known string prefixes produced by the frontend
    for prefix in ("gen_", "doc_"):
        if raw.startswith(prefix):
            raw = raw[len(prefix) :]
            break
    try:
        return int(raw)
    except (ValueError, TypeError):
        return None


@router.post(
    "/assessments/{assessment_id}/suggest-documents",
    response_model=DocumentSuggestionResponse,
)
async def suggest_documents(
    assessment_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get AI-suggested documents for an assessment.

    Analyzes the assessment and recommends which documents
    should be generated based on risk category and decision.
    Uses the comprehensive clause library with proper recommendations.
    """
    # Get assessment
    query = select(Assessment).where(
        Assessment.id == assessment_id, Assessment.created_by == current_user.id
    )
    result = await db.execute(query)
    assessment = result.scalars().first()

    if not assessment:
        raise HTTPException(404, "Assessment not found")

    # Build assessment dict
    risk_category = (
        assessment.risk_category.value if assessment.risk_category else "general"
    )
    territory = assessment.territory or ""
    sum_insured = float(assessment.sum_insured) if assessment.sum_insured else None

    # Extract perils and special features from AI analysis
    perils = []
    special_features = []
    ai_analysis = assessment.ai_analysis or {}

    # Extract risk factors from AI analysis
    if isinstance(ai_analysis, dict):
        # Get perils from risk_factors or identified_risks
        risk_factors = ai_analysis.get("risk_factors", [])
        if isinstance(risk_factors, list):
            for factor in risk_factors:
                if isinstance(factor, str):
                    perils.append(factor)
                elif isinstance(factor, dict):
                    perils.append(factor.get("name", factor.get("factor", "")))

        identified_risks = ai_analysis.get("identified_risks", [])
        if isinstance(identified_risks, list):
            for risk in identified_risks:
                if isinstance(risk, str):
                    perils.append(risk)
                elif isinstance(risk, dict):
                    perils.append(risk.get("name", risk.get("risk", "")))

        # Get special features
        features = ai_analysis.get(
            "special_features", ai_analysis.get("notable_features", [])
        )
        if isinstance(features, list):
            special_features.extend(features)

        # Check for specific keywords in analysis
        summary = ai_analysis.get("summary", "") or ""
        if "cyber" in summary.lower():
            special_features.append("cyber")
        if "climate" in summary.lower() or "environmental" in summary.lower():
            special_features.append("climate")
        if "cryptocurrency" in summary.lower() or "crypto" in summary.lower():
            special_features.append("cryptocurrency")
        if "ai" in summary.lower() or "artificial intelligence" in summary.lower():
            special_features.append("ai")

    def _fmt_currency(val, currency="GBP"):
        if val is None:
            return "TBA"
        try:
            n = float(val)
            return f"{currency} {int(n):,}" if n == int(n) else f"{currency} {n:,.2f}"
        except (ValueError, TypeError):
            return str(val)

    assessment_data = {
        "id": assessment.id,
        "reference_number": assessment.reference_number,
        "title": assessment.title,
        "risk_category": risk_category,
        "decision": assessment.decision.value if assessment.decision else None,
        "insured_name": assessment.insured_name,
        "broker_reference": assessment.broker_reference,
        "premium": assessment.premium,
        "sum_insured": assessment.sum_insured,
        "deductible": assessment.deductible,
        "premium_display": _fmt_currency(assessment.premium),
        "sum_insured_display": _fmt_currency(assessment.sum_insured),
        "deductible_display": _fmt_currency(assessment.deductible),
        "territory": territory,
        "inception_date": str(assessment.inception_date)
        if assessment.inception_date
        else None,
        "expiry_date": str(assessment.expiry_date) if assessment.expiry_date else None,
        "risk_score": assessment.risk_score,
        "ai_analysis": ai_analysis,
        "perils": perils,
        "special_features": special_features,
        "broker_name": assessment.broker_name,
        "commission_rate": float(assessment.commission_rate)
        if assessment.commission_rate
        else None,
        "insured_entity_name": assessment.insured_entity_name,
        "companies_house_number": assessment.companies_house_number,
        "renewal_date": str(assessment.renewal_date)
        if assessment.renewal_date
        else None,
        "loss_run_reporting_rules": assessment.loss_run_reporting_rules,
        "regulatory_framework": assessment.regulatory_framework,
    }

    # Code-based document suggestions — instant, no AI call needed
    category_docs = {
        "cyber": [
            {
                "document_type": "mrc_slip",
                "template_key": "mrc_slip",
                "mandatory": True,
                "confidence": 0.95,
                "priority": 1,
                "reason": "Standard Lloyd's MRC placing slip for cyber risk",
            },
            {
                "document_type": "policy_wording",
                "template_key": "policy_wording",
                "mandatory": True,
                "confidence": 0.92,
                "priority": 1,
                "reason": "Full cyber policy wording with data breach coverage terms",
            },
            {
                "document_type": "endorsement_schedule",
                "template_key": "endorsement_schedule",
                "mandatory": False,
                "confidence": 0.80,
                "priority": 2,
                "reason": "Endorsement schedule for cyber-specific amendments",
            },
            {
                "document_type": "cover_note",
                "template_key": "cover_note",
                "mandatory": False,
                "confidence": 0.75,
                "priority": 3,
                "reason": "Interim cover note pending full policy issuance",
            },
        ],
        "marine": [
            {
                "document_type": "mrc_slip",
                "template_key": "mrc_slip",
                "mandatory": True,
                "confidence": 0.95,
                "priority": 1,
                "reason": "Standard Lloyd's MRC marine placing slip",
            },
            {
                "document_type": "policy_wording",
                "template_key": "policy_wording",
                "mandatory": True,
                "confidence": 0.92,
                "priority": 1,
                "reason": "Marine hull/cargo policy wording",
            },
            {
                "document_type": "endorsement_schedule",
                "template_key": "endorsement_schedule",
                "mandatory": True,
                "confidence": 0.88,
                "priority": 2,
                "reason": "Institute cargo clauses endorsement",
            },
            {
                "document_type": "cover_note",
                "template_key": "cover_note",
                "mandatory": False,
                "confidence": 0.70,
                "priority": 3,
                "reason": "Interim marine cover note",
            },
        ],
        "property": [
            {
                "document_type": "mrc_slip",
                "template_key": "mrc_slip",
                "mandatory": True,
                "confidence": 0.95,
                "priority": 1,
                "reason": "Standard Lloyd's MRC property slip",
            },
            {
                "document_type": "policy_wording",
                "template_key": "policy_wording",
                "mandatory": True,
                "confidence": 0.92,
                "priority": 1,
                "reason": "Property all-risks policy wording",
            },
            {
                "document_type": "endorsement_schedule",
                "template_key": "endorsement_schedule",
                "mandatory": False,
                "confidence": 0.78,
                "priority": 2,
                "reason": "Property endorsement schedule",
            },
        ],
        "financial_lines": [
            {
                "document_type": "mrc_slip",
                "template_key": "mrc_slip",
                "mandatory": True,
                "confidence": 0.95,
                "priority": 1,
                "reason": "Standard Lloyd's MRC financial lines slip",
            },
            {
                "document_type": "policy_wording",
                "template_key": "policy_wording",
                "mandatory": True,
                "confidence": 0.93,
                "priority": 1,
                "reason": "Professional indemnity policy wording",
            },
            {
                "document_type": "endorsement_schedule",
                "template_key": "endorsement_schedule",
                "mandatory": False,
                "confidence": 0.82,
                "priority": 2,
                "reason": "PI endorsement schedule with limit of liability",
            },
            {
                "document_type": "cover_note",
                "template_key": "cover_note",
                "mandatory": False,
                "confidence": 0.72,
                "priority": 3,
                "reason": "Interim PI cover note",
            },
        ],
    }
    default_docs = [
        {
            "document_type": "mrc_slip",
            "template_key": "mrc_slip",
            "mandatory": True,
            "confidence": 0.95,
            "priority": 1,
            "reason": "Standard Lloyd's MRC placing slip",
        },
        {
            "document_type": "policy_wording",
            "template_key": "policy_wording",
            "mandatory": True,
            "confidence": 0.90,
            "priority": 1,
            "reason": "Full policy wording with terms and conditions",
        },
        {
            "document_type": "endorsement_schedule",
            "template_key": "endorsement_schedule",
            "mandatory": False,
            "confidence": 0.80,
            "priority": 2,
            "reason": "Endorsement schedule for amendments",
        },
        {
            "document_type": "cover_note",
            "template_key": "cover_note",
            "mandatory": False,
            "confidence": 0.70,
            "priority": 3,
            "reason": "Cover note for interim coverage confirmation",
        },
    ]
    suggestions = {
        "suggested_documents": category_docs.get(risk_category.lower(), default_docs),
        "bundle_name": f"{risk_category.replace('_', ' ').title()} Document Bundle",
        "total_estimated_time_seconds": 120,
    }

    # Get clause recommendations using the REAL clauses library (with actual data)
    # Falls back to INLINE_MANDATORY_CLAUSES when library is unavailable/empty.
    from app.services.clauses_library_service import clauses_library_service

    lma_clauses = []
    existing_ids = set()

    try:
        # 1. Mandatory LMA clauses (always required for Lloyd's policies)
        mandatory_lma_ids = {
            "LMA5021": "War & terrorism exclusion - mandatory for all Lloyd's policies",
            "LMA5390": "Sanctions compliance - mandatory for all Lloyd's policies",
            "LMA5400": "Several liability - mandatory for all Lloyd's policies",
            "LMA5027": "Market Reform Contract standard - mandatory for Lloyd's",
            "LMA5515": "Law & jurisdiction - mandatory for all Lloyd's policies",
            "LMA5406": "Claims cooperation - mandatory for all Lloyd's policies",
        }

        for clause_id, reason in mandatory_lma_ids.items():
            clause_data = clauses_library_service.get_clause_by_id(clause_id)
            # Fallback to inline definitions when library has no match
            if not clause_data or not clause_data.get("text"):
                clause_data = _resolve_clause_full_text(clause_id)
            if clause_data:
                clause_text = clause_data.get("text", "") or ""
                lma_clauses.append(
                    LMAClauseSuggestion(
                        id=clause_data.get("id", clause_id),
                        name=clause_data.get("name", clause_id),
                        mandatory=True,
                        category=clause_data.get("category", "general"),
                        selected=True,
                        reason=reason,
                        text_preview=clause_text[:300] if clause_text else None,
                    )
                )
                existing_ids.add(clause_data.get("id", clause_id))

        # 1b. Add line-specific mandatory clauses from inline definitions
        line_mandatory_map = {
            "property": ["LMA5567"],
            "marine": ["ICC-A"],
            "cyber": ["LMA5401"],
            "aviation": ["AVN48B"],
        }
        for line_cid in line_mandatory_map.get(risk_category.lower(), []):
            if line_cid not in existing_ids:
                clause_data = _resolve_clause_full_text(line_cid)
                if clause_data:
                    clause_text = clause_data.get("text", "") or ""
                    lma_clauses.append(
                        LMAClauseSuggestion(
                            id=clause_data.get("id", line_cid),
                            name=clause_data.get("name", line_cid),
                            mandatory=True,
                            category=clause_data.get("category", "general"),
                            selected=True,
                            reason=f"Mandatory for {risk_category} risks",
                            text_preview=clause_text[:300] if clause_text else None,
                        )
                    )
                    existing_ids.add(clause_data.get("id", line_cid))

        # 1c. Add recommended clauses from inline definitions
        recommended_map = {
            "property": ["NMA2914", "LMA5014", "LMA5096"],
            "marine": ["ICC-B", "IWC-CARGO"],
            "cyber": ["LMA5402", "LMA5394"],
            "aviation": ["AVN52E"],
            "casualty": ["LMA3200"],
        }
        for rec_cid in recommended_map.get(
            risk_category.lower(), ["LMA5014", "LMA5096"]
        ):
            if rec_cid not in existing_ids:
                clause_data = _resolve_clause_full_text(rec_cid)
                if clause_data:
                    clause_text = clause_data.get("text", "") or ""
                    lma_clauses.append(
                        LMAClauseSuggestion(
                            id=clause_data.get("id", rec_cid),
                            name=clause_data.get("name", rec_cid),
                            mandatory=False,
                            category=clause_data.get("category", "general"),
                            selected=True,
                            reason=f"Recommended for {risk_category} risks",
                            text_preview=clause_text[:300] if clause_text else None,
                        )
                    )
                    existing_ids.add(clause_data.get("id", rec_cid))

        # 2. Risk-category specific clauses from library search (pre-selected)
        category_searches = {
            "property": ["property", "fire", "damage"],
            "marine": ["marine", "cargo", "hull"],
            "cyber": ["cyber", "data", "network"],
            "aviation": ["aviation", "aircraft"],
            "professional": ["professional", "negligence"],
            "casualty": ["liability", "casualty"],
            "energy": ["energy", "offshore"],
        }
        search_terms = category_searches.get(
            risk_category.lower(), [risk_category.lower()]
        )

        for term in search_terms[:2]:  # Max 2 search terms
            results, _ = clauses_library_service.search(
                query=term, source="lma", page_size=5
            )
            for clause_data in results:
                if clause_data["id"] not in existing_ids:
                    clause_text = clause_data.get("text", "") or ""
                    lma_clauses.append(
                        LMAClauseSuggestion(
                            id=clause_data["id"],
                            name=clause_data["name"],
                            mandatory=False,
                            category=clause_data.get("category", "general"),
                            selected=True,
                            reason=f"Recommended for {risk_category} risks",
                            text_preview=clause_text[:300] if clause_text else None,
                        )
                    )
                    existing_ids.add(clause_data["id"])

        # 3. Search clause library for risk-category relevant clauses from all sources
        category_results, _ = clauses_library_service.search(
            query=risk_category, page_size=15
        )
        for clause_data in category_results:
            if clause_data["id"] not in existing_ids:
                clause_text = clause_data.get("text", "") or ""
                lma_clauses.append(
                    LMAClauseSuggestion(
                        id=clause_data["id"],
                        name=clause_data["name"],
                        mandatory=False,
                        category=clause_data.get("category", "general"),
                        selected=False,
                        reason=f"Available for {risk_category} policies",
                        text_preview=clause_text[:300] if clause_text else None,
                    )
                )
                existing_ids.add(clause_data["id"])

        # 4. Add remaining LMA clauses not yet included
        lma_results, _ = clauses_library_service.search(source="lma", page_size=50)
        for clause_data in lma_results:
            if clause_data["id"] not in existing_ids:
                clause_text = clause_data.get("text", "") or ""
                lma_clauses.append(
                    LMAClauseSuggestion(
                        id=clause_data["id"],
                        name=clause_data["name"],
                        mandatory=False,
                        category=clause_data.get("category", "general"),
                        selected=False,
                        reason="Available in LMA clause library",
                        text_preview=clause_text[:300] if clause_text else None,
                    )
                )
                existing_ids.add(clause_data["id"])

    except Exception as e:
        logger.warning(f"Clause library search failed: {e}")
        # Continue with whatever clauses we found so far

    # Map to response schema
    return DocumentSuggestionResponse(
        assessment_id=assessment_id,
        risk_category=risk_category,
        decision=assessment_data.get("decision", ""),
        suggested_documents=[
            DocumentSuggestion(
                document_type=doc.get("document_type", ""),
                template_id=doc.get("template_id"),
                template_key=doc.get("template_key", ""),
                template_name=doc.get("template_key", "").replace("_", " ").title(),
                priority=doc.get("priority", 1),
                mandatory=doc.get("mandatory", False),
                confidence=doc.get("confidence", 0.0),
                reason=doc.get("reason", ""),
            )
            for doc in suggestions.get("suggested_documents", [])
        ],
        bundle_name=suggestions.get("bundle_name", "Document Bundle"),
        total_estimated_time_seconds=suggestions.get(
            "total_estimated_time_seconds", 60
        ),
        lma_clauses=lma_clauses,
    )


@router.post(
    "/assessments/{assessment_id}/generate-documents",
    response_model=GenerationJobResponse,
)
async def generate_documents(
    assessment_id: str,
    request: GenerationJobCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Start document generation for an assessment.

    Creates a generation job that runs the 19-agent OpenDraft pipeline
    with RAG, per-user training, and ML predictions.

    Training documents are optional but improve AI output quality.
    A warning is returned if no training documents exist.
    """
    # Check if user has training documents (informational, not blocking)
    training_count = await qdrant_service.count_training_docs(str(current_user.id))
    training_warnings = []
    if training_count == 0:
        training_warnings.append(
            "No training documents found. Uploading sample policies, endorsements, "
            "and other documents on the Training page will improve AI document quality. "
            "Generation will proceed using built-in templates and clause libraries."
        )

    # Get assessment with eager-loaded documents to avoid lazy loading issues
    query = (
        select(Assessment)
        .options(selectinload(Assessment.documents))
        .where(Assessment.id == assessment_id, Assessment.created_by == current_user.id)
    )
    result = await db.execute(query)
    assessment = result.scalars().first()

    if not assessment:
        raise HTTPException(404, "Assessment not found")

    # Get templates (static + database)
    templates = get_all_templates()

    # Also get database templates
    db_templates_query = select(Template).where(Template.is_active == True)
    db_result = await db.execute(db_templates_query)
    db_templates = db_result.scalars().all()

    # Merge templates
    all_templates = templates + [
        {
            "id": t.id,
            "template_key": t.template_key,
            "name": t.name,
            "category": t.category,
            "document_type": t.document_type,
            "fields": t.fields,
            "sections": t.sections,
        }
        for t in db_templates
    ]

    # Create job record
    job_id = str(uuid.uuid4())[:8]
    job = DocumentGenerationJob(
        id=job_id,
        assessment_id=assessment_id,
        status="pending",
        total_documents=len(request.document_types),
        document_suggestions=[
            {"document_type": dt, "status": "pending"} for dt in request.document_types
        ],
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    # Build assessment dict from top-level fields
    assessment_data = {
        "id": assessment.id,
        "reference_number": assessment.reference_number,
        "title": assessment.title,
        "risk_category": assessment.risk_category.value
        if assessment.risk_category
        else None,
        "decision": assessment.decision.value if assessment.decision else None,
        "insured_name": assessment.insured_name,
        "broker_reference": assessment.broker_reference,
        "premium": assessment.premium,
        "sum_insured": assessment.sum_insured,
        "deductible": assessment.deductible,
        "territory": assessment.territory,
        "inception_date": str(assessment.inception_date)
        if assessment.inception_date
        else None,
        "expiry_date": str(assessment.expiry_date) if assessment.expiry_date else None,
        "risk_score": assessment.risk_score,
        "ai_analysis": assessment.ai_analysis,
        "broker_name": assessment.broker_name,
        "commission_rate": float(assessment.commission_rate)
        if assessment.commission_rate
        else None,
        "insured_entity_name": assessment.insured_entity_name,
        "companies_house_number": assessment.companies_house_number,
        "renewal_date": str(assessment.renewal_date)
        if assessment.renewal_date
        else None,
        "loss_run_reporting_rules": assessment.loss_run_reporting_rules,
        "regulatory_framework": assessment.regulatory_framework,
        "rapidrate_results": assessment.rapidrate_results or {},
    }

    # CRITICAL: Enrich from ai_analysis when top-level fields are empty.
    # The AI analysis often extracts data that isn't saved to top-level columns.
    ai_data = assessment.ai_analysis or {}
    if isinstance(ai_data, str):
        import json as _json

        try:
            ai_data = _json.loads(ai_data)
        except Exception:
            ai_data = {}

    if isinstance(ai_data, dict):
        # Fields to backfill from ai_analysis when top-level is empty/zero/None
        _backfill_map = {
            "territory": "territory",
            "broker_name": "broker_name",
            "broker_reference": "broker_reference",
            "premium": "premium",
            "sum_insured": "sum_insured",
            "deductible": "deductible",
            "inception_date": "inception_date",
            "expiry_date": "expiry_date",
            "currency": "currency",
            "insured_entity_name": "company_name",
            "risk_category": "risk_type",
        }
        for field, ai_key in _backfill_map.items():
            current_val = assessment_data.get(field)
            # Consider empty if None, empty string, or zero for numeric fields
            is_empty = current_val is None or current_val == "" or current_val == "None"
            if field in ("premium", "sum_insured", "deductible"):
                is_empty = is_empty or current_val == 0 or current_val == 0.0
            if is_empty:
                ai_val = ai_data.get(ai_key)
                if (
                    ai_val is not None
                    and str(ai_val).strip()
                    and str(ai_val).strip().lower() != "none"
                ):
                    assessment_data[field] = ai_val
                    logger.info(
                        f"Backfilled {field} from ai_analysis.{ai_key}: {ai_val}"
                    )

    # Get extracted data from linked documents
    extracted_data = {}
    for doc in assessment.documents:
        if doc.extracted_data:
            extracted_data.update(doc.extracted_data)

    # Run generation in background (don't pass db session - create new one in task)
    background_tasks.add_task(
        _run_generation_job,
        job_id,
        assessment_data,
        all_templates,
        request.document_types,
        extracted_data,
        request.clause_ids,  # Pass selected clause IDs
        request.language,  # Pass target language
        str(current_user.id),  # Pass user_id for OpenDraft pipeline
    )

    return GenerationJobResponse(
        id=job.id,
        assessment_id=str(job.assessment_id),
        status=job.status,
        total_documents=job.total_documents,
        completed_documents=0,
        progress_percentage=0,
        warnings=training_warnings if training_warnings else None,
        created_at=job.created_at,
    )


async def _update_job_progress(
    job_id: str, agent: str, description: str, percentage: int
):
    """Helper to update job progress in database."""
    async with AsyncSessionLocal() as db:
        try:
            job_query = select(DocumentGenerationJob).where(
                DocumentGenerationJob.id == job_id
            )
            result = await db.execute(job_query)
            job = result.scalars().first()
            if job:
                job.current_agent = agent
                job.current_agent_description = description
                job.progress_percentage = percentage
                await db.commit()
        except Exception as e:
            logging.getLogger(__name__).debug(f"Progress update skipped: {e}")


async def _run_generation_job(
    job_id: str,
    assessment_data: dict,
    templates: list,
    document_types: list,
    extracted_data: dict,
    clause_ids: list = None,
    language: str = None,
    user_id: str = None,
):
    """Background task to run document generation via the 19-agent OpenDraft pipeline.

    Delegates to the OpenDraft pipeline which uses RAG, per-user training,
    and ML predictions for superior document quality.

    Args:
        clause_ids: Optional list of LMA clause IDs to include in documents
        language: Optional target language code for document generation
        user_id: User ID for per-user RAG and ML adapter predictions
    """
    # Resolve clause IDs (plain strings or dicts) to full clause dicts with text.
    # Without this, the opendraft generator receives empty selected_text for
    # string clause IDs and the clause content never makes it into the document.
    resolved_clauses = _resolve_clauses_batch(clause_ids) if clause_ids else None

    await _run_opendraft_job(
        job_id,
        assessment_data,
        user_id,
        document_types,
        clause_dicts=resolved_clauses,
        language=language,
    )


@router.get("/generation-jobs/")
async def list_generation_jobs(
    db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """List all generation jobs for the current user."""
    assessment_query = select(Assessment.id).where(
        Assessment.created_by == current_user.id
    )
    assessment_result = await db.execute(assessment_query)
    assessment_ids = [a[0] for a in assessment_result.fetchall()]
    if not assessment_ids:
        return []
    query = (
        select(DocumentGenerationJob)
        .where(DocumentGenerationJob.assessment_id.in_(assessment_ids))
        .order_by(DocumentGenerationJob.created_at.desc())
    )
    result = await db.execute(query)
    jobs = result.scalars().all()
    return [GenerationJobResponse.model_validate(job) for job in jobs]


@router.get("/generation-jobs/{job_id}/status", response_model=GenerationJobProgress)
async def get_generation_status(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get the status of a document generation job with detailed step progress."""
    query = select(DocumentGenerationJob).where(DocumentGenerationJob.id == job_id)
    result = await db.execute(query)
    job = result.scalars().first()

    if not job:
        raise HTTPException(404, "Job not found")

    # Build steps array showing real 19-agent pipeline progress
    progress = job.progress_percentage or 0
    current_agent = job.current_agent
    pipeline_steps = [
        ("RiskResearcher", "Searching knowledge base for relevant clauses", 5),
        ("ClauseExtractor", "Extracting key provisions from found clauses", 10),
        ("GapAnalyzer", "Identifying coverage gaps and missing clauses", 15),
        ("ClauseManager", "Mapping clause IDs to standard wordings", 20),
        ("StructurePlanner", "Planning document sections using CUAD patterns", 25),
        ("LloydFormatter", "Applying London market formatting standards", 30),
        ("SectionDrafter", "Drafting each section with selected clauses", 40),
        ("ConsistencyChecker", "Verifying values match across all sections", 45),
        ("ToneUnifier", "Ensuring consistent legal language throughout", 50),
        ("RiskChallenger", "Challenging coverage adequacy", 55),
        ("ClauseVerifier", "Verifying all clause IDs are valid standards", 60),
        ("ComplianceReviewer", "Lloyd's compliance and regulatory check", 65),
        ("HouseStyleAgent", "Matching your uploaded document style", 70),
        ("LanguageVarier", "Varying legal phrasing to avoid repetition", 75),
        ("ProofReader", "Grammar, numbering, and cross-references", 80),
        ("ClauseCompiler", "Inserting full ACORD standard wordings", 85),
        ("ScheduleBuilder", "Building schedules, appendices, and tables", 90),
        ("PDFExporter", "Generating PDF with Lloyd's formatting", 93),
        ("QualityGate", "Final quality checklist before delivery", 95),
    ]

    # Determine which agents are completed based on current_agent
    found_current = False
    steps = []
    for agent, description, threshold in pipeline_steps:
        if job.status == "completed":
            status = "completed"
        elif agent == current_agent:
            status = "running"
            found_current = True
        elif not found_current:
            status = "completed"  # agents before the current one are done
        else:
            status = "pending"
        steps.append(
            GenerationStepProgress(
                agent=agent,
                description=description,
                percentage=threshold,
                status=status,
            )
        )

    return GenerationJobProgress(
        job_id=job.id,
        status=job.status,
        current_agent=job.current_agent,
        current_agent_description=job.current_agent_description,
        progress_percentage=job.progress_percentage or 0,
        completed_documents=job.completed_documents or 0,
        total_documents=job.total_documents or 0,
        steps=steps,
        error_message=job.error_message if hasattr(job, "error_message") else None,
    )


@router.get("/generation-jobs/{job_id}", response_model=GenerationJobResponse)
async def get_generation_job(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get full details of a generation job."""
    query = select(DocumentGenerationJob).where(DocumentGenerationJob.id == job_id)
    result = await db.execute(query)
    job = result.scalars().first()

    if not job:
        raise HTTPException(404, "Job not found")

    return GenerationJobResponse(
        id=job.id,
        assessment_id=str(job.assessment_id),
        status=job.status,
        total_documents=job.total_documents,
        completed_documents=job.completed_documents,
        progress_percentage=job.progress_percentage,
        current_agent=job.current_agent,
        current_agent_description=job.current_agent_description,
        agent_outputs=job.agent_outputs,
        error_message=job.error_message,
        created_at=job.created_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
    )


@router.get(
    "/assessments/{assessment_id}/generated",
    response_model=GeneratedDocumentListResponse,
)
async def list_generated_documents(
    assessment_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all generated documents for an assessment."""
    # Verify assessment ownership
    assessment_result = await db.execute(
        select(Assessment).where(
            Assessment.id == assessment_id, Assessment.created_by == current_user.id
        )
    )
    if not assessment_result.scalar_one_or_none():
        raise HTTPException(404, "Assessment not found or access denied")

    query = (
        select(GeneratedDocument)
        .where(GeneratedDocument.assessment_id == assessment_id)
        .order_by(GeneratedDocument.created_at.desc())
    )

    result = await db.execute(query)
    documents = result.scalars().all()

    return GeneratedDocumentListResponse(
        items=[GeneratedDocumentResponse.model_validate(doc) for doc in documents],
        total=len(documents),
    )


@router.get("/generated-documents/", response_model=GeneratedDocumentListResponse)
async def list_all_generated_documents(
    page: int = 1,
    page_size: int = 10,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all generated documents for the current user across all assessments."""
    # Get assessments owned by user
    assessment_query = select(Assessment.id).where(
        Assessment.created_by == current_user.id
    )
    assessment_result = await db.execute(assessment_query)
    assessment_ids = [a[0] for a in assessment_result.fetchall()]

    if not assessment_ids:
        return GeneratedDocumentListResponse(items=[], total=0)

    # Get generated documents for those assessments
    query = (
        select(GeneratedDocument)
        .where(GeneratedDocument.assessment_id.in_(assessment_ids))
        .order_by(GeneratedDocument.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )

    result = await db.execute(query)
    documents = result.scalars().all()

    # Get total count (efficient SQL COUNT instead of loading all records)
    count_query = select(func.count(GeneratedDocument.id)).where(
        GeneratedDocument.assessment_id.in_(assessment_ids)
    )
    count_result = await db.execute(count_query)
    total = count_result.scalar() or 0

    return GeneratedDocumentListResponse(
        items=[GeneratedDocumentResponse.model_validate(doc) for doc in documents],
        total=total,
    )


@router.get("/generated-documents/{doc_id}", response_model=GeneratedDocumentResponse)
async def get_generated_document(
    doc_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a single generated document."""
    # Parse doc_id: frontend may send string IDs like "gen_1770850906225" or plain integers
    parsed_id = _parse_doc_id(doc_id)
    if parsed_id is None:
        raise HTTPException(400, f"Invalid document ID format: {doc_id}")

    # Join with Assessment to verify ownership
    query = (
        select(GeneratedDocument)
        .join(Assessment, GeneratedDocument.assessment_id == Assessment.id)
        .where(
            GeneratedDocument.id == parsed_id, Assessment.created_by == current_user.id
        )
    )
    result = await db.execute(query)
    doc = result.scalars().first()

    if not doc:
        raise HTTPException(404, "Document not found or access denied")

    return GeneratedDocumentResponse.model_validate(doc)


@router.put("/generated-documents/{doc_id}", response_model=GeneratedDocumentResponse)
async def update_generated_document(
    doc_id: str,
    update_data: GeneratedDocumentUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a generated document (e.g., edit content)."""
    # Parse doc_id: frontend may send string IDs like "gen_1770850906225" or plain integers
    parsed_id = _parse_doc_id(doc_id)
    if parsed_id is None:
        raise HTTPException(400, f"Invalid document ID format: {doc_id}")

    # Join with Assessment to verify ownership
    query = (
        select(GeneratedDocument)
        .join(Assessment, GeneratedDocument.assessment_id == Assessment.id)
        .where(
            GeneratedDocument.id == parsed_id, Assessment.created_by == current_user.id
        )
    )
    result = await db.execute(query)
    doc = result.scalars().first()

    if not doc:
        raise HTTPException(404, "Document not found or access denied")

    if update_data.title:
        doc.title = update_data.title
    if update_data.final_content:
        doc.final_content = update_data.final_content
        doc.status = "approved"

    await db.commit()
    await db.refresh(doc)

    return GeneratedDocumentResponse.model_validate(doc)


@router.delete("/generated-documents/{doc_id}", status_code=204)
async def delete_generated_document(
    doc_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a generated document and its associated PDF file."""
    parsed_id = _parse_doc_id(doc_id)
    if parsed_id is None:
        raise HTTPException(400, f"Invalid document ID format: {doc_id}")

    # Join with Assessment to verify ownership
    query = (
        select(GeneratedDocument)
        .join(Assessment, GeneratedDocument.assessment_id == Assessment.id)
        .where(
            GeneratedDocument.id == parsed_id, Assessment.created_by == current_user.id
        )
    )
    result = await db.execute(query)
    doc = result.scalars().first()

    if not doc:
        raise HTTPException(404, "Document not found or access denied")

    # Delete PDF file from disk if it exists
    if doc.pdf_path:
        import os

        try:
            if os.path.exists(doc.pdf_path):
                os.remove(doc.pdf_path)
        except OSError as e:
            logger.warning(f"Failed to delete PDF file {doc.pdf_path}: {e}")

    await db.delete(doc)
    await db.commit()


@router.post(
    "/assessments/{assessment_id}/prefill/{template_id}", response_model=PrefillResponse
)
async def prefill_template(
    assessment_id: str,
    template_id: str,
    request: PrefillRequest = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get AI-prefilled data for a template based on assessment.

    Optionally uses RAG from reference documents for enhancement.
    """
    # Get assessment with eager-loaded documents
    query = (
        select(Assessment)
        .options(selectinload(Assessment.documents))
        .where(Assessment.id == assessment_id, Assessment.created_by == current_user.id)
    )
    result = await db.execute(query)
    assessment = result.scalars().first()

    if not assessment:
        raise HTTPException(404, "Assessment not found")

    # Get template (try static first, then database)
    template = get_template(template_id)
    if not template:
        # Try database
        try:
            tid = int(template_id)
            t_query = select(Template).where(Template.id == tid)
            t_result = await db.execute(t_query)
            t = t_result.scalars().first()
            if t:
                template = {
                    "id": t.id,
                    "name": t.name,
                    "fields": t.fields,
                    "sections": t.sections,
                }
        except (ValueError, TypeError):
            pass

    if not template:
        raise HTTPException(404, "Template not found")

    # Build assessment dict
    assessment_data = {
        "id": assessment.id,
        "reference_number": assessment.reference_number,
        "title": assessment.title,
        "risk_category": assessment.risk_category.value
        if assessment.risk_category
        else None,
        "decision": assessment.decision.value if assessment.decision else None,
        "insured_name": assessment.insured_name,
        "broker_reference": assessment.broker_reference,
        "premium": assessment.premium,
        "sum_insured": assessment.sum_insured,
        "deductible": assessment.deductible,
        "territory": assessment.territory,
        "inception_date": str(assessment.inception_date)
        if assessment.inception_date
        else None,
        "expiry_date": str(assessment.expiry_date) if assessment.expiry_date else None,
    }

    # Get extracted data from documents
    extracted_data = {}
    for doc in assessment.documents:
        if doc.extracted_data:
            extracted_data.update(doc.extracted_data)

    # Get RAG context (always fetch for better document quality)
    rag_context = None
    try:
        rag_context = await reference_document_service.get_rag_context(
            query=f"{assessment.title} {assessment.risk_category.value if assessment.risk_category else ''} policy wording",
            risk_category=assessment.risk_category.value
            if assessment.risk_category
            else None,
            limit=5,  # Increased from 3 for better coverage
        )
    except Exception as e:
        logger.warning(f"RAG context fetch failed: {e}")

    # Get prefill data
    prefill = await document_generator.prefill_template(
        assessment=assessment_data,
        template=template,
        extracted_data=extracted_data,
        rag_context=rag_context,
    )

    return PrefillResponse(
        template_id=template.get("id"),
        template_name=template.get("name"),
        field_mappings=prefill.get("field_mappings", {}),
        unmapped_fields=prefill.get("unmapped_fields", []),
        data_conflicts=prefill.get("data_conflicts", []),
        completion_percentage=prefill.get("completion_percentage", 0),
        rag_context_used=rag_context is not None,
        rag_sources=[],
    )


@router.post("/generated-documents/{doc_id}/finalize", response_model=FinalizeResponse)
async def finalize_document(
    doc_id: str,
    request: FinalizeRequest = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Finalize a document and generate PDF.
    """
    # Parse doc_id: frontend may send string IDs like "gen_1770850906225" or plain integers
    parsed_id = _parse_doc_id(doc_id)
    if parsed_id is None:
        raise HTTPException(400, f"Invalid document ID format: {doc_id}")

    # Join with Assessment to verify ownership
    query = (
        select(GeneratedDocument)
        .join(Assessment, GeneratedDocument.assessment_id == Assessment.id)
        .where(
            GeneratedDocument.id == parsed_id, Assessment.created_by == current_user.id
        )
    )
    result = await db.execute(query)
    doc = result.scalars().first()

    if not doc:
        raise HTTPException(404, "Document not found or access denied")

    # Update content if provided
    if request and request.final_content:
        doc.final_content = request.final_content

    # Generate PDF using WeasyPrint
    pdf_filename = (
        f"{doc.document_type}_{doc.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    )
    pdf_dir = os.path.join(settings.resolved_upload_dir, "generated")
    os.makedirs(pdf_dir, exist_ok=True)
    pdf_path = os.path.join(pdf_dir, pdf_filename)

    # Get document content and parse sections
    raw_content = doc.final_content or doc.draft_content or {}

    # Build HTML sections from structured content
    def _build_sections_html(content_data):
        """Convert structured JSON sections into formatted HTML."""
        import html as html_mod

        if isinstance(content_data, str):
            # Plain text fallback
            return f'<div class="section"><p>{html_mod.escape(content_data)}</p></div>'

        if not isinstance(content_data, dict):
            return '<div class="section"><p>No content available.</p></div>'

        sections = content_data.get("sections", [])
        doc_title = content_data.get("document_title", "")
        parts = []

        if doc_title:
            parts.append(f'<h1 class="doc-title">{html_mod.escape(doc_title)}</h1>')

        for section in sections:
            title = (
                section.get("section_title", "")
                or section.get("heading", "")
                or section.get("title", "")
            )
            body = section.get("content", "")

            parts.append('<div class="section">')
            if title:
                parts.append(f'<h2 class="section-title">{html_mod.escape(title)}</h2>')

            if body:
                # Convert line breaks to paragraphs and handle bullet points
                paragraphs = body.split("\n\n")
                for para in paragraphs:
                    para = para.strip()
                    if not para:
                        continue
                    lines = para.split("\n")
                    # Check if this looks like a list
                    is_list = all(
                        line.strip().startswith(("-", "•", "*", "–"))
                        or not line.strip()
                        for line in lines
                        if line.strip()
                    )
                    if is_list:
                        parts.append("<ul>")
                        for line in lines:
                            line = line.strip().lstrip("-•*– ").strip()
                            if line:
                                parts.append(f"<li>{html_mod.escape(line)}</li>")
                        parts.append("</ul>")
                    else:
                        parts.append(f"<p>{html_mod.escape(para)}</p>")

            parts.append("</div>")

        # Render schedules
        schedules = content_data.get("schedules", [])
        if schedules:
            parts.append('<div class="schedules">')
            parts.append('<h2 class="section-title">Schedules</h2>')
            for schedule in schedules:
                sched_title = (
                    schedule.get("title", "")
                    or schedule.get("section_title", "")
                    or "Schedule"
                )
                sched_content = schedule.get("content", "")
                parts.append('<div class="schedule">')
                if sched_title:
                    parts.append(
                        f'<h3 class="schedule-title">{html_mod.escape(sched_title)}</h3>'
                    )
                if sched_content:
                    parts.append(
                        f'<div class="schedule-content">{html_mod.escape(sched_content)}</div>'
                    )
                parts.append("</div>")
            parts.append("</div>")

        # Render appendices
        appendices = content_data.get("appendices", [])
        if appendices:
            parts.append('<div class="appendices">')
            parts.append('<h2 class="section-title">Appendices</h2>')
            for appendix in appendices:
                app_title = (
                    appendix.get("title", "")
                    or appendix.get("section_title", "")
                    or "Appendix"
                )
                app_content = appendix.get("content", "")
                parts.append('<div class="appendix">')
                if app_title:
                    parts.append(
                        f'<h3 class="appendix-title">{html_mod.escape(app_title)}</h3>'
                    )
                if app_content:
                    parts.append(
                        f'<div class="appendix-content">{html_mod.escape(app_content)}</div>'
                    )
                parts.append("</div>")
            parts.append("</div>")

        return "\n".join(parts)

    sections_html = _build_sections_html(raw_content)

    # Get document title from content or fallback
    doc_title = ""
    if isinstance(raw_content, dict):
        doc_title = raw_content.get("document_title", "") or raw_content.get(
            "title", ""
        )
    if not doc_title:
        doc_title = doc.document_type.upper().replace("_", " ")

    # Create HTML template for PDF
    html_template = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            @page {{
                size: A4;
                margin: 2cm;
            }}
            body {{
                font-family: 'Times New Roman', Times, serif;
                font-size: 11pt;
                line-height: 1.6;
                color: #333;
            }}
            .header {{
                text-align: center;
                margin-bottom: 30px;
                border-bottom: 2px solid #1a365d;
                padding-bottom: 20px;
            }}
            .header h1 {{
                color: #1a365d;
                font-size: 20pt;
                margin: 0;
                letter-spacing: 1px;
            }}
            .header p {{
                color: #666;
                font-size: 10pt;
                margin: 5px 0 0 0;
            }}
            .meta {{
                background: #f7fafc;
                padding: 15px;
                margin-bottom: 25px;
                border-radius: 5px;
                border-left: 4px solid #1a365d;
            }}
            .meta-item {{
                display: inline-block;
                margin-right: 30px;
            }}
            .meta-label {{
                font-weight: bold;
                color: #1a365d;
            }}
            .doc-title {{
                text-align: center;
                color: #1a365d;
                font-size: 16pt;
                margin: 20px 0;
            }}
            .section {{
                margin-bottom: 20px;
                page-break-inside: avoid;
            }}
            .section-title {{
                color: #1a365d;
                font-size: 13pt;
                font-weight: bold;
                margin-top: 20px;
                margin-bottom: 10px;
                padding-bottom: 5px;
                border-bottom: 1px solid #e2e8f0;
                text-transform: uppercase;
                letter-spacing: 0.5px;
            }}
            .section p {{
                margin: 8px 0;
                text-align: justify;
            }}
            .section ul {{
                margin: 8px 0;
                padding-left: 25px;
            }}
            .section li {{
                margin-bottom: 4px;
            }}
            .footer {{
                position: fixed;
                bottom: 1cm;
                left: 2cm;
                right: 2cm;
                text-align: center;
                font-size: 9pt;
                color: #666;
                border-top: 1px solid #ddd;
                padding-top: 10px;
            }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>{doc_title}</h1>
            <p>Document ID: {doc.id} | Generated: {datetime.now().strftime("%Y-%m-%d %H:%M")}</p>
        </div>
        <div class="meta">
            <div class="meta-item">
                <span class="meta-label">Document Type:</span> {doc.document_type.replace("_", " ").title()}
            </div>
            <div class="meta-item">
                <span class="meta-label">Status:</span> Finalized
            </div>
        </div>
        {sections_html}
        <div class="footer">
            InstantRisk - AI-Powered Underwriting Platform | Confidential
        </div>
    </body>
    </html>
    """

    # Generate PDF with WeasyPrint
    try:
        from weasyprint import HTML

        pdf_bytes = HTML(string=html_template).write_pdf()

        with open(pdf_path, "wb") as f:
            f.write(pdf_bytes)

        pdf_size = len(pdf_bytes)
    except Exception as e:
        # Fallback: create a simple text-based PDF if WeasyPrint fails
        import logging

        logging.error(f"WeasyPrint PDF generation failed: {e}")
        # Create empty placeholder file
        pdf_size = 0
        with open(pdf_path, "wb") as f:
            f.write(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")  # Minimal PDF header

    doc.mark_finalized(pdf_path, pdf_filename, pdf_size)
    await db.commit()
    await db.refresh(doc)

    return FinalizeResponse(
        document_id=doc.id,
        status="finalized",
        pdf_url=f"/api/v1/generated-documents/{doc.id}/download",
        pdf_file_name=pdf_filename,
        pdf_file_size=pdf_size,
        finalized_at=doc.finalized_at,
    )


@router.get("/generated-documents/{doc_id}/download")
async def download_document(
    doc_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Download a finalized document PDF."""
    # Parse doc_id: frontend may send string IDs like "gen_1770850906225" or plain integers
    parsed_id = _parse_doc_id(doc_id)
    if parsed_id is None:
        raise HTTPException(400, f"Invalid document ID format: {doc_id}")

    # Join with Assessment to verify ownership
    query = (
        select(GeneratedDocument)
        .join(Assessment, GeneratedDocument.assessment_id == Assessment.id)
        .where(
            GeneratedDocument.id == parsed_id, Assessment.created_by == current_user.id
        )
    )
    result = await db.execute(query)
    doc = result.scalars().first()

    if not doc:
        raise HTTPException(404, "Document not found or access denied")

    if not doc.pdf_path:
        raise HTTPException(400, "Document has not been finalized")

    # Return file (placeholder)
    from fastapi.responses import FileResponse

    if os.path.exists(doc.pdf_path):
        return FileResponse(
            doc.pdf_path, media_type="application/pdf", filename=doc.pdf_file_name
        )
    else:
        raise HTTPException(404, "PDF file not found")


# =============================================================================
# V3 DOCUMENT GENERATION ENDPOINTS
# =============================================================================

import json
from pathlib import Path
from pydantic import BaseModel, Field
from typing import Any

# Template paths
TEMPLATES_BASE_PATH = Path("/app/data/templates")
POLICIES_PATH = TEMPLATES_BASE_PATH / "policies"
CLAUSES_PATH = TEMPLATES_BASE_PATH / "clauses"


class GenerateDocumentV3Request(BaseModel):
    """Request for V3 document generation."""

    document_type: str = Field(
        ...,
        description="Type of document to generate (policy, endorsement, certificate)",
    )
    line_of_business: str = Field(
        ..., description="Line of business (cyber, property, marine, etc.)"
    )
    template_id: Optional[str] = Field(None, description="Specific template ID to use")
    selected_clauses: List[str] = Field(
        default_factory=list, description="List of clause IDs to include"
    )
    variables: dict = Field(
        default_factory=dict, description="Variables to populate in the document"
    )
    include_standard_clauses: bool = Field(
        True, description="Include standard mandatory clauses"
    )
    language: Optional[str] = Field(
        None,
        description="Target language code (en, de, fr, es, it, pt, nl, ar, zh, ja). Uses user's preferred language if not specified.",
    )


class GeneratedDocumentV3Response(BaseModel):
    """Response for V3 document generation."""

    document_id: str
    document_type: str
    line_of_business: str
    title: str
    template_used: Optional[str] = None
    sections: List[dict]
    clauses_included: List[dict]
    variables_applied: dict
    warnings: List[str] = []
    generated_at: datetime
    language: str = "en"


class ClauseSuggestion(BaseModel):
    """Suggested clause for a document."""

    clause_id: str
    clause_name: str
    clause_type: str
    is_mandatory: bool
    is_recommended: bool
    reason: str
    line_of_business: str


class SuggestClausesResponse(BaseModel):
    """Response for clause suggestions."""

    line_of_business: str
    document_type: str
    mandatory_clauses: List[ClauseSuggestion]
    recommended_clauses: List[ClauseSuggestion]
    optional_clauses: List[ClauseSuggestion]
    total_suggested: int


def _load_json_file(path: Path) -> Optional[dict]:
    """Load and parse a JSON file."""
    try:
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    except (json.JSONDecodeError, IOError):
        pass
    return None


def _load_policies_for_line(line: str) -> List[dict]:
    """Load all policy templates for a specific line of business."""
    policies = []
    line_path = POLICIES_PATH / line

    if line_path.exists() and line_path.is_dir():
        for json_file in line_path.glob("*.json"):
            policy = _load_json_file(json_file)
            if policy:
                policies.append(policy)

    return policies


def _load_all_clause_types() -> List[dict]:
    """Load all clause type files."""
    clause_types = []
    by_type_path = CLAUSES_PATH / "by_type"

    if by_type_path.exists():
        for json_file in by_type_path.glob("*.json"):
            clause_data = _load_json_file(json_file)
            if clause_data:
                clause_types.append(clause_data)

    return clause_types


def _get_clause_by_id(clause_id: str) -> Optional[dict]:
    """Get a specific clause by ID from the full 33k+ clause library."""
    # First try the comprehensive clause service (33k+ clauses)
    clause = clause_service.get_clause_by_id(clause_id)
    if clause:
        return clause

    # Fall back to V3 template files
    clause_types = _load_all_clause_types()
    for clause_type_data in clause_types:
        for c in clause_type_data.get("clauses", []):
            if c.get("id") == clause_id:
                return {**c, "clause_type": clause_type_data.get("type", "")}

    return None


def _get_mandatory_clauses(line_of_business: str, document_type: str) -> List[dict]:
    """Get mandatory clauses for a line of business and document type.

    Returns inline clause definitions (LMA standard) so they work
    regardless of whether template JSON files exist on disk.
    """
    # Core mandatory clauses for ALL Lloyd's policies
    core_mandatory = [
        {
            "id": "LMA5021",
            "name": "War & Civil War Exclusion",
            "clause_type": "exclusion",
            "line_of_business": "general",
            "text": "This insurance excludes loss, damage, liability or expense directly or indirectly caused by war, invasion, acts of foreign enemies, hostilities, civil war, revolution, rebellion, insurrection, or military power.",
        },
        {
            "id": "LMA3100",
            "name": "Sanctions Limitation & Exclusion",
            "clause_type": "exclusion",
            "line_of_business": "general",
            "text": "No insurer shall provide cover or pay any claim to the extent that doing so would expose that insurer to any sanction under United Nations resolutions or EU, UK, or US trade sanctions laws.",
        },
        {
            "id": "LMA5400",
            "name": "Several Liability Clause",
            "clause_type": "condition",
            "line_of_business": "general",
            "text": "The liability of an insurer under this contract is several and not joint with other insurers. An insurer is liable only for the proportion of liability it has underwritten.",
        },
        {
            "id": "LMA5027",
            "name": "Market Reform Contract",
            "clause_type": "condition",
            "line_of_business": "general",
            "text": "This insurance is subject to the Market Reform Contract provisions as agreed by the Lloyd's Market Association.",
        },
        {
            "id": "LMA5515",
            "name": "Law & Jurisdiction (England & Wales)",
            "clause_type": "condition",
            "line_of_business": "general",
            "text": "This insurance shall be governed by and construed in accordance with the law of England and Wales. Each party agrees to submit to the exclusive jurisdiction of the English courts.",
        },
        {
            "id": "LMA5406",
            "name": "Claims Cooperation Clause",
            "clause_type": "condition",
            "line_of_business": "general",
            "text": "The Insured shall cooperate fully with Underwriters in the investigation, defence and settlement of any claim. The Insured shall not admit liability or make any payment without the written consent of Underwriters.",
        },
    ]

    # Line-specific mandatory clauses
    line_specific = {
        "property": [
            {
                "id": "LMA5567",
                "name": "Terrorism Exclusion (Property)",
                "clause_type": "exclusion",
                "line_of_business": "property",
                "text": "This insurance excludes loss or damage directly or indirectly caused by any act of terrorism.",
            },
        ],
        "marine": [
            {
                "id": "ICC-A",
                "name": "Institute Cargo Clauses (A)",
                "clause_type": "coverage",
                "line_of_business": "marine",
                "text": "This insurance covers all risks of loss of or damage to the subject-matter insured except as excluded.",
            },
        ],
        "cyber": [
            {
                "id": "LMA5401",
                "name": "Cyber Attack Exclusion",
                "clause_type": "exclusion",
                "line_of_business": "cyber",
                "text": "This insurance excludes loss directly or indirectly caused by a cyber attack unless specifically covered under this policy.",
            },
        ],
        "aviation": [
            {
                "id": "AVN48B",
                "name": "War, Hi-jacking and Other Perils Exclusion",
                "clause_type": "exclusion",
                "line_of_business": "aviation",
                "text": "This insurance excludes claims arising from war, hi-jacking, confiscation, and related perils in aviation.",
            },
        ],
    }

    line_key = line_of_business.lower().replace(" ", "_")
    return core_mandatory + line_specific.get(line_key, [])


def _get_recommended_clauses(line_of_business: str, document_type: str) -> List[dict]:
    """Get recommended clauses for a line of business and document type."""
    line_recommended = {
        "property": [
            {
                "id": "NMA2914",
                "name": "Joint Excess Loss Clause",
                "clause_type": "condition",
                "line_of_business": "property",
                "text": "If other insurance covers the same loss, the Company shall not be liable for more than its rateable proportion of the amount exceeding the total of other deductibles.",
            },
            {
                "id": "LMA5014",
                "name": "Duty of Fair Presentation",
                "clause_type": "condition",
                "line_of_business": "property",
                "text": "The Insured shall make a fair presentation of the risk in accordance with the Insurance Act 2015.",
            },
            {
                "id": "LMA5096",
                "name": "Premium Payment Clause",
                "clause_type": "condition",
                "line_of_business": "general",
                "text": "Premium is payable in accordance with the London Market settlement procedures within 30 days.",
            },
        ],
        "marine": [
            {
                "id": "ICC-B",
                "name": "Institute Cargo Clauses (B)",
                "clause_type": "coverage",
                "line_of_business": "marine",
                "text": "Named perils coverage for marine cargo including fire, explosion, stranding, and collision.",
            },
            {
                "id": "IWC-CARGO",
                "name": "Institute War Clauses (Cargo)",
                "clause_type": "coverage",
                "line_of_business": "marine",
                "text": "War risk coverage extension for marine cargo shipments.",
            },
        ],
        "cyber": [
            {
                "id": "LMA5402",
                "name": "Cyber Act War Exclusion",
                "clause_type": "exclusion",
                "line_of_business": "cyber",
                "text": "Excludes losses from cyber operations linked to war, whether declared or not.",
            },
            {
                "id": "LMA5394",
                "name": "Pandemic Exclusion",
                "clause_type": "exclusion",
                "line_of_business": "general",
                "text": "Excludes losses arising from or in connection with any pandemic or epidemic.",
            },
        ],
        "aviation": [
            {
                "id": "AVN52E",
                "name": "War and Allied Perils Extension",
                "clause_type": "coverage",
                "line_of_business": "aviation",
                "text": "Extends coverage to include war and allied perils for aviation risks.",
            },
        ],
        "casualty": [
            {
                "id": "LMA3200",
                "name": "Employer's Liability Clause",
                "clause_type": "coverage",
                "line_of_business": "casualty",
                "text": "Coverage for employer's liability arising from bodily injury to employees.",
            },
        ],
    }

    line_key = line_of_business.lower().replace(" ", "_")
    return line_recommended.get(line_key, [])


def _substitute_variables(text: str, variables: dict) -> str:
    """Substitute variables in text using {{variable}} syntax."""
    result = text
    for key, value in variables.items():
        placeholder = f"{{{{{key}}}}}"
        result = result.replace(placeholder, str(value))
    return result


@router.post("/documents/generate-v3", response_model=GeneratedDocumentV3Response)
async def generate_document_v3(
    request: GenerateDocumentV3Request, current_user: User = Depends(get_current_user)
):
    """
    Generate a document using V3 template system with multi-language support.

    Uses templates from /backend/data/templates/ and allows selection
    of specific clauses to include in the generated document.
    Documents are automatically translated to the user's preferred language.

    Args:
        request: GenerateDocumentV3Request with generation parameters

    Returns:
        GeneratedDocumentV3Response with the generated document.
    """
    warnings = []

    # Determine target language
    target_language = None
    if request.language:
        try:
            target_language = SupportedLanguage(request.language)
        except ValueError:
            warnings.append(
                f"Invalid language code: {request.language}. Using English."
            )
            target_language = SupportedLanguage.ENGLISH
    elif current_user.preferred_language:
        target_language = current_user.preferred_language
    else:
        target_language = SupportedLanguage.ENGLISH

    # Normalize line of business
    line_lower = request.line_of_business.lower().replace(" ", "_")

    # Find template to use
    template_used = None
    sections = []

    if request.template_id:
        # Load specific template
        policies = _load_policies_for_line(line_lower)
        for policy in policies:
            if policy.get("id") == request.template_id:
                template_used = policy
                break

        if not template_used:
            # Try all lines
            for line_dir in POLICIES_PATH.iterdir():
                if line_dir.is_dir():
                    for policy in _load_policies_for_line(line_dir.name):
                        if policy.get("id") == request.template_id:
                            template_used = policy
                            break
                if template_used:
                    break

    if not template_used:
        # Find first matching template for line
        policies = _load_policies_for_line(line_lower)
        if policies:
            template_used = policies[0]
            warnings.append(
                f"No specific template requested. Using default: {template_used.get('name')}"
            )
        else:
            warnings.append(
                f"No templates found for line: {line_lower}. Using generic structure."
            )

    # Build sections from template
    if template_used:
        for section in template_used.get("sections", []):
            section_content = section.get("content", "")
            # Substitute variables
            section_content = _substitute_variables(section_content, request.variables)

            sections.append(
                {
                    "name": section.get("name", ""),
                    "content": section_content,
                    "order": len(sections) + 1,
                }
            )

    # Add selected clauses
    clauses_included = []

    # Include mandatory clauses if requested
    if request.include_standard_clauses:
        mandatory = _get_mandatory_clauses(line_lower, request.document_type)
        for clause in mandatory:
            clause_text = _substitute_variables(
                clause.get("text", ""), request.variables
            )
            clauses_included.append(
                {
                    "id": clause.get("id", ""),
                    "name": clause.get("name", ""),
                    "text": clause_text,
                    "type": clause.get("clause_type", ""),
                    "is_mandatory": True,
                }
            )

    # Include explicitly selected clauses
    for clause_id in request.selected_clauses:
        # Skip if already included as mandatory
        if any(c.get("id") == clause_id for c in clauses_included):
            continue

        clause = _get_clause_by_id(clause_id)
        if clause:
            clause_text = _substitute_variables(
                clause.get("text", ""), request.variables
            )
            clauses_included.append(
                {
                    "id": clause.get("id", ""),
                    "name": clause.get("name", ""),
                    "text": clause_text,
                    "type": clause.get("clause_type", ""),
                    "is_mandatory": False,
                }
            )
        else:
            warnings.append(f"Clause not found: {clause_id}")

    # Generate document ID
    doc_id = f"doc_{uuid.uuid4().hex[:12]}"

    # Determine title
    title = f"{request.document_type.title()} - {request.line_of_business.title()}"
    if request.variables.get("insured_name"):
        title = f"{title} - {request.variables.get('insured_name')}"

    # Translate content if not English
    if target_language and target_language != SupportedLanguage.ENGLISH:
        # Translate title
        title = await translation_service.translate_text(
            title, target_language, context="insurance document title"
        )

        # Translate sections
        translated_sections = []
        for section in sections:
            translated_section = section.copy()
            if section.get("name"):
                translated_section["name"] = await translation_service.translate_text(
                    section["name"],
                    target_language,
                    context="insurance document section header",
                )
            if section.get("content"):
                translated_section[
                    "content"
                ] = await translation_service.translate_text(
                    section["content"], target_language, context="insurance document"
                )
            translated_section["original_language"] = "en"
            translated_section["translated_to"] = target_language.value
            translated_sections.append(translated_section)
        sections = translated_sections

        # Translate clauses
        translated_clauses = []
        for clause in clauses_included:
            translated_clause = await translation_service.translate_clause(
                clause, target_language
            )
            translated_clauses.append(translated_clause)
        clauses_included = translated_clauses

        warnings.append(f"Document translated to {target_language.value}")

    return GeneratedDocumentV3Response(
        document_id=doc_id,
        document_type=request.document_type,
        line_of_business=request.line_of_business,
        title=title,
        template_used=template_used.get("id") if template_used else None,
        sections=sections,
        clauses_included=clauses_included,
        variables_applied=request.variables,
        warnings=warnings,
        generated_at=datetime.now(timezone.utc),
        language=target_language.value if target_language else "en",
    )


@router.get("/clauses/suggest", response_model=SuggestClausesResponse)
async def suggest_clauses(
    line_of_business: str,
    document_type: str = "policy",
    territory: Optional[str] = None,
    sum_insured: Optional[float] = None,
    current_user: User = Depends(get_current_user),
):
    """
    Get pre-selected clause suggestions for a line of business and document type.

    Uses the LMA clauses service to recommend mandatory, recommended, and optional
    clauses based on risk category, territory, and sum insured.

    Args:
        line_of_business: Insurance line (cyber, property, marine, etc.)
        document_type: Type of document (policy, endorsement, certificate)
        territory: Optional territory for territory-specific recommendations
        sum_insured: Optional sum insured for large-risk recommendations

    Returns:
        SuggestClausesResponse with categorized clause suggestions.
    """
    # Use the proper LMA clauses service which has real clause IDs
    recommendations = lma_clauses_service.recommend_clauses(
        risk_category=line_of_business,
        territory=territory,
        sum_insured=sum_insured,
    )

    mandatory_suggestions = [
        ClauseSuggestion(
            clause_id=c.get("id", ""),
            clause_name=c.get("name", ""),
            clause_type=c.get("category", ""),
            is_mandatory=True,
            is_recommended=True,
            reason=f"Required for {line_of_business} {document_type} — Lloyd's market standard",
            line_of_business=c.get("category", "general"),
        )
        for c in recommendations.get("mandatory", [])
    ]

    recommended_suggestions = [
        ClauseSuggestion(
            clause_id=c.get("id", ""),
            clause_name=c.get("name", ""),
            clause_type=c.get("category", ""),
            is_mandatory=False,
            is_recommended=True,
            reason=f"Commonly included in {line_of_business} policies",
            line_of_business=c.get("category", "general"),
        )
        for c in recommendations.get("recommended", [])
    ]

    optional_from_lma = [
        ClauseSuggestion(
            clause_id=c.get("id", ""),
            clause_name=c.get("name", ""),
            clause_type=c.get("category", ""),
            is_mandatory=False,
            is_recommended=False,
            reason=f"Available for {line_of_business} placements",
            line_of_business=c.get("category", "general"),
        )
        for c in recommendations.get("optional", [])
    ]

    # Also include clauses from the full 33k+ clause library
    already_suggested = set(
        [c.clause_id for c in mandatory_suggestions]
        + [c.clause_id for c in recommended_suggestions]
        + [c.clause_id for c in optional_from_lma]
    )

    line_lower = line_of_business.lower().replace(" ", "_")
    optional_suggestions = list(optional_from_lma)

    # Add clauses from the comprehensive library
    all_clauses = clause_service.get_all_clauses()
    line_clauses = clause_service.get_clauses_by_category(line_lower)
    clause_map = {c.get("id"): c for c in all_clauses}
    for c in line_clauses:
        clause_map[c.get("id")] = c

    for clause_id, clause in clause_map.items():
        if clause_id in already_suggested:
            continue
        clause_category = clause.get("category", "general")
        if clause_category == line_lower or clause_category in [
            "core",
            "general",
            "claims",
            "sanctions",
        ]:
            optional_suggestions.append(
                ClauseSuggestion(
                    clause_id=clause_id,
                    clause_name=clause.get("name", "")[:100],
                    clause_type=clause_category,
                    is_mandatory=False,
                    is_recommended=False,
                    reason=f"Available from {clause.get('source', 'clause library')}",
                    line_of_business=clause_category,
                )
            )
        if len(optional_suggestions) >= 500:
            break

    total = (
        len(mandatory_suggestions)
        + len(recommended_suggestions)
        + len(optional_suggestions)
    )

    return SuggestClausesResponse(
        line_of_business=line_of_business,
        document_type=document_type,
        mandatory_clauses=mandatory_suggestions,
        recommended_clauses=recommended_suggestions,
        optional_clauses=optional_suggestions,
        total_suggested=total,
    )


# =============================================================================
# AI-Driven Document Generation (OpenDraft Pipeline)
# =============================================================================


@router.post("/document-generation/ai-recommend")
async def ai_recommend_documents(
    request: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    AI-driven document recommendation.
    Analyzes assessment and tells the user exactly what documents they need and why.
    Replaces the old hardcoded DOCUMENT_REQUIREMENTS mapping.
    """
    assessment_id = request.get("assessment_id")
    user_request = request.get("user_request")

    if not assessment_id:
        raise HTTPException(400, "assessment_id is required")

    # Load assessment
    query = select(Assessment).where(
        Assessment.id == assessment_id, Assessment.created_by == current_user.id
    )
    result = await db.execute(query)
    assessment = result.scalars().first()
    if not assessment:
        raise HTTPException(404, "Assessment not found")

    # Try OpenDraft AI analysis
    try:
        from app.services.opendraft_generator import opendraft_generator

        assessment_data = {
            "id": assessment.id,
            "reference_number": assessment.reference_number,
            "title": assessment.title,
            "risk_category": assessment.risk_category.value
            if assessment.risk_category
            else "general",
            "decision": assessment.decision.value if assessment.decision else None,
            "insured_name": assessment.insured_name,
            "territory": assessment.territory or "",
            "premium": assessment.premium,
            "sum_insured": assessment.sum_insured,
            "ai_analysis": assessment.ai_analysis or {},
            "rapidrate_results": assessment.rapidrate_results or {},
        }

        if user_request:
            assessment_data["user_request"] = user_request

        recommendations = await opendraft_generator.analyze_assessment(
            assessment_data, str(current_user.id)
        )
        return {"recommended_documents": recommendations}
    except Exception as e:
        logger.error(f"AI document recommendation failed: {e}", exc_info=True)
        risk_category = (
            assessment.risk_category.value if assessment.risk_category else "general"
        )
        fallback = _get_fallback_recommendations(risk_category)
        return {"recommended_documents": fallback, "is_fallback": True}


@router.post("/document-generation/ai-clauses")
async def ai_clause_search(
    request: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    AI-driven clause search with source attribution.
    Searches user's uploaded docs first, then ACORD, then AI generation.
    """
    assessment_id = request.get("assessment_id")
    document_types = request.get("document_types", [])

    if not assessment_id:
        raise HTTPException(400, "assessment_id is required")

    try:
        from app.services.clauses_library_service import clauses_library_service

        # Build clauses from the real clause library + inline fallbacks
        clauses_by_doc = {}

        # Mandatory LMA clauses for all document types
        mandatory_ids = [
            "LMA5021",
            "LMA5390",
            "LMA5400",
            "LMA5027",
            "LMA5515",
            "LMA5406",
        ]

        for doc_type in document_types or ["policy_wording"]:
            doc_clauses = []

            # 1. Add mandatory LMA clauses with FULL text (library + inline fallback)
            for clause_id in mandatory_ids:
                clause_data = clauses_library_service.get_clause_by_id(clause_id)
                if not clause_data or not clause_data.get("text"):
                    clause_data = _resolve_clause_full_text(clause_id)
                if clause_data:
                    full_text = clause_data.get("text", "") or ""
                    doc_clauses.append(
                        {
                            "clause_id": clause_data.get("id", clause_id),
                            "name": clause_data.get("name", clause_id),
                            "source": clause_data.get("source", "lma"),
                            "content_preview": (
                                full_text or clause_data.get("name", "")
                            )[:200]
                            + ("..." if len(full_text) > 200 else ""),
                            "full_text": full_text,
                            "is_mandatory": True,
                        }
                    )

            # 2. Search for document-type-relevant clauses
            type_searches = {
                "policy_wording": ["insurance policy wording", "indemnification"],
                "endorsement": ["endorsement amendment", "policy extension"],
                "mrc_slip": ["market reform contract", "slip agreement"],
                "certificate": ["certificate insurance", "evidence coverage"],
                "schedule": ["schedule premium", "property schedule"],
                "cover_note": ["cover note interim", "binding authority"],
            }
            search_terms = type_searches.get(doc_type, ["insurance clause"])

            existing_ids = {c["clause_id"] for c in doc_clauses}
            for term in search_terms:
                results, _ = clauses_library_service.search(query=term, page_size=8)
                for r in results:
                    if r["id"] not in existing_ids and len(doc_clauses) < 20:
                        full_text = r.get("text", "") or ""
                        # Resolve full text if the library result is too short
                        if len(full_text) < 50:
                            resolved = _resolve_clause_full_text(r["id"])
                            if resolved:
                                full_text = resolved.get("text", "") or full_text
                        doc_clauses.append(
                            {
                                "clause_id": r["id"],
                                "name": r["name"],
                                "source": r.get("source", "library"),
                                "content_preview": (full_text or r.get("name", ""))[
                                    :200
                                ]
                                + ("..." if len(full_text) > 200 else ""),
                                "full_text": full_text,
                                "is_mandatory": False,
                            }
                        )
                        existing_ids.add(r["id"])

            # 3. Also search RAG for user-specific docs if available
            try:
                from app.services.unified_rag import unified_rag

                # Get assessment context for better search
                assess_query = select(Assessment).where(Assessment.id == assessment_id)
                assess_result = await db.execute(assess_query)
                assess = assess_result.scalars().first()

                risk_cat = ""
                insured = ""
                if assess:
                    risk_cat = (
                        assess.risk_category.value if assess.risk_category else ""
                    )
                    insured = assess.insured_name or assess.insured_entity_name or ""

                # Use risk-category-aware search instead of generic query
                user_search_queries = [
                    f"{risk_cat} {doc_type} insurance policy wording",
                    f"{risk_cat} exclusions conditions warranties",
                ]
                if insured:
                    user_search_queries.append(f"{insured} insurance policy")

                seen_texts = set()
                for uq in user_search_queries:
                    if len(doc_clauses) >= 25:
                        break
                    rag_results = await unified_rag.search(
                        query=uq,
                        user_id=str(current_user.id),
                        top_k=3,
                        min_score=0.5,  # Higher threshold to avoid garbage
                        source_tiers=["user"],
                    )
                    for r in rag_results:
                        text = (r.get("text", "") or "").strip()
                        if not text or len(text) < 50:
                            continue  # Skip tiny/empty chunks
                        # Deduplicate by content
                        text_key = text[:100]
                        if text_key in seen_texts:
                            continue
                        seen_texts.add(text_key)

                        # Use filename + category for meaningful name
                        filename = r.get("filename", "")
                        category = r.get("category", "")
                        name_parts = []
                        if filename:
                            # Clean filename for display
                            clean_name = (
                                filename.rsplit(".", 1)[0]
                                .replace("_", " ")
                                .replace("-", " ")
                                .title()
                            )
                            name_parts.append(clean_name)
                        if category and category != "policy":
                            name_parts.append(f"({category})")
                        display_name = (
                            " ".join(name_parts) if name_parts else "User Document"
                        )

                        doc_clauses.append(
                            {
                                "clause_id": f"user_{abs(hash(text[:200])) % 100000}",
                                "name": display_name,
                                "source": "user_uploaded",
                                "content_preview": text[:200]
                                + ("..." if len(text) > 200 else ""),
                                "is_mandatory": False,
                            }
                        )
            except Exception as e:
                logging.getLogger(__name__).debug(
                    f"User clause search for {doc_type} skipped: {e}"
                )

            clauses_by_doc[doc_type] = doc_clauses

        return {"clauses_by_document": clauses_by_doc}
    except Exception as e:
        logger.error(f"AI clause search failed: {e}", exc_info=True)
        # Minimal fallback
        clauses_by_doc = {}
        for doc_type in document_types or ["policy_wording"]:
            clauses_by_doc[doc_type] = [
                {
                    "clause_id": "preamble",
                    "name": "Preamble & Recitals",
                    "source": "template",
                    "content_preview": "Standard opening recitals...",
                    "is_mandatory": True,
                },
                {
                    "clause_id": "insuring_agreement",
                    "name": "Insuring Agreement",
                    "source": "template",
                    "content_preview": "The Insurer agrees to indemnify...",
                    "is_mandatory": True,
                },
                {
                    "clause_id": "exclusions",
                    "name": "General Exclusions",
                    "source": "template",
                    "content_preview": "Standard exclusions...",
                    "is_mandatory": True,
                },
                {
                    "clause_id": "conditions",
                    "name": "General Conditions",
                    "source": "template",
                    "content_preview": "General conditions...",
                    "is_mandatory": True,
                },
                {
                    "clause_id": "law_jurisdiction",
                    "name": "Law & Jurisdiction",
                    "source": "template",
                    "content_preview": "English law...",
                    "is_mandatory": True,
                },
            ]
        return {"clauses_by_document": clauses_by_doc, "is_fallback": True}


@router.post("/document-generation/generate")
async def generate_documents_opendraft(
    request: dict,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Generate documents using OpenDraft 19-agent pipeline (async).
    Returns a job_id immediately. Frontend polls /generation-jobs/{job_id}/status for progress.
    """
    assessment_id = request.get("assessment_id")
    documents = request.get("documents", [])
    clauses = request.get("clauses")

    if not assessment_id:
        raise HTTPException(400, "assessment_id is required")

    # Load assessment
    query = select(Assessment).where(
        Assessment.id == assessment_id, Assessment.created_by == current_user.id
    )
    result = await db.execute(query)
    assessment = result.scalars().first()
    if not assessment:
        raise HTTPException(404, "Assessment not found")

    # Create job record
    import uuid

    job_id = str(uuid.uuid4())[:8]
    job = DocumentGenerationJob(
        id=job_id,
        assessment_id=assessment_id,
        status="pending",
        total_documents=len(documents),
    )
    db.add(job)
    await db.commit()

    assessment_data = {
        "id": assessment.id,
        "reference_number": assessment.reference_number,
        "title": assessment.title,
        "risk_category": assessment.risk_category.value
        if assessment.risk_category
        else "general",
        "decision": assessment.decision.value if assessment.decision else None,
        "insured_name": assessment.insured_name,
        "broker_reference": assessment.broker_reference,
        "territory": assessment.territory or "",
        "premium": assessment.premium,
        "sum_insured": assessment.sum_insured,
        "deductible": assessment.deductible,
        "inception_date": str(assessment.inception_date)
        if assessment.inception_date
        else None,
        "expiry_date": str(assessment.expiry_date) if assessment.expiry_date else None,
        "risk_score": assessment.risk_score,
        "ai_analysis": assessment.ai_analysis or {},
        "rapidrate_results": assessment.rapidrate_results or {},
        "broker_name": assessment.broker_name,
        "commission_rate": float(assessment.commission_rate)
        if assessment.commission_rate
        else None,
        "insured_entity_name": assessment.insured_entity_name,
        "companies_house_number": assessment.companies_house_number,
        "renewal_date": str(assessment.renewal_date)
        if assessment.renewal_date
        else None,
        "loss_run_reporting_rules": assessment.loss_run_reporting_rules,
        "regulatory_framework": assessment.regulatory_framework,
    }

    # Backfill from ai_analysis when top-level fields are empty
    ai_data = assessment.ai_analysis or {}
    if isinstance(ai_data, str):
        import json as _json

        try:
            ai_data = _json.loads(ai_data)
        except Exception:
            ai_data = {}
    if isinstance(ai_data, dict):
        _backfill_map = {
            "territory": "territory",
            "broker_name": "broker_name",
            "broker_reference": "broker_reference",
            "premium": "premium",
            "sum_insured": "sum_insured",
            "deductible": "deductible",
            "inception_date": "inception_date",
            "expiry_date": "expiry_date",
            "currency": "currency",
            "insured_entity_name": "company_name",
        }
        for field, ai_key in _backfill_map.items():
            current_val = assessment_data.get(field)
            is_empty = current_val is None or current_val == "" or current_val == "None"
            if field in ("premium", "sum_insured", "deductible"):
                is_empty = is_empty or current_val == 0 or current_val == 0.0
            if is_empty:
                ai_val = ai_data.get(ai_key)
                if (
                    ai_val is not None
                    and str(ai_val).strip()
                    and str(ai_val).strip().lower() != "none"
                ):
                    assessment_data[field] = ai_val

    # Resolve clauses to full text using the unified resolver.
    # The frontend sends either:
    #   - dict keyed by doc_type: {"policy_wording": [{clause_id, name, content_preview}], ...}
    #   - list of clause IDs (legacy)
    #   - list of clause dicts
    # _resolve_clauses_batch handles all formats and resolves full clause text
    # from the library/inline fallbacks instead of using 200-char truncated previews.
    flat_clauses = _resolve_clauses_batch(clauses) if clauses else []

    # Queue background task — returns immediately
    background_tasks.add_task(
        _run_opendraft_job,
        job_id,
        assessment_data,
        str(current_user.id),
        documents,
        flat_clauses if flat_clauses else None,
    )

    return {"job_id": job_id, "status": "pending"}


async def _run_opendraft_job(
    job_id: str,
    assessment_data: dict,
    user_id: str,
    doc_types: list,
    clause_dicts: list = None,
    language: str = None,
):
    """Background task that runs the 19-agent pipeline and updates job progress in DB.

    IMPORTANT: Uses short-lived DB sessions for each phase to avoid stale connections.
    The pipeline can run for 2-10+ minutes; holding a single session open that long
    causes the connection to go stale, making both completion and failure commits fail
    silently — leaving the job stuck in 'processing' forever.
    """
    from app.core.database import AsyncSessionLocal
    from app.services.opendraft_generator import opendraft_generator

    # ── Phase 1: Mark as processing (short-lived session) ──────────────
    try:
        async with AsyncSessionLocal() as db:
            job = await db.get(DocumentGenerationJob, job_id)
            if job:
                job.start_processing()
                await db.commit()
                logger.info(f"OpenDraft job {job_id}: marked as processing")
            else:
                logger.error(f"OpenDraft job {job_id}: job record not found, aborting")
                return
    except Exception as e:
        logger.error(f"OpenDraft job {job_id}: failed to mark as processing: {e}")
        return

    # ── Phase 2: Progress callback (each invocation uses its own session) ──
    async def progress_callback(progress):
        try:
            async with AsyncSessionLocal() as cb_db:
                cb_job = await cb_db.get(DocumentGenerationJob, job_id)
                if cb_job:
                    agent_num = progress.get("step", 0)
                    agent_name = progress.get("agent", "")
                    status = progress.get("status", "running")
                    phase = progress.get("phase", "")
                    percentage = min(
                        int((agent_num / 19) * 95), 95
                    )  # cap at 95% until truly done
                    if status == "running":
                        cb_job.update_progress(
                            agent_name, f"{phase}: {agent_name}", percentage
                        )
                        await cb_db.commit()
        except Exception as e:
            logger.debug(f"OpenDraft job {job_id}: progress update skipped: {e}")

    # ── Phase 3: Run the pipeline (NO db session held open) ────────────
    result = None
    error_msg = None
    try:
        result = await asyncio.wait_for(
            opendraft_generator.generate(
                assessment_data=assessment_data,
                user_id=user_id,
                doc_types=doc_types,
                progress_callback=progress_callback,
                clause_ids=clause_dicts,
                language=language,
            ),
            timeout=1800,  # 30-minute overall timeout (33 sections × ~60s each)
        )
    except asyncio.TimeoutError:
        error_msg = "Document generation timed out after 10 minutes"
        logger.error(f"OpenDraft job {job_id}: {error_msg}")
    except Exception as e:
        error_msg = str(e)
        logger.error(f"OpenDraft job {job_id} pipeline failed: {e}", exc_info=True)

    # ── Phase 4: Save results (fresh session, guaranteed not stale) ────
    if error_msg:
        # Pipeline failed — mark job as failed
        try:
            async with AsyncSessionLocal() as db:
                job = await db.get(DocumentGenerationJob, job_id)
                if job:
                    job.fail(error_msg)
                    await db.commit()
                    logger.info(
                        f"OpenDraft job {job_id}: marked as failed: {error_msg}"
                    )
        except Exception as e2:
            logger.error(
                f"OpenDraft job {job_id}: CRITICAL - could not mark job as failed: {e2}",
                exc_info=True,
            )
        return

    # Pipeline succeeded — store documents and mark as completed
    try:
        import json as _json

        def _default(o):
            if hasattr(o, "hex"):  # UUID
                return str(o)
            raise TypeError(
                f"Object of type {type(o).__name__} is not JSON serializable"
            )

        safe_result = _json.loads(_json.dumps(result, default=_default))

        async with AsyncSessionLocal() as db:
            job = await db.get(DocumentGenerationJob, job_id)
            if not job:
                logger.error(
                    f"OpenDraft job {job_id}: job record not found for completion"
                )
                return

            job.completed_documents = len(result.get("documents", []))
            job.complete()

            # Create individual GeneratedDocument records for each document
            from app.models.generated_document import GeneratedDocument
            from sqlalchemy.orm.attributes import flag_modified

            doc_ids = []
            for doc_data in safe_result.get("documents", []):
                sections_to_store = doc_data.get("sections", [])
                if sections_to_store:
                    sample_keys = list(sections_to_store[0].keys())
                    logger.info(
                        f"Storing doc '{doc_data.get('document_type')}': "
                        f"{len(sections_to_store)} sections, "
                        f"section[0] keys={sample_keys}"
                    )
                gen_doc = GeneratedDocument(
                    assessment_id=job.assessment_id,
                    generation_job_id=job_id,
                    document_type=doc_data.get("document_type", "unknown"),
                    title=doc_data.get("title", "Untitled Document"),
                    status="draft",
                    draft_content={
                        "sections": sections_to_store,
                        "schedules": doc_data.get("schedules", []),
                        "appendices": doc_data.get("appendices", []),
                    },
                    ai_suggestions={
                        "compliance": doc_data.get("compliance", {}),
                        "risk_challenge": doc_data.get("risk_challenge", {}),
                        "quality_gate": doc_data.get("quality_gate", {}),
                        "gap_analysis": doc_data.get("gap_analysis", {}),
                        "source_attribution": doc_data.get("source_attribution", {}),
                        "ml_predictions": doc_data.get("ml_predictions"),
                    },
                    ai_confidence=0.85,
                    generation_method="ai_prefill",
                )
                db.add(gen_doc)
                await db.flush()  # get the auto-generated id
                doc_ids.append(gen_doc.id)
                doc_data["id"] = gen_doc.id  # add DB id back to agent_outputs

            # Set agent_outputs AFTER adding document IDs and flag as modified
            job.agent_outputs = safe_result
            flag_modified(job, "agent_outputs")
            await db.commit()
            logger.info(
                f"OpenDraft job {job_id} completed: {len(doc_ids)} documents created (IDs: {doc_ids})"
            )

    except Exception as e:
        logger.error(
            f"OpenDraft job {job_id}: failed to save results: {e}", exc_info=True
        )
        # Last-resort: try to mark as failed with yet another fresh session
        try:
            async with AsyncSessionLocal() as db2:
                job = await db2.get(DocumentGenerationJob, job_id)
                if job and job.status != "completed":
                    job.fail(f"Failed to save results: {str(e)}")
                    await db2.commit()
                    logger.info(
                        f"OpenDraft job {job_id}: marked as failed (save error)"
                    )
        except Exception as e2:
            logger.error(
                f"OpenDraft job {job_id}: CRITICAL - could not mark job as failed after save error: {e2}",
                exc_info=True,
            )


def _get_fallback_recommendations(risk_category: str) -> list:
    """Basic document recommendations when AI is unavailable."""
    base = [
        {
            "type": "mrc_slip",
            "name": "MRC Slip",
            "reason": "Standard placement document for Lloyd's market submissions",
            "priority": "mandatory",
            "estimated_sections": 12,
        },
        {
            "type": "policy_wording",
            "name": "Policy Wording",
            "reason": "Full policy with terms, conditions, and coverage details",
            "priority": "mandatory",
            "estimated_sections": 18,
        },
        {
            "type": "endorsement_schedule",
            "name": "Endorsement Schedule",
            "reason": "List of endorsements and amendments to standard terms",
            "priority": "recommended",
            "estimated_sections": 8,
        },
    ]

    if risk_category in ("marine", "cargo", "hull"):
        base.append(
            {
                "type": "war_risks_endorsement",
                "name": "War Risks Endorsement",
                "reason": "Marine risks typically require separate war risks coverage",
                "priority": "recommended",
                "estimated_sections": 4,
            }
        )
    elif risk_category in ("property", "fire"):
        base.append(
            {
                "type": "nat_cat_endorsement",
                "name": "Natural Catastrophe Endorsement",
                "reason": "Property risks need natural catastrophe sub-limits",
                "priority": "recommended",
                "estimated_sections": 5,
            }
        )

    base.append(
        {
            "type": "pricing_summary",
            "name": "Pricing Summary",
            "reason": "Technical pricing breakdown with rate derivation",
            "priority": "optional",
            "estimated_sections": 6,
        }
    )

    return base
