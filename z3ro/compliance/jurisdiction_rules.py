"""Z3RO — Jurisdiction Rules & Compliance Standards.

Implements Section 9.2:
- Licensing requirements (lending, financial advice, reselling, securities)
- Anti-spam & CAN-SPAM regulations (bulk messaging, harvesting, missing opt-outs)
- Platform Terms of Service compliance (automation bans, multi-accounting)
- Web scraping & robots.txt rules
- Consumer protection principles (deceptive claims, hidden commitments)
"""

import re
import urllib.robotparser
import urllib.parse
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Tuple


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
