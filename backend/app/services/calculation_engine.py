from datetime import date, datetime
from typing import Dict, List, Any, Optional, Set, Tuple
import re
import pandas as pd
from app.models.enums import StandardField, CallCategory


class RecruiterMetricsResult:
    """Encapsulates aggregated daily metrics for a recruiter."""
    def __init__(
        self,
        target_date: date,
        connected_calls: int,
        not_connected_calls: int,
        total_calls: int,
        connected_rate: float,
        job_roles: List[str],
        unmapped_statuses: List[str],
        duplicates_removed: int,
        total_rows_processed: int
    ):
        self.target_date = target_date
        self.connected_calls = connected_calls
        self.not_connected_calls = not_connected_calls
        self.total_calls = total_calls
        self.connected_rate = connected_rate
        self.job_roles = job_roles
        self.unmapped_statuses = unmapped_statuses
        self.duplicates_removed = duplicates_removed
        self.total_rows_processed = total_rows_processed

    def to_dict(self) -> Dict[str, Any]:
        return {
            "target_date": self.target_date.isoformat(),
            "connected_calls": self.connected_calls,
            "not_connected_calls": self.not_connected_calls,
            "total_calls": self.total_calls,
            "connected_rate": self.connected_rate,
            "job_roles": self.job_roles,
            "unmapped_statuses": self.unmapped_statuses,
            "duplicates_removed": self.duplicates_removed,
            "total_rows_processed": self.total_rows_processed
        }


class CalculationEngine:
    """
    Stateless processing engine that:
    1. Parses in-memory DataFrame
    2. Filters activity by reporting date
    3. Deduplicates repetitive rows
    4. Categorizes call statuses
    5. Calculates daily metrics
    6. Strips all candidate PII (DPDP compliant)
    """

    @staticmethod
    def parse_date_series(series: pd.Series) -> pd.Series:
        """Fast vectorized parsing of heterogeneous date strings into standardized datetime objects."""
        s_clean = series.astype(str).str.strip()
        # 1. Vectorized mixed-format parsing with dayfirst=True for Indian conventions
        parsed = pd.to_datetime(s_clean, format="mixed", dayfirst=True, errors="coerce")
        # 2. Correct any YYYY-MM-DD or YYYY/MM/DD ISO rows where day/month might invert
        iso_mask = s_clean.str.match(r"^\d{4}[-/.]")
        if iso_mask.any():
            parsed.loc[iso_mask] = pd.to_datetime(s_clean[iso_mask], format="ISO8601", errors="coerce")
        return parsed



    @classmethod
    def calculate_recruiter_activity(
        cls,
        df: pd.DataFrame,
        column_mapping: Dict[StandardField, str],
        status_taxonomy: Dict[str, CallCategory],
        target_date: Optional[date] = None
    ) -> RecruiterMetricsResult:
        """
        Executes calling calculation pipeline on raw spreadsheet DataFrame.
        """
        if target_date is None:
            target_date = date.today()

        date_col = column_mapping.get(StandardField.ACTIVITY_DATE)
        status_col = column_mapping.get(StandardField.CALL_STATUS)
        candidate_col = column_mapping.get(StandardField.CANDIDATE_REF)
        role_col = column_mapping.get(StandardField.JOB_ROLE)

        if not status_col or status_col not in df.columns:
            raise ValueError(f"Call status column '{status_col}' not found in sheet.")

        # Drop entirely empty rows
        clean_df = df.dropna(how="all").copy()
        total_input_rows = len(clean_df)

        # 1. Date Filtering
        if date_col and date_col in clean_df.columns:
            clean_df["_parsed_date"] = cls.parse_date_series(clean_df[date_col])
            clean_df = clean_df.dropna(subset=["_parsed_date"])
            filtered_df = clean_df[clean_df["_parsed_date"].dt.date == target_date].copy()
        else:
            # If no date column is present, evaluate all rows for the given target date
            filtered_df = clean_df.copy()
        
        if filtered_df.empty:
            return RecruiterMetricsResult(
                target_date=target_date,
                connected_calls=0,
                not_connected_calls=0,
                total_calls=0,
                connected_rate=0.0,
                job_roles=[],
                unmapped_statuses=[],
                duplicates_removed=0,
                total_rows_processed=total_input_rows
            )

        # 2. Keep only rows that actually contain a call status.
        status_values = filtered_df[status_col].astype(str).str.strip().str.lower()
        filtered_df = filtered_df[
            filtered_df[status_col].notna()
            & ~status_values.isin(("", "nan", "none", "-"))
        ].copy()

        # 3. Deduplication Safeguard
        initial_filtered_count = len(filtered_df)
        if candidate_col and candidate_col in filtered_df.columns:
            filtered_df = filtered_df.drop_duplicates(
                subset=[candidate_col, status_col],
                keep="first"
            )
        
        duplicates_removed = initial_filtered_count - len(filtered_df)

        # 4. Status Classification & Metric Calculation
        connected_count = 0
        not_connected_count = 0
        unmapped_list: Set[str] = set()
        counted_rows = []
        ordered_taxonomy = sorted(
            status_taxonomy.items(),
            key=lambda item: len(item[0].strip()),
            reverse=True
        )

        for row_index, raw_val in filtered_df[status_col].items():
            cleaned_status = str(raw_val).strip().lower()

            # Look up in taxonomy
            category = status_taxonomy.get(cleaned_status)

            if category is None and re.search(r"\bnot\s+connected\b", cleaned_status):
                category = status_taxonomy.get("not connected", CallCategory.NOT_CONNECTED)

            # Prefer the most specific taxonomy phrase and don't match inside other words.
            if category is None:
                for taxonomy_term, cat in ordered_taxonomy:
                    term = taxonomy_term.strip().lower()
                    if term and re.search(rf"(?<!\w){re.escape(term)}(?!\w)", cleaned_status):
                        category = cat
                        break

            if category == CallCategory.CONNECTED:
                connected_count += 1
                counted_rows.append(row_index)
            elif category == CallCategory.NOT_CONNECTED:
                not_connected_count += 1
                counted_rows.append(row_index)
            elif category == CallCategory.IGNORED:
                pass  # Discard ignored rows (e.g. duplicate tags)
            else:
                # Unmapped status - alert MIS
                unmapped_list.add(str(raw_val).strip())
                # Default to not connected attempt for safety until confirmed
                not_connected_count += 1
                counted_rows.append(row_index)

        total_calls = connected_count + not_connected_count
        connected_rate = round((connected_count / total_calls * 100), 2) if total_calls > 0 else 0.0

        # Roles belong only to rows counted as actual calls.
        active_roles: Set[str] = set()
        if role_col and role_col in filtered_df.columns and counted_rows:
            for role in filtered_df.loc[counted_rows, role_col].dropna().unique():
                role_str = str(role).strip()
                if role_str and role_str.lower() not in ("nan", "none", "-"):
                    active_roles.add(role_str)

        # Note: Candidate names, phone numbers, and raw rows are NOT returned
        # and are naturally garbage-collected here (Zero PII stored)
        return RecruiterMetricsResult(
            target_date=target_date,
            connected_calls=connected_count,
            not_connected_calls=not_connected_count,
            total_calls=total_calls,
            connected_rate=connected_rate,
            job_roles=sorted(list(active_roles)),
            unmapped_statuses=sorted(list(unmapped_list)),
            duplicates_removed=duplicates_removed,
            total_rows_processed=total_input_rows
        )
