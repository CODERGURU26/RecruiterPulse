import unittest
import sys
import os
import io

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pandas as pd
from app.services.spreadsheet_parser import SpreadsheetParser
from app.services.column_detector import ColumnDetector
from app.models.enums import StandardField


class TestSpreadsheetParserAndRecruiter(unittest.TestCase):
    def test_multi_sheet_and_banner_detection(self):
        """Tests that multi-sheet workbooks with top banners detect the calling sheet and header."""
        out = io.BytesIO()
        with pd.ExcelWriter(out, engine='openpyxl') as writer:
            # Sheet 1: Irrelevant cover sheet
            pd.DataFrame({'Notes': ['Confidential', 'FY26']}).to_excel(writer, sheet_name='Cover', index=False)
            
            # Sheet 2: The actual calling tracker with 2 banner rows at the top
            sheet_data = [
                ['RECRUITER CALLING TRACKER', '', '', '', '', '', '', '', '', ''],
                ['Updated daily by MIS', '', '', '', '', '', '', '', '', ''],
                ['Date', 'Recruiter', 'Profile', 'Source', 'Name', 'Contact Number', 'Email ID', 'Calling Status', 'Candidate status', 'Comments'],
                ['2026-11-12', 'Priya Sharma', 'Java Lead', 'Naukri', 'Rohan', '9876543210', 'rohan@test.com', 'Connected', 'Interested', 'Spoke'],
                ['2026-11-12', 'Rahul Verma', 'React Dev', 'Naukri', 'Sneha', '9876543211', 'sneha@test.com', 'RNR', 'Pending', 'No answer']
            ]
            pd.DataFrame(sheet_data).to_excel(writer, sheet_name='Calling Tracker', index=False, header=False)

        content = out.getvalue()
        df, sheet_name = SpreadsheetParser.parse_file(content, 'test.xlsx')

        self.assertEqual(sheet_name, 'Calling Tracker')
        self.assertIn('Calling Status', df.columns)
        self.assertIn('Recruiter', df.columns)
        self.assertIn('Date', df.columns)
        self.assertEqual(len(df), 2)

        # Detect columns
        detections = ColumnDetector.analyze_dataframe(df)
        self.assertEqual(detections[StandardField.CALL_STATUS]["source_column"], "Calling Status")
        self.assertEqual(detections[StandardField.RECRUITER_NAME]["source_column"], "Recruiter")
        self.assertEqual(detections[StandardField.ACTIVITY_DATE]["source_column"], "Date")
        self.assertEqual(detections[StandardField.JOB_ROLE]["source_column"], "Profile")
        self.assertEqual(detections[StandardField.CANDIDATE_REF]["source_column"], "Contact Number")

    def test_parse_every_calling_tab(self):
        out = io.BytesIO()
        with pd.ExcelWriter(out, engine='openpyxl') as writer:
            for recruiter in ("Priya Sharma", "Rahul Verma"):
                pd.DataFrame([
                    ["Date", "Call Status", "Candidate", "Profile"],
                    ["12/11/2026", "Connected", "Candidate A", "Java"],
                    ["12/11/2026", "RNR", "Candidate B", "React"]
                ]).to_excel(writer, sheet_name=recruiter, index=False, header=False)

        sheets = SpreadsheetParser.parse_excel_sheets(out.getvalue())

        self.assertEqual([name for _, name in sheets], ["Priya Sharma", "Rahul Verma"])
        self.assertTrue(all(len(df) == 2 for df, _ in sheets))

    def test_csv_parser(self):
        """Tests that CSV files with standard or top metadata are parsed cleanly."""
        csv_bytes = b"Title Line\nDate,Recruiter,Calling Status,Candidate,Profile\n2026-11-12,Priya,Connected,9876543210,Java\n"
        df, _ = SpreadsheetParser.parse_file(csv_bytes, 'data.csv')
        self.assertIn('Calling Status', df.columns)
        self.assertEqual(len(df), 1)


if __name__ == '__main__':
    unittest.main()
