"""Z3RO — Autonomous Strategy Representation and Lifecycle.

Implements Section 7 & 8:
- Strategy dataclass and state lifecycle:
  DISCOVERED -> COMPLIANCE_REVIEW -> ESTIMATED -> EXPERIMENTING -> EVALUATED -> ACTIVE / ABANDONED
"""

import uuid
import time
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import List, Dict, Any, Optional


class StrategyLifecycle(str, Enum):
    DISCOVERED = "DISCOVERED"
    COMPLIANCE_REVIEW = "COMPLIANCE_REVIEW"
    REJECTED_COMPLIANCE = "REJECTED_COMPLIANCE"
    ESTIMATED = "ESTIMATED"
    EXPERIMENTING = "EXPERIMENTING"
    EVALUATED = "EVALUATED"
    ACTIVE = "ACTIVE"
    ABANDONED = "ABANDONED"


@dataclass
class Strategy:
    strategy_id: str
    name: str
    description: str
    target_capability: str
    estimated_cost: float = 0.0
    estimated_reward: float = 0.0
    risk_score: float = 0.50  # 0.0 (safest) to 1.0 (riskiest)
    time_budget_sec: float = 60.0
    confidence: float = 0.50
    state: StrategyLifecycle = StrategyLifecycle.DISCOVERED
    created_at: float = field(default_factory=time.time)
    rejection_reason: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        name: str,
        description: str,
        target_capability: str,
        estimated_cost: float = 0.0,
        estimated_reward: float = 0.0,
        risk_score: float = 0.50,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> "Strategy":
        return cls(
            strategy_id=f"strat_{uuid.uuid4().hex[:8]}",
            name=name,
            description=description,
            target_capability=target_capability,
            estimated_cost=estimated_cost,
            estimated_reward=estimated_reward,
            risk_score=risk_score,
            metadata=metadata or {},
        )

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["state"] = self.state.value if hasattr(self.state, "value") else str(self.state)
        return d
