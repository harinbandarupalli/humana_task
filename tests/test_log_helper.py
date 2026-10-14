"""Unit tests for Log Helper, PII redaction, and timing utilities."""

import logging
import time
import unittest
from src.orchestrator.core.log_helper import (
    OrderConsoleFormatter,
    OrderJsonFormatter,
    SecretRedactionFilter,
    get_order_logger,
    order_log_context,
)


class TestLogHelper(unittest.TestCase):
    """Test suite for log helper components."""

    def test_pii_string_redaction(self):
        """Verifies regex redaction on sensitive patterns in raw text."""
        raw_msg = (
            "Calling API with Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.e30.t-x7 and "
            "api_key=secret_123456789_xyz. Card is 4111 2222 3333 4444 and ssn is 123-45-6789."
        )
        sanitized = SecretRedactionFilter.sanitize_string(raw_msg)

        self.assertNotIn("eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9", sanitized)
        self.assertIn("Bearer [REDACTED_TOKEN]", sanitized)
        self.assertNotIn("secret_123456789_xyz", sanitized)
        self.assertIn("api_key=[REDACTED]", sanitized)
        self.assertNotIn("4111 2222 3333 4444", sanitized)
        self.assertIn("[CARD_REDACTED]", sanitized)
        self.assertNotIn("123-45-6789", sanitized)
        self.assertIn("[SSN_REDACTED]", sanitized)

    def test_pii_dict_redaction(self):
        """Verifies dictionary masking on sensitive keys."""
        payload = {
            "order_id": "ORD-12345",
            "password": "supersecretpassword",
            "token": "tok_12345678",
            "nested": {
                "cvv": "123",
                "normal_field": "visible",
            },
        }
        sanitized = SecretRedactionFilter.sanitize_dict(payload)

        self.assertEqual(sanitized["order_id"], "ORD-12345")
        self.assertEqual(sanitized["password"], "[REDACTED]")
        self.assertEqual(sanitized["token"], "[REDACTED]")
        self.assertEqual(sanitized["nested"]["cvv"], "[REDACTED]")
        self.assertEqual(sanitized["nested"]["normal_field"], "visible")

    def test_order_log_context_and_buffering(self):
        """Verifies context variable binding and state log buffering."""
        with order_log_context(order_id="ORD-TEST-01", node_name="inventory_check", stage_version=2) as logger:
            logger.append_state_log("Step 1: Check completed.")
            logger.append_state_log("Step 2: Balance verified.")

            buffered = logger.get_buffered_logs()
            self.assertEqual(len(buffered), 2)
            self.assertTrue(any("Step 1: Check completed." in b for b in buffered))
            self.assertTrue(any("Step 2: Balance verified." in b for b in buffered))

    def test_timed_operation(self):
        """Verifies latency profiling context manager."""
        logger = get_order_logger("test_timing")
        with logger.timed_operation("simulated_api_call") as timer:
            time.sleep(0.05)  # 50ms sleep

        self.assertIsNotNone(timer.duration_ms)
        self.assertGreaterEqual(timer.duration_ms, 40)


if __name__ == "__main__":
    unittest.main()
