"""This is an automatically generated file. Do not modify it.

This file was generated using `langgraph-gen` version 0.0.3.
To regenerate this file, run `langgraph-gen` with the source `yaml` file as an argument.

Usage:

1. Add the generated file to your project.
2. Create a new agent using the stub.

Below is a sample implementation of the generated stub:

```python
from typing_extensions import TypedDict

from stub import CustomAgent

class SomeState(TypedDict):
    # define your attributes here
    foo: str

# Define stand-alone functions
def supervisor(state: SomeState) -> dict:
    print("In node: supervisor")
    return {
        # Add your state update logic here
    }


def react_agent(state: SomeState) -> dict:
    print("In node: react_agent")
    return {
        # Add your state update logic here
    }


def code_act(state: SomeState) -> dict:
    print("In node: code_act")
    return {
        # Add your state update logic here
    }


def final_answer(state: SomeState) -> dict:
    print("In node: final_answer")
    return {
        # Add your state update logic here
    }


def conditional_edge_1(state: SomeState) -> str:
    print("In condition: conditional_edge_1")
    raise NotImplementedError("Implement me.")


agent = CustomAgent(
    state_schema=SomeState,
    impl=[
        ("supervisor", supervisor),
        ("react_agent", react_agent),
        ("code_act", code_act),
        ("final_answer", final_answer),
        ("conditional_edge_1", conditional_edge_1),
    ]
)

compiled_agent = agent.compile()

print(compiled_agent.invoke({"foo": "bar"}))
"""

from typing import Callable, Any, Optional, Type

from langgraph.constants import START, END
from langgraph.graph import StateGraph


def CustomAgent(
    *,
    state_schema: Optional[Type[Any]] = None,
    config_schema: Optional[Type[Any]] = None,
    input: Optional[Type[Any]] = None,
    output: Optional[Type[Any]] = None,
    impl: list[tuple[str, Callable]],
) -> StateGraph:
    """Create the state graph for CustomAgent."""
    # Declare the state graph
    builder = StateGraph(
        state_schema, config_schema=config_schema, input=input, output=output
    )

    nodes_by_name = {name: imp for name, imp in impl}

    all_names = set(nodes_by_name)

    expected_implementations = {
        "supervisor",
        "react_agent",
        "codeact_agent",
        "final_answer",
        "conditional_edge_1",
    }

    missing_nodes = expected_implementations - all_names
    if missing_nodes:
        raise ValueError(f"Missing implementations for: {missing_nodes}")

    extra_nodes = all_names - expected_implementations

    if extra_nodes:
        raise ValueError(
            f"Extra implementations for: {extra_nodes}. Please regenerate the stub."
        )

    # Add nodes
    builder.add_node("supervisor", nodes_by_name["supervisor"])
    builder.add_node("react_agent", nodes_by_name["react_agent"])
    builder.add_node("codeact_agent", nodes_by_name["codeact_agent"])
    builder.add_node("final_answer", nodes_by_name["final_answer"])

    # Add edges
    builder.add_edge(START, "supervisor")
    builder.add_edge("final_answer", END)
    builder.add_edge("react_agent", "final_answer")
    builder.add_edge("codeact_agent", "final_answer")
    builder.add_conditional_edges(
        "supervisor",
        nodes_by_name["conditional_edge_1"],
        [
            "react_agent",
            "codeact_agent",
        ],
    )
    return builder
