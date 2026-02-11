"""
InstantRisk V2 - API Routers

This module exports all API routers for the application.
"""

from app.routers import auth, documents, assessments, extraction

__all__ = ["auth", "documents", "assessments", "extraction"]
