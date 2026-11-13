import io
import re
from typing import Tuple, Optional, List, Dict, Any
import pandas as pd


class SpreadsheetParser:
    """
    Intelligent spreadsheet reader that:
    1. Scans ALL sheets in an Excel workbook
    2. Detects the header row even if there are banner titles or blank rows at the top
    3. Finds the best sheet containing recruitment calling tracking data
    4. Cleans and standardizes column headers
    """

    CALLING_KEYWORDS = [
        "calling status", "call status", "call outcome", "disposition", "status",
        "recruiter", "recruiter name", "caller", "consultant",
        "calling date", "activity date", "date",
        "contact number", "mobile number", "mobile", "contact", "phone", "candidate name", "candidate",
        "profile", "job role", "requirement", "position", "role"
    ]

    STATUS_SPECIFIC_KEYWORDS = [
        "calling status", "call status", "call outcome", "calling status ", "status", "disposition", "outcome"
    ]

    @classmethod
    def score_row_as_header(cls, row_values: List[Any]) -> Tuple[int, bool]:
        """
        Scores a list of cell values in a row to determine if it is the table header.
        Returns: (score, has_status_column)
        """
        cleaned_cells = [str(v).strip().lower() for v in row_values if pd.notna(v) and str(v).strip() != ""]
        if len(cleaned_cells) < 2:
            return 0, False

        score = 0
        has_status = False

        for cell in cleaned_cells:
            # Check for status column explicitly
            if any(skw == cell or skw in cell for skw in cls.STATUS_SPECIFIC_KEYWORDS):
                has_status = True
                score += 5  # Strong weight for status column

            # Check for general calling keywords
            for kw in cls.CALLING_KEYWORDS:
                if kw == cell:
                    score += 3  # Exact match
                    break
                elif kw in cell:
                    score += 1  # Substring match
                    break

        return score, has_status

    @classmethod
    def parse_excel(cls, content: bytes) -> Tuple[pd.DataFrame, str]:
        """
        Examines all sheets in the Excel workbook and finds the one with the best recruitment table.
        Returns (DataFrame, sheet_name).
        """
        xl = pd.ExcelFile(io.BytesIO(content))
        best_df: Optional[pd.DataFrame] = None
        best_sheet_name: str = xl.sheet_names[0]
        best_score = -1
        best_header_row = 0

        for sheet_name in xl.sheet_names:
            try:
                # Read first 20 rows without header to inspect rows
                preview = pd.read_excel(xl, sheet_name=sheet_name, header=None, nrows=20)
            except Exception:
                continue

            if preview.empty or len(preview.columns) < 2:
                continue

            # Check rows 0 to min(15, len(preview))
            max_check = min(15, len(preview))
            for row_idx in range(max_check):
                row_vals = preview.iloc[row_idx].tolist()
                score, has_status = cls.score_row_as_header(row_vals)

                # Prioritize sheets that have a status column
                if score > best_score:
                    best_score = score
                    best_sheet_name = sheet_name
                    best_header_row = row_idx

        # If we found a good candidate row (score >= 4)
        if best_score >= 4:
            df = pd.read_excel(xl, sheet_name=best_sheet_name, header=best_header_row)
        else:
            # Fallback to standard sheet parse
            df = pd.read_excel(xl, sheet_name=best_sheet_name)

        # Clean column names (strip whitespace, ensure string)
        df.columns = [str(c).strip() for c in df.columns]
        # Drop completely empty rows
        df = df.dropna(how="all").copy()

        return df, best_sheet_name

    @classmethod
    def parse_excel_sheets(cls, content: bytes) -> List[Tuple[pd.DataFrame, str]]:
        """Returns every workbook sheet with a detectable calling-status header."""
        xl = pd.ExcelFile(io.BytesIO(content))
        parsed_sheets: List[Tuple[pd.DataFrame, str]] = []

        for sheet_name in xl.sheet_names:
            preview = pd.read_excel(xl, sheet_name=sheet_name, header=None, nrows=20)
            if preview.empty or len(preview.columns) < 2:
                continue

            best_score = -1
            best_header_row = 0
            for row_idx in range(min(15, len(preview))):
                score, has_status = cls.score_row_as_header(preview.iloc[row_idx].tolist())
                if has_status and score > best_score:
                    best_score = score
                    best_header_row = row_idx

            if best_score < 4:
                continue

            df = pd.read_excel(xl, sheet_name=sheet_name, header=best_header_row)
            df.columns = [str(column).strip() for column in df.columns]
            df = df.dropna(how="all").copy()
            if not df.empty:
                parsed_sheets.append((df, sheet_name))

        if not parsed_sheets:
            raise ValueError("No worksheet with a recognizable call-status header was found.")
        return parsed_sheets

    @classmethod
    def parse_csv(cls, content: bytes) -> pd.DataFrame:
        """
        Parses CSV with header row auto-detection, safely handling irregular banner rows.
        """
        try:
            text = content.decode("utf-8", errors="replace")
        except Exception:
            text = str(content)

        lines = [line.strip() for line in text.splitlines() if line.strip()]
        if not lines:
            raise ValueError("CSV file is empty.")

        best_row_idx = 0
        best_score = -1

        for idx, line in enumerate(lines[:15]):
            cells = [c.strip().strip('"').strip("'") for c in line.split(",")]
            score, has_status = cls.score_row_as_header(cells)
            if score > best_score:
                best_score = score
                best_row_idx = idx

        # Reconstruct CSV starting from the best header row
        clean_csv_text = "\n".join(lines[best_row_idx:])
        df = pd.read_csv(io.StringIO(clean_csv_text))
        df.columns = [str(c).strip() for c in df.columns]
        return df.dropna(how="all").copy()

    @classmethod
    def parse_file(cls, content: bytes, filename: str) -> Tuple[pd.DataFrame, Optional[str]]:
        """
        Unified parser entry point for CSV and Excel files.
        """
        fn = filename.lower()
        if fn.endswith((".xlsx", ".xls")):
            return cls.parse_excel(content)
        elif fn.endswith(".csv"):
            return cls.parse_csv(content), None
        else:
            raise ValueError("Unsupported file format. Please upload .xlsx, .xls, or .csv")
