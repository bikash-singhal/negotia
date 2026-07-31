from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.workflows.completion.nodes import CompletionWorkflowNodes
from app.workflows.completion.state import CompletionWorkflowState

type CompletionGraph = CompiledStateGraph[
    CompletionWorkflowState,
    None,
    CompletionWorkflowState,
    CompletionWorkflowState,
]


def build_completion_graph(nodes: CompletionWorkflowNodes) -> CompletionGraph:
    graph = StateGraph[
        CompletionWorkflowState,
        None,
        CompletionWorkflowState,
        CompletionWorkflowState,
    ](CompletionWorkflowState)
    graph.add_node("validate_session", nodes.validate_session)
    graph.add_node("create_or_reuse_debrief", nodes.create_or_reuse_debrief)
    graph.add_node("create_or_reuse_strategy", nodes.create_or_reuse_strategy)
    graph.add_node("create_or_reuse_memory", nodes.create_or_reuse_memory)
    graph.add_node("finalize_completion", nodes.finalize_completion)

    graph.add_edge(START, "validate_session")
    graph.add_edge("validate_session", "create_or_reuse_debrief")
    graph.add_edge("create_or_reuse_debrief", "create_or_reuse_strategy")
    graph.add_edge("create_or_reuse_strategy", "create_or_reuse_memory")
    graph.add_edge("create_or_reuse_memory", "finalize_completion")
    graph.add_edge("finalize_completion", END)

    return graph.compile()
