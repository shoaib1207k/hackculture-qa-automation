"""Graph wiring: three parallel check-type nodes feeding one gate."""

from strands.multiagent import GraphBuilder
from strands.multiagent.graph import Graph

from ..models import ChecklistVersion
from .nodes import BehaviourNode, FactualNode, GateNode, VerbatimNode

# A hung model call otherwise hangs the whole pipeline. A timeout raises out of
# the graph, which score_lead turns into a HUMAN_QA fallback.
NODE_TIMEOUT_S = 120.0
EXECUTION_TIMEOUT_S = 300.0

CHECK_NODES = (VerbatimNode, FactualNode, BehaviourNode)


def build_graph(version: ChecklistVersion) -> Graph:
    """Graph keeps its run state on the instance, so build one per scored lead
    (cheap: agents are created per call, not at build time)."""
    builder = GraphBuilder()
    for node_cls in CHECK_NODES:
        builder.add_node(node_cls(version), node_cls.node_id)
    builder.add_node(GateNode(version.version, [n.node_id for n in CHECK_NODES]), "gate")
    for node_cls in CHECK_NODES:  # edges after every node exists
        builder.add_edge(node_cls.node_id, "gate")
        builder.set_entry_point(node_cls.node_id)
    builder.set_node_timeout(NODE_TIMEOUT_S)
    builder.set_execution_timeout(EXECUTION_TIMEOUT_S)
    return builder.build()
