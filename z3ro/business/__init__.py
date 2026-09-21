"""Z3RO — Business & Experimentation Package.

Provides:
- OpportunityDiscovery (Hypothesis generation from capabilities)
- ExperimentRunner (Bounded experiment execution)
- OutcomeProcessor (Economic verification & settlement)
"""

from z3ro.business.opportunity_discovery import opportunity_discovery, OpportunityDiscovery
from z3ro.business.experiment import experiment_runner, ExperimentRunner, ExperimentResult
from z3ro.business.outcome import outcome_processor, OutcomeProcessor

__all__ = [
    "opportunity_discovery",
    "OpportunityDiscovery",
    "experiment_runner",
    "ExperimentRunner",
    "ExperimentResult",
    "outcome_processor",
    "OutcomeProcessor",
]
