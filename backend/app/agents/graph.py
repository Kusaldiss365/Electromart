from typing import TypedDict
from langgraph.graph import StateGraph, END
from sqlalchemy.orm import Session

from app.agents.router import route_intent
from app.agents.sales_agent import handle as sales_handle
from app.agents.marketing_agent import handle as marketing_handle
from app.agents.support_agent import handle as support_handle
from app.agents.orders_agent import handle as orders_handle


class ChatState(TypedDict):
    message: str
    history: list[dict]
    memory: dict
    route: str
    response: str
    db: Session


def router_node(state: ChatState):
    history = state.get("history", [])
    state["route"] = route_intent(
        state["message"],
        history,
        state.get("memory"),
    )
    return state


def sales_node(state: ChatState):
    history = state.get("history", [])
    memory = state.get("memory", {})
    state["response"] = sales_handle(state["db"], state["message"], history, memory)
    return state


def marketing_node(state: ChatState):
    history = state.get("history", [])
    memory = state.get("memory", {})
    state["response"] = marketing_handle(state["db"], state["message"], history, memory)
    return state


def support_node(state: ChatState):
    history = state.get("history", [])
    memory = state.get("memory", {})
    state["response"] = support_handle(state["db"], state["message"], history, memory)
    return state


def orders_node(state: ChatState):
    history = state.get("history", [])
    memory = state.get("memory", {})
    state["response"] = orders_handle(state["db"], state["message"], history, memory)
    return state


def build_graph():
    g = StateGraph(ChatState)
    g.add_node("router", router_node)
    g.add_node("sales", sales_node)
    g.add_node("marketing", marketing_node)
    g.add_node("support", support_node)
    g.add_node("orders", orders_node)

    g.set_entry_point("router")
    g.add_conditional_edges(
        "router",
        lambda s: s["route"],
        {"sales": "sales", "marketing": "marketing", "support": "support", "orders": "orders"},
    )

    g.add_edge("sales", END)
    g.add_edge("marketing", END)
    g.add_edge("support", END)
    g.add_edge("orders", END)

    return g.compile()
