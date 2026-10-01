import unittest

from abqjobpilot.parsers import classify_datacheck_attempt, classify_final_verdict, latest_attempt_block, parse_console_status


class TestParsers(unittest.TestCase):
    def test_contact_force_error_tolerance_is_not_fatal(self):
        result = classify_final_verdict(msg_text="CONTACT FORCE ERROR TOLERANCE = 0.005")
        self.assertNotEqual(result["status"], "FAILED_FATAL")
        self.assertEqual(parse_console_status("force error tolerance")["fatal_detected"], False)

    def test_success_pattern(self):
        result = classify_final_verdict(sta_text="THE ANALYSIS HAS COMPLETED SUCCESSFULLY")
        self.assertEqual(result["status"], "COMPLETED_OK")
        self.assertEqual(result["final_verdict"], "SUCCESS")

    def test_too_many_attempts_is_failure(self):
        result = classify_final_verdict(log_text="Too many attempts made for this increment")
        self.assertEqual(result["status"], "FAILED_FATAL")
        self.assertEqual(result["final_verdict"], "FAILED")

    def test_datacheck_uses_latest_attempt_block(self):
        log_text = """
        [2026-05-31T00:01:00] START DATACHECK_RUNNING
        Abaqus Error: Command line option "gpus" may not be used with "datacheck"
        [2026-05-31T00:01:05] END DATACHECK_RUNNING return_code=0

        [2026-05-31T00:02:00] START DATACHECK_RUNNING
        Begin Abaqus/Standard Analysis
        Abaqus JOB Job_test COMPLETED
        [2026-05-31T00:02:05] END DATACHECK_RUNNING return_code=0
        """
        block = latest_attempt_block(log_text, "DATACHECK_RUNNING")
        self.assertIn("Abaqus JOB Job_test COMPLETED", block)
        self.assertNotIn("Command line option", block)

        result = classify_datacheck_attempt(log_text, return_code=0)
        self.assertEqual(result["status"], "DATACHECK_PASS")
        self.assertEqual(result["final_verdict"], "DATACHECK_PASS")

    def test_datacheck_invalid_gpu_option_is_specific_failure(self):
        log_text = """
        [2026-05-31T00:01:00] START DATACHECK_RUNNING
        Abaqus Error: Command line option "gpus" may not be used with "datacheck"
        [2026-05-31T00:01:05] END DATACHECK_RUNNING return_code=0
        """
        result = classify_datacheck_attempt(log_text, return_code=0)
        self.assertEqual(result["status"], "DATACHECK_FAILED_INVALID_GPU_OPTION")
        self.assertEqual(result["fatal_reason"], 'Command line option "gpus" may not be used with "datacheck"')


if __name__ == "__main__":
    unittest.main()
