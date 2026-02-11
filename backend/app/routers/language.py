"""
Language & Translation Router

Endpoints for:
- Getting supported languages
- Translating content
- Getting user language preferences
- Managing translated clauses
"""

from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User, SupportedLanguage
from app.services.translation_service import (
    get_translation_service,
    TranslationService,
    INSURANCE_TERMINOLOGY,
    DOCUMENT_SECTION_HEADERS
)
from app.data.clause_service import get_clause_service, ClauseService

router = APIRouter()


# =============================================================================
# Schemas
# =============================================================================

class LanguageInfo(BaseModel):
    """Information about a supported language."""
    code: str
    name: str
    native_name: str
    rtl: bool


class TranslateRequest(BaseModel):
    """Request to translate text."""
    text: str
    target_language: SupportedLanguage
    context: str = "insurance"


class TranslateResponse(BaseModel):
    """Response with translated text."""
    original: str
    translated: str
    target_language: str
    source_language: str = "en"


class TranslateClausesRequest(BaseModel):
    """Request to translate multiple clauses."""
    clause_ids: List[str]
    target_language: SupportedLanguage


class TerminologyEntry(BaseModel):
    """An insurance terminology entry with translations."""
    term: str
    translations: dict


class UpdateLanguageRequest(BaseModel):
    """Request to update user's language preference."""
    language: SupportedLanguage


# =============================================================================
# Endpoints
# =============================================================================

@router.get("/supported", response_model=List[LanguageInfo])
async def get_supported_languages():
    """
    Get all supported languages.

    Returns a list of supported languages with their codes,
    names, and whether they are right-to-left.
    """
    translation_service = get_translation_service()
    languages = translation_service.get_all_supported_languages()
    return [LanguageInfo(**lang) for lang in languages]


@router.get("/terminology", response_model=List[TerminologyEntry])
async def get_insurance_terminology(
    language: Optional[SupportedLanguage] = Query(None, description="Filter by language"),
    limit: int = Query(50, ge=1, le=200)
):
    """
    Get insurance terminology dictionary.

    Returns the insurance terminology with translations
    for all supported languages or filtered by a specific language.
    """
    result = []
    for term, translations in list(INSURANCE_TERMINOLOGY.items())[:limit]:
        if language:
            filtered_translations = {
                "en": translations.get("en", term),
                language.value: translations.get(language.value, term)
            }
            result.append(TerminologyEntry(term=term, translations=filtered_translations))
        else:
            result.append(TerminologyEntry(term=term, translations=translations))
    return result


@router.get("/section-headers")
async def get_section_headers(
    language: SupportedLanguage = Query(SupportedLanguage.ENGLISH)
):
    """
    Get document section headers for a specific language.

    Returns localized section headers used in generated documents.
    """
    result = {}
    for section_id, translations in DOCUMENT_SECTION_HEADERS.items():
        result[section_id] = translations.get(language.value, translations.get("en", section_id))
    return result


@router.post("/translate", response_model=TranslateResponse)
async def translate_text(
    request: TranslateRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Translate text to the specified language.

    Uses AI translation with insurance-specific context
    and proper terminology.
    """
    translation_service = get_translation_service()

    translated = await translation_service.translate_text(
        text=request.text,
        target_language=request.target_language,
        context=request.context
    )

    return TranslateResponse(
        original=request.text,
        translated=translated,
        target_language=request.target_language.value
    )


@router.get("/clauses/all")
async def get_all_clauses_translated(
    language: SupportedLanguage = Query(SupportedLanguage.ENGLISH),
    limit: int = Query(100, ge=1, le=500),
    current_user: User = Depends(get_current_user)
):
    """
    Get all available clauses, optionally translated.

    Returns all clauses from the clause library.
    """
    clause_service = get_clause_service()

    # Get all clauses
    clauses = clause_service.get_all_clauses()[:limit]

    # Translate if needed
    if language != SupportedLanguage.ENGLISH:
        clauses = await clause_service.get_clauses_translated(clauses, language)

    return {
        "language": language.value,
        "count": len(clauses),
        "total_available": len(clause_service.get_all_clauses()),
        "clauses": clauses
    }


@router.get("/clauses/{category}")
async def get_clauses_translated(
    category: str,
    language: SupportedLanguage = Query(SupportedLanguage.ENGLISH),
    limit: int = Query(50, ge=1, le=500),
    current_user: User = Depends(get_current_user)
):
    """
    Get clauses by category, translated to the specified language.

    Uses AI translation with insurance terminology preservation.
    """
    clause_service = get_clause_service()

    # Get clauses
    clauses = clause_service.get_clauses_by_category(category)[:limit]

    if not clauses:
        raise HTTPException(404, f"Category '{category}' not found or has no clauses")

    # Translate if needed
    if language != SupportedLanguage.ENGLISH:
        clauses = await clause_service.get_clauses_translated(clauses, language)

    return {
        "category": category,
        "language": language.value,
        "count": len(clauses),
        "clauses": clauses
    }


@router.get("/clauses")
async def search_clauses_translated(
    query: str = Query(..., min_length=2),
    language: SupportedLanguage = Query(SupportedLanguage.ENGLISH),
    categories: Optional[str] = Query(None, description="Comma-separated category IDs"),
    limit: int = Query(50, ge=1, le=500),
    current_user: User = Depends(get_current_user)
):
    """
    Search clauses and return results translated to the specified language.
    """
    clause_service = get_clause_service()

    # Parse categories
    category_list = None
    if categories:
        category_list = [c.strip() for c in categories.split(",")]

    # Search clauses
    clauses = clause_service.search_clauses(query, category_list)[:limit]

    # Translate if needed
    if language != SupportedLanguage.ENGLISH and clauses:
        clauses = await clause_service.get_clauses_translated(clauses, language)

    return {
        "query": query,
        "language": language.value,
        "count": len(clauses),
        "clauses": clauses
    }


@router.get("/categories")
async def get_categories_translated(
    language: SupportedLanguage = Query(SupportedLanguage.ENGLISH)
):
    """
    Get all clause categories with localized names.
    """
    clause_service = get_clause_service()
    return clause_service.get_categories_translated(language)


@router.get("/user/preference")
async def get_user_language_preference(
    current_user: User = Depends(get_current_user)
):
    """
    Get the current user's language preference.
    """
    translation_service = get_translation_service()
    language_info = translation_service.get_language_info(current_user.preferred_language)

    return {
        "language": current_user.preferred_language.value,
        **language_info
    }


@router.put("/user/preference")
async def update_user_language_preference(
    request: UpdateLanguageRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update the current user's language preference.
    """
    current_user.preferred_language = request.language
    await db.commit()
    await db.refresh(current_user)

    translation_service = get_translation_service()
    language_info = translation_service.get_language_info(current_user.preferred_language)

    return {
        "message": "Language preference updated successfully",
        "language": current_user.preferred_language.value,
        **language_info
    }


@router.post("/batch-translate")
async def batch_translate_clauses(
    request: TranslateClausesRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Translate multiple clauses by their IDs.

    This endpoint is useful for translating specific clauses
    that have been selected for a document.
    """
    clause_service = get_clause_service()
    translation_service = get_translation_service()

    # Get all clauses and filter by IDs
    all_clauses = clause_service.get_all_clauses()
    selected_clauses = [c for c in all_clauses if c.get("id") in request.clause_ids]

    if not selected_clauses:
        raise HTTPException(404, "No clauses found with the provided IDs")

    # Translate
    if request.target_language != SupportedLanguage.ENGLISH:
        translated_clauses = await translation_service.translate_clauses_batch(
            selected_clauses,
            request.target_language
        )
    else:
        translated_clauses = selected_clauses

    return {
        "language": request.target_language.value,
        "count": len(translated_clauses),
        "clauses": translated_clauses
    }


@router.get("/terminology/{term}")
async def get_term_translation(
    term: str,
    language: SupportedLanguage = Query(SupportedLanguage.ENGLISH)
):
    """
    Get the translation of a specific insurance term.
    """
    translation_service = get_translation_service()
    translated = translation_service.get_terminology(term, language)

    return {
        "term": term,
        "language": language.value,
        "translation": translated,
        "is_exact_match": term.lower() in INSURANCE_TERMINOLOGY
    }
