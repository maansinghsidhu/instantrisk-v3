"""
Lloyd's Market Document Content Library

This module contains the FULL text content for Lloyd's market standard insurance documents.
All clauses include real Lloyd's Market Association (LMA), Lloyd's Standard Wording (LSW),
and NMA clause references.

Document Types:
- Lloyd's MRC Slip Content
- Policy Wording Content
- Certificate of Insurance Content
- Endorsement Content
- Reinsurance Document Content

Author: InstantRisk Document Generation System
Version: 1.0
"""

from typing import Dict, List, Any
from datetime import datetime

# =============================================================================
# LLOYD'S STANDARD CLAUSES
# =============================================================================

# -----------------------------------------------------------------------------
# LMA5363 - Several Liability Clause (01/01/2022)
# -----------------------------------------------------------------------------
SEVERAL_LIABILITY_CLAUSE = '''
SEVERAL LIABILITY CLAUSE (LMA5363)

The liability of an insurer under this contract is several and not joint with other insurers
party to this contract. An insurer is liable only for the proportion of liability it has
underwritten. An insurer is not jointly liable for the proportion of liability underwritten
by any other insurer. Nor is an insurer otherwise responsible for any liability of any
other insurer that may underwrite this contract.

The proportion of liability under this contract underwritten by an insurer (or, in the case
of a Lloyd's syndicate, the total of the proportions underwritten by all the members of the
syndicate taken together) is shown in this contract.

In the case of a Lloyd's syndicate, each member of the syndicate (rather than the syndicate
itself) is an insurer. Each member has underwritten a proportion of the total shown for the
syndicate (that total itself being the total of the proportions underwritten by all the
members of the syndicate taken together). The liability of each member of the syndicate is
several and not joint with other members. A member is liable only for that member's
proportion. A member is not jointly liable for any other member's proportion. Nor is any
member otherwise responsible for any liability of any other insurer that may underwrite
this contract. The business address of each member is Lloyd's, One Lime Street,
London EC3M 7HA.

The proportion of liability under this contract underwritten by each member of a Lloyd's
syndicate (member's proportion) is determined by reference to the syndicate's stamp at the
time this contract is entered into by the syndicate.

Although reference is made at various points in this clause to "weights", "percentages" and
"proportions", any stamp may show a member's proportion in any one of these ways or in any
combination thereof. This clause shall be read as if each of these terms is used
interchangeably.

If the total of the proportions of all the members of a syndicate exceeds or falls short of
100%, the member's proportion shall be adjusted to ensure that the total is 100%.

IN WITNESS WHEREOF the Syndicate has caused this policy to be signed by its authorized
representative.
'''

# -----------------------------------------------------------------------------
# LSW1001 - Service of Suit Clause (USA)
# -----------------------------------------------------------------------------
SERVICE_OF_SUIT_CLAUSE_USA = '''
SERVICE OF SUIT CLAUSE (LSW1001)

It is agreed that in the event of the failure of Underwriters hereon to pay any amount
claimed to be due hereunder, Underwriters hereon, at the request of the Insured (or
Reinsured), will submit to the jurisdiction of a Court of competent jurisdiction within
the United States. Nothing in this Clause constitutes or should be understood to constitute
a waiver of Underwriters' rights to commence an action in any Court of competent
jurisdiction in the United States, to remove an action to a United States District Court,
or to seek a transfer of a case to another Court as permitted by the laws of the United
States or of any State in the United States.

It is further agreed that service of process in such suit may be made upon:

    Mendes and Mount
    750 Seventh Avenue
    New York, New York 10019-6829
    United States of America

or their successor in interest, who shall have authority to accept service of process on
behalf of Underwriters hereon, and who is directed at the request of Underwriters hereon to
give a written undertaking to the Insured (or Reinsured) that they will enter an
appearance on behalf of Underwriters hereon in the event such suit is instituted.

Further, pursuant to any statute of any state, territory, or district of the United States
which makes provision therefor, Underwriters hereon hereby designate the Superintendent,
Commissioner, or Director of Insurance, or other officer specified for that purpose in the
statute, or his or her successor or successors in office, as their true and lawful attorney
upon whom may be served any lawful process in any action, suit, or proceeding instituted by
or on behalf of the Insured (or Reinsured) or any beneficiary hereunder arising out of this
contract of insurance (or reinsurance), and hereby designate the above-named as the person
to whom the said officer is authorized to mail such process or a true copy thereof.
'''

# -----------------------------------------------------------------------------
# LSW1002 - Service of Suit Clause (UK and Europe)
# -----------------------------------------------------------------------------
SERVICE_OF_SUIT_CLAUSE_UK = '''
SERVICE OF SUIT CLAUSE (UK/EUROPE) (LSW1002)

The Insurers hereon agree that:

(a) If a dispute arises under this insurance, Insurers will at the request of the Insured
    submit to the exclusive jurisdiction of any competent Court in the relevant
    jurisdiction in which the Insured is located. Such dispute shall be determined in
    accordance with the law and practice applicable in that jurisdiction.

(b) Any summons, notice or process to be served upon Insurers for the purpose of
    instituting any legal proceedings against them in connection with this insurance
    may be served upon:

    Lloyd's Underwriters
    c/o Lloyd's Claims Office
    Gallery 1
    One Lime Street
    London EC3M 7HA
    England

    who have authority to accept service on behalf of Insurers and to enter an
    appearance on their behalf.

(c) If a suit is instituted against any one of them, Insurers will abide by the final
    decision of such Court or any competent Appellate Court.

PROVIDED that nothing in this Clause shall limit the right of the Insurers to bring
proceedings against the Insured in any Court of competent jurisdiction.
'''

# -----------------------------------------------------------------------------
# LMA3100 - Sanctions Limitation and Exclusion Clause
# -----------------------------------------------------------------------------
SANCTIONS_CLAUSE = '''
SANCTIONS LIMITATION AND EXCLUSION CLAUSE (LMA3100)

No (re)insurer shall be deemed to provide cover and no (re)insurer shall be liable to pay
any claim or provide any benefit hereunder to the extent that the provision of such cover,
payment of such claim or provision of such benefit would expose that (re)insurer to any
sanction, prohibition or restriction under United Nations resolutions or the trade or
economic sanctions, laws or regulations of the European Union, United Kingdom or United
States of America.

For the avoidance of doubt, this clause shall apply to, but is not limited to, any
sanctions, prohibitions, or restrictions that:

1. Prohibit or restrict dealing with any person, entity, or government;

2. Prohibit or restrict dealing in any goods, services, or technologies;

3. Prohibit or restrict any transaction or class of transactions;

4. Freeze assets of any person, entity, or government;

5. Prohibit making funds or economic resources available to any person, entity,
   or government.

This clause shall be paramount and shall override anything contained in this insurance
inconsistent therewith.
'''

# -----------------------------------------------------------------------------
# LSW559 / LMA9108 - Premium Payment Clause
# -----------------------------------------------------------------------------
PREMIUM_PAYMENT_CLAUSE = '''
PREMIUM PAYMENT CLAUSE (LSW559 / LMA9108)

Notwithstanding any provision to the contrary within this contract or any endorsement
hereto, the (Re)Insured undertakes that premium will be paid in full to (Re)Insurers
within sixty (60) days of inception of this contract (or, in respect of instalment
premiums, when due).

If the premium due under this contract has not been so paid to (Re)Insurers by the
sixtieth (60th) day from the inception of this contract (and, in respect of instalment
premiums, by the date they are due) (Re)Insurers shall have the right to cancel this
contract by notifying the (Re)Insured via the broker in writing. In the event of
cancellation, premium shall be due to (Re)Insurers on a pro rata basis for the period
that (Re)Insurers were on risk but the full contract minimum premium, if any, shall be
payable.

Unless otherwise agreed, the (Re)Insured shall not be entitled to make any deduction from
the premium(s) payable under this contract in respect of any claim(s) which (Re)Insurers
may pay or be called upon to pay hereunder.

It is agreed that (Re)Insurers shall give not less than fifteen (15) days prior written
notice of cancellation to the (Re)Insured via the broker. If premium due is paid in full
to (Re)Insurers before the notice period expires, notice of cancellation shall
automatically be revoked.

If any premium is payable in a currency other than the settlement currency, the rate of
exchange shall be that prevailing at the date of inception (or, in respect of instalment
premiums, the date each instalment is due).
'''

# -----------------------------------------------------------------------------
# Claims Cooperation Clause (LMA5106)
# -----------------------------------------------------------------------------
CLAIMS_COOPERATION_CLAUSE = '''
CLAIMS COOPERATION CLAUSE (LMA5106)

The Insured shall:

1. NOTIFICATION
   Give written notice to the Insurers as soon as practicable after the Insured becomes
   aware of:
   (a) any occurrence which may give rise to a claim under this insurance;
   (b) receipt of notice of any claim or intention to claim under this insurance;
   (c) any circumstances which may give rise to a claim under this insurance.

2. PARTICULARS
   Within such time as the Insurers may reasonably require, furnish to the Insurers:
   (a) full written particulars of any claim or occurrence;
   (b) all correspondence, documents, and information in connection with such claim
       or occurrence;
   (c) such proofs and information with respect to the claim as may reasonably be required.

3. COOPERATION
   (a) Cooperate fully with the Insurers, and upon the request of the Insurers, assist in:
       (i)   making settlements;
       (ii)  the conduct of proceedings;
       (iii) enforcing any right of contribution or indemnity against any third party;
       (iv)  the defence of any legal proceedings in respect of any such occurrence.

   (b) Not, except at the Insured's own cost, make any admission of liability, offer,
       promise or payment in connection with any occurrence without the prior written
       consent of the Insurers.

4. SUBROGATION
   (a) Take and permit to be taken all necessary steps for enforcing rights against any
       other party in the name of the Insured before or after any payment is made by
       the Insurers.

   (b) The Insurers shall be entitled to take over and conduct in the name of the Insured
       the defence or settlement of any claim for indemnity or damages or otherwise and
       shall have full discretion in the conduct of any such proceedings and in the
       settlement of any claim. The Insured shall give all such information and assistance
       as the Insurers may require.

5. PREJUDICE
   If the Insured fails to comply with any of the above conditions, the Insurers shall
   not be liable for any claim to the extent that such failure has prejudiced the
   handling or settlement of such claim.
'''

# -----------------------------------------------------------------------------
# Cancellation Clause (LMA5020)
# -----------------------------------------------------------------------------
CANCELLATION_CLAUSE = '''
CANCELLATION CLAUSE (LMA5020)

1. CANCELLATION BY THE INSURED
   The Insured may cancel this insurance by giving written notice to the Insurers.
   Cancellation shall take effect from the date specified in the notice or, if no date
   is specified, from the date of receipt of the notice by the Insurers.

   In the event of cancellation by the Insured:
   (a) If cancellation takes effect before inception, the full premium shall be returned.
   (b) If cancellation takes effect after inception, the Insurers shall retain premium
       calculated at the short period rates set out below:

       Period on Risk                    Percentage of Annual Premium
       Up to 1 month                     20%
       Up to 2 months                    30%
       Up to 3 months                    40%
       Up to 4 months                    50%
       Up to 5 months                    60%
       Up to 6 months                    70%
       Up to 7 months                    75%
       Up to 8 months                    80%
       Up to 9 months                    85%
       Up to 10 months                   90%
       Up to 11 months                   95%
       Over 11 months                    100%

2. CANCELLATION BY THE INSURERS
   The Insurers may cancel this insurance by giving thirty (30) days written notice to
   the Insured at the Insured's last known address. Such notice shall be deemed to have
   been received at the expiration of seven (7) days after posting.

   In the event of cancellation by the Insurers, the Insurers shall return the pro rata
   proportion of the premium for the unexpired period from the date of cancellation.

3. AUTOMATIC TERMINATION
   This insurance shall automatically terminate:
   (a) upon non-payment of premium in accordance with the Premium Payment Clause;
   (b) upon the Insured becoming bankrupt, insolvent, going into liquidation or having
       a receiver or administrator appointed.

4. EFFECT OF CANCELLATION
   Cancellation of this insurance shall not affect:
   (a) any claim arising from an occurrence prior to cancellation;
   (b) the rights and obligations of either party in respect of the period prior to
       cancellation.
'''

# -----------------------------------------------------------------------------
# Material Change Clause
# -----------------------------------------------------------------------------
MATERIAL_CHANGE_CLAUSE = '''
MATERIAL CHANGE CLAUSE

The Insured shall give immediate notice to the Insurers of any material change in the
risk insured including but not limited to:

1. Any change in the nature of the Insured's business or occupation;

2. Any change in the ownership, control, or management of the Insured;

3. Any increase in the values at risk or limits of liability required;

4. Any change in the location, construction, or occupancy of insured premises;

5. Any change to security arrangements or protective devices;

6. Any conviction of the Insured (or any director, partner, or employee) for any offence
   involving dishonesty or any other criminal offence;

7. Any other insurance being declined, cancelled, or made subject to special terms;

8. Any material change in circumstances which would affect the judgement of a prudent
   insurer in determining whether to accept the risk and if so on what terms.

Upon receipt of such notice the Insurers shall have the option to:

(a) Continue this insurance on the same terms;

(b) Continue this insurance subject to amended terms and/or additional premium;

(c) Cancel this insurance by giving thirty (30) days notice.

If the Insured fails to notify the Insurers of any material change, the Insurers shall
not be liable for any claim arising out of or in connection with such change and shall
have the right to avoid this insurance from the date of such change.
'''

# -----------------------------------------------------------------------------
# Jurisdiction Clause - English Law
# -----------------------------------------------------------------------------
JURISDICTION_CLAUSE_ENGLISH = '''
JURISDICTION CLAUSE (ENGLISH LAW AND PRACTICE)

This insurance shall be governed by and construed in accordance with the law of England
and Wales.

Each party agrees to submit to the exclusive jurisdiction of the Courts of England and
Wales in any dispute arising out of or in connection with this insurance.

The parties irrevocably agree:

1. That the Courts of England and Wales shall have exclusive jurisdiction to settle any
   dispute or claim (including non-contractual disputes or claims) arising out of or in
   connection with this insurance or its subject matter or formation;

2. That this insurance and any non-contractual obligations arising out of or in
   connection with it shall be governed by English law;

3. To waive any objection to the Courts of England and Wales on grounds of venue or on
   grounds that proceedings have been brought in an inconvenient forum.

SERVICE OF PROCESS

Any claim form, judgment, or other notice of legal process shall be sufficiently served
on the Insurers if delivered to:

    Lloyd's Underwriters General Representative in UK
    Lloyd's
    One Lime Street
    London EC3M 7HA
    United Kingdom

or any subsequent address of which notice has been given in accordance with this clause.
'''

# -----------------------------------------------------------------------------
# Arbitration Clause - London
# -----------------------------------------------------------------------------
ARBITRATION_CLAUSE_LONDON = '''
ARBITRATION CLAUSE (LONDON)

All matters in difference between the Insured and the Insurers in relation to this
insurance shall be referred to an Arbitration Tribunal in accordance with the provisions
of the Arbitration Act 1996 or any statutory modification or re-enactment thereof for
the time being in force.

The Arbitration Tribunal shall consist of three arbitrators, one to be appointed by
the Insurers, one by the Insured and the third by the two so chosen. If either party
fails to appoint its arbitrator within thirty (30) days of being requested in writing
to do so by the other party, or if the two arbitrators fail to agree on the third
arbitrator within thirty (30) days of their appointment, the arbitrator(s) shall be
appointed by the President for the time being of the Chartered Institute of Arbitrators
upon the application of either party.

The arbitrators shall be persons with not less than ten years' experience of insurance
or reinsurance within the London market.

The seat of the arbitration shall be London, England.

The arbitration shall be conducted in the English language.

The Arbitration Tribunal shall have power to make interim awards.

The determination of the Arbitration Tribunal shall be final and binding upon the
parties who covenant to carry out such determination and to honour any award the
Arbitration Tribunal may make.

Each party shall bear its own costs in connection with the arbitration and shall bear
an equal share of the costs of the Arbitration Tribunal unless the Tribunal orders
otherwise.

This clause shall survive the termination of this insurance.
'''

# -----------------------------------------------------------------------------
# War and Civil War Exclusion Clause (LSW556A)
# -----------------------------------------------------------------------------
WAR_EXCLUSION_CLAUSE = '''
WAR AND CIVIL WAR EXCLUSION CLAUSE (LSW556A)

This insurance excludes:

Loss, damage, cost or expense of whatsoever nature directly or indirectly caused by,
resulting from or in connection with any of the following regardless of any other
cause or event contributing concurrently or in any other sequence to the loss:

1. WAR RISKS
   (a) war, invasion, acts of foreign enemies, hostilities or warlike operations
       (whether war be declared or not), civil war, rebellion, revolution,
       insurrection, civil commotion assuming the proportions of or amounting to
       an uprising, military or usurped power;

   (b) strikes, riots, civil commotions;

   (c) any hostile act by or against a belligerent power;

   (d) capture, seizure, arrest, restraint, or detainment, and the consequences
       thereof or any attempt thereat;

   (e) derelict mines, torpedoes, bombs, or other derelict weapons of war.

2. TERRORISM
   Any act of terrorism being an act of any person acting on behalf of, or in
   connection with, any organisation which carries out activities directed towards
   the overthrowing or influencing, by force or violence, of any government whether
   or not legally constituted.

3. CONFISCATION
   Confiscation, nationalisation, requisition, preemption, or detention by or by
   order of any Government (whether civil, military or de facto) or Public or
   Local Authority.

4. BIOLOGICAL AND CHEMICAL
   Any chemical, biological, bio-chemical, or electromagnetic weapon.

5. NUCLEAR
   Any weapon employing atomic or nuclear fission and/or fusion or other like
   reaction or radioactive force or matter.
'''

# -----------------------------------------------------------------------------
# Nuclear Exclusion Clause (NMA1975a)
# -----------------------------------------------------------------------------
NUCLEAR_EXCLUSION_CLAUSE = '''
NUCLEAR EXCLUSION CLAUSE (NMA1975a)

This insurance does not cover any loss or liability accruing to the Insured as a
member of any association of Insurers or Reinsurers formed for the purpose of
covering nuclear energy risks or as a direct Insurer or Reinsurer of any such risks.

This Policy does not cover loss, damage, cost or expense directly or indirectly
caused by, contributed to by, resulting from, or arising out of or in connection
with:

1. NUCLEAR HAZARD
   (a) ionizing radiations from or contamination by radioactivity from any nuclear
       fuel or from any nuclear waste or from the combustion of nuclear fuel;

   (b) the radioactive, toxic, explosive, or other hazardous or contaminating
       properties of any nuclear installation, reactor, or other nuclear assembly
       or nuclear component thereof;

   (c) any weapon or device employing atomic or nuclear fission and/or fusion or
       other like reaction or radioactive force or matter;

   (d) the radioactive, toxic, explosive, or other hazardous or contaminating
       properties of any radioactive matter. The exclusion in this sub-clause does
       not extend to radioactive isotopes, other than nuclear fuel, when such
       isotopes are being prepared, carried, stored, or used for commercial,
       agricultural, medical, scientific, or other similar peaceful purposes.

2. NUCLEAR INSTALLATION
   For the purposes of this exclusion:

   (a) "Nuclear installation" means any nuclear reactor, any equipment or device
       designed or adapted for:
       (i)   producing or splitting atomic nuclei;
       (ii)  processing nuclear fuel;
       (iii) storing nuclear fuel (other than storage incidental to the carriage
             of such fuel);

   (b) "Nuclear fuel" means any substance which can be used for nuclear fission
       in a nuclear reactor or in a nuclear weapon.

This exclusion shall be paramount and shall override anything contained in this
Policy inconsistent therewith.
'''

# -----------------------------------------------------------------------------
# Terrorism Exclusion (NMA2918)
# -----------------------------------------------------------------------------
TERRORISM_EXCLUSION_CLAUSE = '''
TERRORISM EXCLUSION CLAUSE (NMA2918)

Notwithstanding any provision to the contrary within this insurance or any
endorsement thereto, this insurance excludes:

Any loss, damage, cost, or expense of whatsoever nature directly or indirectly
caused by, resulting from, or in connection with:

1. TERRORISM
   Any act of terrorism being an act, including but not limited to the use of
   force or violence and/or the threat thereof, of any person or group(s) of
   persons, whether acting alone or on behalf of or in connection with any
   organisation(s) or government(s), committed for political, religious,
   ideological, or ethnic purposes or reasons including the intention to
   influence any government and/or to put the public, or any section of the
   public, in fear.

2. ACTION IN CONTROLLING OR PREVENTING TERRORISM
   Any action taken in controlling, preventing, suppressing, or in any way
   relating to any act of terrorism.

3. CYBER TERRORISM
   Any act of terrorism involving the use of a computer system or network to
   destroy, damage, interfere with, sabotage, or deny service to:
   (a) any computer or computer system;
   (b) any computer network;
   (c) any data or software stored therein;
   (d) any physical property or infrastructure controlled thereby.

4. RADIOACTIVE CONTAMINATION
   Any loss, damage, cost, or expense directly or indirectly caused by,
   resulting from, or in connection with any act of terrorism involving the
   dispersal or application of pathogenic or poisonous biological or chemical
   materials, or any release, escape, or discharge of any nuclear emissions,
   radiations, ionizing radiations, or contamination by radioactivity.

If the Insurers allege that by reason of this exclusion any loss, damage, cost,
or expense is not covered by this insurance, the burden of proving the contrary
shall be upon the Insured.

In the event any portion of this exclusion is found to be invalid or
unenforceable, the remainder shall remain in full force and effect.
'''

# -----------------------------------------------------------------------------
# Cyber Attack Exclusion (LMA5400)
# -----------------------------------------------------------------------------
CYBER_EXCLUSION_CLAUSE = '''
CYBER ATTACK EXCLUSION CLAUSE (LMA5400)

1. Subject only to paragraph 3 below, this Policy excludes any loss, damage,
   liability, claim, cost, or expense of whatsoever nature directly or indirectly
   caused by, contributed to by, resulting from, arising out of, or in connection
   with any Cyber Act or Cyber Incident including, but not limited to, any action
   taken in controlling, preventing, suppressing, or remediating any Cyber Act or
   Cyber Incident.

2. DEFINITIONS

   (a) "Cyber Act" means an unauthorized, malicious, or criminal act or series of
       related unauthorized, malicious, or criminal acts, regardless of time and
       place, or the threat or hoax thereof involving access to, processing of,
       use of, or operation of, any Computer System.

   (b) "Cyber Incident" means:
       (i)   any error or omission or series of related errors or omissions
             involving access to, processing of, use of, or operation of, any
             Computer System;
       (ii)  any partial or total unavailability or failure or series of related
             partial or total unavailabilities or failures to access, process,
             use, or operate any Computer System.

   (c) "Computer System" means:
       (i)   any computer, hardware, software, communications system, electronic
             device (including, but not limited to, smart phone, laptop, tablet,
             wearable device), server, cloud or microcontroller including any
             similar system or any configuration of the aforementioned and
             including any associated input, output, data storage device,
             networking equipment, or back up facility;
       (ii)  data.

3. Subject to all other terms, conditions, exclusions, and limits of this Policy,
   if any portion of this exclusion is found to be invalid or unenforceable, the
   remainder shall remain in full force and effect. This exclusion shall not apply
   to the following coverages where expressly provided for within this Policy:

   (a) [List of applicable coverages to be inserted as required]

4. This exclusion shall apply regardless of any other cause or event contributing
   concurrently or in any other sequence to the loss.

5. This exclusion supersedes any previous Cyber Attack exclusion attached to this
   Policy.
'''

# -----------------------------------------------------------------------------
# Communicable Disease Exclusion (LMA5393)
# -----------------------------------------------------------------------------
COMMUNICABLE_DISEASE_EXCLUSION = '''
COMMUNICABLE DISEASE EXCLUSION CLAUSE (LMA5393)

This clause shall apply to any policy of insurance except as follows:

1. MARINE: Hull and cargo, including war risks and loss of hire
2. AVIATION: Hull and spares, including war risks
3. TRANSIT: Cargo in the course of transit

Notwithstanding any provision to the contrary within this policy, this policy
does not insure any loss, damage, liability, claim, cost, or expense of
whatsoever nature, caused by, contributed to by, resulting from, arising out of,
or in connection with:

A. COMMUNICABLE DISEASE

   (a) a Communicable Disease; or

   (b) the fear or threat (whether actual or perceived) of a Communicable Disease;

regardless of any other cause or event contributing concurrently or in any other
sequence thereto.

B. DEFINITIONS

   "Communicable Disease" means any disease which can be transmitted by means of
   any substance or agent from any organism to another organism where:

   (i)   the substance or agent includes, but is not limited to, a virus,
         bacterium, parasite, or other organism or any variation thereof, whether
         deemed living or not; and

   (ii)  the method of transmission, whether direct or indirect, includes but is
         not limited to, airborne transmission, bodily fluid transmission,
         transmission from or to any surface or object, solid, liquid or gas or
         between organisms; and

   (iii) the disease, substance, or agent can cause or threaten damage to human
         health or human welfare or can cause or threaten damage to, deterioration
         of, loss of value of, marketability of, or loss of use of property
         insured hereunder.

C. This clause shall not apply to:

   (a) any amount of insurance identified as "Communicable Disease Cover" in
       the Schedule;

   (b) any endorsement to this policy that specifically provides cover for
       Communicable Disease.

D. All other terms, conditions, insured coverage and exclusions of the policy
   shall remain the same.
'''


# =============================================================================
# LLOYD'S MRC SLIP FULL DOCUMENT CONTENT
# =============================================================================

MRC_SLIP_HEADER = '''
MARKET REFORM CONTRACT

LLOYD'S AND/OR COMPANY MARKET

This document is issued in accordance with the provisions of the Market Reform
Contract (MRC) and is evidence of the contract between the Insured (named below)
and the Insurers whose definitive numbers and the proportions underwritten by them
are set out in the Schedule attached hereto.

This contract is subject to the terms and conditions of the MRC Version 3.0 and
any subsequent amendments thereto as agreed between Lloyd's and the IUA.

================================================================================
'''

MRC_RISK_DETAILS_SECTION = '''
SECTION 1: RISK DETAILS
================================================================================

Unique Market Reference (UMR):     {umr}
Placing Broker Contract Ref:       {broker_reference}
Type of Business:                  {type_of_business}
Class of Business:                 {class_of_business}
Lloyd's Risk Code:                 {risk_code}
Placing Type:                      {placing_type}

This contract is placed in the London Market in accordance with the requirements
of the Market Reform Contract and the Lloyd's Market Association guidelines for
the placement of insurance business.

The risk details set out above are material to the contract and any change thereto
shall be notified to Insurers in accordance with the Material Change provisions
of this contract.
'''

MRC_ASSURED_SECTION = '''
SECTION 2: THE ASSURED
================================================================================

Named Insured:                     {insured_name}
Address:                           {insured_address}
Country of Domicile:               {insured_country}

Additional Insureds:
{additional_insureds}

The Insured includes:
(a) The Named Insured and any subsidiary or affiliated companies thereof existing
    at inception or created or acquired during the Policy Period;

(b) Any director, officer, partner, member, employee, or agent of the Named
    Insured, but only whilst acting within the scope of their duties as such;

(c) Any person or entity to whom the Insured is obligated by virtue of a written
    contract to provide insurance, but only to the extent of such obligation;

(d) The legal representatives of any Insured in the event of their death,
    incapacity, insolvency, or bankruptcy.

The coverage afforded to any additional insured is subject to all terms,
conditions, exclusions, and limitations of this contract.
'''

MRC_PERIOD_SECTION = '''
SECTION 3: PERIOD OF INSURANCE
================================================================================

Period From:                       {period_from}
Period To:                         {period_to}
Both days inclusive, Local Standard Time at the address of the Insured

Retroactive Date:                  {retroactive_date}

The Insurers shall not be liable for any claim arising from any act, error,
omission, or occurrence which took place prior to the Retroactive Date, or
any claim of which the Insured had knowledge prior to the inception of this
contract.

EXTENDED REPORTING PERIOD

In the event that this contract is cancelled or non-renewed other than for
non-payment of premium or fraud, the Insured shall have the right to purchase
an Extended Reporting Period of:

   (a) 12 months at an additional premium of 50% of the annual premium; or
   (b) 24 months at an additional premium of 100% of the annual premium; or
   (c) 36 months at an additional premium of 150% of the annual premium.

Such Extended Reporting Period shall apply only to claims arising from acts,
errors, omissions, or occurrences which took place during the Policy Period
but which are first reported during the Extended Reporting Period.
'''

MRC_INTEREST_SECTION = '''
SECTION 4: INTEREST / SUBJECT MATTER INSURED
================================================================================

{interest}

The interest insured hereunder includes but is not limited to:

(a) All property of the Insured or for which the Insured is responsible or has
    assumed responsibility under contract;

(b) Improvements and betterments made by the Insured to premises occupied but
    not owned by the Insured;

(c) Personal effects of directors, officers, partners, and employees of the
    Insured;

(d) Property of others in the care, custody, or control of the Insured;

(e) Newly acquired property, subject to the Newly Acquired Property provisions
    of this contract.

VALUATION

Unless otherwise stated, property is insured on a Replacement Cost basis,
meaning the cost of repair or replacement with materials of like kind and
quality without deduction for depreciation.

Business Interruption coverage is provided on an Actual Loss Sustained basis
subject to the Maximum Indemnity Period stated in the Schedule.
'''

MRC_TERRITORIAL_LIMITS_SECTION = '''
SECTION 5: TERRITORIAL LIMITS
================================================================================

Territorial Limits:                {territorial_limits}

This insurance applies to occurrences taking place anywhere within the
Territorial Limits stated above and to claims made anywhere in the world,
subject to the Jurisdiction provisions of this contract.

WORLDWIDE TRAVEL

Coverage is extended to include the Insured's directors, officers, partners,
and employees whilst travelling outside the Territorial Limits on the business
of the Insured, but:

(a) Not for any permanent operations outside the Territorial Limits;
(b) Not for any liability arising under any workers' compensation or similar
    statutory obligation;
(c) Subject to all other terms, conditions, and exclusions of this contract.
'''

MRC_BASIS_OF_COVER_SECTION = '''
SECTION 6: BASIS OF COVER
================================================================================

Basis of Cover:                    {basis}

CLAIMS MADE BASIS
Where indicated above, this insurance is written on a Claims Made basis which
means that this contract covers only those claims first made against the Insured
and reported to the Insurers during the Policy Period or any Extended Reporting
Period, regardless of when the act, error, omission, or occurrence giving rise
to the claim took place, subject always to the Retroactive Date.

OCCURRENCE BASIS
Where indicated above, this insurance is written on an Occurrence basis which
means that this contract covers claims arising from occurrences taking place
during the Policy Period, regardless of when the claim is made or reported,
subject always to the applicable statute of limitations.

LOSSES OCCURRING BASIS
Where indicated above, this insurance is written on a Losses Occurring basis
which means that this contract covers losses which occur during the Policy
Period, regardless of when the underlying event giving rise to the loss took
place.
'''

MRC_LIMITS_SECTION = '''
SECTION 7: LIMIT OF LIABILITY
================================================================================

Limit of Liability:                {currency} {limit_of_liability}
Any One Occurrence:                {currency} {any_one_occurrence}
Aggregate Limit:                   {currency} {aggregate_limit}

SUB-LIMITS OF LIABILITY

The following sub-limits apply and are part of and not in addition to the
Limit of Liability stated above:

{sub_limits}

AGGREGATE LIMIT

The Aggregate Limit stated above is the maximum amount the Insurers will pay
for all claims under this contract during the Policy Period. Once the Aggregate
Limit has been exhausted, the Insurers shall have no further liability under
this contract.

REINSTATEMENT

Unless otherwise stated, the Limit of Liability shall be reinstated following
the payment of a claim, subject to payment of the appropriate reinstatement
premium as follows:

   Reinstatement Premium = Original Premium x (Amount of Claim / Original Limit)

The maximum number of reinstatements available is [unlimited/one/two] unless
otherwise stated in the Schedule.

DEFENCE COSTS

Defence costs are [included within/in addition to] the Limit of Liability.
Where defence costs are included within the Limit of Liability, payment of
defence costs shall reduce the Limit of Liability available to pay claims.
'''

MRC_DEDUCTIBLE_SECTION = '''
SECTION 8: DEDUCTIBLE / EXCESS
================================================================================

Deductible:                        {currency} {deductible}
Inner Aggregate Deductible:        {currency} {inner_aggregate_deductible}

APPLICATION OF DEDUCTIBLE

The Deductible stated above shall apply to each and every claim and shall be
borne by the Insured. The Deductible shall apply to both indemnity payments
and defence costs unless otherwise stated.

INNER AGGREGATE DEDUCTIBLE

Where an Inner Aggregate Deductible (IAD) is shown, the Insured shall bear
the amount of each claim up to the per claim Deductible, and the aggregate
of all such amounts borne by the Insured during the Policy Period up to the
IAD amount. Thereafter, the Insurers shall pay claims in full without
application of the per claim Deductible.

NON-AGGREGATION OF DEDUCTIBLES

Where a claim arises from a single occurrence which gives rise to multiple
claims, only one Deductible shall apply to such occurrence.

DROP-DOWN PROVISION

In the event that underlying insurance is exhausted by the payment of claims,
this insurance shall continue to apply excess of the Deductible stated above,
subject to all other terms, conditions, and exclusions of this contract.
'''

MRC_PREMIUM_SECTION = '''
SECTION 9: PREMIUM
================================================================================

Premium:                           {currency} {premium_amount}
Rate:                              {rate}
Minimum & Deposit Premium:         {currency} {minimum_premium}
Deposit Premium:                   {currency} {deposit_premium}
Adjustable:                        {adjustable}

PREMIUM PAYMENT TERMS

Premium is payable in accordance with the Premium Payment Clause (LSW559/LMA9108)
attached hereto, within sixty (60) days of inception.

{installments}

ADJUSTABLE PREMIUM

Where this contract is written on an adjustable basis, the premium shall be
adjusted at the expiration of the Policy Period based on the actual values
declared or exposure experienced during the Policy Period.

The minimum premium payable shall be the Minimum & Deposit Premium stated above,
regardless of the actual adjustment calculation.

The deposit premium is payable at inception and represents {deposit_percentage}%
of the estimated annual premium.

PREMIUM ALLOCATION

For the purpose of premium allocation, the premium is deemed to be earned:
(a) Pro rata over the Policy Period for occurrence-based coverages;
(b) In full at inception for claims-made coverages.
'''

MRC_CONDITIONS_PRECEDENT_SECTION = '''
SECTION 10: CONDITIONS PRECEDENT TO LIABILITY
================================================================================

The following are Conditions Precedent to Liability under this contract:

1. PREMIUM PAYMENT
   The payment of premium in accordance with the Premium Payment Clause attached
   hereto is a condition precedent to the liability of Insurers.

2. SUBJECTIVITIES
   Compliance with the Subjectivities set out in Section 11 within the time
   specified therein is a condition precedent to the liability of Insurers.

3. WARRANTIES
   Compliance with the Warranties set out in Section 12 is a condition precedent
   to the liability of Insurers.

4. CLAIMS NOTIFICATION
   Compliance with the claims notification requirements set out in Section 15
   is a condition precedent to the liability of Insurers, but only to the
   extent that the Insurers have been prejudiced by any breach thereof.

5. DUTY OF FAIR PRESENTATION
   The Insured shall make a fair presentation of the risk to the Insurers in
   accordance with Section 3 of the Insurance Act 2015. A breach of this duty
   may entitle the Insurers to avoid the contract or to vary its terms.

EFFECT OF BREACH

In the event of any breach of a condition precedent:
(a) If the breach is remediable, the Insurers shall not be liable for any
    claim arising before the breach is remedied;
(b) If the breach is not remediable, the Insurers may avoid liability for
    any claim affected by the breach.
'''

MRC_SUBJECTIVITIES_SECTION = '''
SECTION 11: SUBJECTIVITIES
================================================================================

This insurance is subject to the following subjectivities which must be
satisfied within the time stated:

{subjectivities}

STANDARD SUBJECTIVITIES

Unless otherwise stated, the following standard subjectivities apply:

1. RECEIPT OF COMPLETED PROPOSAL FORM
   Receipt by Insurers of a completed and signed proposal form within 30 days
   of inception.

2. SURVEY
   Completion of a satisfactory survey of the insured premises within 60 days
   of inception (where applicable).

3. NO KNOWN LOSSES
   Confirmation that there are no known or reported losses or circumstances
   which may give rise to a claim as at the date of inception.

4. PRIOR CLAIMS HISTORY
   Receipt by Insurers of a full claims history for the previous 5 years
   within 30 days of inception.

EFFECT OF NON-COMPLIANCE

If any subjectivity is not satisfied within the time stated:
(a) Insurers may at their option avoid this contract from inception; or
(b) Insurers may elect to hold the Insured covered on amended terms and/or
    at an additional premium to be agreed.

Any election by Insurers under this clause must be communicated to the
Insured in writing within 14 days of the expiry of the relevant deadline.
'''

MRC_WARRANTIES_SECTION = '''
SECTION 12: WARRANTIES
================================================================================

The Insured warrants that:

{warranties}

STANDARD WARRANTIES

Unless otherwise stated, the following standard warranties apply:

1. PROTECTIVE DEVICES WARRANTY
   The Insured warrants that all fire protection, burglar alarm, and other
   protective devices installed at the insured premises shall be maintained
   in good working order at all times and shall be in operation during non-
   business hours.

2. MAINTENANCE WARRANTY
   The Insured warrants that all insured property shall be maintained in a
   good state of repair and in accordance with manufacturers' recommendations.

3. HOUSEKEEPING WARRANTY
   The Insured warrants that good housekeeping standards shall be maintained
   at all times, including the proper storage of combustible materials.

4. UNOCCUPANCY WARRANTY
   The Insured warrants that the insured premises shall not be left unoccupied
   for more than 30 consecutive days without prior written notification to
   the Insurers.

5. CONTRACTUAL LIABILITY WARRANTY
   The Insured warrants that no liability shall be assumed under contract
   which exceeds the liability that would have attached in the absence of
   such contract.

EFFECT OF BREACH

A breach of warranty shall suspend the Insurers' liability from the time of
the breach, and such liability shall remain suspended until the breach is
remedied (where capable of remedy). The Insurers shall have no liability for
any loss occurring, or attributable to something happening, during the period
of suspension.
'''

MRC_EXCLUSIONS_SECTION = '''
SECTION 13: EXCLUSIONS
================================================================================

This insurance does not cover:

{exclusions}

STANDARD EXCLUSIONS

Unless otherwise stated, the following standard exclusions apply:

1. WAR AND CIVIL WAR EXCLUSION (LSW556A)
   As per the War and Civil War Exclusion Clause attached hereto.

2. NUCLEAR EXCLUSION (NMA1975a)
   As per the Nuclear Exclusion Clause attached hereto.

3. TERRORISM EXCLUSION (NMA2918)
   As per the Terrorism Exclusion Clause attached hereto.

4. SANCTIONS EXCLUSION (LMA3100)
   As per the Sanctions Limitation and Exclusion Clause attached hereto.

5. CYBER EXCLUSION (LMA5400)
   As per the Cyber Attack Exclusion Clause attached hereto (where applicable).

6. COMMUNICABLE DISEASE EXCLUSION (LMA5393)
   As per the Communicable Disease Exclusion Clause attached hereto.

7. ASBESTOS EXCLUSION
   Any claim arising out of, relating to, or in any way connected with:
   (a) The mining, processing, manufacture, removal, disposal, or distribution
       of asbestos or products containing asbestos;
   (b) Exposure to asbestos or products containing asbestos.

8. POLLUTION AND CONTAMINATION EXCLUSION
   Any claim arising out of or relating to the discharge, dispersal, release,
   or escape of pollutants, contaminants, or irritants, unless such discharge
   is sudden, unintended, and unexpected.

9. MOULD AND FUNGUS EXCLUSION
   Any claim arising out of or relating to the presence, growth, proliferation,
   spread, or any activity of mould, mildew, fungi, spores, or other microorganisms.

10. PROFESSIONAL LIABILITY EXCLUSION
    Any claim arising out of the rendering or failure to render professional
    services (unless Professional Liability coverage is specifically included).

11. EMPLOYMENT PRACTICES EXCLUSION
    Any claim arising out of any actual or alleged wrongful dismissal,
    termination, harassment, discrimination, or violation of employment law
    (unless Employment Practices Liability coverage is specifically included).

12. INTENTIONAL ACTS EXCLUSION
    Any claim arising out of any dishonest, fraudulent, criminal, malicious,
    or intentional act or omission of the Insured.
'''

MRC_EXTENSIONS_SECTION = '''
SECTION 14: EXTENSIONS
================================================================================

The following extensions are included subject to all other terms, conditions,
and exclusions of this contract:

{extension_clauses}

STANDARD EXTENSIONS

Unless otherwise stated, the following standard extensions apply:

1. NEWLY ACQUIRED PROPERTY
   This insurance extends to cover property at locations acquired or occupied
   by the Insured during the Policy Period, subject to:
   (a) A sub-limit of 25% of the total sum insured or GBP 5,000,000 whichever
       is the lesser;
   (b) Notification to Insurers within 90 days of acquisition;
   (c) Payment of additional premium at pro rata rates.

2. DEBRIS REMOVAL
   This insurance extends to cover the reasonable costs of removing debris
   of insured property following a covered loss, subject to a sub-limit of
   25% of the claim amount or the sub-limit stated in the Schedule.

3. PROFESSIONAL FEES
   This insurance extends to cover reasonable architects', surveyors',
   engineers', and other professional fees necessarily incurred in the
   reinstatement of insured property following a covered loss.

4. EXPEDITING EXPENSES
   This insurance extends to cover the reasonable additional costs of
   expediting repairs to damaged property, including overtime and express
   delivery charges, subject to a sub-limit as stated in the Schedule.

5. AUTOMATIC INCREASE IN VALUES
   The sums insured under this contract shall automatically increase by
   10% to provide for inflation and increased stock during peak periods.

6. LOSS PREVENTION COSTS
   This insurance extends to cover reasonable costs incurred by the Insured
   to prevent or minimize an imminent covered loss.

7. FIRE BRIGADE CHARGES
   This insurance extends to cover fire brigade charges for which the
   Insured becomes legally liable.

8. LOCK REPLACEMENT
   This insurance extends to cover the cost of replacing locks following
   the theft or loss of keys to the insured premises.
'''

MRC_CLAIMS_CONDITIONS_SECTION = '''
SECTION 15: CLAIMS CONDITIONS
================================================================================

Claims Contact:                    {claims_contact}
Claims Notification Period:        {claims_notification}

CLAIMS NOTIFICATION

1. The Insured shall give written notice to the Insurers as soon as
   practicable after becoming aware of:
   (a) Any occurrence which may give rise to a claim under this insurance;
   (b) Receipt of notice of any claim or legal proceeding;
   (c) Any circumstance which may reasonably be expected to give rise to
       a claim under this insurance.

2. Notice shall be given to:
   Lloyd's Claims Office
   One Lime Street
   London EC3M 7HA
   Email: claims@lloyds.com

   With a copy to the placing broker.

CLAIMS PROCEDURE

3. Upon notification of a claim, the Insured shall:
   (a) Take all reasonable steps to mitigate the loss;
   (b) Preserve any damaged property for inspection;
   (c) Cooperate fully with Insurers and their appointed representatives;
   (d) Provide all documentation and information reasonably required;
   (e) Submit a sworn proof of loss if requested.

4. The Insured shall not admit liability, make any offer or payment, or
   incur any expense without the prior written consent of the Insurers,
   except for emergency measures to protect life or property.

CLAIMS SETTLEMENT

5. The Insurers shall have the right to:
   (a) Take over and conduct the defence or settlement of any claim;
   (b) Pursue recovery action in the name of the Insured;
   (c) Appoint loss adjusters, surveyors, or other experts.

6. Claims shall be payable within 30 days of:
   (a) Agreement of the claim amount; or
   (b) Receipt of a final court judgment or arbitration award.

7. Defence costs shall be paid as incurred, subject to the terms of this
   contract.

CLAIMS COOPERATION CLAUSE (LMA5106)

As per the Claims Cooperation Clause attached hereto.
'''

MRC_GENERAL_CONDITIONS_SECTION = '''
SECTION 16: GENERAL CONDITIONS
================================================================================

1. INSPECTION
   The Insurers shall have the right, but not the duty, to inspect the
   insured property and operations at any reasonable time. Such inspection
   shall not constitute an undertaking to identify all hazards or guarantee
   compliance with laws or regulations.

2. ASSIGNMENT
   This contract shall not be assigned without the prior written consent
   of the Insurers. Any purported assignment without such consent shall
   be void and of no effect.

3. WAIVER
   No waiver by the Insurers of any term, condition, or provision of this
   contract shall be effective unless in writing signed by an authorized
   representative of the Insurers. No such waiver shall constitute a
   continuing waiver or a waiver of any other breach.

4. MISREPRESENTATION
   If the Insured has made any misrepresentation or failed to disclose
   any material fact, the Insurers may avoid this contract in accordance
   with the remedies available under the Insurance Act 2015.

5. OTHER INSURANCE
   If at the time of any loss there is any other insurance covering the
   same loss, the Insurers shall not be liable for more than their
   rateable proportion of such loss.

6. SUBROGATION
   The Insurers shall be subrogated to all rights of recovery of the
   Insured against any third party. The Insured shall do nothing to
   prejudice such rights and shall cooperate fully with the Insurers
   in exercising such rights.

7. CURRENCY
   All amounts under this contract are expressed in the currency stated
   in the Schedule. Where amounts are payable in a different currency,
   conversion shall be at the rate prevailing on the date of loss or
   payment as applicable.

8. NOTICES
   All notices under this contract shall be in writing and shall be
   delivered personally, sent by recorded delivery, or sent by email
   to the addresses specified in the Schedule.

9. HEADINGS
   The headings in this contract are for convenience only and shall not
   affect the interpretation of this contract.

10. ENTIRE AGREEMENT
    This contract, together with the Schedule and any endorsements,
    constitutes the entire agreement between the parties.

11. CONTRACTS (RIGHTS OF THIRD PARTIES) ACT 1999
    A person who is not a party to this contract shall have no rights
    under the Contracts (Rights of Third Parties) Act 1999 to enforce
    any term of this contract, except where this contract expressly
    provides that such person may enforce such term.
'''

MRC_JURISDICTION_SECTION = '''
SECTION 17: JURISDICTION AND ARBITRATION
================================================================================

Jurisdiction:                      {jurisdiction}
Arbitration:                       {arbitration}

LAW AND JURISDICTION

This contract shall be governed by and construed in accordance with the law
specified above. The parties agree to submit to the exclusive jurisdiction
of the courts specified above in any dispute arising out of or in connection
with this contract.

ARBITRATION

Any dispute arising out of or in connection with this contract, including
any question regarding its existence, validity, or termination, shall be
referred to and finally resolved by arbitration in accordance with the
Arbitration Clause attached hereto.

CHOICE OF LAW

For the avoidance of doubt:
(a) English law shall apply to the interpretation of this contract;
(b) The Marine Insurance Act 1906 shall not apply to this contract unless
    specifically stated;
(c) The Insurance Act 2015 shall apply to this contract;
(d) The Consumer Insurance (Disclosure and Representations) Act 2012 shall
    not apply to this contract.
'''

MRC_SERVICE_OF_SUIT_SECTION = '''
SECTION 18: SERVICE OF SUIT
================================================================================

Service of Suit:                   {service_of_suit}

SERVICE OF SUIT CLAUSE

As per the Service of Suit Clause (LSW1001 or LSW1002 as applicable)
attached hereto.

For US domiciled risks, service of process may be made upon:
    Mendes and Mount
    750 Seventh Avenue
    New York, New York 10019-6829
    United States of America

For UK/European domiciled risks, service of process may be made upon:
    Lloyd's Underwriters
    c/o Lloyd's Claims Office
    One Lime Street
    London EC3M 7HA
    England
'''

MRC_SEVERAL_LIABILITY_SECTION = '''
SECTION 19: SEVERAL LIABILITY CLAUSE
================================================================================

SEVERAL LIABILITY CLAUSE (LMA5363)

As per the Several Liability Clause attached hereto.

The liability of each insurer is several and not joint with any other insurer.
An insurer is liable only for the proportion of liability it has underwritten.

In the case of a Lloyd's syndicate, each member of the syndicate is separately
and not jointly liable. The business address of each member is Lloyd's, One
Lime Street, London EC3M 7HA.
'''

MRC_SECURITY_SECTION = '''
SECTION 20: SECURITY
================================================================================

Lead Underwriter:                  {lead_underwriter}
Lead Syndicate:                    {lead_syndicate}
Lead Reference:                    {lead_reference}

PARTICIPATION

                                   Written Line    Signed Line    Order %
Lead:
{lead_syndicate}                   {written_line}%  {signed_line}%   {order_percentage}%

Following Markets:
{following_markets}

--------------------------------------------------------------------------------
TOTAL                              100.00%         100.00%        100.00%
--------------------------------------------------------------------------------

AGREEMENT BETWEEN INSURERS

The Lead Underwriter has authority to agree to the terms of this contract
on behalf of all participating insurers. The following matters require the
agreement of the Lead Underwriter only:

(a) Claims up to GBP 500,000 or 10% of the limit whichever is the lesser;
(b) Minor amendments to policy wording;
(c) Extensions and endorsements not affecting the overall exposure;
(d) Agreement of additional premium up to 25% of the original premium.

The following matters require the agreement of insurers representing not
less than two-thirds of the signed line:

(a) Claims in excess of GBP 500,000 or 10% of the limit;
(b) Major amendments to policy wording;
(c) Commutation or termination of the contract;
(d) Settlement of coverage disputes.

BUREAU ARRANGEMENTS

This contract is processed through the Lloyd's Bureau/Xchanging under the
following arrangements:
    Bureau Leader: {lead_syndicate}
    Bureau Signing Number: To be advised
    Settlement Currency: {currency}
'''


# =============================================================================
# POLICY WORDING FULL DOCUMENT CONTENT
# =============================================================================

POLICY_WORDING_HEADER = '''
================================================================================
                              POLICY OF INSURANCE
================================================================================

                              LLOYD'S OF LONDON

This Policy is issued on behalf of the Underwriters whose syndicate stamp numbers
and proportions are shown in the Schedule attached hereto.

Policy Number:                     {policy_number}
Unique Market Reference:           {umr}
Wording Reference:                 {wording_reference}
Effective Date:                    {effective_date}

================================================================================
'''

POLICY_DECLARATIONS_SECTION = '''
                               DECLARATIONS PAGE
================================================================================

ITEM 1.  NAMED INSURED AND ADDRESS

         Named Insured:            {named_insured}
         Address:                  {insured_address}

ITEM 2.  POLICY PERIOD

         From:                     {period_from}
         To:                       {period_to}
         (Both dates at 12:01 a.m. Local Standard Time at the Named Insured's address)

ITEM 3.  LIMITS OF LIABILITY

         Aggregate Limit:          {currency} {aggregate_limit}
         Each Occurrence/Claim:    {currency} {each_occurrence_limit}

         Sub-Limits:
         {sub_limits}

ITEM 4.  DEDUCTIBLES/RETENTIONS

         Each Occurrence/Claim:    {currency} {deductible}

ITEM 5.  PREMIUM

         Annual Premium:           {currency} {premium}
         Minimum Premium:          {currency} {minimum_premium}

ITEM 6.  RETROACTIVE DATE

         {retroactive_date}

ITEM 7.  NOTICE OF CLAIM ADDRESS

         Lloyd's Claims Office
         One Lime Street
         London EC3M 7HA
         United Kingdom
         Email: claims@lloyds.com

ITEM 8.  BROKER

         {broker_name}
         {broker_address}

ITEM 9.  FORMS AND ENDORSEMENTS

         The following forms and endorsements are attached to and form part of
         this Policy:

         {attached_endorsements}

================================================================================
'''

POLICY_INSURING_AGREEMENTS = '''
                             INSURING AGREEMENTS
================================================================================

COVERAGE A - PRIMARY INSURING AGREEMENT

The Insurers agree, subject to all the terms, conditions, limitations, and
exclusions of this Policy, to pay on behalf of the Insured all Loss which the
Insured becomes legally obligated to pay as a result of a Claim first made
against the Insured and reported to the Insurers during the Policy Period or
any Extended Reporting Period, arising from:

1. Any actual or alleged Wrongful Act committed by or on behalf of the Insured;

2. Any actual or alleged breach of duty, neglect, error, misstatement, misleading
   statement, omission, or other act committed by or on behalf of the Insured in
   the conduct of the Insured's business or profession;

3. Any matter claimed against the Insured solely by reason of the Insured's
   capacity as such.

COVERAGE B - DEFENCE COSTS

The Insurers agree, subject to all the terms, conditions, limitations, and
exclusions of this Policy, to pay on behalf of the Insured all Defence Costs
arising from any Claim covered under Coverage A.

Defence Costs are [included within / in addition to] the Limit of Liability.

COVERAGE C - SUPPLEMENTARY PAYMENTS

In addition to the Limit of Liability, the Insurers will pay:

1. All reasonable expenses incurred by the Insured at the Insurers' request to
   assist in the investigation or defence of any Claim, including loss of
   earnings up to GBP 500 per day;

2. All court costs taxed against the Insured in any Claim defended by the
   Insurers;

3. All interest accruing after entry of judgment and before the Insurers pay
   their portion of the judgment;

4. Premiums for appeal bonds and bonds to release attachments, but only for
   bond amounts within the applicable Limit of Liability.

TERRITORIAL SCOPE

This insurance applies to Claims arising from Wrongful Acts committed anywhere
in the world, provided that any legal proceedings are brought within the
Territorial Limits specified in the Declarations.
'''

POLICY_DEFINITIONS_SECTION = '''
                                DEFINITIONS
================================================================================

As used in this Policy:

1. "Claim" means:

   (a) A written demand for monetary damages or non-monetary relief;

   (b) A civil, criminal, administrative, or regulatory proceeding commenced
       by the service of a complaint, indictment, information, or similar
       document;

   (c) A formal investigation of the Insured commenced by the filing or issuance
       of a notice of charges, formal investigative order, or similar document;

   (d) A written request to toll or waive any statute of limitations applicable
       to any potential Claim against the Insured.

   Multiple Claims arising from the same Wrongful Act, or from a series of
   related Wrongful Acts, shall be treated as a single Claim first made at the
   time the earliest such Claim was made.

2. "Defence Costs" means:

   (a) Reasonable and necessary fees, costs, and expenses incurred by the
       Insured or by attorneys retained by or on behalf of the Insured, with
       the prior written consent of the Insurers, in the investigation,
       defence, or appeal of any Claim;

   (b) The cost of any appeal bond, but without any obligation to apply for
       or furnish any such bond;

   (c) Reasonable and necessary costs of experts, investigators, or other
       professionals retained by or on behalf of the Insured with the prior
       written consent of the Insurers.

   Defence Costs shall not include salaries, wages, overhead, or benefit
   expenses of the Insured.

3. "Insured" means:

   (a) The Named Insured and any Subsidiary;

   (b) Any past, present, or future director, officer, partner, member,
       trustee, or employee of the Named Insured or any Subsidiary, but
       only whilst acting within the scope of their duties as such;

   (c) Any natural person who was, is, or becomes during the Policy Period
       a director, officer, or equivalent of an Outside Entity, but only
       for Wrongful Acts in such capacity;

   (d) The lawful spouse or domestic partner of any natural person Insured,
       but only for Claims arising from such natural person's status as an
       Insured;

   (e) The estate, heirs, or legal representatives of any natural person
       Insured who is deceased, incompetent, insolvent, or bankrupt.

4. "Loss" means:

   (a) Damages, judgments, settlements, and pre-judgment and post-judgment
       interest;

   (b) Defence Costs;

   (c) Civil fines or penalties, but only to the extent insurable under
       applicable law.

   Loss shall not include:

   (i)   Taxes, fines, or penalties imposed by law (except as stated above);

   (ii)  Punitive or exemplary damages (except where insurable under applicable
         law);

   (iii) The multiplied portion of multiple damages;

   (iv)  Amounts for which the Insured is not financially liable or legally
         obligated to pay;

   (v)   Matters uninsurable under applicable law;

   (vi)  Any amount allocated to non-covered matters pursuant to the
         Allocation provisions.

5. "Policy Period" means:

   The period of time from the inception date to the expiration date set forth
   in the Declarations, or any earlier termination date.

6. "Pollutants" means:

   Any solid, liquid, gaseous, or thermal irritant or contaminant, including
   smoke, vapor, soot, fumes, acids, alkalis, chemicals, electromagnetic
   fields, noise, and waste. Waste includes materials to be recycled,
   reconditioned, or reclaimed.

7. "Retroactive Date" means:

   The date specified in Item 6 of the Declarations. The Insurers shall not be
   liable for any Claim arising from any Wrongful Act committed before such date.

8. "Subsidiary" means:

   (a) Any entity which, on or before the inception date of this Policy, the
       Named Insured owns, directly or indirectly, more than 50% of the issued
       and outstanding voting securities;

   (b) Any entity which becomes a Subsidiary during the Policy Period, provided
       that:
       (i)   The entity's total assets do not exceed 25% of the total consolidated
             assets of the Named Insured; and
       (ii)  The Named Insured gives written notice to the Insurers within
             90 days of acquisition.

9. "Wrongful Act" means:

   (a) Any actual or alleged breach of duty, neglect, error, misstatement,
       misleading statement, omission, breach of fiduciary duty, breach of
       trust, or other act committed or allegedly committed by an Insured in
       the discharge of their duties;

   (b) Any matter claimed against an Insured solely by reason of their status
       as an Insured.
'''

POLICY_EXCLUSIONS_SECTION = '''
                                EXCLUSIONS
================================================================================

This insurance does not cover any Loss arising from or in connection with:

1. PRIOR KNOWLEDGE

   Any Claim based upon, arising from, or attributable to any Wrongful Act
   which, before the inception date of this Policy:

   (a) Has been the subject of any notice given under any other policy;

   (b) Any Insured knew or could reasonably have foreseen might result in a
       Claim;

   (c) Any Insured knew to be a breach of duty, breach of contract, or
       wrongful act.

2. PRIOR CLAIMS AND LITIGATION

   Any Claim based upon, arising from, or attributable to:

   (a) Any litigation, arbitration, or administrative proceeding pending on
       or before the inception date of this Policy;

   (b) Any demand, suit, claim, investigation, or proceeding made or commenced
       against any Insured on or before the inception date of this Policy.

3. BODILY INJURY AND PROPERTY DAMAGE

   Any Claim for bodily injury, sickness, disease, death, emotional distress,
   or damage to or destruction of any tangible property, including loss of use
   thereof.

   This exclusion shall not apply to Defence Costs arising from such Claims.

4. POLLUTION

   Any Claim based upon, arising from, or attributable to the actual, alleged,
   or threatened discharge, dispersal, seepage, migration, release, or escape
   of Pollutants.

5. NUCLEAR HAZARD

   Any Claim based upon, arising from, or attributable to nuclear reaction,
   nuclear radiation, or radioactive contamination, however caused.

6. WAR AND TERRORISM

   Any Claim based upon, arising from, or attributable to:

   (a) War, invasion, acts of foreign enemies, hostilities, civil war,
       rebellion, revolution, insurrection, military or usurped power,
       or confiscation, nationalization, or requisition by any government;

   (b) Any act of terrorism, regardless of any other cause or event
       contributing concurrently or in any other sequence to the loss.

7. INTENTIONAL ACTS

   Any Claim based upon, arising from, or attributable to any:

   (a) Dishonest, fraudulent, criminal, or malicious act or omission;

   (b) Deliberate breach of contract;

   (c) Wilful violation of any statute, regulation, or law;

   committed by or at the direction of any Insured with actual knowledge of
   its wrongful nature.

   This exclusion shall only apply if such conduct has been established by
   a final, non-appealable adjudication.

8. EMPLOYMENT PRACTICES

   Any Claim brought by or on behalf of any employee, former employee, or
   applicant for employment with any Insured, based upon, arising from, or
   attributable to:

   (a) Wrongful dismissal, discharge, or termination;

   (b) Harassment, discrimination, or retaliation;

   (c) Employment-related defamation, invasion of privacy, or infliction of
       emotional distress;

   (d) Any violation of employment or labor law.

   This exclusion shall not apply if Employment Practices Liability coverage
   is specifically provided by endorsement.

9. PROFESSIONAL SERVICES

   Any Claim based upon, arising from, or attributable to the rendering of or
   failure to render professional services for others for a fee.

   This exclusion shall not apply if Professional Liability coverage is
   specifically provided by endorsement.

10. INSURED VERSUS INSURED

    Any Claim brought or maintained by or on behalf of:

    (a) Any Insured against any other Insured;

    (b) Any security holder of the Named Insured (unless such Claim is instigated
        and continued totally independent of any Insured).

11. CONTRACTUAL LIABILITY

    Any Claim based upon, arising from, or attributable to any liability assumed
    by any Insured under any contract or agreement, except to the extent the
    Insured would have been liable in the absence of such contract or agreement.

12. MAJOR SHAREHOLDER

    Any Claim brought or maintained by or on behalf of any person or entity that
    owns or controls more than 15% of the voting securities of the Named Insured.
'''

POLICY_CONDITIONS_SECTION = '''
                                CONDITIONS
================================================================================

1. NOTICE OF CLAIM

   The Insured shall give written notice to the Insurers as soon as practicable
   after any Insured first becomes aware of:

   (a) Any Claim made against an Insured;

   (b) Any circumstances which may reasonably be expected to give rise to a
       Claim against an Insured.

   Such notice shall include:
   (i)   The identity of the claimant;
   (ii)  The nature of the alleged Wrongful Act;
   (iii) The nature of the alleged injury or damage;
   (iv)  The date and manner in which the Insured first became aware of the
         Claim or circumstances;
   (v)   The names of any actual or potential claimants;
   (vi)  Details of the relief or damages sought or anticipated.

2. DEFENCE AND SETTLEMENT

   (a) The Insurers shall have the right and duty to defend any Claim covered
       hereunder, even if any of the allegations are groundless, false, or
       fraudulent.

   (b) The Insured shall not admit liability, make any payment, assume any
       obligation, or incur any expense without the prior written consent
       of the Insurers.

   (c) The Insurers shall not settle any Claim without the written consent of
       the Insured. If the Insured refuses to consent to a settlement
       recommended by the Insurers and acceptable to the claimant, the
       Insurers' liability shall not exceed:
       (i)   The amount for which the Claim could have been settled, plus
       (ii)  Defence Costs incurred up to the date of refusal.

   (d) The Insured shall cooperate with the Insurers in the defence of any
       Claim, including providing all relevant documents and information.

3. ALLOCATION

   If both covered and non-covered matters are involved in any Claim, the
   Insured and Insurers shall use their best efforts to agree upon a fair and
   proper allocation of Loss between covered and non-covered matters, taking
   into account the relative legal and financial exposures attributable to
   each.

   If the parties cannot agree on an allocation, the matter shall be submitted
   to binding arbitration.

4. SUBROGATION

   In the event of any payment under this Policy, the Insurers shall be
   subrogated to all of the Insured's rights of recovery. The Insured shall
   execute all documents and do all things necessary to secure such rights.

   The Insurers shall not exercise any right of subrogation against any
   natural person Insured unless such Insured has been found by a final,
   non-appealable adjudication to have committed a dishonest, fraudulent,
   criminal, or malicious act.

5. OTHER INSURANCE

   This insurance shall be excess of any other valid and collectible insurance
   available to the Insured, except for insurance specifically written to be
   excess of this Policy.

6. CANCELLATION

   (a) The Named Insured may cancel this Policy by giving written notice to
       the Insurers stating when such cancellation shall be effective.

   (b) The Insurers may cancel this Policy only for non-payment of premium,
       by giving at least thirty (30) days written notice to the Named Insured.

   (c) If the Policy is cancelled, the Insurers shall retain premium calculated
       on a short-rate basis if cancelled by the Insured, or on a pro rata
       basis if cancelled by the Insurers.

7. ENTIRE AGREEMENT

   This Policy, including the Declarations, forms, and endorsements attached
   hereto, embodies all agreements between the Insured and the Insurers
   relating to this insurance.

8. REPRESENTATIONS

   By accepting this Policy, the Insured agrees that the statements in the
   application are the Insured's representations, that this Policy is issued
   in reliance upon the truth of such representations, and that this Policy
   embodies all agreements between the Insured and the Insurers.

9. AUTHORIZATION

   The Named Insured is authorized to act on behalf of all Insureds with
   respect to:
   (a) Giving and receiving notice of Claim or cancellation;
   (b) Receiving any return premium;
   (c) Accepting any endorsements;
   (d) Agreeing to the settlement of any Claim.
'''

POLICY_CLAIMS_SECTION = '''
                              CLAIMS PROVISIONS
================================================================================

1. CLAIMS NOTIFICATION

   All Claims and circumstances that may give rise to Claims shall be reported
   in writing to:

   Lloyd's Claims Office
   One Lime Street
   London EC3M 7HA
   United Kingdom

   Email: claims@lloyds.com
   Telephone: +44 (0)20 7327 1000

   With a copy to the placing broker shown in the Declarations.

2. CLAIM MADE AND REPORTED

   This Policy covers only those Claims that are:

   (a) First made against an Insured during the Policy Period or any Extended
       Reporting Period; and

   (b) Reported to the Insurers in writing during the Policy Period or within
       sixty (60) days thereafter.

3. CIRCUMSTANCES

   If, during the Policy Period, any Insured becomes aware of circumstances
   which may reasonably be expected to give rise to a Claim and gives written
   notice to the Insurers of:

   (a) The specific circumstances;
   (b) The reasons for anticipating such Claim;
   (c) Full particulars of the dates, acts, and persons involved;

   then any Claim subsequently arising from such circumstances shall be deemed
   to have been first made at the time such notice was given.

4. RELATED CLAIMS

   All Claims arising from the same Wrongful Act or from a series of related,
   continuous, or repeated Wrongful Acts shall be treated as a single Claim
   first made at the time the earliest such Claim was first made or the
   earliest such circumstances were first notified.

5. EXTENDED REPORTING PERIOD

   If this Policy is cancelled or non-renewed for any reason other than non-
   payment of premium or fraud:

   (a) The Insured shall have the right to an automatic Basic Extended Reporting
       Period of sixty (60) days following the effective date of cancellation
       or non-renewal, at no additional premium;

   (b) The Insured shall have the right to purchase an Optional Extended
       Reporting Period of twelve (12), twenty-four (24), or thirty-six (36)
       months at the following additional premiums:
       - 12 months: 50% of the annual premium
       - 24 months: 100% of the annual premium
       - 36 months: 150% of the annual premium

   The Extended Reporting Period shall apply only to Claims arising from
   Wrongful Acts committed before the effective date of cancellation or
   non-renewal and after the Retroactive Date.

6. LOSS PAYABLE

   Claims shall be payable within thirty (30) days of:

   (a) The Insurers' receipt of all necessary documentation supporting the
       Claim; and

   (b) Agreement between the Insurers and the Insured on the amount of Loss,
       or entry of a final, non-appealable judgment or arbitration award.
'''

SUBROGATION_CLAUSE = '''
SUBROGATION CLAUSE

The Insurers shall be subrogated to all the Insured's rights of recovery
therefor against any person or organization, and the Insured shall execute
and deliver instruments and papers and do whatever else is necessary to
secure such rights. The Insured shall do nothing after loss to prejudice
such rights.

In the event of any payment under this Policy, the Insurers shall be
subrogated to all of the Insured's rights of recovery against any person
or organization. The Insured shall:

(a) Execute and deliver all documents and instruments and do all things
    necessary to secure such rights;

(b) Do nothing after knowledge of a loss that would impair such rights;

(c) Cooperate with the Insurers in any recovery action.

The Insurers' right of subrogation shall be subject to the following:

1. The Insurers shall not pursue any subrogation recovery against any
   employee of the Insured unless such employee has been found guilty of
   dishonesty or fraud by a court of competent jurisdiction;

2. The Insurers shall not exercise any right of subrogation that would
   violate any agreement between the Insured and a third party made prior
   to the occurrence of a loss;

3. The net amount of any recovery shall be applied first to the amount of
   the Deductible borne by the Insured, and the balance to reimburse the
   Insurers for their payments under this Policy.
'''


# =============================================================================
# CERTIFICATE OF INSURANCE CONTENT
# =============================================================================

CERTIFICATE_HEADER = '''
================================================================================
                         CERTIFICATE OF INSURANCE
================================================================================

                    THIS CERTIFICATE IS ISSUED AS A MATTER OF
                     INFORMATION ONLY AND CONFERS NO RIGHTS
                            UPON THE CERTIFICATE HOLDER

This Certificate does not amend, extend, or alter the coverage afforded by
the policies described herein. This Certificate does not constitute a contract
between the issuing insurer(s), authorized representative or producer, and
the Certificate Holder.

IMPORTANT: If the Certificate Holder is an ADDITIONAL INSURED, the policy(ies)
must be endorsed. A statement on this Certificate does not confer rights to
the Certificate Holder in lieu of such endorsement(s).

================================================================================

Certificate Number:                {certificate_number}
Date Issued:                       {issue_date}

================================================================================
'''

CERTIFICATE_PRODUCER_SECTION = '''
PRODUCER                                   CONTACT INFORMATION
--------------------------------------------------------------------------------

{producer}                                 Contact: {producer_contact}
                                          Phone:   {producer_phone}
                                          Email:   {producer_email}
'''

CERTIFICATE_INSURED_SECTION = '''
INSURED
--------------------------------------------------------------------------------

{insured_name}
{insured_address}
'''

CERTIFICATE_INSURERS_SECTION = '''
INSURERS AFFORDING COVERAGE                                      NAIC #
--------------------------------------------------------------------------------

INSURER A: {insurer_a}                                          {insurer_a_naic}
INSURER B: {insurer_b}                                          {insurer_b_naic}
INSURER C: {insurer_c}                                          {insurer_c_naic}
INSURER D: {insurer_d}                                          {insurer_d_naic}
INSURER E: {insurer_e}                                          {insurer_e_naic}
'''

CERTIFICATE_COVERAGES_SECTION = '''
COVERAGES
================================================================================

THIS IS TO CERTIFY THAT THE POLICIES OF INSURANCE LISTED BELOW HAVE BEEN ISSUED
TO THE INSURED NAMED ABOVE FOR THE POLICY PERIOD INDICATED. NOTWITHSTANDING ANY
REQUIREMENT, TERM OR CONDITION OF ANY CONTRACT OR OTHER DOCUMENT WITH RESPECT TO
WHICH THIS CERTIFICATE MAY BE ISSUED OR MAY PERTAIN, THE INSURANCE AFFORDED BY
THE POLICIES DESCRIBED HEREIN IS SUBJECT TO ALL THE TERMS, EXCLUSIONS AND
CONDITIONS OF SUCH POLICIES. LIMITS SHOWN MAY HAVE BEEN REDUCED BY PAID CLAIMS.

--------------------------------------------------------------------------------
TYPE OF INSURANCE    INSURER  POLICY NUMBER   EFFECTIVE   EXPIRATION    LIMITS
                     LTR                       DATE        DATE
--------------------------------------------------------------------------------

COMMERCIAL GENERAL LIABILITY
[ ] Claims Made  [ ] Occur
                     {gl_insurer}  {gl_policy}    {gl_eff}    {gl_exp}

[ ] General Aggregate Limit Applies Per:                Each Occurrence      {gl_occurrence}
    [ ] Policy  [ ] Project  [ ] Location              Damage to Rented
                                                        Premises             {gl_premises}
[ ] Additional Insured                                  Med Exp (Any 1 person) {gl_med_exp}
[ ] Waiver of Subrogation                              Personal & Adv Injury {gl_personal}
                                                        General Aggregate    {gl_aggregate}
                                                        Products-Comp/Op Agg {gl_products}

--------------------------------------------------------------------------------

AUTOMOBILE LIABILITY
[ ] Any Auto                                           Combined Single Limit {auto_csl}
[ ] All Owned Autos  {auto_insurer} {auto_policy} {auto_eff} {auto_exp}
[ ] Scheduled Autos                                    Bodily Injury
[ ] Hired Autos                                         (Per Person)         {auto_bi_person}
[ ] Non-Owned Autos                                    Bodily Injury
                                                        (Per Accident)       {auto_bi_accident}
[ ] Waiver of Subrogation                              Property Damage       {auto_pd}

--------------------------------------------------------------------------------

UMBRELLA/EXCESS LIABILITY
[ ] Umbrella  [ ] Excess                               Each Occurrence      {umbrella_occurrence}
[ ] Claims Made  [ ] Occur                             Aggregate            {umbrella_aggregate}
                     {umbrella_insurer} {umbrella_policy} {umbrella_eff} {umbrella_exp}
[ ] Retention/Deductible                               Retention            {umbrella_retention}

--------------------------------------------------------------------------------

WORKERS COMPENSATION AND EMPLOYERS' LIABILITY
[ ] ANY PROPRIETOR/PARTNER/                            WC Statutory Limits  {wc_statutory}
    EXECUTIVE OFFICER/MEMBER
    EXCLUDED?                                          E.L. Each Accident   {wc_el_accident}
[ ] N/A                                                E.L. Disease -
                     {wc_insurer} {wc_policy} {wc_eff} {wc_exp}   Each Employee       {wc_el_disease_ee}
                                                       E.L. Disease -
[ ] Waiver of Subrogation                               Policy Limit        {wc_el_disease_policy}

--------------------------------------------------------------------------------

PROFESSIONAL LIABILITY / ERRORS & OMISSIONS
[ ] Claims Made  [ ] Occur
                     {pl_insurer} {pl_policy} {pl_eff} {pl_exp}
                                                       Each Claim           {pl_each_claim}
[ ] Retroactive Date: {pl_retro}                       Aggregate            {pl_aggregate}

--------------------------------------------------------------------------------
'''

CERTIFICATE_DESCRIPTION_SECTION = '''
DESCRIPTION OF OPERATIONS / LOCATIONS / VEHICLES / SPECIAL ITEMS
================================================================================

{operations}

Certificate Holder is included as Additional Insured as respects the operations
of the Named Insured, subject to the terms, conditions, and exclusions of the
policy(ies). Coverage is primary and non-contributory. Waiver of subrogation
applies in favor of the Certificate Holder. Thirty (30) days notice of
cancellation will be provided to the Certificate Holder.

================================================================================
'''

CERTIFICATE_HOLDER_SECTION = '''
CERTIFICATE HOLDER                         CANCELLATION
================================================================================

{holder_name}                              SHOULD ANY OF THE ABOVE DESCRIBED
{holder_address}                           POLICIES BE CANCELLED BEFORE THE
                                          EXPIRATION DATE THEREOF, NOTICE WILL
                                          BE DELIVERED IN ACCORDANCE WITH THE
                                          POLICY PROVISIONS.

[ ] ADDITIONAL INSURED                    AUTHORIZED REPRESENTATIVE
[ ] SUBROGATION WAIVED

                                          _____________________________________
                                          Signature

================================================================================
'''

CERTIFICATE_DISCLAIMER = '''
DISCLAIMER
================================================================================

This Certificate of Insurance does not constitute a contract of insurance
between any insurer and the Certificate Holder.

This Certificate is provided for informational purposes only and does not
affirmatively or negatively amend, extend or alter the coverage afforded by
the policies listed herein.

The Certificate Holder has no rights under the insurance policies other than
those specifically granted by an endorsement to such policies.

The issuing party makes no representations or warranties regarding the
coverage afforded by the policies described herein.

Should any of the above described policies be cancelled before the expiration
date thereof, notice will be delivered in accordance with the policy
provisions. The insurer has no obligation to provide notice to the Certificate
Holder unless required by endorsement to the policy.

================================================================================
'''


# =============================================================================
# ENDORSEMENT CONTENT
# =============================================================================

ENDORSEMENT_HEADER = '''
================================================================================
                              POLICY ENDORSEMENT
================================================================================

Policy Number:                     {policy_number}
Unique Market Reference:           {umr}
Endorsement Number:                {endorsement_number}
Effective Date:                    {effective_date}
Endorsement Type:                  {endorsement_type}

================================================================================

This Endorsement forms part of and is subject to all the terms, conditions,
exclusions, and limitations of the Policy to which it is attached, except as
specifically modified herein.

All other terms, conditions, exclusions, and limitations remain unchanged.

================================================================================
'''

# Additional Insured Endorsement
ADDITIONAL_INSURED_ENDORSEMENT = '''
ADDITIONAL INSURED ENDORSEMENT (LMA5217)

It is hereby agreed that the following person(s) or organization(s) is/are
included as an Additional Insured under this Policy:

Additional Insured Name:           {additional_insured_name}
Additional Insured Address:        {additional_insured_address}
Relationship to Named Insured:     {relationship}

COVERAGE

The Additional Insured is included as an Insured under this Policy, but only
with respect to liability arising out of:

1. The Named Insured's ongoing operations performed for the Additional Insured
   at the location(s) designated above or in the schedule of covered locations;

2. "Your work" performed for the Additional Insured and included within the
   "products-completed operations hazard," but only if:
   (a) This Policy has been endorsed to provide products-completed operations
       coverage; and
   (b) This endorsement is required by a written contract or agreement;

3. The maintenance or use of equipment, premises, or operations leased or
   rented by the Named Insured from the Additional Insured.

LIMITATIONS

The coverage afforded to the Additional Insured:

1. Does not apply to "bodily injury" or "property damage" arising out of the
   sole negligence of the Additional Insured;

2. Is limited to the extent of liability assumed by the Named Insured under
   the written contract or agreement with the Additional Insured;

3. Is subject to all the terms, conditions, exclusions, and limitations of
   this Policy;

4. Does not increase the Limits of Liability stated in the Declarations;

5. Shall not be broader than coverage required by the written contract or
   agreement.

NOTICE OF CANCELLATION

The Insurers will endeavor to give thirty (30) days written notice to the
Additional Insured in the event of cancellation or material change to this
Policy, but failure to provide such notice shall impose no obligation or
liability upon the Insurers.

All other terms, conditions, exclusions, and limitations of the Policy
remain unchanged.
'''

# Waiver of Subrogation Endorsement
WAIVER_OF_SUBROGATION_ENDORSEMENT = '''
WAIVER OF SUBROGATION ENDORSEMENT (LMA5218)

It is hereby agreed that the Insurers waive any right of subrogation against
the following person(s) or organization(s):

Name:                              {waiver_party_name}
Address:                           {waiver_party_address}

SCOPE OF WAIVER

1. The Insurers waive any right of recovery they may have against the above-
   named party arising out of payments made under this Policy for:

   (a) "Bodily injury" or "property damage" that arises out of the Named
       Insured's ongoing operations; or

   (b) "Your work" performed under a written contract or agreement with the
       above-named party.

2. This waiver applies only when required by a written contract or agreement
   entered into by the Named Insured prior to the occurrence giving rise to
   the loss.

CONDITIONS

1. This waiver shall not apply to any recovery or subrogation against any
   party who has caused loss through their gross negligence, wilful misconduct,
   or fraud.

2. This waiver shall not apply to any recovery that the Named Insured is
   entitled to under any other insurance policy.

3. The waiver of subrogation shall only apply to the extent permitted by law.

4. This waiver does not increase the Limits of Liability or waive any
   deductible or self-insured retention stated in the Declarations.

PREMIUM ADJUSTMENT

Additional Premium:                {additional_premium}

All other terms, conditions, exclusions, and limitations of the Policy
remain unchanged.
'''

# Primary and Non-Contributory Endorsement
PRIMARY_NON_CONTRIBUTORY_ENDORSEMENT = '''
PRIMARY AND NON-CONTRIBUTORY ENDORSEMENT (LMA5219)

It is hereby agreed that this insurance shall be primary and non-contributory
with respect to:

Name:                              {primary_party_name}
Address:                           {primary_party_address}

SCOPE

1. This insurance is primary. The Insurers will not seek contribution from
   any other insurance available to the above-named party when such other
   insurance applies as additional insurance, whether primary, excess,
   contingent, or any other basis.

2. This primary and non-contributory provision applies only when:

   (a) The above-named party is an Additional Insured under this Policy; and

   (b) Such primary and non-contributory status is required by a written
       contract or agreement between the Named Insured and the above-named
       party, entered into prior to the occurrence giving rise to the loss.

3. When this insurance is primary, the Insurers' obligations are not affected
   by any other insurance of which the above-named party is the named insured.

LIMITATIONS

1. This provision shall not apply to any loss, damage, or liability arising
   out of the sole negligence of the above-named party.

2. This provision does not increase the Limits of Liability stated in the
   Declarations.

3. The coverage afforded to the above-named party is still subject to all
   other terms, conditions, exclusions, and limitations of this Policy.

4. This provision shall not apply if prohibited by law.

All other terms, conditions, exclusions, and limitations of the Policy
remain unchanged.
'''

# Notice of Cancellation Endorsement
NOTICE_OF_CANCELLATION_ENDORSEMENT = '''
NOTICE OF CANCELLATION ENDORSEMENT (LMA5220)

It is hereby agreed that the following notice provisions shall apply:

NOTICE RECIPIENT

Name:                              {notice_recipient_name}
Address:                           {notice_recipient_address}
Email:                             {notice_recipient_email}

NOTICE REQUIREMENTS

1. In the event of cancellation of this Policy by the Insurers (other than
   for non-payment of premium), the Insurers will endeavor to give written
   notice of such cancellation to the above-named party at least:

   [ ] Thirty (30) days prior to the effective date of cancellation; or
   [ ] {custom_notice_days} days prior to the effective date of cancellation.

2. In the event of cancellation of this Policy for non-payment of premium,
   the Insurers will endeavor to give written notice of such cancellation
   to the above-named party at least:

   [ ] Ten (10) days prior to the effective date of cancellation; or
   [ ] {custom_nonpay_days} days prior to the effective date of cancellation.

3. In the event of any material change to this Policy, the Insurers will
   endeavor to give written notice of such change to the above-named party
   at least:

   [ ] Thirty (30) days prior to the effective date of change; or
   [ ] {custom_change_days} days prior to the effective date of change.

LIMITATION OF LIABILITY

Notwithstanding the foregoing, the failure of the Insurers to provide such
notice to the above-named party shall not:

1. Invalidate the cancellation or change;

2. Extend the Policy beyond its cancellation or change date;

3. Create any additional liability or obligation on the part of the Insurers;

4. Create any cause of action against the Insurers.

This endorsement does not create any rights in favor of the above-named party
beyond receipt of such notice.

All other terms, conditions, exclusions, and limitations of the Policy
remain unchanged.
'''

# Blanket Additional Insured Endorsement
BLANKET_ADDITIONAL_INSURED_ENDORSEMENT = '''
BLANKET ADDITIONAL INSURED - CONTRACTORS ENDORSEMENT (LMA5221)

It is hereby agreed that any person or organization for whom the Named Insured
is performing operations is automatically included as an Additional Insured
under this Policy, subject to the following:

CONDITIONS

1. The Additional Insured status is required by a written contract or
   agreement entered into by the Named Insured prior to the occurrence
   giving rise to the loss;

2. The operations are performed by the Named Insured for the Additional
   Insured;

3. A Certificate of Insurance evidencing such Additional Insured status
   has been issued.

COVERAGE

The coverage afforded to such Additional Insured applies only:

1. With respect to liability for "bodily injury" or "property damage" that
   arises out of:

   (a) The Named Insured's ongoing operations performed for such Additional
       Insured; or

   (b) Acts or omissions of such Additional Insured in connection with their
       general supervision of the Named Insured's operations;

2. To the extent required by the written contract or agreement;

3. Subject to all terms, conditions, exclusions, and limitations of this Policy.

LIMITS OF INSURANCE

The most the Insurers will pay on behalf of all Additional Insureds is the
lesser of:

1. The Limits of Liability stated in the Declarations; or

2. The limits of liability required by the written contract or agreement.

The limits shown above are the most the Insurers will pay for the sum of all
damages under Coverage A, Coverage B, and medical expenses covered under
Coverage C regardless of the number of:

1. Insureds;
2. Claims made or "suits" brought; or
3. Persons or organizations making claims or bringing "suits."

All other terms, conditions, exclusions, and limitations of the Policy
remain unchanged.
'''


# =============================================================================
# DOCUMENT ASSEMBLY FUNCTIONS
# =============================================================================

def assemble_mrc_slip(data: Dict) -> str:
    """Assemble a complete MRC slip document from the provided data."""
    document = MRC_SLIP_HEADER.format(**data)
    document += MRC_RISK_DETAILS_SECTION.format(**data)
    document += MRC_ASSURED_SECTION.format(**data)
    document += MRC_PERIOD_SECTION.format(**data)
    document += MRC_INTEREST_SECTION.format(**data)
    document += MRC_TERRITORIAL_LIMITS_SECTION.format(**data)
    document += MRC_BASIS_OF_COVER_SECTION.format(**data)
    document += MRC_LIMITS_SECTION.format(**data)
    document += MRC_DEDUCTIBLE_SECTION.format(**data)
    document += MRC_PREMIUM_SECTION.format(**data)
    document += MRC_CONDITIONS_PRECEDENT_SECTION
    document += MRC_SUBJECTIVITIES_SECTION.format(**data)
    document += MRC_WARRANTIES_SECTION.format(**data)
    document += MRC_EXCLUSIONS_SECTION.format(**data)
    document += MRC_EXTENSIONS_SECTION.format(**data)
    document += MRC_CLAIMS_CONDITIONS_SECTION.format(**data)
    document += MRC_GENERAL_CONDITIONS_SECTION
    document += MRC_JURISDICTION_SECTION.format(**data)
    document += MRC_SERVICE_OF_SUIT_SECTION.format(**data)
    document += MRC_SEVERAL_LIABILITY_SECTION
    document += MRC_SECURITY_SECTION.format(**data)

    # Add standard clauses
    document += "\n\n" + "=" * 80 + "\n"
    document += "                         ATTACHED CLAUSES\n"
    document += "=" * 80 + "\n"
    document += SEVERAL_LIABILITY_CLAUSE
    document += SANCTIONS_CLAUSE
    document += PREMIUM_PAYMENT_CLAUSE
    document += CLAIMS_COOPERATION_CLAUSE
    document += CANCELLATION_CLAUSE
    document += JURISDICTION_CLAUSE_ENGLISH
    document += WAR_EXCLUSION_CLAUSE
    document += NUCLEAR_EXCLUSION_CLAUSE
    document += TERRORISM_EXCLUSION_CLAUSE

    return document


def assemble_policy_wording(data: Dict) -> str:
    """Assemble a complete policy wording document from the provided data."""
    document = POLICY_WORDING_HEADER.format(**data)
    document += POLICY_DECLARATIONS_SECTION.format(**data)
    document += POLICY_INSURING_AGREEMENTS
    document += POLICY_DEFINITIONS_SECTION
    document += POLICY_EXCLUSIONS_SECTION
    document += POLICY_CONDITIONS_SECTION
    document += POLICY_CLAIMS_SECTION
    document += SUBROGATION_CLAUSE

    # Add standard clauses
    document += "\n\n" + "=" * 80 + "\n"
    document += "                         ATTACHED CLAUSES\n"
    document += "=" * 80 + "\n"
    document += SEVERAL_LIABILITY_CLAUSE
    document += SANCTIONS_CLAUSE
    document += WAR_EXCLUSION_CLAUSE
    document += NUCLEAR_EXCLUSION_CLAUSE
    document += TERRORISM_EXCLUSION_CLAUSE

    return document


def assemble_certificate(data: Dict) -> str:
    """Assemble a complete certificate of insurance from the provided data."""
    document = CERTIFICATE_HEADER.format(**data)
    document += CERTIFICATE_PRODUCER_SECTION.format(**data)
    document += CERTIFICATE_INSURED_SECTION.format(**data)
    document += CERTIFICATE_INSURERS_SECTION.format(**data)
    document += CERTIFICATE_COVERAGES_SECTION.format(**data)
    document += CERTIFICATE_DESCRIPTION_SECTION.format(**data)
    document += CERTIFICATE_HOLDER_SECTION.format(**data)
    document += CERTIFICATE_DISCLAIMER

    return document


def assemble_endorsement(endorsement_type: str, data: Dict) -> str:
    """Assemble an endorsement document based on the type."""
    document = ENDORSEMENT_HEADER.format(**data)

    endorsement_map = {
        "additional_insured": ADDITIONAL_INSURED_ENDORSEMENT,
        "waiver_of_subrogation": WAIVER_OF_SUBROGATION_ENDORSEMENT,
        "primary_non_contributory": PRIMARY_NON_CONTRIBUTORY_ENDORSEMENT,
        "notice_of_cancellation": NOTICE_OF_CANCELLATION_ENDORSEMENT,
        "blanket_additional_insured": BLANKET_ADDITIONAL_INSURED_ENDORSEMENT,
    }

    endorsement_content = endorsement_map.get(endorsement_type, "")
    if endorsement_content:
        document += endorsement_content.format(**data)

    return document


# =============================================================================
# CLAUSE LIBRARY
# =============================================================================

CLAUSE_LIBRARY = {
    "several_liability": {
        "id": "LMA5363",
        "name": "Several Liability Clause",
        "content": SEVERAL_LIABILITY_CLAUSE,
        "mandatory": True,
        "category": "standard"
    },
    "service_of_suit_usa": {
        "id": "LSW1001",
        "name": "Service of Suit Clause (USA)",
        "content": SERVICE_OF_SUIT_CLAUSE_USA,
        "mandatory": False,
        "category": "jurisdiction"
    },
    "service_of_suit_uk": {
        "id": "LSW1002",
        "name": "Service of Suit Clause (UK/Europe)",
        "content": SERVICE_OF_SUIT_CLAUSE_UK,
        "mandatory": False,
        "category": "jurisdiction"
    },
    "sanctions": {
        "id": "LMA3100",
        "name": "Sanctions Limitation and Exclusion Clause",
        "content": SANCTIONS_CLAUSE,
        "mandatory": True,
        "category": "exclusion"
    },
    "premium_payment": {
        "id": "LSW559/LMA9108",
        "name": "Premium Payment Clause",
        "content": PREMIUM_PAYMENT_CLAUSE,
        "mandatory": True,
        "category": "standard"
    },
    "claims_cooperation": {
        "id": "LMA5106",
        "name": "Claims Cooperation Clause",
        "content": CLAIMS_COOPERATION_CLAUSE,
        "mandatory": True,
        "category": "claims"
    },
    "cancellation": {
        "id": "LMA5020",
        "name": "Cancellation Clause",
        "content": CANCELLATION_CLAUSE,
        "mandatory": True,
        "category": "standard"
    },
    "material_change": {
        "id": "Custom",
        "name": "Material Change Clause",
        "content": MATERIAL_CHANGE_CLAUSE,
        "mandatory": False,
        "category": "standard"
    },
    "jurisdiction_english": {
        "id": "Custom",
        "name": "Jurisdiction Clause (English Law)",
        "content": JURISDICTION_CLAUSE_ENGLISH,
        "mandatory": False,
        "category": "jurisdiction"
    },
    "arbitration_london": {
        "id": "Custom",
        "name": "Arbitration Clause (London)",
        "content": ARBITRATION_CLAUSE_LONDON,
        "mandatory": False,
        "category": "jurisdiction"
    },
    "war_exclusion": {
        "id": "LSW556A",
        "name": "War and Civil War Exclusion Clause",
        "content": WAR_EXCLUSION_CLAUSE,
        "mandatory": True,
        "category": "exclusion"
    },
    "nuclear_exclusion": {
        "id": "NMA1975a",
        "name": "Nuclear Exclusion Clause",
        "content": NUCLEAR_EXCLUSION_CLAUSE,
        "mandatory": True,
        "category": "exclusion"
    },
    "terrorism_exclusion": {
        "id": "NMA2918",
        "name": "Terrorism Exclusion Clause",
        "content": TERRORISM_EXCLUSION_CLAUSE,
        "mandatory": True,
        "category": "exclusion"
    },
    "cyber_exclusion": {
        "id": "LMA5400",
        "name": "Cyber Attack Exclusion Clause",
        "content": CYBER_EXCLUSION_CLAUSE,
        "mandatory": False,
        "category": "exclusion"
    },
    "communicable_disease_exclusion": {
        "id": "LMA5393",
        "name": "Communicable Disease Exclusion Clause",
        "content": COMMUNICABLE_DISEASE_EXCLUSION,
        "mandatory": False,
        "category": "exclusion"
    },
    "subrogation": {
        "id": "Custom",
        "name": "Subrogation Clause",
        "content": SUBROGATION_CLAUSE,
        "mandatory": True,
        "category": "standard"
    },
}


def get_clause(clause_id: str) -> Dict:
    """Get a clause by its ID."""
    return CLAUSE_LIBRARY.get(clause_id)


def get_mandatory_clauses() -> List[Dict]:
    """Get all mandatory clauses."""
    return [clause for clause in CLAUSE_LIBRARY.values() if clause.get("mandatory")]


def get_clauses_by_category(category: str) -> List[Dict]:
    """Get clauses by category."""
    return [clause for clause in CLAUSE_LIBRARY.values() if clause.get("category") == category]


def get_all_clauses() -> Dict:
    """Get all available clauses."""
    return CLAUSE_LIBRARY


# =============================================================================
# ENDORSEMENT LIBRARY
# =============================================================================

ENDORSEMENT_LIBRARY = {
    "additional_insured": {
        "id": "LMA5217",
        "name": "Additional Insured Endorsement",
        "content": ADDITIONAL_INSURED_ENDORSEMENT,
        "category": "coverage_extension"
    },
    "waiver_of_subrogation": {
        "id": "LMA5218",
        "name": "Waiver of Subrogation Endorsement",
        "content": WAIVER_OF_SUBROGATION_ENDORSEMENT,
        "category": "coverage_extension"
    },
    "primary_non_contributory": {
        "id": "LMA5219",
        "name": "Primary and Non-Contributory Endorsement",
        "content": PRIMARY_NON_CONTRIBUTORY_ENDORSEMENT,
        "category": "coverage_extension"
    },
    "notice_of_cancellation": {
        "id": "LMA5220",
        "name": "Notice of Cancellation Endorsement",
        "content": NOTICE_OF_CANCELLATION_ENDORSEMENT,
        "category": "administrative"
    },
    "blanket_additional_insured": {
        "id": "LMA5221",
        "name": "Blanket Additional Insured - Contractors Endorsement",
        "content": BLANKET_ADDITIONAL_INSURED_ENDORSEMENT,
        "category": "coverage_extension"
    },
}


def get_endorsement(endorsement_id: str) -> Dict:
    """Get an endorsement by its ID."""
    return ENDORSEMENT_LIBRARY.get(endorsement_id)


def get_all_endorsements() -> Dict:
    """Get all available endorsements."""
    return ENDORSEMENT_LIBRARY


# =============================================================================
# DOCUMENT SECTION MAPPING
# =============================================================================

MRC_SECTIONS = {
    "header": MRC_SLIP_HEADER,
    "risk_details": MRC_RISK_DETAILS_SECTION,
    "assured": MRC_ASSURED_SECTION,
    "period": MRC_PERIOD_SECTION,
    "interest": MRC_INTEREST_SECTION,
    "territorial_limits": MRC_TERRITORIAL_LIMITS_SECTION,
    "basis_of_cover": MRC_BASIS_OF_COVER_SECTION,
    "limits": MRC_LIMITS_SECTION,
    "deductible": MRC_DEDUCTIBLE_SECTION,
    "premium": MRC_PREMIUM_SECTION,
    "conditions_precedent": MRC_CONDITIONS_PRECEDENT_SECTION,
    "subjectivities": MRC_SUBJECTIVITIES_SECTION,
    "warranties": MRC_WARRANTIES_SECTION,
    "exclusions": MRC_EXCLUSIONS_SECTION,
    "extensions": MRC_EXTENSIONS_SECTION,
    "claims_conditions": MRC_CLAIMS_CONDITIONS_SECTION,
    "general_conditions": MRC_GENERAL_CONDITIONS_SECTION,
    "jurisdiction": MRC_JURISDICTION_SECTION,
    "service_of_suit": MRC_SERVICE_OF_SUIT_SECTION,
    "several_liability": MRC_SEVERAL_LIABILITY_SECTION,
    "security": MRC_SECURITY_SECTION,
}

POLICY_SECTIONS = {
    "header": POLICY_WORDING_HEADER,
    "declarations": POLICY_DECLARATIONS_SECTION,
    "insuring_agreements": POLICY_INSURING_AGREEMENTS,
    "definitions": POLICY_DEFINITIONS_SECTION,
    "exclusions": POLICY_EXCLUSIONS_SECTION,
    "conditions": POLICY_CONDITIONS_SECTION,
    "claims": POLICY_CLAIMS_SECTION,
    "subrogation": SUBROGATION_CLAUSE,
}

CERTIFICATE_SECTIONS = {
    "header": CERTIFICATE_HEADER,
    "producer": CERTIFICATE_PRODUCER_SECTION,
    "insured": CERTIFICATE_INSURED_SECTION,
    "insurers": CERTIFICATE_INSURERS_SECTION,
    "coverages": CERTIFICATE_COVERAGES_SECTION,
    "description": CERTIFICATE_DESCRIPTION_SECTION,
    "holder": CERTIFICATE_HOLDER_SECTION,
    "disclaimer": CERTIFICATE_DISCLAIMER,
}


def get_section(document_type: str, section_name: str) -> str:
    """Get a specific section content by document type and section name."""
    section_maps = {
        "mrc": MRC_SECTIONS,
        "policy": POLICY_SECTIONS,
        "certificate": CERTIFICATE_SECTIONS,
    }

    section_map = section_maps.get(document_type.lower(), {})
    return section_map.get(section_name, "")
