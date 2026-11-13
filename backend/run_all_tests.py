import sys
import os
import time
import unittest

# Ensure backend root is on sys.path
backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)


def main():
    print("=" * 70, flush=True)
    print("RECRUITERPULSE — BACKEND EXHAUSTIVE TEST SUITE RUNNER", flush=True)
    print("=" * 70, flush=True)

    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # Discover and add all test modules
    from tests.test_column_detector import TestColumnDetector
    from tests.test_calculation_engine import TestCalculationEngine
    from tests.test_whatsapp_formatter import TestWhatsAppFormatter
    from tests.test_multi_tenancy import TestMultiTenancyIsolation
    from tests.test_report_lifecycle import TestReportLifecycle
    from tests.test_performance import TestPerformanceAndScalability
    from tests.test_google_integrations import TestGoogleIntegrations
    from tests.test_spreadsheet_parser import TestSpreadsheetParserAndRecruiter
    from tests.test_real_file_processing import TestRealFileProcessing

    suite.addTests(loader.loadTestsFromTestCase(TestColumnDetector))
    suite.addTests(loader.loadTestsFromTestCase(TestCalculationEngine))
    suite.addTests(loader.loadTestsFromTestCase(TestWhatsAppFormatter))
    suite.addTests(loader.loadTestsFromTestCase(TestMultiTenancyIsolation))
    suite.addTests(loader.loadTestsFromTestCase(TestReportLifecycle))
    suite.addTests(loader.loadTestsFromTestCase(TestPerformanceAndScalability))
    suite.addTests(loader.loadTestsFromTestCase(TestGoogleIntegrations))
    suite.addTests(loader.loadTestsFromTestCase(TestSpreadsheetParserAndRecruiter))
    suite.addTests(loader.loadTestsFromTestCase(TestRealFileProcessing))


    runner = unittest.TextTestRunner(verbosity=2)
    start_time = time.perf_counter()
    result = runner.run(suite)
    total_time = time.perf_counter() - start_time

    print("\n" + "=" * 70, flush=True)
    print("TEST SUITE EXECUTION SUMMARY", flush=True)
    print("=" * 70, flush=True)
    print(f"Total Tests Run: {result.testsRun}", flush=True)
    print(f"Passed:         {result.testsRun - len(result.failures) - len(result.errors)}", flush=True)
    print(f"Failures:       {len(result.failures)}", flush=True)
    print(f"Errors:         {len(result.errors)}", flush=True)
    print(f"Execution Time: {total_time:.3f} seconds", flush=True)

    if result.wasSuccessful():
        print("\n>>> ALL TESTS PASSED! BACKEND IS 100% SOLID AND PRODUCTION-READY. <<<", flush=True)
        sys.exit(0)
    else:
        print("\n>>> TEST SUITE FAILED! PLEASE REVIEW FAILURES ABOVE. <<<", flush=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
