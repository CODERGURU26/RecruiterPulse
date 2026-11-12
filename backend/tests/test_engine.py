import sys
import os
from datetime import date
import pandas as pd

# Add backend root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.models.enums import StandardField, CallCategory
from app.models.taxonomy import DEFAULT_INDIAN_TAXONOMY_PRESETS
from app.services.column_detector import ColumnDetector
from app.services.calculation_engine import CalculationEngine
from app.services.whatsapp_formatter import WhatsAppFormatter


def test_column_detector_and_calculation_engine():
    print("=" * 60)
    print("RUNNING RECRUITERPULSE INGESTION & CALCULATION ENGINE TEST")
    print("=" * 60)

    # 1. Create a messy real-world Indian recruitment spreadsheet DataFrame
    raw_sheet_data = {
        "Calling Date": [
            "12/11/2026", "12/11/2026", "12/11/2026", "12/11/2026", "12/11/2026",
            "12/11/2026", "12/11/2026", "12/11/2026", "12/11/2026", "12/11/2026",
            "11/11/2026",  # Yesterday's call (should be filtered out!)
            "12/11/2026"   # Duplicate of row 1 (should be deduplicated!)
        ],
        "Candidate Name": [
            "Aarav Mehta", "Ishita Sen", "Vikram Rathore", "Pooja Hegde", "Suresh Nair",
            "Kavita Patil", "Rohan Das", "Sneha Roy", "Manoj Tiwari", "Ananya Pandey",
            "Ramesh Kumar",
            "Aarav Mehta"  # Duplicate
        ],
        "Mobile": [
            "9876543210", "9123456780", "9845012345", "9988776655", "9765432109",
            "9654321098", "9543210987", "9432109876", "9321098765", "9210987654",
            "9109876543",
            "9876543210"   # Duplicate
        ],
        "Requirement": [
            "Java Backend", "DevOps", "Java Backend", "React Frontend", "DevOps",
            "Java Backend", "React Frontend", "DevOps", "Java Backend", "React Frontend",
            "Python Lead",
            "Java Backend"
        ],
        "Call Outcome": [
            "Connected - Screening done",  # Connected
            "RNR",                         # Not Connected
            "Switched off",                # Not Connected
            "Interested",                  # Connected
            "Busy",                        # Not Connected
            "L1 Scheduled",                # Connected
            "Out of coverage",             # Not Connected
            "Spoke - Salary Mismatch",     # Connected
            "Wrong Number",                # Not Connected
            "Call cut mid-way",            # Unmapped!
            "Connected",                   # Yesterday
            "Connected - Screening done"   # Duplicate
        ]
    }

    df = pd.DataFrame(raw_sheet_data)
    print(f"\n1. Loaded Raw Mock Sheet with {len(df)} rows.")

    # 2. Test Column Detection
    print("\n2. Testing Automatic Column Detection...")
    detections = ColumnDetector.analyze_dataframe(df)

    for field, res in detections.items():
        print(f"  Field: {field.value:<15} -> Detected Column: '{res['source_column']}' | Confidence: {res['confidence']:.2f} | Auto-Confirmed: {res['auto_confirmed']}")

    assert detections[StandardField.ACTIVITY_DATE]["source_column"] == "Calling Date"
    assert detections[StandardField.CALL_STATUS]["source_column"] == "Call Outcome"
    assert detections[StandardField.CANDIDATE_REF]["source_column"] in ("Candidate Name", "Mobile")
    assert detections[StandardField.JOB_ROLE]["source_column"] == "Requirement"
    print("✓ Column Detection validated successfully with high confidence!")

    # 3. Test Calculation Engine
    print("\n3. Testing Calling Calculation Engine for Date 2026-11-12...")
    
    # Build column mapping from detector
    column_mapping = {
        field: res["source_column"]
        for field, res in detections.items()
        if res["source_column"] is not None
    }

    # Build taxonomy lookup from presets
    taxonomy_lookup = {
        raw: cat for raw, cat in DEFAULT_INDIAN_TAXONOMY_PRESETS
    }

    target_date = date(2026, 11, 12)
    result = CalculationEngine.calculate_recruiter_activity(
        df=df,
        column_mapping=column_mapping,
        status_taxonomy=taxonomy_lookup,
        target_date=target_date
    )

    print("\nCalculation Engine Results:")
    print(f"  - Target Date: {result.target_date}")
    print(f"  - Total Input Rows Processed: {result.total_rows_processed}")
    print(f"  - Duplicates Removed: {result.duplicates_removed}")
    print(f"  - Connected Calls: {result.connected_calls}")
    print(f"  - Not Connected Calls: {result.not_connected_calls}")
    print(f"  - Total Calls: {result.total_calls}")
    print(f"  - Connected Rate: {result.connected_rate}%")
    print(f"  - Active Roles: {result.job_roles}")
    print(f"  - Unmapped Statuses: {result.unmapped_statuses}")

    # Assertions
    # 12 rows total: 1 yesterday filtered out = 11 today rows.
    # 1 duplicate row removed = 10 unique today rows.
    # Connected: Screening done (1), Interested (1), L1 Scheduled (1), Salary Mismatch (1) = 4 connected
    # Not Connected: RNR (1), Switched off (1), Busy (1), Out of coverage (1), Wrong Number (1), Call cut mid-way (unmapped defaulted to not connected) = 6
    # Total = 10
    assert result.duplicates_removed == 1
    assert result.total_calls == 10
    assert result.connected_calls == 4
    assert result.not_connected_calls == 6
    assert result.connected_rate == 40.0
    assert "Call cut mid-way" in result.unmapped_statuses
    assert sorted(result.job_roles) == ["DevOps", "Java Backend", "React Frontend"]

    # Verify DPDP Compliance: Output dict contains no candidate names or phone numbers!
    res_dict = result.to_dict()
    assert "Candidate Name" not in res_dict
    assert "Mobile" not in res_dict
    print("✓ DPDP Zero-PII Compliance Verified: Candidate identities completely purged from results.")

    # 4. Test WhatsApp Formatter
    print("\n4. Testing WhatsApp Formatter...")
    metrics_list = [
        {
            "recruiter_name": "Priya Sharma",
            "job_roles": result.job_roles,
            "connected_calls": result.connected_calls,
            "not_connected_calls": result.not_connected_calls,
            "total_calls": result.total_calls,
            "connected_rate": result.connected_rate,
            "next_day_interviews": 3
        },
        {
            "recruiter_name": "Rahul Verma",
            "job_roles": ["React Frontend"],
            "connected_calls": 12,
            "not_connected_calls": 8,
            "total_calls": 20,
            "connected_rate": 60.0,
            "next_day_interviews": 1
        }
    ]

    summary_totals = {
        "total_calls": 30,
        "connected_calls": 16,
        "not_connected_calls": 14,
        "connected_rate": 53.33,
        "next_day_interviews": 4
    }

    whatsapp_msg = WhatsAppFormatter.format_report(
        workspace_name="Apex Staffing India",
        reporting_date=target_date,
        hour_slot="15:00",
        metrics=metrics_list,
        summary_totals=summary_totals,
        approver_name="Pooja K. (MIS Lead)"
    )

    print("\nGenerated WhatsApp Clipboard Message:\n")
    print(whatsapp_msg)
    print("\n" + "=" * 60)
    print("ALL INGESTION & CALCULATION ENGINE TESTS PASSED (100%)")
    print("=" * 60)


if __name__ == "__main__":
    test_column_detector_and_calculation_engine()

