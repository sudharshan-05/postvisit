"""
PostVisit AI - Medical Guidelines Package
Provides source registry, retrieval, and evidence extraction for Indian clinical standards.
"""

from src.guidelines.source_registry import (
    GuidelineSourceRegistry,
    get_guideline_registry,
    CURATED_GUIDELINE_SOURCES
)
from src.guidelines.retrieval_service import (
    GuidelineRetrievalService,
    get_guideline_retrieval_service
)

__all__ = [
    "GuidelineSourceRegistry",
    "get_guideline_registry",
    "CURATED_GUIDELINE_SOURCES",
    "GuidelineRetrievalService",
    "get_guideline_retrieval_service",
]
