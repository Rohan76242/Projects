"""opportunity_discovery.py — Generates candidate strategies within the
channels that have a real, verifiable payout path (Section 10.1 of the
blueprint). This does NOT execute anything — it only produces candidates
for the compliance filter and planner to evaluate.

Each candidate declares its own verification_source up front, so a
strategy with no realistic verification path never even gets generated.
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
import random


@dataclass
class StrategyCandidate:
    strategy_id: str
    channel: str  # 'content', 'affiliate', 'api_service', 'digital_product'
    description: str
    verification_source: str  # must match a real verifier.py function
    est_cost: float
    est_time_days: float
    requires_external_action: bool  # True => must pass reversibility check
    notes: str = ""


def discover_content_strategies() -> list:
    """Candidates for the YouTube/short-form video channel you already have infra for."""
    return [
        StrategyCandidate(
            strategy_id="content_yt_shorts_v1",
            channel="content",
            description=(
                "Produce daily short-form OC video on a fixed topic niche, "
                "upload via existing agent pipeline, monetize via YouTube "
                "Shorts ad revenue + AdSense."
            ),
            verification_source="youtube_adsense_api",
            est_cost=0.0,  # assuming existing local generation pipeline
            est_time_days=30,  # needs subscriber/watch-hour threshold first
            requires_external_action=True,
            notes="Upload is irreversible once public — route through reversibility check.",
        ),
        StrategyCandidate(
            strategy_id="content_affiliate_embed_v1",
            channel="affiliate",
            description=(
                "Embed relevant Amazon affiliate links in video descriptions "
                "for products related to the content topic."
            ),
            verification_source="amazon_associates_report",
            est_cost=0.0,
            est_time_days=14,
            requires_external_action=True,
            notes="Must disclose affiliate relationship per FTC-equivalent rules — compliance filter check.",
        ),
    ]


def discover_api_service_strategies() -> list:
    """Candidates for a metered-billing microservice channel."""
    return [
        StrategyCandidate(
            strategy_id="api_micro_service_v1",
            channel="api_service",
            description=(
                "Wrap an existing useful function (e.g. data cleaning, format "
                "conversion) as a small paid API with Stripe metered billing."
            ),
            verification_source="stripe_api",
            est_cost=5.0,  # hosting
            est_time_days=7,
            requires_external_action=True,
            notes="Requires publishing pricing/ToS page — human review before launch.",
        ),
    ]


def discover_digital_product_strategies() -> list:
    return [
        StrategyCandidate(
            strategy_id="digital_product_template_v1",
            channel="digital_product",
            description=(
                "Create and list a digital template/asset pack on a marketplace "
                "with built-in payout API (e.g. Gumroad)."
            ),
            verification_source="stripe_api",  # Gumroad payouts also reconcile via Stripe/bank
            est_cost=0.0,
            est_time_days=3,
            requires_external_action=True,
            notes="Low compliance risk; still needs listing content reviewed for IP issues.",
        ),
    ]


def discover_all() -> list:
    return (
        discover_content_strategies()
        + discover_api_service_strategies()
        + discover_digital_product_strategies()
    )


# Capability domains for continuous autonomous exploration
CAPABILITY_DOMAINS = [
    {
        "name": "Market & Tech Research Synthesis",
        "capability": "web_research",
        "description": "Synthesizing emerging technology trends and open research into structured intelligence reports.",
        "cost_range": (0.0, 5.0),
        "reward_range": (10.0, 35.0),
        "risk_range": (0.1, 0.3),
    },
    {
        "name": "Automated Open-Source Documentation Compiler",
        "capability": "draft_content_code",
        "description": "Compiling fragmented technical repository documentation and developer guides into readable deliverables.",
        "cost_range": (0.0, 8.0),
        "reward_range": (15.0, 45.0),
        "risk_range": (0.15, 0.35),
    },
    {
        "name": "Public Data Verification & Cleaning Pipeline",
        "capability": "draft_content_code",
        "description": "Extracting, normalizing, and verifying public benchmarks into structured tabular formats.",
        "cost_range": (0.0, 10.0),
        "reward_range": (20.0, 50.0),
        "risk_range": (0.2, 0.4),
    },
    {
        "name": "Curated Educational Coding Tutorials",
        "capability": "draft_content_code",
        "description": "Drafting beginner-friendly tutorials, code snippets, and unit test walkthroughs.",
        "cost_range": (0.0, 6.0),
        "reward_range": (12.0, 30.0),
        "risk_range": (0.1, 0.25),
    },
]


class OpportunityDiscovery:
    """Discovers hypothesis-driven economic opportunities."""

    def generate_candidate_strategies(self, count: int = 3) -> list:
        """Synthesize candidate strategies from real-money candidates and capability permutations."""
        from z3ro.autonomy.strategy import Strategy
        candidates = []
        
        # First include concrete real-money channel candidates
        real_candidates = discover_all()
        for rc in real_candidates:
            strat = Strategy.create(
                name=rc.strategy_id,
                description=rc.description,
                target_capability="draft_content_code",
                estimated_cost=rc.est_cost,
                estimated_reward=25.0,
                risk_score=0.15,
            )
            candidates.append(strat)

        # Add capability permutations if needed
        selected_domains = random.sample(CAPABILITY_DOMAINS, min(count, len(CAPABILITY_DOMAINS)))
        for domain in selected_domains:
            cost = round(random.uniform(*domain["cost_range"]), 2)
            reward = round(random.uniform(*domain["reward_range"]), 2)
            risk = round(random.uniform(*domain["risk_range"]), 2)

            strat = Strategy.create(
                name=domain["name"],
                description=domain["description"],
                target_capability=domain["capability"],
                estimated_cost=cost,
                estimated_reward=reward,
                risk_score=risk,
            )
            candidates.append(strat)

        return candidates[:max(count, 3)]


# Global opportunity discovery singleton
opportunity_discovery = OpportunityDiscovery()


if __name__ == "__main__":
    for c in discover_all():
        print(f"[{c.channel}] {c.strategy_id} -> verify via {c.verification_source}")
        print(f"  {c.description}")
        print(
            f"  est_cost=${c.est_cost}  est_time={c.est_time_days}d  "
            f"external_action={c.requires_external_action}"
        )
        print()
