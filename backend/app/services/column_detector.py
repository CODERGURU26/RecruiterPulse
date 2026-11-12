import re
from typing import List, Dict, Any, Optional
import pandas as pd
from app.models.enums import StandardField


# Known aliases for fuzzy matching
ALIAS_MAP: Dict[StandardField, List[str]] = {
    StandardField.ACTIVITY_DATE: [
        "call date", "calling date", "activity date", "date", "created on",
        "timestamp", "log date", "calling_date", "call_date", "call_dt",
        "activity_date", "entry date", "dated"
    ],
    StandardField.CALL_STATUS: [
        "call status", "call outcome", "calling status", "connection status",
        "response", "disposition", "status", "result", "outcome", "call response",
        "feedback", "remark", "remarks", "calling remark", "calling remarks"
    ],
    StandardField.CANDIDATE_REF: [
        "candidate name", "applicant name", "candidate", "applicant", "name",
        "phone", "mobile", "contact", "contact number", "mobile number",
        "phone number", "lead name", "lead", "candidate_name", "candidate id"
    ],
    StandardField.JOB_ROLE: [
        "job role", "role", "position", "designation", "job title",
        "requirement", "profile", "technology", "skill", "opening",
        "job", "job_role", "client requirement"
    ]
}

# Value patterns for sample-based detection
STATUS_SAMPLE_KEYWORDS = {
    "rnr", "busy", "connected", "not connected", "switched off", "interested",
    "not interested", "screening", "l1", "interview", "call back", "disconnected",
    "wrong number", "spoke"
}


class ColumnDetector:
    """
    Analyzes raw spreadsheet headers and sample data rows to automatically
    detect and map standard recruitment fields with a confidence score.
    """

    @staticmethod
    def clean_header(header: str) -> str:
        """Standardizes header for matching: lowercase, strip punctuation & extra whitespace."""
        h = str(header).lower().strip()
        h = re.sub(r"[_\-\.]+", " ", h)
        h = re.sub(r"\s+", " ", h)
        return h

    @classmethod
    def detect_column(
        cls,
        header: str,
        sample_values: List[Any],
        target_field: StandardField
    ) -> float:
        """
        Calculates confidence score (0.0 to 1.0) that 'header' matches 'target_field'.
        Combines header exact/partial match with sample value inspection.
        """
        cleaned = cls.clean_header(header)
        aliases = ALIAS_MAP[target_field]
        confidence = 0.0

        # 1. Exact alias match
        if cleaned in aliases:
            confidence = 0.90
        # 2. Substring / partial match
        elif any(alias in cleaned or cleaned in alias for alias in aliases):
            confidence = 0.70

        # 3. Value-based verification / adjustment
        valid_samples = [str(v).strip() for v in sample_values if pd.notna(v) and str(v).strip() != ""]
        if not valid_samples:
            return confidence

        if target_field == StandardField.ACTIVITY_DATE:
            # Check if samples can be parsed as dates
            date_matches = 0
            for val in valid_samples[:10]:
                try:
                    pd.to_datetime(val, dayfirst=True)
                    date_matches += 1
                except Exception:
                    pass
            if date_matches >= max(1, len(valid_samples[:10]) // 2):
                confidence = max(confidence + 0.15, 0.85)

        elif target_field == StandardField.CALL_STATUS:
            # Check if samples match known call status phrases
            status_matches = sum(
                1 for val in valid_samples[:10]
                if any(kw in val.lower() for kw in STATUS_SAMPLE_KEYWORDS)
            )
            if status_matches > 0:
                confidence = max(confidence + 0.20, 0.88)

        elif target_field == StandardField.CANDIDATE_REF:
            # Check if samples look like names or phone numbers
            phone_matches = sum(
                1 for val in valid_samples[:10]
                if re.search(r"\b\d{10}\b|\b\d{5}\s\d{5}\b|\+\d{1,3}", val)
            )
            if phone_matches > 0:
                confidence = max(confidence + 0.20, 0.85)

        return min(round(confidence, 2), 1.0)

    @classmethod
    def analyze_dataframe(
        cls,
        df: pd.DataFrame,
        sample_size: int = 5
    ) -> Dict[StandardField, Dict[str, Any]]:
        """
        Analyzes an entire DataFrame and suggests best-match mappings for all standard fields.
        Returns:
            {
                StandardField.ACTIVITY_DATE: {
                    "source_column": "Calling Date",
                    "confidence": 0.95,
                    "sample_values": ["12/11/2026", "12/11/2026"],
                    "auto_confirmed": True
                },
                ...
            }
        """
        results: Dict[StandardField, Dict[str, Any]] = {}
        assigned_columns = set()

        # For each standard field, find the best matching source column
        for standard_field in StandardField:
            best_col: Optional[str] = None
            best_score = 0.0
            best_samples: List[Any] = []

            for col in df.columns:
                if col in assigned_columns:
                    continue

                samples = df[col].dropna().head(sample_size).tolist()
                score = cls.detect_column(col, samples, standard_field)

                if score > best_score:
                    best_score = score
                    best_col = col
                    best_samples = [str(s) for s in samples[:3]]

            if best_col and best_score >= 0.50:
                assigned_columns.add(best_col)
                results[standard_field] = {
                    "source_column": best_col,
                    "confidence": best_score,
                    "sample_values": best_samples,
                    "auto_confirmed": best_score >= 0.85  # Threshold from PRD v1.1
                }
            else:
                results[standard_field] = {
                    "source_column": None,
                    "confidence": 0.0,
                    "sample_values": [],
                    "auto_confirmed": False
                }

        return results

