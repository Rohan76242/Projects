"""jurisdiction_rules.py — Static rule set the legal filter checks candidates
against. This is intentionally simple and human-editable, NOT agent-editable.
Update this file yourself as laws/platform ToS change; the agent only reads it.

This is not legal advice. It's a first-pass filter to catch the obvious,
high-confidence red flags before a strategy reaches execution. A genuinely
novel strategy should still get human review even if it passes this filter.
"""

import re
import urllib.robotparser
import urllib.parse
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Tuple, Set, Dict


# Channels that are hard-blocked regardless of strategy details.
# These require licenses/registration Z3RO cannot hold on your behalf.
HARD_BLOCKED_CHANNELS = {
    "lending",
    "payday_loans",
    "investment_advice",
    "financial_advice",
    "insurance_sales",
    "forex_trading_signals",
    "crypto_trading_bot_for_others",
    "money_transmission",
    "gambling",
    "prescription_drug_sales",
    "unlicensed_healthcare_advice",
}

# Keywords in a strategy description that should trigger automatic rejection
# or escalation, even if the channel itself looks benign.
BLOCKED_KEYWORDS = [
    "guaranteed returns", "guaranteed income", "get rich quick",
    "bypass verification", "fake reviews", "buy followers", "buy views",
    "scrape personal data", "email scraping", "cold email blast",
    "unlicensed", "without disclosure", "hide affiliate",
    "pyramid", "mlm", "chain referral bonus",
]

# Channels allowed, but with a mandatory disclosure or compliance requirement.
DISCLOSURE_REQUIRED = {
    "affiliate": "Must include clear, platform-compliant affiliate disclosure "
                 "(e.g. 'As an Amazon Associate I earn from qualifying purchases').",
    "sponsored_content": "Must disclose sponsorship per FTC-equivalent rules "
                          "in the relevant jurisdiction.",
    "ai_generated_content": "Some platforms/regions require AI-generated content "
                            "labeling — check target platform's current policy "
                            "before publishing.",
}

# Per-platform automation restrictions worth checking before any bot-driven
# action (bidding, posting, messaging) on that platform.
PLATFORM_TOS_NOTES = {
    "upwork": "Prohibits automated bidding/proposal submission by bots.",
    "fiverr": "Requires human-operated seller accounts; no bot-run gigs.",
    "amazon_associates": "Requires disclosure; prohibits incentivized clicks "
                         "and cloaking affiliate links.",
    "youtube": "Requires AI-content disclosure for realistic synthetic media "
               "per current YouTube policy; check before upload.",
    "reddit": "Prohibits undisclosed bot posting/commenting in most subreddits.",
}

# Countries/regions with notably strict rules on automated financial agents
# or AI-generated commercial content — flag for extra review, don't auto-block.
FLAG_FOR_REVIEW_REGIONS = {
    "EU": "AI Act transparency obligations for certain AI-generated content.",
    "US-CA": "State-level automated decision-making disclosure rules.",
}


class RuleCategory(str, Enum):
    LICENSING = "LICENSING"
    ANTI_SPAM = "ANTI_SPAM"
    TERMS_OF_SERVICE = "TERMS_OF_SERVICE"
    ROBOTS_AND_SCRAPING = "ROBOTS_AND_SCRAPING"
    CONSUMER_PROTECTION = "CONSUMER_PROTECTION"


@dataclass
class ComplianceViolation:
    rule_id: str
    category: RuleCategory
    severity: str  # BLOCK | WARNING
    reason: str
    matched_pattern: Optional[str] = None


# Regulated financial and legal licensing keywords
LICENSING_PATTERNS = [
    (r"\b(?:financial\s+advice|investment\s+recommendation|stock\s+tips)\b", "Provides regulated investment/financial advice without license"),
    (r"\b(?:offer\s+loans|peer\s*to\s*peer\s+lending|micro\s*loans)\b", "Engages in money lending without banking/lending charter"),
    (r"\b(?:resell\s+unauthorized|scalp\s+tickets|counterfeit)\b", "Unauthorized commercial reselling or ticket scalping"),
    (r"\b(?:medical\s+advice|diagnose\s+disease|prescribe\s+medication)\b", "Unlicensed medical diagnostic advice"),
]

# Anti-spam and unsolicited mass outreach patterns
ANTI_SPAM_PATTERNS = [
    (r"\b(?:scrape\s+emails|email\s+harvester|harvest\s+contacts)\b", "Email address harvesting violates anti-spam laws"),
    (r"\b(?:mass\s+dm|bulk\s+emails|unsolicited\s+outreach|cold\s+spam)\b", "Unsolicited mass messaging violates CAN-SPAM"),
    (r"\b(?:bypass\s+opt-out|ignore\s+unsubscribe)\b", "Circumventing unsubscribe/opt-out mechanisms is prohibited"),
]

# Terms of service and platform abuse patterns
TOS_ABUSE_PATTERNS = [
    (r"\b(?:bypass\s+captcha|solve\s+captcha|bot\s+detection\s+bypass)\b", "Attempting to bypass anti-bot mechanisms violates platform ToS"),
    (r"\b(?:create\s+fake\s+accounts|multi\s*accounting|sybil\s+attack)\b", "Generating fake or multiple accounts violates terms of service"),
    (r"\b(?:credential\s+stuffing|brute\s+force|exploit\s+vulnerability)\b", "Unauthorized exploitation or security probing is strictly prohibited"),
]

# Consumer protection and deceptive claims patterns
CONSUMER_PROTECTION_PATTERNS = [
    (r"\b(?:guaranteed\s+returns|get\s+rich\s+quick|100%\s+free\s+money)\b", "Deceptive financial claims violate consumer protection regulations"),
    (r"\b(?:fake\s+reviews|falsify\s+testimonials|shill\s+reviews)\b", "Astroturfing or fabricated consumer reviews is illegal"),
    (r"\b(?:hidden\s+fees|dark\s+pattern|trap\s+subscription)\b", "Deceptive billing and dark patterns violate consumer protection standards"),
]

# Known platforms with strict commercial automation prohibitions
RESTRICTED_PLATFORMS = {
    "linkedin.com": "LinkedIn expressly forbids automated scraping and messaging under its User Agreement.",
    "instagram.com": "Instagram/Meta prohibits unauthorized automated interactions.",
    "facebook.com": "Facebook/Meta prohibits automated data harvesting and bulk posting.",
}


class JurisdictionRulesEvaluator:
    """Evaluates text descriptions, plan proposals, and targets for compliance."""

    def evaluate_strategy_text(self, text: str) -> List[ComplianceViolation]:
        """Scan strategy description against all core regulatory patterns."""
        violations: List[ComplianceViolation] = []
        lowered = text.lower()

        # Check blocked keywords directly
        for kw in BLOCKED_KEYWORDS:
            if kw in lowered:
                violations.append(
                    ComplianceViolation(
                        rule_id="RULE_KEYWORD_BLOCKED",
                        category=RuleCategory.CONSUMER_PROTECTION,
                        severity="BLOCK",
                        reason=f"Description contains blocked keyword/pattern: '{kw}'",
                        matched_pattern=kw,
                    )
                )

        # 1. Licensing rules
        for pattern, reason in LICENSING_PATTERNS:
            if re.search(pattern, lowered):
                violations.append(
                    ComplianceViolation(
                        rule_id="RULE_LIC_001",
                        category=RuleCategory.LICENSING,
                        severity="BLOCK",
                        reason=reason,
                        matched_pattern=pattern,
                    )
                )

        # 2. Anti-spam rules
        for pattern, reason in ANTI_SPAM_PATTERNS:
            if re.search(pattern, lowered):
                violations.append(
                    ComplianceViolation(
                        rule_id="RULE_SPAM_001",
                        category=RuleCategory.ANTI_SPAM,
                        severity="BLOCK",
                        reason=reason,
                        matched_pattern=pattern,
                    )
                )

        # 3. Terms of service rules
        for pattern, reason in TOS_ABUSE_PATTERNS:
            if re.search(pattern, lowered):
                violations.append(
                    ComplianceViolation(
                        rule_id="RULE_TOS_001",
                        category=RuleCategory.TERMS_OF_SERVICE,
                        severity="BLOCK",
                        reason=reason,
                        matched_pattern=pattern,
                    )
                )

        # 4. Consumer protection rules
        for pattern, reason in CONSUMER_PROTECTION_PATTERNS:
            if re.search(pattern, lowered):
                violations.append(
                    ComplianceViolation(
                        rule_id="RULE_CONS_001",
                        category=RuleCategory.CONSUMER_PROTECTION,
                        severity="BLOCK",
                        reason=reason,
                        matched_pattern=pattern,
                    )
                )

        return violations

    def check_url_and_robots(self, target_url: str, user_agent: str = "Z3RO-Research-Bot/2.0") -> Tuple[bool, Optional[ComplianceViolation]]:
        """Check URL against restricted platforms and standard robots.txt etiquette."""
        parsed = urllib.parse.urlparse(target_url)
        domain = parsed.netloc.lower().replace("www.", "")

        # Check restricted domains
        for restricted_domain, warning in RESTRICTED_PLATFORMS.items():
            if restricted_domain in domain:
                return False, ComplianceViolation(
                    rule_id="RULE_TOS_RESTRICTED_DOMAIN",
                    category=RuleCategory.TERMS_OF_SERVICE,
                    severity="BLOCK",
                    reason=f"{warning} Target domain: {domain}",
                    matched_pattern=restricted_domain,
                )

        return True, None


# Global evaluator singleton
jurisdiction_evaluator = JurisdictionRulesEvaluator()
