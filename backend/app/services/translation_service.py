"""
InstantRisk V2 - Translation Service

Multi-language support for insurance content with:
1. AI-powered translation using OpenAI
2. Insurance-specific terminology dictionary
3. Caching for performance
4. Lloyd's/Insurance market terminology localization
"""

import json
import hashlib
import logging
from typing import Dict, Any, List, Optional
from functools import lru_cache
import asyncio

from app.config import settings
from app.models.user import SupportedLanguage

logger = logging.getLogger(__name__)


# =============================================================================
# INSURANCE TERMINOLOGY DICTIONARY
# Proper Lloyd's/Insurance market terminology in each language
# =============================================================================
INSURANCE_TERMINOLOGY: Dict[str, Dict[str, str]] = {
    # Core Insurance Terms
    "coverage": {
        "en": "coverage",
        "fr": "couverture",
        "de": "Deckung",
        "es": "cobertura",
        "it": "copertura",
        "pt": "cobertura",
        "nl": "dekking",
        "ar": "تغطية",
        "zh": "保险范围",
        "ja": "補償範囲"
    },
    "premium": {
        "en": "premium",
        "fr": "prime",
        "de": "Prämie",
        "es": "prima",
        "it": "premio",
        "pt": "prémio",
        "nl": "premie",
        "ar": "قسط",
        "zh": "保费",
        "ja": "保険料"
    },
    "deductible": {
        "en": "deductible",
        "fr": "franchise",
        "de": "Selbstbeteiligung",
        "es": "deducible",
        "it": "franchigia",
        "pt": "franquia",
        "nl": "eigen risico",
        "ar": "مبلغ قابل للخصم",
        "zh": "免赔额",
        "ja": "免責金額"
    },
    "policyholder": {
        "en": "policyholder",
        "fr": "assuré",
        "de": "Versicherungsnehmer",
        "es": "asegurado",
        "it": "contraente",
        "pt": "segurado",
        "nl": "verzekeringnemer",
        "ar": "حامل الوثيقة",
        "zh": "投保人",
        "ja": "保険契約者"
    },
    "insured": {
        "en": "insured",
        "fr": "assuré",
        "de": "Versicherter",
        "es": "asegurado",
        "it": "assicurato",
        "pt": "segurado",
        "nl": "verzekerde",
        "ar": "المؤمن عليه",
        "zh": "被保险人",
        "ja": "被保険者"
    },
    "insurer": {
        "en": "insurer",
        "fr": "assureur",
        "de": "Versicherer",
        "es": "asegurador",
        "it": "assicuratore",
        "pt": "segurador",
        "nl": "verzekeraar",
        "ar": "شركة التأمين",
        "zh": "保险人",
        "ja": "保険者"
    },
    "underwriter": {
        "en": "underwriter",
        "fr": "souscripteur",
        "de": "Underwriter",
        "es": "suscriptor",
        "it": "sottoscrittore",
        "pt": "subscritor",
        "nl": "acceptant",
        "ar": "ضامن الاكتتاب",
        "zh": "承保人",
        "ja": "アンダーライター"
    },
    "broker": {
        "en": "broker",
        "fr": "courtier",
        "de": "Makler",
        "es": "corredor",
        "it": "broker",
        "pt": "corretor",
        "nl": "makelaar",
        "ar": "وسيط",
        "zh": "经纪人",
        "ja": "ブローカー"
    },
    "claim": {
        "en": "claim",
        "fr": "sinistre",
        "de": "Schaden",
        "es": "siniestro",
        "it": "sinistro",
        "pt": "sinistro",
        "nl": "claim",
        "ar": "مطالبة",
        "zh": "索赔",
        "ja": "クレーム"
    },
    "limit of liability": {
        "en": "limit of liability",
        "fr": "limite de responsabilité",
        "de": "Haftungshöchstgrenze",
        "es": "límite de responsabilidad",
        "it": "limite di responsabilità",
        "pt": "limite de responsabilidade",
        "nl": "aansprakelijkheidslimiet",
        "ar": "حد المسؤولية",
        "zh": "责任限额",
        "ja": "責任限度額"
    },
    "sum insured": {
        "en": "sum insured",
        "fr": "somme assurée",
        "de": "Versicherungssumme",
        "es": "suma asegurada",
        "it": "somma assicurata",
        "pt": "capital seguro",
        "nl": "verzekerd bedrag",
        "ar": "مبلغ التأمين",
        "zh": "保险金额",
        "ja": "保険金額"
    },
    "excess": {
        "en": "excess",
        "fr": "franchise",
        "de": "Selbstbehalt",
        "es": "franquicia",
        "it": "franchigia",
        "pt": "franquia",
        "nl": "eigen risico",
        "ar": "المبلغ الزائد",
        "zh": "自负额",
        "ja": "自己負担額"
    },
    "endorsement": {
        "en": "endorsement",
        "fr": "avenant",
        "de": "Nachtrag",
        "es": "endoso",
        "it": "appendice",
        "pt": "averbamento",
        "nl": "aanhangsel",
        "ar": "ملحق",
        "zh": "批单",
        "ja": "裏書"
    },
    "exclusion": {
        "en": "exclusion",
        "fr": "exclusion",
        "de": "Ausschluss",
        "es": "exclusión",
        "it": "esclusione",
        "pt": "exclusão",
        "nl": "uitsluiting",
        "ar": "استثناء",
        "zh": "除外责任",
        "ja": "免責事項"
    },
    "subrogation": {
        "en": "subrogation",
        "fr": "subrogation",
        "de": "Subrogation",
        "es": "subrogación",
        "it": "surrogazione",
        "pt": "sub-rogação",
        "nl": "subrogatie",
        "ar": "الحلول",
        "zh": "代位求偿",
        "ja": "代位"
    },
    "reinsurance": {
        "en": "reinsurance",
        "fr": "réassurance",
        "de": "Rückversicherung",
        "es": "reaseguro",
        "it": "riassicurazione",
        "pt": "resseguro",
        "nl": "herverzekering",
        "ar": "إعادة التأمين",
        "zh": "再保险",
        "ja": "再保険"
    },
    "inception date": {
        "en": "inception date",
        "fr": "date d'effet",
        "de": "Vertragsbeginn",
        "es": "fecha de inicio",
        "it": "data di decorrenza",
        "pt": "data de início",
        "nl": "ingangsdatum",
        "ar": "تاريخ البدء",
        "zh": "生效日期",
        "ja": "保険開始日"
    },
    "expiry date": {
        "en": "expiry date",
        "fr": "date d'expiration",
        "de": "Ablaufdatum",
        "es": "fecha de vencimiento",
        "it": "data di scadenza",
        "pt": "data de vencimento",
        "nl": "einddatum",
        "ar": "تاريخ الانتهاء",
        "zh": "到期日期",
        "ja": "満期日"
    },
    "policy": {
        "en": "policy",
        "fr": "police",
        "de": "Police",
        "es": "póliza",
        "it": "polizza",
        "pt": "apólice",
        "nl": "polis",
        "ar": "وثيقة",
        "zh": "保单",
        "ja": "保険証券"
    },
    "certificate of insurance": {
        "en": "certificate of insurance",
        "fr": "attestation d'assurance",
        "de": "Versicherungszertifikat",
        "es": "certificado de seguro",
        "it": "certificato di assicurazione",
        "pt": "certificado de seguro",
        "nl": "verzekeringscertificaat",
        "ar": "شهادة التأمين",
        "zh": "保险证书",
        "ja": "保険証明書"
    },
    "slip": {
        "en": "slip",
        "fr": "bordereau",
        "de": "Slip",
        "es": "slip",
        "it": "slip",
        "pt": "slip",
        "nl": "slip",
        "ar": "قسيمة",
        "zh": "投保单",
        "ja": "スリップ"
    },
    "warranty": {
        "en": "warranty",
        "fr": "garantie",
        "de": "Gewährleistung",
        "es": "garantía",
        "it": "garanzia",
        "pt": "garantia",
        "nl": "garantie",
        "ar": "ضمان",
        "zh": "保证条款",
        "ja": "担保条項"
    },
    "condition": {
        "en": "condition",
        "fr": "condition",
        "de": "Bedingung",
        "es": "condición",
        "it": "condizione",
        "pt": "condição",
        "nl": "voorwaarde",
        "ar": "شرط",
        "zh": "条件",
        "ja": "条件"
    },
    "syndicate": {
        "en": "syndicate",
        "fr": "syndicat",
        "de": "Syndikat",
        "es": "sindicato",
        "it": "sindacato",
        "pt": "sindicato",
        "nl": "syndicaat",
        "ar": "نقابة",
        "zh": "辛迪加",
        "ja": "シンジケート"
    },
    "loss": {
        "en": "loss",
        "fr": "perte",
        "de": "Verlust",
        "es": "pérdida",
        "it": "perdita",
        "pt": "perda",
        "nl": "verlies",
        "ar": "خسارة",
        "zh": "损失",
        "ja": "損失"
    },
    "peril": {
        "en": "peril",
        "fr": "péril",
        "de": "Gefahr",
        "es": "peligro",
        "it": "pericolo",
        "pt": "perigo",
        "nl": "gevaar",
        "ar": "خطر",
        "zh": "风险",
        "ja": "危険"
    },
    "risk": {
        "en": "risk",
        "fr": "risque",
        "de": "Risiko",
        "es": "riesgo",
        "it": "rischio",
        "pt": "risco",
        "nl": "risico",
        "ar": "مخاطر",
        "zh": "风险",
        "ja": "リスク"
    },
    # Lloyd's-specific terms
    "unique market reference": {
        "en": "unique market reference",
        "fr": "référence unique du marché",
        "de": "einzigartige Marktreferenz",
        "es": "referencia única del mercado",
        "it": "riferimento unico di mercato",
        "pt": "referência única de mercado",
        "nl": "unieke marktreferentie",
        "ar": "مرجع السوق الفريد",
        "zh": "唯一市场参考号",
        "ja": "固有市場参照番号"
    },
    "leading underwriter": {
        "en": "leading underwriter",
        "fr": "apériteur",
        "de": "Führender Underwriter",
        "es": "suscriptor líder",
        "it": "sottoscrittore leader",
        "pt": "subscritor líder",
        "nl": "leidende acceptant",
        "ar": "الضامن الرئيسي",
        "zh": "首席承保人",
        "ja": "リードアンダーライター"
    },
    "following market": {
        "en": "following market",
        "fr": "marché suiveur",
        "de": "Folgender Markt",
        "es": "mercado seguidor",
        "it": "mercato seguente",
        "pt": "mercado seguidor",
        "nl": "volgende markt",
        "ar": "السوق التابع",
        "zh": "跟随市场",
        "ja": "フォローイングマーケット"
    },
    "signed line": {
        "en": "signed line",
        "fr": "ligne signée",
        "de": "gezeichnete Linie",
        "es": "línea firmada",
        "it": "linea firmata",
        "pt": "linha assinada",
        "nl": "getekende lijn",
        "ar": "الخط الموقع",
        "zh": "签署份额",
        "ja": "引受割合"
    },
    "written line": {
        "en": "written line",
        "fr": "ligne écrite",
        "de": "gezeichnete Quote",
        "es": "línea escrita",
        "it": "linea scritta",
        "pt": "linha escrita",
        "nl": "geschreven lijn",
        "ar": "الخط المكتوب",
        "zh": "书面份额",
        "ja": "書面引受割合"
    },
}

# Section headers for document generation
DOCUMENT_SECTION_HEADERS: Dict[str, Dict[str, str]] = {
    "risk_details": {
        "en": "RISK DETAILS",
        "fr": "DÉTAILS DU RISQUE",
        "de": "RISIKODETAILS",
        "es": "DETALLES DEL RIESGO",
        "it": "DETTAGLI DEL RISCHIO",
        "pt": "DETALHES DO RISCO",
        "nl": "RISICO DETAILS",
        "ar": "تفاصيل المخاطر",
        "zh": "风险详情",
        "ja": "リスク詳細"
    },
    "period": {
        "en": "PERIOD",
        "fr": "PÉRIODE",
        "de": "ZEITRAUM",
        "es": "PERÍODO",
        "it": "PERIODO",
        "pt": "PERÍODO",
        "nl": "PERIODE",
        "ar": "الفترة",
        "zh": "保险期间",
        "ja": "保険期間"
    },
    "interest": {
        "en": "INTEREST",
        "fr": "INTÉRÊT ASSURÉ",
        "de": "VERSICHERTES INTERESSE",
        "es": "INTERÉS",
        "it": "INTERESSE",
        "pt": "INTERESSE",
        "nl": "BELANG",
        "ar": "المصلحة",
        "zh": "保险标的",
        "ja": "被保険利益"
    },
    "limits": {
        "en": "LIMITS OF LIABILITY / SUMS INSURED",
        "fr": "LIMITES DE RESPONSABILITÉ / SOMMES ASSURÉES",
        "de": "HAFTUNGSGRENZEN / VERSICHERUNGSSUMMEN",
        "es": "LÍMITES DE RESPONSABILIDAD / SUMAS ASEGURADAS",
        "it": "LIMITI DI RESPONSABILITÀ / SOMME ASSICURATE",
        "pt": "LIMITES DE RESPONSABILIDADE / CAPITAIS SEGUROS",
        "nl": "AANSPRAKELIJKHEIDSGRENZEN / VERZEKERDE BEDRAGEN",
        "ar": "حدود المسؤولية / المبالغ المؤمنة",
        "zh": "责任限额 / 保险金额",
        "ja": "責任限度額 / 保険金額"
    },
    "premium": {
        "en": "PREMIUM",
        "fr": "PRIME",
        "de": "PRÄMIE",
        "es": "PRIMA",
        "it": "PREMIO",
        "pt": "PRÉMIO",
        "nl": "PREMIE",
        "ar": "القسط",
        "zh": "保费",
        "ja": "保険料"
    },
    "deductible": {
        "en": "DEDUCTIBLE / EXCESS",
        "fr": "FRANCHISE",
        "de": "SELBSTBETEILIGUNG / SELBSTBEHALT",
        "es": "DEDUCIBLE / FRANQUICIA",
        "it": "FRANCHIGIA / SCOPERTO",
        "pt": "FRANQUIA",
        "nl": "EIGEN RISICO",
        "ar": "المبلغ القابل للخصم / الزائد",
        "zh": "免赔额",
        "ja": "免責金額"
    },
    "conditions": {
        "en": "CONDITIONS",
        "fr": "CONDITIONS",
        "de": "BEDINGUNGEN",
        "es": "CONDICIONES",
        "it": "CONDIZIONI",
        "pt": "CONDIÇÕES",
        "nl": "VOORWAARDEN",
        "ar": "الشروط",
        "zh": "条款",
        "ja": "条件"
    },
    "clauses": {
        "en": "CLAUSES",
        "fr": "CLAUSES",
        "de": "KLAUSELN",
        "es": "CLÁUSULAS",
        "it": "CLAUSOLE",
        "pt": "CLÁUSULAS",
        "nl": "CLAUSULES",
        "ar": "البنود",
        "zh": "条款",
        "ja": "約款"
    },
    "exclusions": {
        "en": "EXCLUSIONS",
        "fr": "EXCLUSIONS",
        "de": "AUSSCHLÜSSE",
        "es": "EXCLUSIONES",
        "it": "ESCLUSIONI",
        "pt": "EXCLUSÕES",
        "nl": "UITSLUITINGEN",
        "ar": "الاستثناءات",
        "zh": "除外责任",
        "ja": "免責事項"
    },
    "security": {
        "en": "SECURITY",
        "fr": "SÉCURITÉ / ASSUREURS",
        "de": "SICHERHEIT / VERSICHERER",
        "es": "SEGURIDAD / ASEGURADORES",
        "it": "SICUREZZA / ASSICURATORI",
        "pt": "SEGURANÇA / SEGURADORES",
        "nl": "ZEKERHEID / VERZEKERAARS",
        "ar": "الأمان / شركات التأمين",
        "zh": "承保方",
        "ja": "引受保険会社"
    },
    "broker": {
        "en": "BROKER",
        "fr": "COURTIER",
        "de": "MAKLER",
        "es": "CORREDOR",
        "it": "BROKER",
        "pt": "CORRETOR",
        "nl": "MAKELAAR",
        "ar": "الوسيط",
        "zh": "经纪人",
        "ja": "ブローカー"
    },
}


class TranslationService:
    """
    Translation service for insurance content.

    Features:
    - AI-powered translation using OpenAI
    - Insurance terminology dictionary
    - Document section localization
    - Clause translation with caching
    """

    def __init__(self):
        self.openai_api_key = settings.openai_api_key
        self.model = settings.openai_model
        self._translation_cache: Dict[str, str] = {}

    def _cache_key(self, text: str, target_lang: str) -> str:
        """Generate cache key for translation."""
        text_hash = hashlib.md5(text.encode(), usedforsecurity=False).hexdigest()[:16]
        return f"{target_lang}:{text_hash}"

    def get_terminology(self, term: str, language: SupportedLanguage) -> str:
        """
        Get localized insurance terminology.

        Args:
            term: English term to translate
            language: Target language

        Returns:
            Localized term or original if not found
        """
        term_lower = term.lower()
        if term_lower in INSURANCE_TERMINOLOGY:
            return INSURANCE_TERMINOLOGY[term_lower].get(
                language.value,
                INSURANCE_TERMINOLOGY[term_lower].get("en", term)
            )
        return term

    def get_section_header(self, section_id: str, language: SupportedLanguage) -> str:
        """
        Get localized section header for documents.

        Args:
            section_id: Section identifier
            language: Target language

        Returns:
            Localized section header
        """
        if section_id in DOCUMENT_SECTION_HEADERS:
            return DOCUMENT_SECTION_HEADERS[section_id].get(
                language.value,
                DOCUMENT_SECTION_HEADERS[section_id].get("en", section_id.upper())
            )
        return section_id.upper().replace("_", " ")

    def localize_insurance_terms(self, text: str, language: SupportedLanguage) -> str:
        """
        Replace English insurance terms with localized versions.

        Args:
            text: Text containing insurance terms
            language: Target language

        Returns:
            Text with localized terms
        """
        if language == SupportedLanguage.ENGLISH:
            return text

        result = text
        # Sort by length descending to replace longer phrases first
        sorted_terms = sorted(INSURANCE_TERMINOLOGY.keys(), key=len, reverse=True)

        for term in sorted_terms:
            localized = INSURANCE_TERMINOLOGY[term].get(language.value)
            if localized:
                # Case-insensitive replacement
                import re
                pattern = re.compile(re.escape(term), re.IGNORECASE)
                result = pattern.sub(localized, result)

        return result

    async def translate_text(
        self,
        text: str,
        target_language: SupportedLanguage,
        context: str = "insurance",
        use_cache: bool = True
    ) -> str:
        """
        Translate text using AI with insurance context.

        Args:
            text: Text to translate
            target_language: Target language
            context: Domain context (default: insurance)
            use_cache: Whether to use translation cache

        Returns:
            Translated text
        """
        if target_language == SupportedLanguage.ENGLISH:
            return text

        # Check cache
        cache_key = self._cache_key(text, target_language.value)
        if use_cache and cache_key in self._translation_cache:
            return self._translation_cache[cache_key]

        # Use AI translation
        translated = await self._ai_translate(text, target_language, context)

        # Cache result
        if use_cache:
            self._translation_cache[cache_key] = translated

        return translated

    async def _ai_translate(
        self,
        text: str,
        target_language: SupportedLanguage,
        context: str
    ) -> str:
        """
        Use OpenAI to translate text with insurance context.
        """
        if not self.openai_api_key:
            logger.warning("No OpenAI API key configured, returning original text")
            # Fallback: just localize terminology
            return self.localize_insurance_terms(text, target_language)

        try:
            import openai
            client = openai.AsyncOpenAI(api_key=self.openai_api_key)

            language_names = {
                "en": "English",
                "fr": "French",
                "de": "German",
                "es": "Spanish",
                "it": "Italian",
                "pt": "Portuguese",
                "nl": "Dutch",
                "ar": "Arabic",
                "zh": "Chinese (Simplified)",
                "ja": "Japanese"
            }

            target_name = language_names.get(target_language.value, target_language.value)

            # Build terminology context
            terminology_context = []
            for term, translations in list(INSURANCE_TERMINOLOGY.items())[:20]:
                if target_language.value in translations:
                    terminology_context.append(
                        f"- {term} -> {translations[target_language.value]}"
                    )

            prompt = f"""Translate the following {context} text to {target_name}.
Use proper insurance/Lloyd's market terminology. Here are key term translations:

{chr(10).join(terminology_context)}

IMPORTANT:
- Use formal, professional insurance language
- Maintain the original formatting and structure
- Keep proper nouns, clause references (e.g., LMA3100), and UMR numbers unchanged
- Use the terminology mappings provided above

Text to translate:
{text}

Translation:"""

            response = await client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a professional insurance translator specializing in Lloyd's of London and international insurance markets. You translate with precision, maintaining legal accuracy and using proper insurance terminology."
                    },
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=4000
            )

            return response.choices[0].message.content.strip()

        except Exception as e:
            logger.error(f"AI translation error: {e}")
            # Fallback: localize terminology only
            return self.localize_insurance_terms(text, target_language)

    async def translate_clause(
        self,
        clause: Dict[str, Any],
        target_language: SupportedLanguage
    ) -> Dict[str, Any]:
        """
        Translate an insurance clause to the target language.

        Args:
            clause: Clause dictionary with text, name, description
            target_language: Target language

        Returns:
            Clause with translated fields
        """
        if target_language == SupportedLanguage.ENGLISH:
            return clause

        translated_clause = clause.copy()

        # Translate text fields
        if clause.get("text"):
            translated_clause["text"] = await self.translate_text(
                clause["text"],
                target_language,
                context="insurance clause"
            )
            translated_clause["original_text"] = clause["text"]

        if clause.get("name"):
            translated_clause["name"] = await self.translate_text(
                clause["name"],
                target_language,
                context="insurance clause title"
            )
            translated_clause["original_name"] = clause["name"]

        if clause.get("description"):
            translated_clause["description"] = await self.translate_text(
                clause["description"],
                target_language,
                context="insurance description"
            )

        # Mark as translated
        translated_clause["translated_to"] = target_language.value
        translated_clause["translation_source"] = "ai"

        return translated_clause

    async def translate_clauses_batch(
        self,
        clauses: List[Dict[str, Any]],
        target_language: SupportedLanguage,
        max_concurrent: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Translate multiple clauses concurrently.

        Args:
            clauses: List of clauses to translate
            target_language: Target language
            max_concurrent: Maximum concurrent translations

        Returns:
            List of translated clauses
        """
        if target_language == SupportedLanguage.ENGLISH:
            return clauses

        # Create semaphore for rate limiting
        semaphore = asyncio.Semaphore(max_concurrent)

        async def translate_with_limit(clause):
            async with semaphore:
                return await self.translate_clause(clause, target_language)

        tasks = [translate_with_limit(clause) for clause in clauses]
        return await asyncio.gather(*tasks)

    async def translate_document_sections(
        self,
        sections: List[Dict[str, Any]],
        target_language: SupportedLanguage
    ) -> List[Dict[str, Any]]:
        """
        Translate document sections for PDF generation.

        Args:
            sections: Document sections
            target_language: Target language

        Returns:
            Translated sections
        """
        if target_language == SupportedLanguage.ENGLISH:
            return sections

        translated_sections = []

        for section in sections:
            translated = section.copy()

            # Translate section title
            section_id = section.get("section_id", "")
            if section_id in DOCUMENT_SECTION_HEADERS:
                translated["title"] = DOCUMENT_SECTION_HEADERS[section_id].get(
                    target_language.value,
                    section.get("title", "")
                )
            elif section.get("title"):
                translated["title"] = await self.translate_text(
                    section["title"],
                    target_language,
                    context="document section header"
                )

            # Translate field labels and values
            if section.get("fields"):
                translated_fields = {}
                for field_name, value in section["fields"].items():
                    if isinstance(value, str) and value:
                        # Translate non-empty string values
                        translated_fields[field_name] = await self.translate_text(
                            value,
                            target_language,
                            context="insurance document field"
                        )
                    elif isinstance(value, list):
                        # Translate list items
                        translated_list = []
                        for item in value:
                            if isinstance(item, str):
                                translated_list.append(
                                    await self.translate_text(
                                        item,
                                        target_language,
                                        context="insurance document"
                                    )
                                )
                            elif isinstance(item, dict):
                                translated_item = {}
                                for k, v in item.items():
                                    if isinstance(v, str):
                                        translated_item[k] = await self.translate_text(
                                            v,
                                            target_language,
                                            context="insurance document"
                                        )
                                    else:
                                        translated_item[k] = v
                                translated_list.append(translated_item)
                            else:
                                translated_list.append(item)
                        translated_fields[field_name] = translated_list
                    else:
                        translated_fields[field_name] = value

                translated["fields"] = translated_fields

            translated_sections.append(translated)

        return translated_sections

    def get_language_info(self, language: SupportedLanguage) -> Dict[str, Any]:
        """Get information about a supported language."""
        language_info = {
            "en": {"name": "English", "native_name": "English", "rtl": False},
            "fr": {"name": "French", "native_name": "Français", "rtl": False},
            "de": {"name": "German", "native_name": "Deutsch", "rtl": False},
            "es": {"name": "Spanish", "native_name": "Español", "rtl": False},
            "it": {"name": "Italian", "native_name": "Italiano", "rtl": False},
            "pt": {"name": "Portuguese", "native_name": "Português", "rtl": False},
            "nl": {"name": "Dutch", "native_name": "Nederlands", "rtl": False},
            "ar": {"name": "Arabic", "native_name": "العربية", "rtl": True},
            "zh": {"name": "Chinese", "native_name": "中文", "rtl": False},
            "ja": {"name": "Japanese", "native_name": "日本語", "rtl": False},
        }
        return language_info.get(language.value, {"name": language.value, "native_name": language.value, "rtl": False})

    def get_all_supported_languages(self) -> List[Dict[str, Any]]:
        """Get list of all supported languages with info."""
        return [
            {
                "code": lang.value,
                **self.get_language_info(lang)
            }
            for lang in SupportedLanguage
        ]


# Singleton instance
translation_service = TranslationService()


def get_translation_service() -> TranslationService:
    """Get the singleton translation service instance."""
    return translation_service
