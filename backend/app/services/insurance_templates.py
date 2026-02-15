"""
Lloyd's Market Compliant Insurance Document Templates

Based on official Lloyd's Market Association (LMA) standards and
Market Reform Contract (MRC) v3.0 specifications.

Sources:
- Lloyd's Wordings Repository (LWR)
- London Market Group (LMG) MRC v3.0 Template
- LMA Model Clauses (LMA5096, etc.)
- Institute Cargo Clauses (ICC) 2009
"""

from typing import Dict, List, Any
from datetime import datetime, timedelta


# =============================================================================
# STANDARD LLOYD'S MARKET CLAUSES (LMA/LSW)
# =============================================================================

STANDARD_CLAUSES = {
    "several_liability": {
        "id": "LMA5096",
        "name": "Several Liability Clause",
        "text": """The liability of an insurer under this contract is several and not joint with other insurers party to this contract. An insurer is liable only for the proportion of liability it has underwritten. An insurer is not jointly liable for the proportion of liability underwritten by any other insurer. Nor is an insurer otherwise responsible for any liability of any other insurer that may underwrite this contract.

The proportion of liability under this contract underwritten by an insurer (or, in the case of a Lloyd's syndicate, the total of the proportions underwritten by all the members of the syndicate taken together) is shown in this contract.

In the case of a Lloyd's syndicate, each member of the syndicate (rather than the syndicate itself) is an insurer. Each member has underwritten a proportion of the total shown for the syndicate. The liability of each member of the syndicate is several and not joint with other members. A member is liable only for that member's proportion. A member is not jointly liable for any other member's proportion.

The business address of each member is Lloyd's, One Lime Street, London EC3M 7HA. The identity of each member and their respective proportion may be obtained by writing to Market Services, Lloyd's."""
    },

    "service_of_suit_usa": {
        "id": "NMA1998",
        "name": "Service of Suit Clause (USA)",
        "text": """It is agreed that in the event of the failure of Underwriters hereon to pay any amount claimed to be due hereunder, Underwriters hereon, at the request of the Insured (or Reinsured), will submit to the jurisdiction of a Court of competent jurisdiction within the United States. Nothing in this Clause constitutes or should be understood to constitute a waiver of Underwriters' rights to commence an action in any Court of competent jurisdiction in the United States, to remove an action to a United States District Court, or to seek a transfer of a case to another Court as permitted by the laws of the United States or of any State in the United States.

The undersigned are authorized and directed to accept service of process on behalf of Underwriters in any such suit."""
    },

    "english_jurisdiction": {
        "id": "LMA5121",
        "name": "Law and Jurisdiction Clause (England)",
        "text": """This insurance shall be governed by and construed in accordance with the law of England and Wales. Each party agrees to submit to the exclusive jurisdiction of the Courts of England and Wales for any dispute arising under or in connection with this insurance."""
    },

    "arbitration": {
        "id": "LMA3090",
        "name": "Arbitration Clause",
        "text": """Any dispute arising out of or in connection with this contract, including any question regarding its existence, validity or termination, shall be referred to and finally resolved by arbitration under the rules of the London Court of International Arbitration (LCIA), which rules are deemed to be incorporated by reference into this clause.

The number of arbitrators shall be three. The seat, or legal place, of arbitration shall be London, England. The language to be used in the arbitral proceedings shall be English."""
    },

    "nuclear_exclusion": {
        "id": "NMA1191",
        "name": "Radioactive Contamination Exclusion Clause",
        "text": """This insurance does not cover loss or destruction of or damage to any property whatsoever or any loss or expense whatsoever resulting or arising therefrom or any consequential loss directly or indirectly caused by or contributed to by or arising from ionising radiations from or contamination by radioactivity from any nuclear fuel or from any nuclear waste from the combustion of nuclear fuel, or the radioactive, toxic, explosive or other hazardous properties of any explosive nuclear assembly or nuclear component thereof."""
    },

    "sanctions": {
        "id": "LMA3100",
        "name": "Sanctions Limitation and Exclusion Clause",
        "text": """No (re)insurer shall be deemed to provide cover and no (re)insurer shall be liable to pay any claim or provide any benefit hereunder to the extent that the provision of such cover, payment of such claim or provision of such benefit would expose that (re)insurer to any sanction, prohibition or restriction under United Nations resolutions or the trade or economic sanctions, laws or regulations of the European Union, United Kingdom or United States of America."""
    },

    "premium_payment": {
        "id": "LMA5235",
        "name": "Premium Payment Clause",
        "text": """Notwithstanding any provision to the contrary within this contract or any endorsement hereto, in the event of non-payment of premium, or any instalment thereof, when due Underwriters may give notice requiring payment within 30 days. In the event of non-payment within this period Underwriters may give not less than 30 days notice of cancellation.

Premium shall be paid in accordance with the London Market settlement procedures."""
    },

    "claims_notification": {
        "id": "NMA358",
        "name": "Claims Notification Clause",
        "text": """The Insured shall give notice to Underwriters as soon as practicable of any occurrence which may give rise to a claim under this Policy. Such notice shall include full particulars of the occurrence and shall be accompanied by all available supporting documentation.

The Insured shall not admit liability, make any payment, settle any claim, incur any expense or enter into any litigation without the prior written consent of Underwriters, except at the Insured's own cost."""
    },

    "cancellation": {
        "id": "NMA1331",
        "name": "Cancellation Clause",
        "text": """This insurance may be cancelled by either party giving 30 days' notice in writing to the other party. In the event of cancellation by Underwriters, premium shall be returned pro rata for the unexpired period. In the event of cancellation at the request of the Insured, Underwriters shall retain a premium calculated in accordance with their customary short rate table."""
    },

    "subrogation": {
        "id": "LMA5400",
        "name": "Subrogation Clause",
        "text": """In the event of any payment under this Policy, Underwriters shall be subrogated to all the Insured's rights of recovery therefor against any person or organisation and the Insured shall execute and deliver instruments and papers and do whatever else is necessary to secure such rights. The Insured shall do nothing after loss to prejudice such rights."""
    },
}


# =============================================================================
# TEMPLATE CATEGORIES
# =============================================================================

TEMPLATE_CATEGORIES = [
    {"id": "lloyds", "name": "Lloyd's Market", "description": "Lloyd's of London standard MRC documents", "icon": "shield"},
    {"id": "commercial", "name": "Commercial Lines", "description": "Standard commercial insurance templates", "icon": "business"},
    {"id": "specialty", "name": "Specialty Lines", "description": "Specialty and professional lines", "icon": "star"},
    {"id": "marine", "name": "Marine & Cargo", "description": "Marine hull and cargo insurance", "icon": "directions_boat"},
]


# =============================================================================
# LLOYD'S MRC SLIP TEMPLATE (v3.0)
# =============================================================================

LLOYDS_MRC_SLIP = {
    "id": "lloyds_mrc_slip",
    "name": "Lloyd's MRC Slip v3.0",
    "category": "lloyds",
    "description": "Market Reform Contract (MRC) v3.0 - Standard Lloyd's placing slip format per LMG specifications",
    "version": "3.0",
    "is_system": True,
    "tags": ["lloyds", "slip", "primary", "placing", "mrc"],
    "content_template": """
MARKET REFORM CONTRACT

UNIQUE MARKET REFERENCE: {umr}
PLACING BROKER CONTRACT REFERENCE: {broker_ref}

================================================================================
RISK DETAILS
================================================================================

Type:                   {type_of_business}
Placing Basis:          {placing_type}
Risk Code:              {risk_code}
Class of Business:      {class_of_business}

================================================================================
THE ASSURED
================================================================================

Name:                   {insured_name}
Address:                {insured_address}
Country:                {insured_country}

================================================================================
PERIOD
================================================================================

From:                   {period_from} at {inception_time}
To:                     {period_to}
Both days inclusive, local standard time at the Insured's address.

================================================================================
INTEREST
================================================================================

{interest}

================================================================================
TERRITORIAL LIMITS
================================================================================

{territorial_limits}

================================================================================
LIMIT OF LIABILITY
================================================================================

{limit_of_liability} {currency} any one occurrence and in the aggregate
{sub_limits}

================================================================================
DEDUCTIBLE
================================================================================

{deductible} {currency} each and every loss

================================================================================
BASIS OF COVER
================================================================================

{basis_of_cover}
{retroactive_date}

================================================================================
PREMIUM
================================================================================

{premium_amount} {currency}
{premium_terms}

Premium payable in accordance with the London Market settlement procedures.

================================================================================
SUBJECTIVITIES
================================================================================

{subjectivities}

================================================================================
WARRANTIES
================================================================================

{warranties}

================================================================================
EXCLUSIONS
================================================================================

{exclusions}

Standard Market Exclusions apply:
- Radioactive Contamination (NMA1191)
- Sanctions (LMA3100)

================================================================================
CONDITIONS
================================================================================

{conditions}

================================================================================
CLAIMS
================================================================================

Claims to be notified as soon as practicable to:
{claims_contact}

Claims Cooperation Clause applies.
Claims payable in {currency} at {claims_location}.

================================================================================
CHOICE OF LAW AND JURISDICTION
================================================================================

This insurance shall be governed by and construed in accordance with the law of England and Wales.
Each party agrees to submit to the exclusive jurisdiction of the Courts of England and Wales.

================================================================================
SEVERAL LIABILITY CLAUSE (LMA5096)
================================================================================

The liability of an insurer under this contract is several and not joint with other insurers party to this contract. An insurer is liable only for the proportion of liability it has underwritten. An insurer is not jointly liable for the proportion of liability underwritten by any other insurer.

In the case of a Lloyd's syndicate, each member of the syndicate (rather than the syndicate itself) is an insurer. The business address of each member is Lloyd's, One Lime Street, London EC3M 7HA.

================================================================================
SECURITY
================================================================================

Lead Underwriter:       {lead_underwriter}
Syndicate:              {lead_syndicate}
Reference:              {lead_reference}
Signed Line:            {signed_line}%
Order:                  {order_percentage}%

Following Markets:
{following_markets}

================================================================================
BROKER
================================================================================

{broker_name}
{broker_address}
PIN: {broker_pin}

================================================================================
INFORMATION
================================================================================

This slip is for placing purposes only and is subject to contract.

{additional_information}
""",
    "fields": {
        "risk_details": {
            "umr": {"label": "Unique Market Reference (UMR)", "required": True, "format": "B0999XXXXX"},
            "broker_ref": {"label": "Placing Broker Contract Reference", "required": True},
            "type_of_business": {"label": "Type", "required": True, "options": ["New", "Renewal", "Rewrite", "Transfer"]},
            "class_of_business": {"label": "Class of Business", "required": True},
            "risk_code": {"label": "Lloyd's Risk Code", "required": True},
            "placing_type": {"label": "Placing Type", "options": ["Open Market", "Facility", "Lineslip", "Binder"]},
        },
        "assured": {
            "insured_name": {"label": "Assured Name", "required": True},
            "insured_address": {"label": "Address", "required": True},
            "insured_country": {"label": "Country", "required": True},
        },
        "period": {
            "period_from": {"label": "Period From", "required": True, "type": "date"},
            "period_to": {"label": "Period To", "required": True, "type": "date"},
            "inception_time": {"label": "Inception Time", "default": "00:01"},
        },
        "coverage": {
            "interest": {"label": "Interest/Subject Matter Insured", "required": True, "type": "textarea"},
            "territorial_limits": {"label": "Territorial Limits", "required": True},
            "basis_of_cover": {"label": "Basis of Cover", "required": True, "options": ["Claims Made", "Occurrence", "Losses Occurring"]},
            "retroactive_date": {"label": "Retroactive Date", "type": "date"},
        },
        "financials": {
            "limit_of_liability": {"label": "Limit of Liability", "required": True, "type": "currency"},
            "sub_limits": {"label": "Sub-Limits", "type": "textarea"},
            "deductible": {"label": "Deductible/Excess", "required": True, "type": "currency"},
            "currency": {"label": "Currency", "required": True, "options": ["GBP", "USD", "EUR"]},
            "premium_amount": {"label": "Premium", "required": True, "type": "currency"},
            "premium_terms": {"label": "Premium Terms", "type": "textarea"},
        },
        "security": {
            "lead_underwriter": {"label": "Lead Underwriter", "required": True},
            "lead_syndicate": {"label": "Lead Syndicate", "required": True},
            "lead_reference": {"label": "Lead Reference"},
            "signed_line": {"label": "Signed Line %", "required": True, "type": "percentage"},
            "order_percentage": {"label": "Order %", "required": True, "type": "percentage"},
            "following_markets": {"label": "Following Markets", "type": "list"},
        },
        "broker": {
            "broker_name": {"label": "Broker Name", "required": True},
            "broker_address": {"label": "Broker Address"},
            "broker_pin": {"label": "Broker PIN"},
        },
        "conditions": {
            "subjectivities": {"label": "Subjectivities", "type": "list"},
            "warranties": {"label": "Warranties", "type": "list"},
            "exclusions": {"label": "Additional Exclusions", "type": "list"},
            "conditions": {"label": "Special Conditions", "type": "list"},
        },
        "claims": {
            "claims_contact": {"label": "Claims Contact"},
            "claims_location": {"label": "Claims Payable At", "default": "London"},
        },
    },
    "sections": [
        "RISK DETAILS", "THE ASSURED", "PERIOD", "INTEREST", "TERRITORIAL LIMITS",
        "LIMIT OF LIABILITY", "DEDUCTIBLE", "BASIS OF COVER", "PREMIUM", "SUBJECTIVITIES",
        "WARRANTIES", "EXCLUSIONS", "CONDITIONS", "CLAIMS", "CHOICE OF LAW AND JURISDICTION",
        "SEVERAL LIABILITY CLAUSE", "SECURITY", "BROKER", "INFORMATION"
    ],
    "standard_clauses": ["several_liability", "english_jurisdiction", "nuclear_exclusion", "sanctions"],
}


# =============================================================================
# LLOYD'S POLICY WORDING TEMPLATE
# =============================================================================

LLOYDS_POLICY_WORDING = {
    "id": "lloyds_policy_wording",
    "name": "Lloyd's Policy Wording",
    "category": "lloyds",
    "description": "Standard Lloyd's policy wording document with full legal text",
    "version": "2.0",
    "is_system": True,
    "tags": ["lloyds", "policy", "wording", "contract"],
    "content_template": """
LLOYD'S POLICY

Policy Number: {policy_number}
Unique Market Reference: {umr}

================================================================================
DECLARATIONS
================================================================================

Item 1.  Named Insured:           {named_insured}
Item 2.  Address:                 {insured_address}
Item 3.  Policy Period:           From {period_from} to {period_to}
                                  Both days inclusive at 12:01 a.m. local time
Item 4.  Limit of Liability:      {limit_of_liability} {currency}
Item 5.  Retention/Deductible:    {deductible} {currency}
Item 6.  Premium:                 {premium} {currency}
Item 7.  Retroactive Date:        {retroactive_date}

================================================================================
INSURING AGREEMENTS
================================================================================

Subject to all terms, conditions and limitations of this Policy, the Underwriters agree:

COVERAGE A - {coverage_a_title}

{coverage_a_text}

COVERAGE B - {coverage_b_title}

{coverage_b_text}

================================================================================
DEFINITIONS
================================================================================

"Claim" means:
(a) a written demand for monetary damages or non-monetary relief;
(b) a civil proceeding commenced by the service of a complaint or similar pleading;
(c) a criminal proceeding commenced by the return of an indictment;
(d) a formal administrative or regulatory proceeding commenced by the filing of a notice of charges.

"Defence Costs" means reasonable legal fees and expenses incurred by the Insured with the prior written consent of the Underwriters in the investigation, defence, appeal or settlement of any Claim.

"Insured" means:
(a) the Named Insured;
(b) any subsidiary of the Named Insured;
(c) any director, officer, or employee of (a) or (b) above while acting within the scope of their duties.

"Loss" means:
(a) damages, judgments, settlements;
(b) Defence Costs;
(c) pre-judgment and post-judgment interest on any judgment.

"Policy Period" means the period stated in Item 3 of the Declarations.

"Wrongful Act" means any actual or alleged error, omission, misstatement, misleading statement, neglect, or breach of duty.

================================================================================
EXCLUSIONS
================================================================================

This Policy does not cover any Claim:

1.  PRIOR KNOWLEDGE
    based upon any fact or circumstance which, before the inception of the Policy Period, any Insured knew or could reasonably have foreseen might give rise to a Claim;

2.  PRIOR CLAIMS AND CIRCUMSTANCES
    based upon any Claim made or circumstances notified prior to the inception of the Policy Period;

3.  DELIBERATE ACTS
    arising out of any dishonest, fraudulent, criminal or malicious act or omission committed by the Insured; provided that this exclusion shall not apply unless and until there is a final adjudication adverse to the Insured;

4.  BODILY INJURY AND PROPERTY DAMAGE
    for bodily injury, sickness, disease or death of any person, or damage to or destruction of any tangible property;

5.  INSURED VS INSURED
    brought by or on behalf of any Insured against any other Insured;

6.  CONTRACTUAL LIABILITY
    arising out of any liability assumed by the Insured under any contract or agreement, except to the extent that such liability would have attached in the absence of such contract;

7.  NUCLEAR
    arising directly or indirectly out of nuclear reaction, nuclear radiation or radioactive contamination;

8.  SANCTIONS
    to the extent that providing cover would expose Underwriters to any sanction, prohibition or restriction under UN resolutions or EU, UK or USA sanctions laws.

================================================================================
CONDITIONS
================================================================================

1.  NOTICE OF CLAIM
    The Insured shall give written notice to the Underwriters as soon as practicable of any Claim made against the Insured.

2.  NOTICE OF CIRCUMSTANCES
    If during the Policy Period the Insured becomes aware of any circumstances which may reasonably be expected to give rise to a Claim, the Insured may give written notice to the Underwriters of such circumstances.

3.  DEFENCE AND SETTLEMENT
    The Underwriters shall have the right and duty to defend any Claim covered under this Policy. The Underwriters shall not settle any Claim without the consent of the Insured.

4.  ASSISTANCE AND COOPERATION
    The Insured shall cooperate with the Underwriters and provide such information and documentation as the Underwriters may reasonably require.

5.  SUBROGATION
    In the event of any payment under this Policy, the Underwriters shall be subrogated to all the Insured's rights of recovery therefor.

6.  OTHER INSURANCE
    This Policy shall be excess of any other valid and collectible insurance available to the Insured.

7.  CANCELLATION
    This Policy may be cancelled by the Insured at any time by written notice. This Policy may be cancelled by the Underwriters by giving thirty (30) days written notice.

8.  ENTIRE AGREEMENT
    This Policy constitutes the entire agreement between the parties.

================================================================================
CLAIMS
================================================================================

All claims should be notified to:

{claims_handler}
{claims_address}
{claims_email}

Claims shall be payable in {currency} at Lloyd's, London.

================================================================================
CHOICE OF LAW AND JURISDICTION
================================================================================

This Policy shall be governed by and construed in accordance with the law of England and Wales.
Each party agrees to submit to the exclusive jurisdiction of the Courts of England and Wales.

================================================================================
SEVERAL LIABILITY CLAUSE
================================================================================

The liability of an insurer under this contract is several and not joint with other insurers party to this contract. An insurer is liable only for the proportion of liability it has underwritten.

In the case of a Lloyd's syndicate, each member of the syndicate (rather than the syndicate itself) is an insurer.

The business address of each member is Lloyd's, One Lime Street, London EC3M 7HA.

================================================================================
SECURITY
================================================================================

{security_details}

================================================================================

IN WITNESS WHEREOF, the Underwriters have caused this Policy to be signed.

Signed at Lloyd's, London
Date: {issue_date}
""",
    "fields": {
        "declarations": {
            "policy_number": {"label": "Policy Number", "required": True},
            "umr": {"label": "Unique Market Reference", "required": True},
            "named_insured": {"label": "Named Insured", "required": True},
            "insured_address": {"label": "Insured Address", "required": True},
            "period_from": {"label": "Period From", "required": True, "type": "date"},
            "period_to": {"label": "Period To", "required": True, "type": "date"},
            "limit_of_liability": {"label": "Limit of Liability", "required": True, "type": "currency"},
            "deductible": {"label": "Retention/Deductible", "required": True, "type": "currency"},
            "premium": {"label": "Premium", "required": True, "type": "currency"},
            "currency": {"label": "Currency", "required": True, "options": ["GBP", "USD", "EUR"]},
            "retroactive_date": {"label": "Retroactive Date", "type": "date"},
        },
        "coverage": {
            "coverage_a_title": {"label": "Coverage A Title", "default": "Professional Liability"},
            "coverage_a_text": {"label": "Coverage A Text", "type": "textarea"},
            "coverage_b_title": {"label": "Coverage B Title", "default": "Defence Costs"},
            "coverage_b_text": {"label": "Coverage B Text", "type": "textarea"},
        },
        "claims": {
            "claims_handler": {"label": "Claims Handler"},
            "claims_address": {"label": "Claims Address"},
            "claims_email": {"label": "Claims Email"},
        },
        "security": {
            "security_details": {"label": "Security Details", "type": "textarea"},
            "issue_date": {"label": "Issue Date", "type": "date"},
        },
    },
    "sections": [
        "DECLARATIONS", "INSURING AGREEMENTS", "DEFINITIONS", "EXCLUSIONS",
        "CONDITIONS", "CLAIMS", "CHOICE OF LAW AND JURISDICTION",
        "SEVERAL LIABILITY CLAUSE", "SECURITY"
    ],
    "standard_clauses": ["several_liability", "english_jurisdiction", "claims_notification", "cancellation", "subrogation"],
}


# =============================================================================
# LLOYD'S COVER NOTE TEMPLATE
# =============================================================================

LLOYDS_COVER_NOTE = {
    "id": "lloyds_cover_note",
    "name": "Lloyd's Cover Note",
    "category": "lloyds",
    "description": "Temporary cover note confirming insurance pending policy issuance",
    "version": "1.0",
    "is_system": True,
    "tags": ["lloyds", "cover_note", "temporary", "confirmation"],
    "content_template": """
LLOYD'S COVER NOTE

Cover Note Number: {cover_note_number}
Date of Issue: {issue_date}
Valid Until: {valid_until}

================================================================================

This is to certify that insurance has been effected as follows:

================================================================================
INSURED
================================================================================

Name:       {insured_name}
Address:    {insured_address}

================================================================================
PERIOD OF INSURANCE
================================================================================

From:       {period_from}
To:         {period_to}
Both days inclusive, local standard time at the Insured's address.

================================================================================
INTEREST INSURED
================================================================================

{interest}

================================================================================
SUM INSURED / LIMIT OF LIABILITY
================================================================================

{limit_of_liability} {currency}

================================================================================
DEDUCTIBLE
================================================================================

{deductible} {currency} each and every loss

================================================================================
PREMIUM
================================================================================

{premium} {currency}
{premium_terms}

================================================================================
CONDITIONS
================================================================================

This Cover Note is issued subject to the terms, conditions, warranties and exclusions of Lloyd's standard policy form.

{special_conditions}

================================================================================
SUBJECTIVITIES
================================================================================

This insurance is subject to:

{subjectivities}

================================================================================
IMPORTANT NOTICE
================================================================================

This Cover Note is issued as evidence of insurance effected at Lloyd's and is for information purposes only. It does not amend, extend or alter the coverage afforded by the policy to which it refers.

The policy will be prepared and forwarded to the Insured in due course. In the event of any discrepancy between this Cover Note and the policy, the policy shall prevail.

================================================================================
SECURITY
================================================================================

Underwriters at Lloyd's, London
Lead: {lead_underwriter} ({lead_syndicate})
Line: {signed_line}%

================================================================================
BROKER
================================================================================

{broker_name}
{broker_address}

================================================================================

Issued at Lloyd's, London
Date: {issue_date}
""",
    "fields": {
        "cover_note": {
            "cover_note_number": {"label": "Cover Note Number", "required": True},
            "issue_date": {"label": "Issue Date", "required": True, "type": "date"},
            "valid_until": {"label": "Valid Until", "required": True, "type": "date"},
        },
        "insured": {
            "insured_name": {"label": "Insured Name", "required": True},
            "insured_address": {"label": "Insured Address", "required": True},
        },
        "coverage": {
            "period_from": {"label": "Period From", "required": True, "type": "date"},
            "period_to": {"label": "Period To", "required": True, "type": "date"},
            "interest": {"label": "Interest Insured", "required": True, "type": "textarea"},
            "limit_of_liability": {"label": "Limit of Liability", "required": True, "type": "currency"},
            "deductible": {"label": "Deductible", "type": "currency"},
            "currency": {"label": "Currency", "required": True, "options": ["GBP", "USD", "EUR"]},
            "premium": {"label": "Premium", "type": "currency"},
            "premium_terms": {"label": "Premium Terms"},
        },
        "conditions": {
            "special_conditions": {"label": "Special Conditions", "type": "textarea"},
            "subjectivities": {"label": "Subjectivities", "type": "list"},
        },
        "security": {
            "lead_underwriter": {"label": "Lead Underwriter", "required": True},
            "lead_syndicate": {"label": "Lead Syndicate"},
            "signed_line": {"label": "Signed Line %", "type": "percentage"},
        },
        "broker": {
            "broker_name": {"label": "Broker Name"},
            "broker_address": {"label": "Broker Address"},
        },
    },
    "sections": [
        "HEADER", "INSURED", "PERIOD OF INSURANCE", "INTEREST INSURED",
        "SUM INSURED", "DEDUCTIBLE", "PREMIUM", "CONDITIONS", "SUBJECTIVITIES",
        "IMPORTANT NOTICE", "SECURITY", "BROKER"
    ],
}


# =============================================================================
# CERTIFICATE OF INSURANCE TEMPLATE
# =============================================================================

CERTIFICATE_OF_INSURANCE = {
    "id": "certificate_of_insurance",
    "name": "Certificate of Insurance",
    "category": "commercial",
    "description": "Standard Certificate of Insurance providing evidence of coverage",
    "version": "2.0",
    "is_system": True,
    "tags": ["certificate", "proof", "commercial", "evidence"],
    "content_template": """
CERTIFICATE OF INSURANCE

Certificate Number: {certificate_number}
Date Issued: {issue_date}

================================================================================
THIS CERTIFICATE IS ISSUED AS A MATTER OF INFORMATION ONLY AND CONFERS NO RIGHTS
UPON THE CERTIFICATE HOLDER. THIS CERTIFICATE DOES NOT AMEND, EXTEND OR ALTER THE
COVERAGE AFFORDED BY THE POLICIES BELOW.
================================================================================

PRODUCER/BROKER
--------------------------------------------------------------------------------
{producer_name}
{producer_address}
Contact: {producer_contact}
Phone: {producer_phone}
Email: {producer_email}

INSURED
--------------------------------------------------------------------------------
{insured_name}
{insured_address}

================================================================================
COVERAGES
================================================================================

GENERAL LIABILITY                                    POLICY NUMBER: {gl_policy_number}
--------------------------------------------------------------------------------
Insurer: {gl_insurer}
Policy Period: {gl_effective_date} to {gl_expiration_date}

    Each Occurrence:                    {gl_each_occurrence}
    Damage to Rented Premises:          {gl_damage_rented_premises}
    Medical Expense (Any one person):   {gl_medical_expense}
    Personal & Advertising Injury:      {gl_personal_adv_injury}
    General Aggregate:                  {gl_general_aggregate}
    Products-Completed Ops Aggregate:   {gl_products_completed}

--------------------------------------------------------------------------------
AUTOMOBILE LIABILITY                                 POLICY NUMBER: {auto_policy_number}
--------------------------------------------------------------------------------
Insurer: {auto_insurer}
Policy Period: {auto_effective_date} to {auto_expiration_date}

    Combined Single Limit:              {auto_combined_single}
    Bodily Injury (Per person):         {auto_bi_per_person}
    Bodily Injury (Per accident):       {auto_bi_per_accident}
    Property Damage:                    {auto_property_damage}

--------------------------------------------------------------------------------
UMBRELLA/EXCESS LIABILITY                            POLICY NUMBER: {umbrella_policy_number}
--------------------------------------------------------------------------------
Insurer: {umbrella_insurer}
Policy Period: {umbrella_effective_date} to {umbrella_expiration_date}

    Each Occurrence:                    {umbrella_each_occurrence}
    Aggregate:                          {umbrella_aggregate}
    Retention:                          {umbrella_retention}

--------------------------------------------------------------------------------
WORKERS COMPENSATION                                 POLICY NUMBER: {wc_policy_number}
--------------------------------------------------------------------------------
Insurer: {wc_insurer}
Policy Period: {wc_effective_date} to {wc_expiration_date}

    Statutory Limits Apply
    E.L. Each Accident:                 {wc_el_each_accident}
    E.L. Disease - Policy Limit:        {wc_el_disease_policy}
    E.L. Disease - Each Employee:       {wc_el_disease_employee}

--------------------------------------------------------------------------------
PROFESSIONAL LIABILITY / E&O                         POLICY NUMBER: {pl_policy_number}
--------------------------------------------------------------------------------
Insurer: {pl_insurer}
Policy Period: {pl_effective_date} to {pl_expiration_date}

    Claims-Made    Retroactive Date: {pl_retroactive_date}
    Each Claim:                         {pl_each_claim}
    Aggregate:                          {pl_aggregate}
    Retention:                          {pl_retention}

================================================================================
DESCRIPTION OF OPERATIONS / LOCATIONS / VEHICLES
================================================================================

{description_of_operations}

================================================================================
CERTIFICATE HOLDER
================================================================================

{certificate_holder_name}
{certificate_holder_address}

Additional Insured Status: {additional_insured}
Waiver of Subrogation: {subrogation_waived}

================================================================================
CANCELLATION
================================================================================

Should any of the above described policies be cancelled before the expiration date
thereof, notice will be delivered in accordance with the policy provisions.

================================================================================

AUTHORIZED REPRESENTATIVE: _____________________

This certificate is issued by:
{issuer_name}
Date: {issue_date}
""",
    "fields": {
        "certificate": {
            "certificate_number": {"label": "Certificate Number", "required": True},
            "issue_date": {"label": "Date Issued", "required": True, "type": "date"},
        },
        "producer": {
            "producer_name": {"label": "Producer/Broker Name", "required": True},
            "producer_address": {"label": "Address", "required": True},
            "producer_contact": {"label": "Contact Name"},
            "producer_phone": {"label": "Phone"},
            "producer_email": {"label": "Email"},
        },
        "insured": {
            "insured_name": {"label": "Insured Name", "required": True},
            "insured_address": {"label": "Insured Address", "required": True},
        },
        "general_liability": {
            "gl_policy_number": {"label": "GL Policy Number"},
            "gl_insurer": {"label": "GL Insurer"},
            "gl_effective_date": {"label": "GL Effective Date", "type": "date"},
            "gl_expiration_date": {"label": "GL Expiration Date", "type": "date"},
            "gl_each_occurrence": {"label": "Each Occurrence", "type": "currency"},
            "gl_damage_rented_premises": {"label": "Damage to Rented Premises", "type": "currency"},
            "gl_medical_expense": {"label": "Medical Expense", "type": "currency"},
            "gl_personal_adv_injury": {"label": "Personal & Adv Injury", "type": "currency"},
            "gl_general_aggregate": {"label": "General Aggregate", "type": "currency"},
            "gl_products_completed": {"label": "Products-Comp/Op Agg", "type": "currency"},
        },
        "certificate_holder": {
            "certificate_holder_name": {"label": "Certificate Holder Name"},
            "certificate_holder_address": {"label": "Certificate Holder Address"},
            "description_of_operations": {"label": "Description of Operations", "type": "textarea"},
            "additional_insured": {"label": "Additional Insured", "type": "boolean"},
            "subrogation_waived": {"label": "Waiver of Subrogation", "type": "boolean"},
        },
    },
    "sections": [
        "HEADER", "PRODUCER/BROKER", "INSURED", "GENERAL LIABILITY",
        "AUTOMOBILE LIABILITY", "UMBRELLA/EXCESS LIABILITY", "WORKERS COMPENSATION",
        "PROFESSIONAL LIABILITY", "DESCRIPTION OF OPERATIONS", "CERTIFICATE HOLDER", "CANCELLATION"
    ],
}


# =============================================================================
# MARINE CARGO POLICY TEMPLATE (ICC 2009)
# =============================================================================

MARINE_CARGO = {
    "id": "marine_cargo",
    "name": "Marine Cargo Policy (ICC 2009)",
    "category": "marine",
    "description": "Marine cargo insurance based on Institute Cargo Clauses (A) 2009",
    "version": "2009",
    "is_system": True,
    "tags": ["marine", "cargo", "transit", "icc", "goods"],
    "content_template": """
MARINE CARGO POLICY

Policy Number: {policy_number}
Certificate Number: {certificate_number}

================================================================================
ASSURED
================================================================================

Name:       {assured_name}
Address:    {assured_address}
Interest:   {interest_type}

================================================================================
SUBJECT MATTER INSURED
================================================================================

{cargo_description}

Marks and Numbers: {marks_numbers}
Packing: {packing_type}

================================================================================
VOYAGE
================================================================================

From:       {from_location}
To:         {to_location}
Via:        {via_location}

Conveyance: {conveyance_type}
Vessel/Flight: {vessel_name}

================================================================================
AGREED VALUE / SUM INSURED
================================================================================

{sum_insured} {currency}
Basis of Valuation: {valuation_basis}

================================================================================
CONDITIONS
================================================================================

This insurance is subject to:

INSTITUTE CARGO CLAUSES (A) 2009

RISKS COVERED
This insurance covers all risks of loss of or damage to the subject-matter insured except as excluded by the provisions of Clauses 4, 5, 6 and 7 below.

GENERAL AVERAGE
This insurance covers general average and salvage charges, adjusted or determined according to the contract of carriage and/or the governing law and practice.

BOTH TO BLAME COLLISION CLAUSE
This insurance indemnifies the Assured against liability incurred under any Both to Blame Collision Clause in the contract of carriage.

================================================================================
EXCLUSIONS
================================================================================

4. GENERAL EXCLUSIONS
In no case shall this insurance cover:
4.1 loss damage or expense attributable to wilful misconduct of the Assured
4.2 ordinary leakage, ordinary loss in weight or volume, or ordinary wear and tear
4.3 loss damage or expense caused by insufficiency or unsuitability of packing
4.4 loss damage or expense caused by inherent vice or nature of the subject-matter
4.5 loss damage or expense caused by delay
4.6 loss damage or expense caused by insolvency or financial default of owners managers charterers or operators

================================================================================
DURATION - TRANSIT CLAUSE
================================================================================

This insurance attaches from the time the subject-matter insured is first moved in the warehouse for the purpose of immediate loading into the carrying vehicle for commencement of transit, continues during the ordinary course of transit and terminates either:

(a) on completion of unloading at the final warehouse at the destination, or
(b) on expiry of 60 days after completion of discharge from the oversea vessel at the final port of discharge,

whichever shall first occur.

================================================================================
CLAIMS
================================================================================

INSURABLE INTEREST
In order to recover under this insurance the Assured must have an insurable interest in the subject-matter insured at the time of the loss.

FORWARDING CHARGES
The Insurers will reimburse the Assured for extra charges properly incurred in forwarding the subject-matter insured to the destination following a covered event.

================================================================================
MINIMISING LOSSES - DUTY OF ASSURED
================================================================================

It is the duty of the Assured and their employees and agents:
- to take such measures as may be reasonable for the purpose of averting or minimising loss
- to ensure that all rights against carriers, bailees or other third parties are properly preserved

================================================================================
DEDUCTIBLE
================================================================================

{deductible} {currency}

================================================================================
PREMIUM
================================================================================

{premium} {currency}

================================================================================
LAW AND PRACTICE
================================================================================

This insurance is subject to English law and practice.

================================================================================
SECURITY
================================================================================

{security_details}

Certificate issued at Lloyd's, London
Date: {issue_date}
""",
    "fields": {
        "policy": {
            "policy_number": {"label": "Policy Number"},
            "certificate_number": {"label": "Certificate Number"},
        },
        "assured": {
            "assured_name": {"label": "Assured", "required": True},
            "assured_address": {"label": "Address", "required": True},
            "interest_type": {"label": "Interest", "options": ["Seller/Exporter", "Buyer/Importer", "Freight Forwarder", "Bank"]},
        },
        "cargo": {
            "cargo_description": {"label": "Description of Goods", "required": True, "type": "textarea"},
            "marks_numbers": {"label": "Marks & Numbers"},
            "packing_type": {"label": "Packing Type", "options": ["FCL", "LCL", "Breakbulk", "Bulk", "Containerized"]},
        },
        "voyage": {
            "from_location": {"label": "From", "required": True},
            "to_location": {"label": "To", "required": True},
            "via_location": {"label": "Via"},
            "conveyance_type": {"label": "Conveyance", "required": True, "options": ["Sea", "Air", "Road", "Rail", "Multi-Modal"]},
            "vessel_name": {"label": "Vessel/Flight Name"},
        },
        "values": {
            "sum_insured": {"label": "Sum Insured", "required": True, "type": "currency"},
            "currency": {"label": "Currency", "required": True, "options": ["GBP", "USD", "EUR"]},
            "valuation_basis": {"label": "Basis of Valuation", "options": ["CIF", "CIF+10%", "CIP", "FOB+10%", "Agreed Value"]},
        },
        "financials": {
            "deductible": {"label": "Deductible", "type": "currency"},
            "premium": {"label": "Premium", "type": "currency"},
        },
        "security": {
            "security_details": {"label": "Security Details", "type": "textarea"},
            "issue_date": {"label": "Issue Date", "type": "date"},
        },
    },
    "sections": [
        "ASSURED", "SUBJECT MATTER INSURED", "VOYAGE", "AGREED VALUE",
        "CONDITIONS", "EXCLUSIONS", "DURATION", "CLAIMS",
        "MINIMISING LOSSES", "DEDUCTIBLE", "PREMIUM", "LAW AND PRACTICE", "SECURITY"
    ],
    "standard_clauses": ["english_jurisdiction"],
}


# =============================================================================
# PROFESSIONAL INDEMNITY POLICY TEMPLATE
# =============================================================================

PROFESSIONAL_INDEMNITY = {
    "id": "professional_indemnity",
    "name": "Professional Indemnity Policy",
    "category": "specialty",
    "description": "Professional liability / Errors & Omissions insurance policy",
    "version": "2.0",
    "is_system": True,
    "tags": ["pi", "e&o", "professional", "liability", "claims-made"],
    "content_template": """
PROFESSIONAL INDEMNITY POLICY

Policy Number: {policy_number}
Unique Market Reference: {umr}

================================================================================
DECLARATIONS
================================================================================

Item 1.  Named Insured:           {firm_name}
Item 2.  Address:                 {firm_address}
Item 3.  Profession:              {profession}
Item 4.  Policy Period:           From {period_from} to {period_to}
Item 5.  Retroactive Date:        {retroactive_date}
Item 6.  Limit of Indemnity:      {limit_any_one_claim} {currency} any one claim
                                  {aggregate_limit} {currency} in the aggregate
Item 7.  Excess/Deductible:       {excess} {currency} each and every claim
Item 8.  Premium:                 {premium} {currency}

================================================================================
INSURING CLAUSE
================================================================================

The Underwriters agree to indemnify the Insured against:

(a) any civil liability incurred by the Insured arising out of any claim or claims first made against the Insured during the Policy Period and notified to the Underwriters during the Policy Period for breach of professional duty by reason of any negligent act, error or omission committed or alleged to have been committed by the Insured in the conduct of the Professional Business;

(b) all costs, fees and expenses incurred with the written consent of the Underwriters in the defence, investigation or settlement of any such claim.

================================================================================
BASIS OF COVER
================================================================================

This Policy is issued on a CLAIMS MADE BASIS. This means that the Policy covers only claims first made against the Insured and notified to the Underwriters during the Policy Period, provided always that any negligent act, error or omission giving rise to such claim occurred on or after the Retroactive Date.

================================================================================
LIMIT OF INDEMNITY
================================================================================

The liability of the Underwriters in respect of:

(a) any one claim including all Defence Costs relating thereto shall not exceed the Limit of Indemnity stated in Item 6;

(b) all claims made during the Policy Period including all Defence Costs shall not exceed the Aggregate Limit stated in Item 6.

Defence Costs are {defence_costs_treatment}.

================================================================================
EXCESS
================================================================================

The Insured shall bear the first {excess} {currency} of each and every claim including Defence Costs.

================================================================================
TERRITORIAL LIMITS
================================================================================

This Policy applies to claims arising from Professional Services performed anywhere in {territorial_limits}.

================================================================================
DEFINITIONS
================================================================================

"Claim" means any written demand for monetary or non-monetary relief, or any civil proceeding commenced by service of a writ.

"Defence Costs" means legal fees and expenses incurred in the investigation, defence, appeal or settlement of any Claim.

"Insured" means the firm named in Item 1 and any principal, partner, member, director or employee while acting within the scope of their duties.

"Professional Business" means the business of {profession} as conducted by the Insured.

================================================================================
EXTENSIONS
================================================================================

Subject to the Policy terms, conditions and exclusions, cover is extended to include:

1. LOSS OF DOCUMENTS
   Loss of or damage to documents in the Insured's custody or control up to {loss_of_documents_limit} {currency}.

2. DEFAMATION
   Claims arising from unintentional libel, slander or defamation in the conduct of the Professional Business.

3. COURT ATTENDANCE COSTS
   Costs of attendance at court by principals, partners or employees up to {court_attendance_rate} per day.

4. MITIGATION COSTS
   Reasonable costs incurred to avoid or mitigate a potential claim, subject to prior written consent.

================================================================================
EXCLUSIONS
================================================================================

This Policy does not cover any Claim:

1. PRIOR KNOWLEDGE - arising from any fact known before inception which might give rise to a Claim;
2. PRIOR CLAIMS - notified under any previous policy;
3. DELIBERATE ACTS - arising from dishonest, fraudulent, criminal or malicious acts of the Insured;
4. TRADING LOSSES - for trading losses, debts or trading liabilities;
5. BODILY INJURY / PROPERTY DAMAGE - for bodily injury or damage to tangible property;
6. NUCLEAR - arising from nuclear reaction, radiation or radioactive contamination;

================================================================================
CONDITIONS
================================================================================

1. CLAIMS NOTIFICATION
   The Insured shall give written notice to the Underwriters as soon as practicable of any Claim or circumstance which may give rise to a Claim.

2. CONDUCT OF CLAIMS
   The Insured shall not admit liability or make any payment without the prior written consent of the Underwriters.

3. COOPERATION
   The Insured shall cooperate fully with the Underwriters.

4. SUBROGATION
   The Underwriters shall be subrogated to all rights of recovery of the Insured.

5. DISCOVERY PERIOD
   If this Policy is not renewed, the Insured shall have the right to an Extended Reporting Period of {discovery_period} days upon payment of additional premium.

================================================================================
CLAIMS
================================================================================

All claims should be notified to:
{claims_contact}
{claims_email}

================================================================================
CHOICE OF LAW AND JURISDICTION
================================================================================

This Policy shall be governed by and construed in accordance with the law of England and Wales.

================================================================================
SEVERAL LIABILITY CLAUSE
================================================================================

The liability of an insurer under this contract is several and not joint with other insurers party to this contract.

================================================================================
SECURITY
================================================================================

{security_details}

Issue Date: {issue_date}
""",
    "fields": {
        "declarations": {
            "policy_number": {"label": "Policy Number", "required": True},
            "umr": {"label": "UMR"},
            "firm_name": {"label": "Firm Name", "required": True},
            "firm_address": {"label": "Address", "required": True},
            "profession": {"label": "Profession", "required": True},
            "period_from": {"label": "Period From", "required": True, "type": "date"},
            "period_to": {"label": "Period To", "required": True, "type": "date"},
            "retroactive_date": {"label": "Retroactive Date", "type": "date"},
            "limit_any_one_claim": {"label": "Limit Any One Claim", "required": True, "type": "currency"},
            "aggregate_limit": {"label": "Aggregate Limit", "required": True, "type": "currency"},
            "excess": {"label": "Excess/Deductible", "required": True, "type": "currency"},
            "currency": {"label": "Currency", "required": True, "options": ["GBP", "USD", "EUR"]},
            "premium": {"label": "Premium", "required": True, "type": "currency"},
        },
        "coverage": {
            "defence_costs_treatment": {"label": "Defence Costs", "options": ["Inside Limit", "Outside Limit", "Supplementary"]},
            "territorial_limits": {"label": "Territorial Limits", "required": True},
        },
        "extensions": {
            "loss_of_documents_limit": {"label": "Loss of Documents Limit", "type": "currency"},
            "court_attendance_rate": {"label": "Court Attendance Rate", "type": "currency"},
            "discovery_period": {"label": "Discovery Period (Days)", "type": "number", "default": 60},
        },
        "claims": {
            "claims_contact": {"label": "Claims Contact"},
            "claims_email": {"label": "Claims Email"},
        },
        "security": {
            "security_details": {"label": "Security Details", "type": "textarea"},
            "issue_date": {"label": "Issue Date", "type": "date"},
        },
    },
    "sections": [
        "DECLARATIONS", "INSURING CLAUSE", "BASIS OF COVER", "LIMIT OF INDEMNITY",
        "EXCESS", "TERRITORIAL LIMITS", "DEFINITIONS", "EXTENSIONS", "EXCLUSIONS",
        "CONDITIONS", "CLAIMS", "CHOICE OF LAW AND JURISDICTION", "SEVERAL LIABILITY CLAUSE", "SECURITY"
    ],
    "standard_clauses": ["several_liability", "english_jurisdiction", "claims_notification"],
}


# =============================================================================
# ALL TEMPLATES COLLECTION
# =============================================================================

INSURANCE_TEMPLATES = {
    "lloyds_mrc_slip": LLOYDS_MRC_SLIP,
    "lloyds_policy_wording": LLOYDS_POLICY_WORDING,
    "lloyds_cover_note": LLOYDS_COVER_NOTE,
    "certificate_of_insurance": CERTIFICATE_OF_INSURANCE,
    "marine_cargo": MARINE_CARGO,
    "professional_indemnity": PROFESSIONAL_INDEMNITY,
}


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def get_all_templates() -> List[Dict]:
    """Get summary of all available templates."""
    return [
        {
            "id": t["id"],
            "name": t["name"],
            "category": t["category"],
            "description": t["description"],
            "version": t.get("version", "1.0"),
            "tags": t.get("tags", []),
            "sections": t.get("sections", []),
            "is_system": t.get("is_system", True),
            "has_content_template": "content_template" in t,
        }
        for t in INSURANCE_TEMPLATES.values()
    ]


def get_template(template_id: str) -> Dict:
    """Get full template by ID."""
    return INSURANCE_TEMPLATES.get(template_id)


def get_template_content(template_id: str) -> str:
    """Get the content template for a given template ID."""
    template = INSURANCE_TEMPLATES.get(template_id)
    if template:
        return template.get("content_template", "")
    return ""


def get_standard_clause(clause_id: str) -> Dict:
    """Get a standard clause by ID."""
    return STANDARD_CLAUSES.get(clause_id)


def get_all_standard_clauses() -> Dict:
    """Get all standard clauses."""
    return STANDARD_CLAUSES


def get_templates_by_category(category: str) -> List[Dict]:
    """Get templates filtered by category."""
    return [t for t in INSURANCE_TEMPLATES.values() if t["category"] == category]


def auto_select_template(risk_category: str, document_type: str = None) -> str:
    """Auto-select appropriate template based on risk category and document type."""
    doc_type_lower = (document_type or "").lower()
    risk_lower = (risk_category or "").lower()

    # Direct document type mapping
    if "slip" in doc_type_lower or "mrc" in doc_type_lower:
        return "lloyds_mrc_slip"
    if "policy" in doc_type_lower or "wording" in doc_type_lower:
        return "lloyds_policy_wording"
    if "cover note" in doc_type_lower or "covernote" in doc_type_lower:
        return "lloyds_cover_note"
    if "certificate" in doc_type_lower:
        return "certificate_of_insurance"
    if "cargo" in doc_type_lower or "marine" in risk_lower:
        return "marine_cargo"
    if "professional" in risk_lower or "pi" in doc_type_lower or "e&o" in doc_type_lower:
        return "professional_indemnity"

    # Default to MRC slip for Lloyd's market
    return "lloyds_mrc_slip"


def render_template(template_id: str, data: Dict) -> str:
    """Render a template with the provided data."""
    import re
    template = INSURANCE_TEMPLATES.get(template_id)
    if not template or "content_template" not in template:
        return ""

    content = template["content_template"]

    # Replace placeholders with data
    for key, value in data.items():
        if value is not None:
            placeholder = "{" + key + "}"
            content = content.replace(placeholder, str(value))

    # Remove any remaining empty placeholders
    content = re.sub(r'\{[a-z_]+\}', '', content)

    return content


def get_template_field_count(template_id: str) -> int:
    """Get total number of fields in a template."""
    template = INSURANCE_TEMPLATES.get(template_id)
    if not template:
        return 0

    count = 0
    for section in template.get("fields", {}).values():
        if isinstance(section, dict):
            count += len(section)
    return count


def validate_template_data(template_id: str, data: Dict) -> Dict:
    """Validate data against template requirements."""
    template = INSURANCE_TEMPLATES.get(template_id)
    if not template:
        return {"valid": False, "errors": ["Template not found"]}

    errors = []

    for section_name, section_fields in template.get("fields", {}).items():
        if isinstance(section_fields, dict):
            for field_name, field_config in section_fields.items():
                if isinstance(field_config, dict):
                    if field_config.get("required"):
                        if field_name not in data or not data[field_name]:
                            errors.append(f"Required field missing: {field_config.get('label', field_name)}")

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "field_count": get_template_field_count(template_id),
        "filled_count": len([k for k, v in data.items() if v])
    }


# =============================================================================
# LLOYD'S COVER NOTE TEMPLATE
# =============================================================================

LLOYDS_COVER_NOTE = {
    "id": "lloyds_cover_note",
    "name": "Lloyd's Cover Note",
    "category": "lloyds",
    "description": "Temporary cover note confirming insurance pending policy issuance",
    "version": "1.0",
    "is_system": True,
    "tags": ["lloyds", "cover_note", "temporary", "confirmation"],
    "content_template": """
LLOYD'S COVER NOTE

Cover Note Number: {cover_note_number}
Date of Issue: {issue_date}
Valid Until: {valid_until}

================================================================================

This is to certify that insurance has been effected as follows:

================================================================================
INSURED
================================================================================

Name:       {insured_name}
Address:    {insured_address}

================================================================================
PERIOD OF INSURANCE
================================================================================

From:       {period_from}
To:         {period_to}
Both days inclusive, local standard time at the Insured's address.

================================================================================
INTEREST INSURED
================================================================================

{interest}

================================================================================
LIMIT OF LIABILITY
================================================================================

{limit_of_liability} {currency}

================================================================================
DEDUCTIBLE
================================================================================

{deductible} {currency} each and every loss

================================================================================
PREMIUM
================================================================================

{premium} {currency}
{premium_terms}

================================================================================
CONDITIONS
================================================================================

This Cover Note is issued subject to the terms, conditions, warranties and exclusions of Lloyd's standard policy form.

{special_conditions}

================================================================================
SUBJECTIVITIES
================================================================================

This insurance is subject to:

{subjectivities}

================================================================================
IMPORTANT NOTICE
================================================================================

This Cover Note is issued as evidence of insurance effected at Lloyd's and is for information purposes only. It does not amend, extend or alter the coverage afforded by the policy to which it refers.

The policy will be prepared and forwarded to the Insured in due course. In the event of any discrepancy between this Cover Note and the policy, the policy shall prevail.

================================================================================
SECURITY
================================================================================

Underwriters at Lloyd's, London
Lead: {lead_underwriter} ({lead_syndicate})
Line: {signed_line}%

================================================================================
BROKER
================================================================================

{broker_name}
{broker_address}

================================================================================

Issued at Lloyd's, London
Date: {issue_date}
""",
    "fields": {
        "cover_note": {
            "cover_note_number": {"label": "Cover Note Number", "required": True},
            "issue_date": {"label": "Issue Date", "required": True, "type": "date"},
            "valid_until": {"label": "Valid Until", "required": True, "type": "date"},
        },
        "insured": {
            "insured_name": {"label": "Insured Name", "required": True},
            "insured_address": {"label": "Insured Address", "required": True},
        },
        "coverage": {
            "period_from": {"label": "Period From", "required": True, "type": "date"},
            "period_to": {"label": "Period To", "required": True, "type": "date"},
            "interest": {"label": "Interest Insured", "required": True, "type": "textarea"},
            "limit_of_liability": {"label": "Limit of Liability", "required": True, "type": "currency"},
            "deductible": {"label": "Deductible", "type": "currency"},
            "currency": {"label": "Currency", "required": True, "options": ["GBP", "USD", "EUR"]},
            "premium": {"label": "Premium", "type": "currency"},
            "premium_terms": {"label": "Premium Terms"},
        },
        "conditions": {
            "special_conditions": {"label": "Special Conditions", "type": "textarea"},
            "subjectivities": {"label": "Subjectivities", "type": "list"},
        },
        "security": {
            "lead_underwriter": {"label": "Lead Underwriter", "required": True},
            "lead_syndicate": {"label": "Lead Syndicate"},
            "signed_line": {"label": "Signed Line %", "type": "percentage"},
        },
        "broker": {
            "broker_name": {"label": "Broker Name"},
            "broker_address": {"label": "Broker Address"},
        },
    },
    "sections": [
        "HEADER", "INSURED", "PERIOD OF INSURANCE", "INTEREST INSURED",
        "LIMIT OF LIABILITY", "DEDUCTIBLE", "PREMIUM", "CONDITIONS",
        "SUBJECTIVITIES", "IMPORTANT NOTICE", "SECURITY", "BROKER"
    ],
}


# =============================================================================
# CERTIFICATE OF INSURANCE TEMPLATE
# =============================================================================

CERTIFICATE_OF_INSURANCE = {
    "id": "certificate_of_insurance",
    "name": "Certificate of Insurance",
    "category": "commercial",
    "description": "Standard Certificate of Insurance providing evidence of coverage",
    "version": "2.0",
    "is_system": True,
    "tags": ["certificate", "proof", "commercial", "evidence"],
    "content_template": """
CERTIFICATE OF INSURANCE

Certificate Number: {certificate_number}
Date Issued: {issue_date}

================================================================================
THIS CERTIFICATE IS ISSUED AS A MATTER OF INFORMATION ONLY AND CONFERS NO RIGHTS
UPON THE CERTIFICATE HOLDER. THIS CERTIFICATE DOES NOT AMEND, EXTEND OR ALTER THE
COVERAGE AFFORDED BY THE POLICIES BELOW.
================================================================================

PRODUCER/BROKER
--------------------------------------------------------------------------------
{producer_name}
{producer_address}
Contact: {producer_contact}
Phone: {producer_phone}
Email: {producer_email}

INSURED
--------------------------------------------------------------------------------
{insured_name}
{insured_address}

================================================================================
COVERAGES
================================================================================

GENERAL LIABILITY                                    POLICY NUMBER: {gl_policy_number}
--------------------------------------------------------------------------------
Insurer: {gl_insurer}
Policy Period: {gl_effective_date} to {gl_expiration_date}

    Each Occurrence:                    {gl_each_occurrence}
    General Aggregate:                  {gl_general_aggregate}
    Products-Completed Ops Aggregate:   {gl_products_completed}
    Personal & Advertising Injury:      {gl_personal_adv_injury}

AUTOMOBILE LIABILITY                                 POLICY NUMBER: {auto_policy_number}
--------------------------------------------------------------------------------
Insurer: {auto_insurer}
Policy Period: {auto_effective_date} to {auto_expiration_date}

    Combined Single Limit:              {auto_combined_single}

UMBRELLA/EXCESS LIABILITY                            POLICY NUMBER: {umbrella_policy_number}
--------------------------------------------------------------------------------
Insurer: {umbrella_insurer}
Policy Period: {umbrella_effective_date} to {umbrella_expiration_date}

    Each Occurrence:                    {umbrella_each_occurrence}
    Aggregate:                          {umbrella_aggregate}

WORKERS COMPENSATION                                 POLICY NUMBER: {wc_policy_number}
--------------------------------------------------------------------------------
Insurer: {wc_insurer}
Policy Period: {wc_effective_date} to {wc_expiration_date}

    Statutory Limits
    E.L. Each Accident:                 {wc_el_each_accident}
    E.L. Disease - Policy Limit:        {wc_el_disease_policy}

================================================================================
DESCRIPTION OF OPERATIONS / LOCATIONS / VEHICLES
================================================================================

{description_of_operations}

================================================================================
CERTIFICATE HOLDER
================================================================================

{certificate_holder_name}
{certificate_holder_address}

Additional Insured: {additional_insured}
Waiver of Subrogation: {subrogation_waived}

================================================================================
CANCELLATION
================================================================================

Should any of the above described policies be cancelled before the expiration date
thereof, notice will be delivered in accordance with the policy provisions.

================================================================================

AUTHORIZED REPRESENTATIVE: _____________________

This certificate is issued by:
{issuer_name}
Date: {issue_date}
""",
    "fields": {
        "certificate": {
            "certificate_number": {"label": "Certificate Number", "required": True},
            "issue_date": {"label": "Date Issued", "required": True, "type": "date"},
        },
        "producer": {
            "producer_name": {"label": "Producer/Broker Name", "required": True},
            "producer_address": {"label": "Address", "required": True},
            "producer_contact": {"label": "Contact Name"},
            "producer_phone": {"label": "Phone"},
            "producer_email": {"label": "Email"},
        },
        "insured": {
            "insured_name": {"label": "Insured Name", "required": True},
            "insured_address": {"label": "Insured Address", "required": True},
        },
        "general_liability": {
            "gl_policy_number": {"label": "GL Policy Number"},
            "gl_insurer": {"label": "GL Insurer"},
            "gl_effective_date": {"label": "GL Effective Date", "type": "date"},
            "gl_expiration_date": {"label": "GL Expiration Date", "type": "date"},
            "gl_each_occurrence": {"label": "Each Occurrence", "type": "currency"},
            "gl_general_aggregate": {"label": "General Aggregate", "type": "currency"},
            "gl_products_completed": {"label": "Products-Comp/Op Agg", "type": "currency"},
            "gl_personal_adv_injury": {"label": "Personal & Adv Injury", "type": "currency"},
        },
        "certificate_holder": {
            "certificate_holder_name": {"label": "Certificate Holder Name"},
            "certificate_holder_address": {"label": "Certificate Holder Address"},
            "description_of_operations": {"label": "Description of Operations", "type": "textarea"},
            "additional_insured": {"label": "Additional Insured", "type": "boolean"},
            "subrogation_waived": {"label": "Waiver of Subrogation", "type": "boolean"},
        },
    },
    "sections": [
        "HEADER", "PRODUCER/BROKER", "INSURED", "GENERAL LIABILITY",
        "AUTOMOBILE LIABILITY", "UMBRELLA/EXCESS LIABILITY", "WORKERS COMPENSATION",
        "DESCRIPTION OF OPERATIONS", "CERTIFICATE HOLDER", "CANCELLATION"
    ],
}


# =============================================================================
# MARINE CARGO POLICY TEMPLATE (ICC 2009)
# =============================================================================

MARINE_CARGO = {
    "id": "marine_cargo",
    "name": "Marine Cargo Policy (ICC 2009)",
    "category": "marine",
    "description": "Marine cargo insurance based on Institute Cargo Clauses (A) 2009",
    "version": "2009",
    "is_system": True,
    "tags": ["marine", "cargo", "transit", "icc", "goods"],
    "content_template": """
MARINE CARGO POLICY

Policy Number: {policy_number}
Certificate Number: {certificate_number}

================================================================================
ASSURED
================================================================================

Name:       {assured_name}
Address:    {assured_address}
Interest:   {interest_type}

================================================================================
SUBJECT MATTER INSURED
================================================================================

{cargo_description}

Marks and Numbers: {marks_numbers}
Packing: {packing_type}

================================================================================
VOYAGE
================================================================================

From:       {from_location}
To:         {to_location}
Via:        {via_location}

Conveyance: {conveyance_type}
Vessel/Flight: {vessel_name}

================================================================================
AGREED VALUE / SUM INSURED
================================================================================

{sum_insured} {currency}
Basis of Valuation: {valuation_basis}

================================================================================
CONDITIONS
================================================================================

This insurance is subject to:

INSTITUTE CARGO CLAUSES (A) 2009

RISKS COVERED
This insurance covers all risks of loss of or damage to the subject-matter insured except as excluded by the provisions of Clauses 4, 5, 6 and 7 below.

GENERAL AVERAGE
This insurance covers general average and salvage charges, adjusted or determined according to the contract of carriage and/or the governing law and practice.

BOTH TO BLAME COLLISION CLAUSE
This insurance indemnifies the Assured against liability incurred under any Both to Blame Collision Clause in the contract of carriage.

================================================================================
EXCLUSIONS
================================================================================

4. GENERAL EXCLUSIONS
In no case shall this insurance cover:
4.1 loss damage or expense attributable to wilful misconduct of the Assured
4.2 ordinary leakage, ordinary loss in weight or volume, or ordinary wear and tear
4.3 loss damage or expense caused by insufficiency or unsuitability of packing
4.4 loss damage or expense caused by inherent vice or nature of the subject-matter
4.5 loss damage or expense caused by delay
4.6 loss damage or expense caused by insolvency of owners managers charterers
4.7 loss damage or expense caused by nuclear reaction radiation or contamination

================================================================================
DURATION
================================================================================

TRANSIT CLAUSE
This insurance attaches from the time the subject-matter insured is first moved in the warehouse for the purpose of immediate loading into the carrying conveyance, continues during the ordinary course of transit and terminates on completion of unloading at the final warehouse at the destination, or on expiry of 60 days after completion of discharge from the oversea vessel, whichever first occurs.

================================================================================
CLAIMS
================================================================================

INSURABLE INTEREST
In order to recover under this insurance the Assured must have an insurable interest in the subject-matter insured at the time of the loss.

FORWARDING CHARGES
Where the insured transit is terminated at a port or place other than the destination, the Insurers will reimburse the Assured for extra charges properly incurred in forwarding the subject-matter to the destination.

================================================================================
BENEFIT OF INSURANCE
================================================================================

This insurance shall not inure to the benefit of the carrier or other bailee.

================================================================================
MINIMISING LOSSES
================================================================================

It is the duty of the Assured and their agents to take such measures as may be reasonable for the purpose of averting or minimising loss, and to ensure that all rights against carriers and other third parties are properly preserved and exercised.

================================================================================
DEDUCTIBLE
================================================================================

{deductible} {currency}

================================================================================
PREMIUM
================================================================================

{premium} {currency}

================================================================================
LAW AND PRACTICE
================================================================================

This insurance is subject to English law and practice.

================================================================================
SECURITY
================================================================================

{security_details}

Certificate issued at Lloyd's, London
Date: {issue_date}
""",
    "fields": {
        "policy": {
            "policy_number": {"label": "Policy Number"},
            "certificate_number": {"label": "Certificate Number"},
        },
        "assured": {
            "assured_name": {"label": "Assured", "required": True},
            "assured_address": {"label": "Address", "required": True},
            "interest_type": {"label": "Interest", "options": ["Seller/Exporter", "Buyer/Importer", "Freight Forwarder", "Bank"]},
        },
        "cargo": {
            "cargo_description": {"label": "Description of Goods", "required": True, "type": "textarea"},
            "marks_numbers": {"label": "Marks & Numbers"},
            "packing_type": {"label": "Packing Type", "options": ["FCL", "LCL", "Breakbulk", "Bulk", "Containerized"]},
        },
        "voyage": {
            "from_location": {"label": "From", "required": True},
            "to_location": {"label": "To", "required": True},
            "via_location": {"label": "Via"},
            "conveyance_type": {"label": "Conveyance", "required": True, "options": ["Sea", "Air", "Road", "Rail", "Multi-Modal"]},
            "vessel_name": {"label": "Vessel/Flight Name"},
        },
        "values": {
            "sum_insured": {"label": "Sum Insured", "required": True, "type": "currency"},
            "currency": {"label": "Currency", "required": True, "options": ["GBP", "USD", "EUR"]},
            "valuation_basis": {"label": "Basis of Valuation", "options": ["CIF", "CIF+10%", "CIP", "FOB+10%", "Agreed Value"]},
        },
        "financials": {
            "deductible": {"label": "Deductible", "type": "currency"},
            "premium": {"label": "Premium", "type": "currency"},
        },
        "security": {
            "security_details": {"label": "Security Details", "type": "textarea"},
            "issue_date": {"label": "Issue Date", "type": "date"},
        },
    },
    "sections": [
        "ASSURED", "SUBJECT MATTER INSURED", "VOYAGE", "AGREED VALUE",
        "CONDITIONS", "EXCLUSIONS", "DURATION", "CLAIMS", "BENEFIT OF INSURANCE",
        "MINIMISING LOSSES", "DEDUCTIBLE", "PREMIUM", "LAW AND PRACTICE", "SECURITY"
    ],
    "standard_clauses": ["english_jurisdiction"],
}


# =============================================================================
# PROFESSIONAL INDEMNITY POLICY TEMPLATE
# =============================================================================

PROFESSIONAL_INDEMNITY = {
    "id": "professional_indemnity",
    "name": "Professional Indemnity Policy",
    "category": "specialty",
    "description": "Professional liability / Errors & Omissions insurance policy",
    "version": "2.0",
    "is_system": True,
    "tags": ["pi", "e&o", "professional", "liability", "claims-made"],
    "content_template": """
PROFESSIONAL INDEMNITY POLICY

Policy Number: {policy_number}
Unique Market Reference: {umr}

================================================================================
DECLARATIONS
================================================================================

Item 1.  Named Insured:           {firm_name}
Item 2.  Address:                 {firm_address}
Item 3.  Profession:              {profession}
Item 4.  Policy Period:           From {period_from} to {period_to}
Item 5.  Retroactive Date:        {retroactive_date}
Item 6.  Limit of Indemnity:      {limit_any_one_claim} {currency} any one claim
                                  {aggregate_limit} {currency} in the aggregate
Item 7.  Excess/Deductible:       {excess} {currency} each and every claim
Item 8.  Premium:                 {premium} {currency}

================================================================================
INSURING CLAUSE
================================================================================

The Underwriters agree to indemnify the Insured against:

(a) any civil liability incurred by the Insured arising out of any claim or claims first made against the Insured during the Policy Period and notified to the Underwriters during the Policy Period for breach of professional duty by reason of any negligent act, error or omission committed in the conduct of the Professional Business;

(b) all costs, fees and expenses incurred with the written consent of the Underwriters in the defence, investigation or settlement of any such claim.

================================================================================
BASIS OF COVER
================================================================================

This Policy is issued on a CLAIMS MADE BASIS. This means that the Policy covers only claims first made against the Insured and notified to the Underwriters during the Policy Period, provided always that any negligent act, error or omission giving rise to such claim occurred on or after the Retroactive Date stated in Item 5 of the Declarations.

================================================================================
LIMIT OF INDEMNITY
================================================================================

The liability of the Underwriters in respect of:

(a) any one claim including all Defence Costs relating thereto shall not exceed the Limit of Indemnity stated in Item 6 of the Declarations;

(b) all claims made during the Policy Period including all Defence Costs relating thereto shall not exceed the Aggregate Limit stated in Item 6 of the Declarations.

Defence Costs are {defence_costs_treatment}.

================================================================================
EXCESS
================================================================================

The Insured shall bear the first {excess} {currency} of each and every claim including Defence Costs.

================================================================================
TERRITORIAL LIMITS
================================================================================

This Policy applies to claims arising from Professional Services performed anywhere in {territorial_limits}.

================================================================================
DEFINITIONS
================================================================================

"Claim" means:
(a) any written demand for monetary or non-monetary relief;
(b) any civil proceeding commenced by service of a claim form or similar legal document;
(c) any arbitration or alternative dispute resolution proceeding.

"Defence Costs" means legal fees and expenses incurred in the investigation, defence, appeal or settlement of any Claim.

"Insured" means:
(a) the firm or company named in Item 1 of the Declarations;
(b) any principal, partner, member, director or employee of the Named Insured while acting within the scope of their duties.

"Professional Business" means the business of {profession} as conducted by the Insured.

================================================================================
EXTENSIONS
================================================================================

Subject to the Policy terms, conditions and exclusions, cover is extended to include:

1. LOSS OF DOCUMENTS
   Loss of or damage to documents in the Insured's custody or control up to {loss_of_documents_limit} {currency}.

2. DEFAMATION
   Claims arising from unintentional libel, slander or defamation in the conduct of the Professional Business.

3. COURT ATTENDANCE COSTS
   Costs of attendance at court by principals, partners or employees up to {court_attendance_rate} per day.

4. MITIGATION COSTS
   Reasonable costs incurred to avoid or mitigate a potential claim, subject to prior written consent.

================================================================================
EXCLUSIONS
================================================================================

This Policy does not cover any Claim:

1. PRIOR KNOWLEDGE
   arising from any fact or circumstance which the Insured knew before inception might give rise to a Claim;

2. PRIOR CLAIMS
   which has been notified under any previous policy;

3. DELIBERATE ACTS
   arising from any dishonest, fraudulent, criminal or malicious act of the Insured;

4. TRADING LOSSES
   for trading losses, debts or trading liabilities;

5. DIRECTORS & OFFICERS
   for breach of duty owed specifically as a director or officer;

6. BODILY INJURY / PROPERTY DAMAGE
   for bodily injury, sickness, disease, death or damage to tangible property;

7. EMPLOYMENT PRACTICES
   brought by or on behalf of any employee alleging wrongful dismissal, discrimination, or harassment.

================================================================================
CONDITIONS
================================================================================

1. CLAIMS NOTIFICATION
   The Insured shall give written notice to the Underwriters as soon as practicable of:
   (a) any Claim made against the Insured;
   (b) any circumstance which may give rise to a Claim.

2. CONDUCT OF CLAIMS
   The Insured shall not admit liability, make any payment, settle any Claim or incur any Defence Costs without the prior written consent of the Underwriters.

3. COOPERATION
   The Insured shall cooperate fully with the Underwriters and provide such information and documentation as the Underwriters may reasonably require.

4. SUBROGATION
   The Underwriters shall be subrogated to all rights of recovery of the Insured.

================================================================================
CLAIMS
================================================================================

All claims and circumstances should be notified to:
{claims_contact}
{claims_email}

================================================================================
CHOICE OF LAW AND JURISDICTION
================================================================================

This Policy shall be governed by and construed in accordance with the law of England and Wales.

================================================================================
SEVERAL LIABILITY CLAUSE
================================================================================

The liability of an insurer under this contract is several and not joint with other insurers party to this contract.

================================================================================
SECURITY
================================================================================

{security_details}

Issue Date: {issue_date}
""",
    "fields": {
        "declarations": {
            "policy_number": {"label": "Policy Number", "required": True},
            "umr": {"label": "UMR"},
            "firm_name": {"label": "Firm Name", "required": True},
            "firm_address": {"label": "Address", "required": True},
            "profession": {"label": "Profession", "required": True},
            "period_from": {"label": "Period From", "required": True, "type": "date"},
            "period_to": {"label": "Period To", "required": True, "type": "date"},
            "retroactive_date": {"label": "Retroactive Date", "type": "date"},
            "limit_any_one_claim": {"label": "Limit Any One Claim", "required": True, "type": "currency"},
            "aggregate_limit": {"label": "Aggregate Limit", "required": True, "type": "currency"},
            "excess": {"label": "Excess/Deductible", "required": True, "type": "currency"},
            "currency": {"label": "Currency", "required": True, "options": ["GBP", "USD", "EUR"]},
            "premium": {"label": "Premium", "required": True, "type": "currency"},
        },
        "coverage": {
            "defence_costs_treatment": {"label": "Defence Costs", "options": ["Inside Limit", "Outside Limit", "Supplementary"]},
            "territorial_limits": {"label": "Territorial Limits", "required": True},
        },
        "extensions": {
            "loss_of_documents_limit": {"label": "Loss of Documents Limit", "type": "currency"},
            "court_attendance_rate": {"label": "Court Attendance Rate", "type": "currency"},
        },
        "claims": {
            "claims_contact": {"label": "Claims Contact"},
            "claims_email": {"label": "Claims Email"},
        },
        "security": {
            "security_details": {"label": "Security Details", "type": "textarea"},
            "issue_date": {"label": "Issue Date", "type": "date"},
        },
    },
    "sections": [
        "DECLARATIONS", "INSURING CLAUSE", "BASIS OF COVER", "LIMIT OF INDEMNITY",
        "EXCESS", "TERRITORIAL LIMITS", "DEFINITIONS", "EXTENSIONS", "EXCLUSIONS",
        "CONDITIONS", "CLAIMS", "CHOICE OF LAW AND JURISDICTION",
        "SEVERAL LIABILITY CLAUSE", "SECURITY"
    ],
    "standard_clauses": ["several_liability", "english_jurisdiction", "claims_notification"],
}


# =============================================================================
# ALL TEMPLATES COLLECTION
# =============================================================================

INSURANCE_TEMPLATES = {
    "lloyds_mrc_slip": LLOYDS_MRC_SLIP,
    "lloyds_policy_wording": LLOYDS_POLICY_WORDING,
    "lloyds_cover_note": LLOYDS_COVER_NOTE,
    "certificate_of_insurance": CERTIFICATE_OF_INSURANCE,
    "marine_cargo": MARINE_CARGO,
    "professional_indemnity": PROFESSIONAL_INDEMNITY,
}


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def get_all_templates() -> List[Dict]:
    """Get summary of all available templates."""
    return [
        {
            "id": t["id"],
            "name": t["name"],
            "category": t["category"],
            "description": t["description"],
            "version": t.get("version", "1.0"),
            "tags": t.get("tags", []),
            "sections": t.get("sections", []),
            "is_system": t.get("is_system", True),
            "has_content_template": "content_template" in t,
        }
        for t in INSURANCE_TEMPLATES.values()
    ]


def get_template(template_id: str) -> Dict:
    """Get full template by ID."""
    return INSURANCE_TEMPLATES.get(template_id)


def get_template_content(template_id: str) -> str:
    """Get the content template for a given template ID."""
    template = INSURANCE_TEMPLATES.get(template_id)
    if template:
        return template.get("content_template", "")
    return ""


def get_standard_clause(clause_id: str) -> Dict:
    """Get a standard clause by ID."""
    return STANDARD_CLAUSES.get(clause_id)


def get_all_standard_clauses() -> Dict:
    """Get all standard clauses."""
    return STANDARD_CLAUSES


def get_templates_by_category(category: str) -> List[Dict]:
    """Get templates filtered by category."""
    return [t for t in INSURANCE_TEMPLATES.values() if t["category"] == category]


def auto_select_template(risk_category: str, document_type: str = None) -> str:
    """Auto-select appropriate template based on risk category and document type."""

    doc_type_lower = (document_type or "").lower()
    risk_lower = (risk_category or "").lower()

    if "slip" in doc_type_lower or "mrc" in doc_type_lower:
        return "lloyds_mrc_slip"
    if "policy" in doc_type_lower or "wording" in doc_type_lower:
        return "lloyds_policy_wording"
    if "cover note" in doc_type_lower or "covernote" in doc_type_lower:
        return "lloyds_cover_note"
    if "certificate" in doc_type_lower:
        return "certificate_of_insurance"
    if "cargo" in doc_type_lower or "marine" in risk_lower:
        return "marine_cargo"
    if "professional" in risk_lower or "pi" in doc_type_lower or "e&o" in doc_type_lower:
        return "professional_indemnity"

    return "lloyds_mrc_slip"


def render_template(template_id: str, data: Dict) -> str:
    """Render a template with the provided data."""
    template = INSURANCE_TEMPLATES.get(template_id)
    if not template or "content_template" not in template:
        return ""

    content = template["content_template"]

    for key, value in data.items():
        if value is not None:
            placeholder = "{" + key + "}"
            content = content.replace(placeholder, str(value))

    import re
    content = re.sub(r'\{[a-z_]+\}', '', content)

    return content


def get_template_field_count(template_id: str) -> int:
    """Get total number of fields in a template."""
    template = INSURANCE_TEMPLATES.get(template_id)
    if not template:
        return 0

    count = 0
    for section in template.get("fields", {}).values():
        if isinstance(section, dict):
            count += len(section)
    return count


def validate_template_data(template_id: str, data: Dict) -> Dict:
    """Validate data against template requirements."""
    template = INSURANCE_TEMPLATES.get(template_id)
    if not template:
        return {"valid": False, "errors": ["Template not found"]}

    errors = []

    for section_name, section_fields in template.get("fields", {}).items():
        if isinstance(section_fields, dict):
            for field_name, field_config in section_fields.items():
                if isinstance(field_config, dict):
                    if field_config.get("required"):
                        if field_name not in data or not data[field_name]:
                            errors.append(f"Required field missing: {field_config.get('label', field_name)}")

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "field_count": get_template_field_count(template_id),
        "filled_count": len([k for k, v in data.items() if v])
    }


# Alias for backwards compatibility
auto_select_templates = auto_select_template
