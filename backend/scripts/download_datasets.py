"""
Download and prepare insurance datasets for RAG indexing.

Downloads from HuggingFace:
- CUAD (Contract Understanding Atticus Dataset) - 84K labeled contract clauses
- JETech underwriting dataset blocks - 49.9K underwriting doc blocks

Outputs JSONL files ready for RAG indexer consumption.
"""

import json
import os
import sys
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# Output directory
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "app", "data", "training_data", "embeddings")


def download_cuad():
    """Download CUAD dataset from HuggingFace and convert to JSONL.

    Uses streaming mode to avoid Windows long-path issues with PDF downloads.
    """
    from datasets import load_dataset

    logger.info("Downloading CUAD dataset (streaming mode)...")
    # Use streaming=True to avoid downloading full PDF files (Windows path length issue)
    # CUAD has 'train' split in streaming mode
    ds = load_dataset("theatticusproject/cuad", split="train", streaming=True)

    output_path = os.path.join(OUTPUT_DIR, "cuad_clauses.jsonl")
    count = 0
    seen_contexts = set()  # deduplicate by context hash

    with open(output_path, "w", encoding="utf-8") as f:
        for row in ds:
            context = row.get("context", "")
            question = row.get("question", "")
            answers = row.get("answers", {})
            answer_texts = answers.get("text", []) if isinstance(answers, dict) else []

            if not context or len(context.strip()) < 20:
                continue

            # Deduplicate - CUAD has same context repeated for different questions
            ctx_hash = hash(context[:500])
            if ctx_hash in seen_contexts:
                continue
            seen_contexts.add(ctx_hash)

            # Extract clause type from question (e.g., "Highlight the parts...")
            clause_type = question.split("(")[0].strip() if question else "general"

            record = {
                "text": context[:2000],
                "category": "cuad_clause",
                "source": "cuad",
                "metadata": {
                    "clause_type": clause_type[:100],
                    "question": question[:200],
                    "has_answer": len(answer_texts) > 0,
                    "answer_excerpt": answer_texts[0][:200] if answer_texts else "",
                },
            }
            f.write(json.dumps(record) + "\n")
            count += 1

            if count % 1000 == 0:
                logger.info(f"  CUAD progress: {count} records...")

    logger.info(f"CUAD: wrote {count} records to {output_path}")
    return count


def download_jetech():
    """Download JETech underwriting dataset blocks from HuggingFace."""
    from datasets import load_dataset

    logger.info("Downloading JETech underwriting-dataset-blocks...")
    ds = load_dataset("JETech/underwriting-dataset-blocks", split="train")

    output_path = os.path.join(OUTPUT_DIR, "jetech_blocks.jsonl")
    count = 0

    with open(output_path, "w", encoding="utf-8") as f:
        for row in ds:
            # JETech uses capitalized field names: Text, Quality, Type
            text = (row.get("Text", "") or row.get("text", "") or
                    row.get("block_text", "") or row.get("content", ""))
            quality = (row.get("Quality", "") or row.get("quality", "") or
                       row.get("label", ""))

            if not text or len(text.strip()) < 20:
                continue

            # Filter to good quality blocks if quality field exists
            if quality and str(quality).lower() not in ("good", "high", "acceptable", ""):
                continue

            block_type = (row.get("Type", "") or row.get("block_type", "") or
                          row.get("type", "") or row.get("category", ""))

            record = {
                "text": text[:2000],
                "category": "underwriting_block",
                "source": "jetech",
                "metadata": {
                    "block_type": str(block_type)[:100],
                    "quality": str(quality)[:50],
                },
            }
            f.write(json.dumps(record) + "\n")
            count += 1

    logger.info(f"JETech: wrote {count} records to {output_path}")
    return count


def generate_acord_clauses():
    """
    Generate ACORD-style standard clause library.

    Since the Atticus ACORD dataset requires manual download from atticusprojectai.org,
    we generate a comprehensive library of standard insurance clauses based on
    well-known LMA, ICC, and market standard wordings.
    """
    logger.info("Generating ACORD standard clause library...")

    output_path = os.path.join(OUTPUT_DIR, "acord_clauses.jsonl")
    count = 0

    # Standard insurance clauses - LMA, ICC, and market standard
    clauses = [
        # Institute Cargo Clauses
        {"id": "ICC_A", "name": "Institute Cargo Clauses (A)", "category": "cargo",
         "text": "This insurance covers all risks of loss of or damage to the subject-matter insured except as excluded. This insurance covers general average and salvage charges, adjusted or determined according to the contract of carriage and/or the governing law and practice, incurred to avoid or in connection with the avoidance of loss from any cause except those excluded."},
        {"id": "ICC_B", "name": "Institute Cargo Clauses (B)", "category": "cargo",
         "text": "This insurance covers, except as excluded, loss of or damage to the subject-matter insured reasonably attributable to fire or explosion, vessel or craft being stranded grounded sunk or capsized, overturning or derailment of land conveyance, collision or contact of vessel craft or conveyance with any external object other than water, discharge of cargo at a port of distress, earthquake volcanic eruption or lightning."},
        {"id": "ICC_C", "name": "Institute Cargo Clauses (C)", "category": "cargo",
         "text": "This insurance covers, except as excluded, loss of or damage to the subject-matter insured reasonably attributable to fire or explosion, vessel or craft being stranded grounded sunk or capsized, overturning or derailment of land conveyance, collision or contact of vessel craft or conveyance with any external object other than water, discharge of cargo at a port of distress."},
        {"id": "ICC_WAR", "name": "Institute War Clauses (Cargo)", "category": "cargo",
         "text": "This insurance covers, except as excluded, loss of or damage to the subject-matter insured caused by war civil war revolution rebellion insurrection, or civil strife arising therefrom, or any hostile act by or against a belligerent power, capture seizure arrest restraint or detainment, arising from risks covered, derelict mines torpedoes bombs or other derelict weapons of war."},
        {"id": "ICC_STRIKES", "name": "Institute Strikes Clauses (Cargo)", "category": "cargo",
         "text": "This insurance covers, except as excluded, loss of or damage to the subject-matter insured caused by strikers, locked-out workmen, or persons taking part in labour disturbances, riots or civil commotions, any act of terrorism being an act of any person acting on behalf of, or in connection with, any organisation which carries out activities directed towards the overthrowing or influencing, by force or violence, of any government."},

        # LMA Clauses
        {"id": "LMA5021", "name": "LMA Several Liability Notice", "category": "market_standard",
         "text": "The liability of an insurer under this contract is several and not joint with other insurers party to this contract. An insurer is liable only for the proportion of liability it has underwritten. An insurer is not jointly liable for the proportion of liability underwritten by any other insurer. Nor is an insurer otherwise responsible for any liability of any other insurer that may underwrite this contract."},
        {"id": "LMA5173", "name": "LMA Sanctions Limitation and Exclusion", "category": "sanctions",
         "text": "No insurer shall be deemed to provide cover and no insurer shall be liable to pay any claim or provide any benefit hereunder to the extent that the provision of such cover, payment of such claim or provision of such benefit would expose that insurer to any sanction, prohibition or restriction under United Nations resolutions or the trade or economic sanctions, laws or regulations of the European Union, United Kingdom or United States of America."},
        {"id": "LMA5403", "name": "LMA War and Terrorism Exclusion", "category": "war",
         "text": "Notwithstanding any provision to the contrary within this insurance or any endorsement thereto it is agreed that this insurance excludes loss, damage, cost or expense of whatsoever nature directly or indirectly caused by, resulting from or in connection with any of the following regardless of any other cause or event contributing concurrently or in any other sequence to the loss: war, invasion, acts of foreign enemies, hostilities, civil war, rebellion, revolution, insurrection, military or usurped power or confiscation or nationalisation."},
        {"id": "LMA5218", "name": "LMA Communicable Disease Exclusion", "category": "communicable_disease",
         "text": "This clause shall be paramount and shall override anything contained in this insurance inconsistent therewith. This insurance excludes any loss, damage, liability, claim, cost or expense of whatsoever nature, directly or indirectly caused by, contributed to by, resulting from, arising out of, or in connection with a Communicable Disease or the fear or threat of a Communicable Disease regardless of any other cause or event contributing concurrently or in any other sequence thereto."},
        {"id": "LMA5394", "name": "LMA Cyber War and Cyber Operation Exclusion", "category": "cyber",
         "text": "Notwithstanding any provision to the contrary in this insurance or any endorsement, this insurance excludes any loss, damage, liability, claim, cost, or expense of any kind directly or indirectly occasioned by, happening through, or in consequence of a cyber operation, including where the cyber operation involves the use of a computer system as a means to commit a hostile act, espionage, or sabotage against a computer system."},

        # Marine Hull Clauses
        {"id": "IHC_2003", "name": "Institute Hull Clauses 2003", "category": "hull",
         "text": "This insurance is subject to English law and practice. In case of any loss or misfortune it shall be lawful and necessary for the Assured, their factors, servants and assigns, to sue, labour and travel for, in, about and beyond, the defence, safeguard and recovery of the Vessel, or any part thereof, without prejudice to this insurance, nor shall the acts of the Assured or Insurers in recovering, saving, or preserving the Vessel be considered as a waiver or acceptance of an abandonment."},

        # Property Clauses
        {"id": "FLEXA", "name": "Fire, Lightning, Explosion, Aircraft (FLEXA)", "category": "property",
         "text": "This Policy covers physical loss or damage to the insured property directly caused by: Fire however caused, Lightning, Explosion including the explosion of boilers and pressure vessels, Impact by aircraft or aerial devices or articles dropped therefrom. Extensions include smoke damage, extinguishing expenses, and removal of debris following an insured event."},
        {"id": "NAT_CAT", "name": "Natural Catastrophe Extension", "category": "property",
         "text": "This extension covers physical loss or damage to the insured property directly caused by earthquake, volcanic eruption, tsunami, hurricane, typhoon, cyclone, tornado, windstorm, hail, flood, or any other natural catastrophe. Subject to applicable sub-limits and deductibles as specified in the Schedule. Waiting periods may apply for earthquake and flood perils."},
        {"id": "BI_COVER", "name": "Business Interruption Coverage", "category": "property",
         "text": "This insurance covers loss of Gross Profit due to interruption of or interference with the Business in consequence of damage to property used by the Insured at the Premises for the purpose of the Business. The insurance under this Section shall not apply to any loss occurring after the expiry of the Indemnity Period. The Indemnity Period means the period during which the results of the Business shall be affected in consequence of the damage."},

        # Liability Clauses
        {"id": "GL_OCCURRENCE", "name": "General Liability Occurrence Form", "category": "liability",
         "text": "The insurer will pay those sums that the insured becomes legally obligated to pay as damages because of bodily injury or property damage to which this insurance applies. This insurance applies to bodily injury and property damage only if the bodily injury or property damage is caused by an occurrence that takes place in the coverage territory and the bodily injury or property damage occurs during the policy period."},
        {"id": "GL_CLAIMS_MADE", "name": "General Liability Claims-Made Form", "category": "liability",
         "text": "The insurer will pay those sums that the insured becomes legally obligated to pay as damages because of bodily injury or property damage to which this insurance applies. This insurance applies to bodily injury and property damage only if a claim for damages is first made against any insured during the policy period or any Extended Reporting Period and only if the bodily injury or property damage is caused by an occurrence."},
        {"id": "PI_COVERAGE", "name": "Professional Indemnity Coverage", "category": "liability",
         "text": "The Insurer agrees to indemnify the Insured against civil liability for any claim first made against the Insured during the Period of Insurance and notified to the Insurer during the Period of Insurance arising from any act, error or omission in the conduct of the Insured's Professional Business. This includes defence costs and legal expenses incurred with the prior written consent of the Insurer."},
        {"id": "DO_LIABILITY", "name": "Directors & Officers Liability", "category": "liability",
         "text": "The Insurer shall pay on behalf of the Directors and Officers Loss arising from any Claim first made against any Director or Officer during the Policy Period for any Wrongful Act committed by such Director or Officer in their capacity as Directors or Officers of the Company. Wrongful Act means any actual or alleged breach of duty, breach of trust, neglect, error, misstatement, misleading statement, omission, or other act done or wrongfully attempted."},

        # Workers Compensation
        {"id": "WC_STANDARD", "name": "Workers Compensation Standard Provisions", "category": "workers_comp",
         "text": "The insurer will pay promptly when due the benefits required of the insured by the workers compensation law. The insurer will defend at its expense any claim, proceeding or suit against the insured for benefits payable by this insurance. The insurer has the right to investigate and settle these claims, proceedings or suits. This insurance applies to bodily injury by accident or bodily injury by disease."},

        # Auto Liability
        {"id": "AL_COVERAGE", "name": "Commercial Auto Liability Coverage", "category": "auto",
         "text": "The insurer will pay all sums an insured legally must pay as damages because of bodily injury or property damage to which this insurance applies, caused by an accident and resulting from the ownership, maintenance or use of a covered auto. The insurer will settle or defend, as it considers appropriate, any claim or suit asking for these damages. Coverage applies to the use of a covered auto within the coverage territory."},

        # Cyber Insurance
        {"id": "CYBER_BREACH", "name": "Data Breach Response Coverage", "category": "cyber",
         "text": "The Insurer will reimburse the Insured for Data Breach Response Costs incurred as a result of a Data Breach that is first discovered by the Insured during the Policy Period. Data Breach Response Costs include: forensic investigation expenses, notification costs, credit monitoring services, call center services, public relations expenses, and legal advice in connection with the Data Breach. Subject to the applicable retention and sublimit."},
        {"id": "CYBER_LIABILITY", "name": "Cyber Liability Coverage", "category": "cyber",
         "text": "The Insurer will pay on behalf of the Insured all Loss which the Insured becomes legally obligated to pay as a result of a Claim first made against the Insured during the Policy Period arising out of a Network Security Failure, Privacy Violation, or Media Liability Event. The Insurer will defend any covered Claim at the Insurer's expense using counsel selected by the Insurer. Defence costs are included within and erode the Limit of Liability."},

        # Reinsurance
        {"id": "FOLLOW_FORM", "name": "Follow the Fortunes / Follow the Settlements", "category": "reinsurance",
         "text": "All loss settlements by the Reinsured including compromise settlements and the establishment of policy reserves shall be binding upon the Reinsurer, provided they are within the terms and conditions of the original policies and within the terms and conditions of this reinsurance. The Reinsurer agrees to follow the fortunes of the Reinsured in all respects, subject to the terms and conditions of this Contract."},
        {"id": "CLASH_COVER", "name": "Clash Cover / Catastrophe Excess of Loss", "category": "reinsurance",
         "text": "The Reinsurer agrees to indemnify the Reinsured for the Ultimate Net Loss in respect of each and every Loss Occurrence, in excess of the retention specified in the Schedule, subject to the limit specified in the Schedule. A Loss Occurrence means the sum of all individual losses arising out of and directly occasioned by one catastrophe. The duration and extent of any one Loss Occurrence shall be limited to 168 consecutive hours."},

        # Exclusions - Common
        {"id": "NUCLEAR_EXCL", "name": "Nuclear Exclusion Clause", "category": "exclusion",
         "text": "This insurance does not cover loss, damage, liability or expense directly or indirectly caused by or contributed to by or arising from ionising radiations or contamination by radioactivity from any nuclear fuel or from any nuclear waste from the combustion of nuclear fuel, the radioactive, toxic, explosive or other hazardous properties of any explosive nuclear assembly or nuclear component thereof."},
        {"id": "ASBESTOS_EXCL", "name": "Asbestos Exclusion", "category": "exclusion",
         "text": "This insurance does not cover any loss, damage, liability, claim, cost, expense or any other sum directly or indirectly arising out of, relating to or in connection with asbestos or asbestos-containing materials in whatever form or quantity, including but not limited to the mining, manufacture, use, sale, installation, removal, distribution or storage of asbestos or products containing asbestos."},

        # Conditions
        {"id": "SUBROGATION", "name": "Subrogation Clause", "category": "condition",
         "text": "In the event of any payment under this Policy, the Insurer shall be subrogated to all the Insured's rights of recovery therefor against any person or organisation and the Insured shall execute and deliver instruments and papers and do whatever else is necessary to secure such rights. The Insured shall do nothing after loss to prejudice such rights."},
        {"id": "UTMOST_GOOD", "name": "Duty of Utmost Good Faith", "category": "condition",
         "text": "This contract of insurance is based upon the duty of utmost good faith. The Insured shall make a fair presentation of the risk to the Insurer before the contract is entered into and before each renewal. A fair presentation means disclosure of every material circumstance which the Insured knows or ought to know, and that disclosure must be made in a manner which would be reasonably clear and accessible to a prudent insurer."},
        {"id": "CLAIMS_COOP", "name": "Claims Cooperation Clause", "category": "condition",
         "text": "The Insured shall give immediate written notice to the Insurer of any occurrence likely to give rise to a claim under this Policy. The Insured shall cooperate with the Insurer and, upon the Insurer's request, assist in making settlements, in the conduct of suits, and in enforcing any right of contribution or indemnity against any person or organisation who may be liable to the Insured."},
    ]

    with open(output_path, "w", encoding="utf-8") as f:
        for clause in clauses:
            record = {
                "text": clause["text"],
                "category": "acord",
                "source": "acord_standard",
                "metadata": {
                    "clause_id": clause["id"],
                    "name": clause["name"],
                    "clause_category": clause["category"],
                },
            }
            f.write(json.dumps(record) + "\n")
            count += 1

    logger.info(f"ACORD: wrote {count} standard clauses to {output_path}")
    return count


def download_ledgar():
    """Download LEDGAR dataset from LexGLUE — 80K SEC contract provisions with clause type labels."""
    from datasets import load_dataset

    logger.info("Downloading LEDGAR (SEC contract provisions) from LexGLUE...")
    ds = load_dataset("coastalcph/lex_glue", "ledgar", split="train")

    # Get label names (100 clause types)
    label_names = ds.features["label"].names

    output_path = os.path.join(OUTPUT_DIR, "ledgar_provisions.jsonl")
    count = 0

    with open(output_path, "w", encoding="utf-8") as f:
        for row in ds:
            text = row.get("text", "")
            label_idx = row.get("label", 0)

            if not text or len(text.strip()) < 20:
                continue

            clause_type = label_names[label_idx] if label_idx < len(label_names) else "unknown"

            record = {
                "text": text[:2000],
                "category": "ledgar_provision",
                "source": "ledgar",
                "metadata": {
                    "clause_type": clause_type,
                    "label_index": label_idx,
                },
            }
            f.write(json.dumps(record) + "\n")
            count += 1

            if count % 5000 == 0:
                logger.info(f"  LEDGAR progress: {count} records...")

    logger.info(f"LEDGAR: wrote {count} records to {output_path}")
    return count


def download_maud():
    """Download MAUD dataset — 25K+ merger agreement clauses from Atticus Project."""
    from datasets import load_dataset

    logger.info("Downloading MAUD (merger agreement clauses)...")
    ds = load_dataset("theatticusproject/maud", split="train")

    output_path = os.path.join(OUTPUT_DIR, "maud_clauses.jsonl")
    count = 0
    seen_texts = set()

    with open(output_path, "w", encoding="utf-8") as f:
        for row in ds:
            text = row.get("text", "")
            if not text or len(text.strip()) < 20:
                continue

            # Deduplicate by text hash (MAUD repeats same text for different questions)
            text_hash = hash(text[:500])
            if text_hash in seen_texts:
                continue
            seen_texts.add(text_hash)

            question = row.get("question", "")
            answer = row.get("answer", "")
            category = row.get("category", "")

            record = {
                "text": text[:2000],
                "category": "maud_clause",
                "source": "maud",
                "metadata": {
                    "question": question[:200] if question else "",
                    "answer": answer[:200] if answer else "",
                    "maud_category": category[:100] if category else "",
                },
            }
            f.write(json.dumps(record) + "\n")
            count += 1

            if count % 2000 == 0:
                logger.info(f"  MAUD progress: {count} records...")

    logger.info(f"MAUD: wrote {count} records to {output_path}")
    return count


def download_contract_nli():
    """Download ContractNLI — 7K contract provisions with NLI labels."""
    from datasets import load_dataset

    logger.info("Downloading ContractNLI...")
    ds = load_dataset("kiddothe2b/contract-nli", "contractnli_a", split="train", trust_remote_code=True)

    output_path = os.path.join(OUTPUT_DIR, "contract_nli.jsonl")
    count = 0
    seen_premises = set()

    nli_labels = {0: "contradiction", 1: "entailment", 2: "neutral"}

    with open(output_path, "w", encoding="utf-8") as f:
        for row in ds:
            premise = row.get("premise", "")
            hypothesis = row.get("hypothesis", "")
            label = row.get("label", 2)

            if not premise or len(premise.strip()) < 20:
                continue

            # Deduplicate by premise (same clause appears with different hypotheses)
            premise_hash = hash(premise[:500])
            if premise_hash in seen_premises:
                continue
            seen_premises.add(premise_hash)

            record = {
                "text": premise[:2000],
                "category": "contract_nli",
                "source": "contract_nli",
                "metadata": {
                    "hypothesis": hypothesis[:200] if hypothesis else "",
                    "nli_label": nli_labels.get(label, "unknown"),
                },
            }
            f.write(json.dumps(record) + "\n")
            count += 1

    logger.info(f"ContractNLI: wrote {count} records to {output_path}")
    return count


def download_insurance_qa():
    """Download InsuranceQA v2 — 21K+ insurance Q&A pairs."""
    from datasets import load_dataset

    logger.info("Downloading InsuranceQA v2...")
    ds = load_dataset("deccan-ai/insuranceQA-v2", split="train")

    output_path = os.path.join(OUTPUT_DIR, "insurance_qa.jsonl")
    count = 0

    with open(output_path, "w", encoding="utf-8") as f:
        for row in ds:
            question = row.get("input", "")
            answer = row.get("output", "")

            if not answer or len(answer.strip()) < 20:
                continue

            # For QA pairs, combine question + answer as the searchable text
            combined = f"Q: {question}\nA: {answer}" if question else answer

            record = {
                "text": combined[:2000],
                "category": "insurance_qa",
                "source": "insurance_qa",
                "metadata": {
                    "question": question[:300] if question else "",
                },
            }
            f.write(json.dumps(record) + "\n")
            count += 1

            if count % 2000 == 0:
                logger.info(f"  InsuranceQA progress: {count} records...")

    logger.info(f"InsuranceQA: wrote {count} records to {output_path}")
    return count


def main():
    """Download all datasets."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    results = {}

    # ACORD standard clauses (generated, no download needed)
    try:
        results["acord"] = generate_acord_clauses()
    except Exception as e:
        logger.error(f"ACORD generation failed: {e}")
        results["acord"] = 0

    # CUAD from HuggingFace
    try:
        results["cuad"] = download_cuad()
    except Exception as e:
        logger.error(f"CUAD download failed: {e}")
        logger.error("Install datasets: pip install datasets")
        results["cuad"] = 0

    # JETech from HuggingFace
    try:
        results["jetech"] = download_jetech()
    except Exception as e:
        logger.error(f"JETech download failed: {e}")
        logger.error("Install datasets: pip install datasets")
        results["jetech"] = 0

    # LEDGAR from LexGLUE (80K SEC contract provisions)
    try:
        results["ledgar"] = download_ledgar()
    except Exception as e:
        logger.error(f"LEDGAR download failed: {e}")
        results["ledgar"] = 0

    # MAUD from Atticus Project (25K+ merger agreement clauses)
    try:
        results["maud"] = download_maud()
    except Exception as e:
        logger.error(f"MAUD download failed: {e}")
        results["maud"] = 0

    # ContractNLI (7K contract provisions)
    try:
        results["contract_nli"] = download_contract_nli()
    except Exception as e:
        logger.error(f"ContractNLI download failed: {e}")
        results["contract_nli"] = 0

    # InsuranceQA v2 (21K+ Q&A pairs)
    try:
        results["insurance_qa"] = download_insurance_qa()
    except Exception as e:
        logger.error(f"InsuranceQA download failed: {e}")
        results["insurance_qa"] = 0

    print("\n" + "=" * 50)
    print("DATASET DOWNLOAD SUMMARY")
    print("=" * 50)
    for name, count in results.items():
        print(f"  {name}: {count} records")
    print(f"  Total: {sum(results.values())} records")
    print(f"  Output dir: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
