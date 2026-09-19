"""Strands graph nodes: one per check type, plus the deterministic gate.

Retailer-level config (the checklist version's checks) is baked in at
construction. Lead-level data (lead, segments) arrives per run in
`invocation_state`, the caller's own dict, shared by every node in the run.

Graph hands a downstream node only upstream TEXT, so check nodes also record
their verdicts in invocation_state[VERDICTS_KEY] under their node id; that is
how the gate receives structured data."""

import logging
import time
from dataclasses import dataclass, field

from strands.multiagent.base import MultiAgentBase, MultiAgentResult, Status

from ..checks.behaviour import run_behaviour_checks
from ..checks.factual import run_factual_checks
from ..checks.verbatim import run_verbatim_checks
from ..models import ChecklistVersion, CheckType, CheckVerdict
from .gate import decide

logger = logging.getLogger(__name__)

VERDICTS_KEY = "verdicts_by_node"


@dataclass
class CheckNodeResult(MultiAgentResult):
    verdicts: list[CheckVerdict] = field(default_factory=list)


@dataclass
class GateResult(MultiAgentResult):
    decision: str = ""
    reasons: list[str] = field(default_factory=list)
    verdicts: list[CheckVerdict] = field(default_factory=list)
    checklist_version: str = ""


class CheckNode(MultiAgentBase):
    """Runs every check of one type from the checklist version."""

    node_id: str
    check_type: CheckType

    def __init__(self, version: ChecklistVersion):
        super().__init__()
        self.id = self.node_id
        self.version = version
        self.checks = [c for c in version.checks if c.type == self.check_type]

    async def evaluate(self, lead, segments) -> list[CheckVerdict]:
        raise NotImplementedError

    async def invoke_async(self, task, invocation_state: dict | None = None, **kwargs) -> CheckNodeResult:
        lead, segments = invocation_state["lead"], invocation_state["segments"]
        logger.info("node %s start lead=%s checks=%d", self.id, lead.lead_id, len(self.checks))
        started = time.perf_counter()
        verdicts = await self.evaluate(lead, segments)
        invocation_state.setdefault(VERDICTS_KEY, {})[self.id] = verdicts
        logger.info("node %s done lead=%s verdicts=%d in %.1fs", self.id, lead.lead_id,
                    len(verdicts), time.perf_counter() - started)
        return CheckNodeResult(status=Status.COMPLETED, verdicts=verdicts)


class VerbatimNode(CheckNode):
    node_id, check_type = "verbatim", "verbatim"

    async def evaluate(self, lead, segments):
        return await run_verbatim_checks(segments, lead, self.checks, self.version.version)


class FactualNode(CheckNode):
    node_id, check_type = "factual", "factual"

    async def evaluate(self, lead, segments):
        return await run_factual_checks(segments, lead, self.checks, self.version.version)


class BehaviourNode(CheckNode):
    node_id, check_type = "behaviour", "behaviour"

    async def evaluate(self, lead, segments):
        return run_behaviour_checks(segments, lead, self.checks, self.version.version)


class GateNode(MultiAgentBase):
    """Deterministic gate -- no LLM call, hard business rule (see gate.decide())."""

    def __init__(self, checklist_version: str, upstream_ids: list[str]):
        super().__init__()
        self.id = "gate"
        self.checklist_version = checklist_version
        self.upstream_ids = upstream_ids

    async def invoke_async(self, task, invocation_state: dict | None = None, **kwargs) -> GateResult:
        # Integrity check on the data channel: every upstream node must have
        # recorded its verdicts, or the decision would rest on partial evidence.
        by_node = invocation_state.get(VERDICTS_KEY, {})
        missing = [n for n in self.upstream_ids if n not in by_node]
        if missing:
            raise RuntimeError(f"Gate is missing verdicts from upstream nodes: {missing}")

        verdicts = [v for n in self.upstream_ids for v in by_node[n]]
        gate = decide(invocation_state["lead"].lead_id, verdicts)
        return GateResult(status=Status.COMPLETED, decision=gate.decision, reasons=gate.reasons,
                          verdicts=verdicts, checklist_version=self.checklist_version)
