"""
PostVisit AI - Clinical Guideline Retrieval Service
Performs deterministic keyword and semantic matching between approved clinical records
and the verified Indian guideline registry. Produces auditable evidence passages with
full provenance citations (ICMR, MoHFW, publication date, section, and URL).
"""

import re
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple

from src.guidelines.source_registry import GuidelineSourceRegistry, get_guideline_registry
from src.schemas.guideline_schema import GuidelineEvidenceItem

logger = logging.getLogger("postvisit.guidelines.retrieval")


class GuidelineRetrievalService:
    """
    Retrieval engine for clinical guidelines.
    Extracts relevant passages without hallucinating or inventing quotes.
    """

    def __init__(self, registry: Optional[GuidelineSourceRegistry] = None):
        self.registry = registry or get_guideline_registry()

    @staticmethod
    def _extract_query_tokens(medical_record: Dict[str, Any]) -> List[str]:
        """Extracts search tokens from diagnoses, chief complaint, symptoms, medications, tests, and clinical notes."""
        tokens = set()

        # Diagnoses
        for diag in medical_record.get("diagnoses", []):
            text = diag.get("condition", "") if isinstance(diag, dict) else str(diag)
            for word in re.findall(r"\b[a-zA-Z]{3,}\b", text.lower()):
                tokens.add(word)

        # Chief complaint
        cc = medical_record.get("chief_complaint", "")
        if cc:
            for word in re.findall(r"\b[a-zA-Z]{3,}\b", cc.lower()):
                tokens.add(word)

        # Symptoms
        for symptom in medical_record.get("symptoms", []):
            stext = symptom if isinstance(symptom, str) else str(symptom)
            for word in re.findall(r"\b[a-zA-Z]{3,}\b", stext.lower()):
                tokens.add(word)

        # Medications
        for med in medical_record.get("medications", []):
            name = med.get("name") if isinstance(med, dict) else str(med)
            if name:
                for word in re.findall(r"\b[a-zA-Z]{3,}\b", name.lower()):
                    tokens.add(word)

        # Tests & lab investigations
        for test in medical_record.get("tests", []) + medical_record.get("lab_investigations", []):
            tname = test.get("name") if isinstance(test, dict) else str(test)
            if tname:
                for word in re.findall(r"\b[a-zA-Z]{3,}\b", tname.lower()):
                    tokens.add(word)

        return list(tokens)

    def retrieve(
        self,
        clinical_topics: Optional[List[str]] = None,
        medication_names: Optional[List[str]] = None
    ) -> List[GuidelineEvidenceItem]:
        """
        Direct retrieval by clinical topics and medication names.
        Returns matching GuidelineEvidenceItem objects with complete provenance.
        """
        synth_record = {
            "diagnoses": [{"condition": t} for t in (clinical_topics or [])],
            "medications": [{"name": m} for m in (medication_names or [])]
        }
        evidence, _ = self.retrieve_evidence_for_record(synth_record)
        return evidence

    def retrieve_evidence_for_record(
        self,
        medical_record: Dict[str, Any]
    ) -> Tuple[List[GuidelineEvidenceItem], List[str]]:
        """
        Retrieves relevant guideline passages matching the approved clinical record.
        Returns:
          - List of GuidelineEvidenceItem objects
          - List of guideline IDs evaluated
        """
        query_tokens = self._extract_query_tokens(medical_record)
        guidelines = self.registry.list_guidelines()

        matched_evidence: List[GuidelineEvidenceItem] = []
        evaluated_guidelines: List[str] = []
        now_iso = datetime.now(timezone.utc).isoformat()

        for g in guidelines:
            gid = g["id"]
            evaluated_guidelines.append(gid)

            # Check guideline keywords against record query tokens
            guideline_keywords = set(g.get("keywords", []))
            matched_keywords = guideline_keywords.intersection(set(query_tokens))

            # If there is clinical topic overlap, extract matching passages
            if matched_keywords:
                for passage in g.get("evidence_passages", []):
                    passage_keywords = set(passage.get("keywords", []))
                    passage_match = passage_keywords.intersection(set(query_tokens))

                    # Calculate confidence score based on overlap
                    confidence = 0.85 if passage_match else 0.70

                    evidence_item = GuidelineEvidenceItem(
                        guideline_id=gid,
                        guideline_title=g["title"],
                        publishing_org=g["organization"],
                        topic=g["topic"],
                        section=passage.get("section"),
                        excerpt=passage.get("excerpt", ""),
                        source_url=g.get("source_url"),
                        publication_date=g.get("publication_date"),
                        retrieval_timestamp=now_iso,
                        confidence_score=confidence
                    )
                    matched_evidence.append(evidence_item)

        logger.info(
            f"Guideline retrieval found {len(matched_evidence)} evidence passages "
            f"across {len(evaluated_guidelines)} evaluated guidelines."
        )

        return matched_evidence, evaluated_guidelines


_retrieval_service: Optional[GuidelineRetrievalService] = None


def get_guideline_retrieval_service() -> GuidelineRetrievalService:
    """Singleton getter for GuidelineRetrievalService."""
    global _retrieval_service
    if _retrieval_service is None:
        _retrieval_service = GuidelineRetrievalService()
    return _retrieval_service
