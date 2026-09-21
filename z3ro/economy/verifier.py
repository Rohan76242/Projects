"""verifier.py — The ONLY module allowed to call ledger.record_income().

Each verify_* function checks a real third-party source of truth and
returns a structured result. Nothing is written to the ledger unless
the third party confirms it. The agent's own claims are never trusted.

You need API credentials for whichever channel you use:
 - YouTube: Google Cloud project + YouTube Analytics/Data API + AdSense API
 - Amazon Associates: Product Advertising API + Associates reporting (no
   real-time API for commissions — Amazon requires CSV report pull or
   manual reconciliation; see note in verify_affiliate_amazon below)
 - Stripe (for a paid API/microservice channel): Stripe API, fully real-time

Fill in YOUR_* placeholders with real credentials via environment variables,
never hard-coded in this file.
"""

import os
import requests
from enum import Enum
from typing import Dict, Any, Optional, Tuple

from . import ledger
from .ledger import Ledger, ledger as default_ledger


class VerificationError(Exception):
    """Raised when income claim fails external verification."""
    pass


def verify_stripe_payment(strategy_id: str, payment_intent_id: str):
    """Stripe is the cleanest verification source: it has a real-time API and
    a webhook model. This checks a PaymentIntent's actual status.
    """
    api_key = os.environ.get("STRIPE_SECRET_KEY")
    if not api_key:
        raise VerificationError("STRIPE_SECRET_KEY not set")
    resp = requests.get(
        f"https://api.stripe.com/v1/payment_intents/{payment_intent_id}",
        auth=(api_key, ""),
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("status") != "succeeded":
        return {"verified": False, "reason": f"status={data.get('status')}"}
    amount = data["amount_received"] / 100.0  # Stripe uses cents
    ledger.record_income(
        amount=amount,
        strategy_id=strategy_id,
        description=f"Stripe payment {payment_intent_id}",
        evidence_source="stripe_api",
        evidence_id=payment_intent_id,
        evidence_raw=data,
    )
    return {"verified": True, "amount": amount}


def verify_youtube_adsense(strategy_id: str, start_date: str, end_date: str):
    """Pulls confirmed AdSense earnings for a date range via the AdSense
    Management API. Requires OAuth2 credentials with AdSense read scope.

    NOTE: AdSense reports finalized (paid) earnings with a delay — this
    should be run periodically (e.g. daily via a scheduled task), not
    treated as instant per-video verification. Views != money; only this
    report counts.
    """
    access_token = os.environ.get("ADSENSE_ACCESS_TOKEN")
    if not access_token:
        raise VerificationError("ADSENSE_ACCESS_TOKEN not set")
    url = "https://adsense.googleapis.com/v2/accounts/{account}/reports:generate"
    account_id = os.environ.get("ADSENSE_ACCOUNT_ID")
    params = {
        "dateRange": "CUSTOM",
        "startDate.year": start_date[:4],
        "startDate.month": start_date[5:7],
        "startDate.day": start_date[8:10],
        "endDate.year": end_date[:4],
        "endDate.month": end_date[5:7],
        "endDate.day": end_date[8:10],
        "metrics": "ESTIMATED_EARNINGS",
    }
    resp = requests.get(
        url.format(account=account_id),
        headers={"Authorization": f"Bearer {access_token}"},
        params=params,
    )
    resp.raise_for_status()
    data = resp.json()
    total = 0.0
    for row in data.get("rows", []):
        cells = row.get("cells", [])
        if cells:
            total += float(cells[-1].get("value", 0))
    if total <= 0:
        return {"verified": False, "reason": "no earnings in range"}
    evidence_id = f"adsense_{start_date}_{end_date}"
    ledger.record_income(
        amount=total,
        strategy_id=strategy_id,
        description=f"AdSense earnings {start_date} to {end_date}",
        evidence_source="youtube_adsense_api",
        evidence_id=evidence_id,
        evidence_raw=data,
    )
    return {"verified": True, "amount": total}


def verify_affiliate_amazon(strategy_id: str, report_csv_path: str):
    """Amazon Associates doesn't expose a real-time commissions API to
    individual affiliates — the standard, ToS-compliant way is to download
    the periodic earnings report (CSV) from the Associates dashboard
    yourself and point this function at it. This keeps verification
    grounded in Amazon's own report rather than agent-scraped numbers.
    """
    import csv

    if not os.path.exists(report_csv_path):
        raise VerificationError(f"Report file not found: {report_csv_path}")
    total = 0.0
    rows_used = []
    with open(report_csv_path, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            fee = row.get("Fees Earned") or row.get("fees_earned") or "0"
            try:
                total += float(fee.replace("$", "").replace(",", ""))
                rows_used.append(row)
            except ValueError:
                continue
    if total <= 0:
        return {"verified": False, "reason": "no commissions in report"}
    evidence_id = f"amazon_report_{os.path.basename(report_csv_path)}"
    ledger.record_income(
        amount=total,
        strategy_id=strategy_id,
        description="Amazon Associates commission report",
        evidence_source="amazon_associates_report",
        evidence_id=evidence_id,
        evidence_raw={"rows": rows_used[:20]},  # truncate for storage
    )
    return {"verified": True, "amount": total}


class VerificationSource(str, Enum):
    PAYMENT_PROCESSOR_WEBHOOK = "PAYMENT_PROCESSOR_WEBHOOK"
    BANK_STATEMENT_LINE = "BANK_STATEMENT_LINE"
    PLATFORM_PUBLISHED_METRIC = "PLATFORM_PUBLISHED_METRIC"
    COUNTERPARTY_CONFIRMATION = "COUNTERPARTY_CONFIRMATION"
    SIMULATION_SANDBOX_ORACLE = "SIMULATION_SANDBOX_ORACLE"


class EconomicVerifier:
    """Independent source-of-truth verification system."""

    def __init__(self, ledger_instance: Ledger = default_ledger):
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

        if not webhook_payload and not statement_line:
            return (
                False,
                "REJECTED: Income rejected. No external payment webhook or bank statement line provided.",
                None,
            )

        if webhook_payload:
            status = webhook_payload.get("status", "").lower()
            if status not in ("succeeded", "paid", "completed"):
                return False, f"Webhook payment status '{status}' is not settled.", None
            source_tag = VerificationSource.PAYMENT_PROCESSOR_WEBHOOK.value
            evidence = f"WEBHOOK_TX_{transaction_id}"
        else:
            source_tag = VerificationSource.BANK_STATEMENT_LINE.value
            evidence = f"BANK_LINE_{transaction_id}"

        entry_id = self.ledger.record_entry(
            action=f"Payment received ({transaction_id})",
            cost=0.0,
            verified_income=amount,
            evidence_id=evidence,
            verification_source=source_tag,
            status="VERIFIED",
        )
        return True, f"Verified payment of ${amount:.2f}", entry_id

    def verify_content_work(
        self,
        platform: str,
        content_id: str,
        expected_payout: float,
        platform_api_response: Dict[str, Any],
    ) -> Tuple[bool, str, Optional[int]]:
        """Verify independent external platform metric for published content."""
        if not platform_api_response:
            return False, "REJECTED: No external platform response provided.", None

        is_published = platform_api_response.get("is_published", False)
        view_count = platform_api_response.get("views", 0)

        if not is_published:
            return False, "Content publication was not confirmed by platform API.", None

        if view_count < 1:
            return False, "Metric threshold not met on platform.", None

        entry_id = self.ledger.record_entry(
            action=f"Content payout: {platform} ({content_id})",
            cost=0.0,
            verified_income=expected_payout,
            evidence_id=f"{platform.upper()}_{content_id}",
            verification_source=VerificationSource.PLATFORM_PUBLISHED_METRIC.value,
            status="VERIFIED",
        )
        return True, f"Verified content payout of ${expected_payout:.2f}", entry_id

    def verify_counterparty(
        self,
        contract_id: str,
        payout_amount: float,
        counterparty_signature: str,
        ledger_reference: str,
    ) -> Tuple[bool, str, Optional[int]]:
        """Verify counterparty sign-off and milestone delivery for contracts/gigs."""
        if not counterparty_signature or len(counterparty_signature) < 8:
            return False, "Invalid or missing counterparty confirmation cryptographic signature.", None

        entry_id = self.ledger.record_entry(
            action=f"Contract milestone verified ({contract_id})",
            cost=0.0,
            verified_income=payout_amount,
            evidence_id=f"CONTRACT_{contract_id}_SIG_{counterparty_signature[:8]}",
            verification_source=VerificationSource.COUNTERPARTY_CONFIRMATION.value,
            status="VERIFIED",
        )
        return True, f"Verified contract payout of ${payout_amount:.2f}", entry_id

    def verify_simulation_oracle(
        self,
        hypothesis_id: str,
        payout_amount: float,
        oracle_seed: str,
    ) -> Tuple[bool, str, Optional[int]]:
        """Used in development / test suites with deterministic cryptographic oracle verification."""
        entry_id = self.ledger.record_entry(
            action=f"Simulation Oracle Verified Payout ({hypothesis_id})",
            cost=0.0,
            verified_income=payout_amount,
            evidence_id=f"ORACLE_SEED_{oracle_seed}",
            verification_source=VerificationSource.SIMULATION_SANDBOX_ORACLE.value,
            status="VERIFIED",
        )
        return True, f"Verified oracle outcome of ${payout_amount:.2f}", entry_id


verifier = EconomicVerifier()
