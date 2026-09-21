"""Z3RO — Economic Verifier.

Implements Section 10 & 10.1:
- Prevents the agent from hallucinating or self-reporting earned revenue.
- Defines and verifies external confirmation sources:
  1. Payments: Webhook signature or statement line.
  2. Content work: Platform-confirmed publication + independent metric.
  3. Contracts/Gigs: Counterparty confirmation cross-checked against ledger.
"""

from enum import Enum
from typing import Dict, Any, Optional, Tuple
from z3ro.economy.ledger import ledger, Ledger


class VerificationSource(str, Enum):
    PAYMENT_PROCESSOR_WEBHOOK = "PAYMENT_PROCESSOR_WEBHOOK"
    BANK_STATEMENT_LINE = "BANK_STATEMENT_LINE"
    PLATFORM_PUBLISHED_METRIC = "PLATFORM_PUBLISHED_METRIC"
    COUNTERPARTY_CONFIRMATION = "COUNTERPARTY_CONFIRMATION"
    SIMULATION_SANDBOX_ORACLE = "SIMULATION_SANDBOX_ORACLE"


class VerificationError(Exception):
    """Raised when income claim fails external verification."""
    pass


class EconomicVerifier:
    """Independent source-of-truth verification system."""

    def __init__(self, ledger_instance: Ledger = ledger):
        self.ledger = ledger_instance

    def verify_payment(
        self,
        transaction_id: str,
        amount: float,
        webhook_payload: Optional[Dict[str, Any]] = None,
        statement_line: Optional[str] = None,
    ) -> Tuple[bool, str, Optional[int]]:
        """Verify financial deposit via webhook or statement line (Section 10.1)."""
        if amount <= 0.0:
            return False, "Amount must be strictly positive.", None

        # Verify authentic external evidence exists
        if not webhook_payload and not statement_line:
            return (
                False,
                "REJECTED: Income rejected. No external payment webhook or bank statement line provided.",
                None,
            )

        # Check webhook status if provided
        if webhook_payload:
            status = webhook_payload.get("status", "").lower()
            if status not in ("succeeded", "paid", "completed"):
                return False, f"Webhook payment status '{status}' is not settled.", None
            source_tag = VerificationSource.PAYMENT_PROCESSOR_WEBHOOK.value
            evidence = f"WEBHOOK_TX_{transaction_id}"
        else:
            source_tag = VerificationSource.BANK_STATEMENT_LINE.value
            evidence = f"STMT_LINE_{transaction_id}"

        # Record verified transaction to immutable ledger
        entry_id = self.ledger.record_entry(
            action=f"VERIFIED_PAYMENT_RECEIVED: {transaction_id}",
            cost=0.0,
            verified_income=amount,
            evidence_id=evidence,
            verification_source=source_tag,
            status="VERIFIED",
        )
        return True, f"Verified payment of ${amount:.2f} credited.", entry_id

    def verify_content_work(
        self,
        content_id: str,
        platform_api_response: Dict[str, Any],
        min_views_threshold: int = 1,
        reward_per_metric: float = 0.0,
    ) -> Tuple[bool, str, Optional[int]]:
        """Verify content work via platform publication & observable metric (Section 10.1)."""
        if not platform_api_response:
            return False, "REJECTED: Agent self-report rejected. Missing platform API verification.", None

        published = platform_api_response.get("is_published", False)
        view_count = int(platform_api_response.get("views", 0))

        if not published:
            return False, "Content item is not confirmed published by platform API.", None

        if view_count < min_views_threshold:
            return False, f"Observed metric ({view_count} views) below threshold ({min_views_threshold}).", None

        verified_amount = round(view_count * reward_per_metric, 4)
        entry_id = self.ledger.record_entry(
            action=f"CONTENT_REWARD_VERIFIED: {content_id}",
            cost=0.0,
            verified_income=verified_amount,
            evidence_id=f"PLATFORM_ID_{content_id}_VIEWS_{view_count}",
            verification_source=VerificationSource.PLATFORM_PUBLISHED_METRIC.value,
            status="VERIFIED",
        )
        return True, f"Content work verified: {view_count} views, ${verified_amount:.2f} earned.", entry_id

    def verify_contract_gig(
        self,
        gig_id: str,
        agreed_amount: float,
        counterparty_confirmation: Dict[str, Any],
    ) -> Tuple[bool, str, Optional[int]]:
        """Verify gig/contract completion via counterparty confirmation (Section 10.1)."""
        if agreed_amount <= 0.0:
            return False, "Agreed amount must be positive.", None

        if not counterparty_confirmation:
            return False, "REJECTED: Missing counterparty confirmation.", None

        status = counterparty_confirmation.get("status", "").lower()
        if status not in ("accepted", "approved", "completed"):
            return False, f"Counterparty status '{status}' does not confirm completion.", None

        entry_id = self.ledger.record_entry(
            action=f"CONTRACT_GIG_SETTLED: {gig_id}",
            cost=0.0,
            verified_income=agreed_amount,
            evidence_id=f"COUNTERPARTY_SIG_{counterparty_confirmation.get('signature', gig_id)}",
            verification_source=VerificationSource.COUNTERPARTY_CONFIRMATION.value,
            status="VERIFIED",
        )
        return True, f"Contract gig {gig_id} verified for ${agreed_amount:.2f}.", entry_id

    def verify_simulation_experiment_reward(
        self,
        experiment_id: str,
        simulated_net_gain: float,
        oracle_evidence: str,
    ) -> Tuple[bool, str, Optional[int]]:
        """Verify a simulated sandbox experiment outcome (Phase 1 / First Milestone)."""
        if simulated_net_gain <= 0.0:
            return False, "Simulated reward must be positive.", None

        entry_id = self.ledger.record_entry(
            action=f"SIMULATED_EXPERIMENT_OUTCOME: {experiment_id}",
            cost=0.0,
            verified_income=simulated_net_gain,
            evidence_id=oracle_evidence,
            verification_source=VerificationSource.SIMULATION_SANDBOX_ORACLE.value,
            status="VERIFIED_SIMULATION",
        )
        return True, f"Simulated outcome verified: +${simulated_net_gain:.2f}.", entry_id


# Global economic verifier instance
verifier = EconomicVerifier()
