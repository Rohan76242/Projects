"""Unit Tests for Scoped Credential Broker (Blueprint v2.0 Section 9.3)."""

import unittest
import time
from z3ro.tools.credentials import CredentialBroker


class TestCredentialBroker(unittest.TestCase):

    def setUp(self):
        self.broker = CredentialBroker()

    def test_issue_and_validate_scoped_credential(self):
        cred = self.broker.issue_credential(
            scope="READ_ONLY_WEB",
            max_amount_cap=10.0,
            ttl_seconds=60.0,
            description="Test temporary search token",
        )
        self.assertIsNotNone(cred.token_id)

        # Valid scope and cost
        valid, reason = self.broker.validate(cred.token_id, "READ_ONLY_WEB", cost=5.0)
        self.assertTrue(valid)

        # Scope mismatch
        valid, reason = self.broker.validate(cred.token_id, "FINANCIAL_PAYMENT", cost=5.0)
        self.assertFalse(valid)
        self.assertIn("Scope mismatch", reason)

        # Cost cap exceeded
        valid, reason = self.broker.validate(cred.token_id, "READ_ONLY_WEB", cost=15.0)
        self.assertFalse(valid)
        self.assertIn("exceeds credential cap", reason)

    def test_credential_revocation(self):
        cred = self.broker.issue_credential(scope="SANDBOX_API", ttl_seconds=120.0)
        valid, _ = self.broker.validate(cred.token_id, "SANDBOX_API")
        self.assertTrue(valid)

        # Revoke centrally
        revoked = self.broker.revoke(cred.token_id)
        self.assertTrue(revoked)

        # Validate now fails
        valid, reason = self.broker.validate(cred.token_id, "SANDBOX_API")
        self.assertFalse(valid)
        self.assertIn("revoked", reason)

    def test_credential_expiration(self):
        cred = self.broker.issue_credential(scope="TEMP_SCOPE", ttl_seconds=0.01)
        time.sleep(0.02)
        valid, reason = self.broker.validate(cred.token_id, "TEMP_SCOPE")
        self.assertFalse(valid)
        self.assertIn("expired", reason)


if __name__ == "__main__":
    unittest.main()
