"""
Trip Swarm — backend.py

Multi-agent travel planning workflow using LangGraph.
Agents: Flight Agent → Hotel Agent → Itinerary Agent → Response Agent
"""

import os
from typing import TypedDict

from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import StateGraph, END

from tools.tavily_tool import tavily_search
from tools.flight_tool import search_flights

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

#  LLM 
llm = ChatGroq(
    api_key=GROQ_API_KEY,
    model="openai/gpt-oss-120b",
    temperature=0,
)

_SEARCH_SNIPPET = 800

# Helpers

def _trim(text: str, limit: int = _SEARCH_SNIPPET) -> str:
    """Hard-trim a string to `limit` chars, breaking on a word boundary."""
    if len(text) <= limit:
        return text
    return text[:limit].rsplit(" ", 1)[0] + "…"


def _llm_call(system: str, user: str) -> str:
    """Single LLM call with basic error handling."""
    try:
        resp = llm.invoke([
            SystemMessage(content=system),
            HumanMessage(content=user),
        ])
        return resp.content
    except Exception as e:
        return f"[LLM error: {e}]"

# Travel State

class TravelState(TypedDict):
    user_query:      str
    flight_results:  str   
    hotel_results:   str  
    itinerary:       str   
    response:        str   


# Agent Nodes

# 1. Flight Agent 

def flight_agent(state: TravelState) -> TravelState:
    """
    Fetch live flight data from AviationStack.
    Returns raw formatted string — no LLM involved.
    """
    raw = search_flights(state["user_query"])
    return {**state, "flight_results": raw}


# 2. Hotel Agent

def hotel_agent(state: TravelState) -> TravelState:
    """
    Search for hotels via Tavily.
    Returns raw formatted string — no LLM involved.
    """
    query = f"Best hotels for {state['user_query']}"
    raw   = tavily_search(query, max_results=5)
    return {**state, "hotel_results": _trim(raw, 1200)}


#  3. Itinerary Agent

def itinerary_agent(state: TravelState) -> TravelState:
    """
    Use Tavily to fetch attractions + food, then ask the LLM to
    build a concise day-by-day itinerary.  
    """
    query = state["user_query"]

    places = _trim(tavily_search(f"top things to do {query}", max_results=4), 900)
    food   = _trim(tavily_search(f"local food must-eat {query}", max_results=3), 600)

    system = (
        "You are an expert travel itinerary planner. "
        "Create a practical, day-by-day itinerary with key activities and food tips. "
        "Be concise — 250 words max."
    )
    prompt = (
        f"Trip request: {query}\n\n"
        f"Top attractions:\n{places}\n\n"
        f"Local food highlights:\n{food}\n\n"
        "Create a concise day-by-day itinerary (≤250 words)."
    )

    itinerary = _llm_call(system, prompt)
    return {**state, "itinerary": itinerary}


# 4. Final Agent 
def final_agent(state: TravelState) -> TravelState:
    """
    Combine flight data, hotel data, and the itinerary into one
    beautifully formatted Markdown travel report.  
    """
    system = (
        "You are a professional AI travel booking assistant and formatter. "
        "Combine all provided information into one clean, well-structured Markdown report. "
        "Use these exact sections:\n"
        "1. 🗺️ Trip Summary\n"
        "2. ✈️ Flight Information\n"
        "3. 🏨 Hotel Suggestions\n"
        "4. 📅 Day-by-Day Itinerary\n"
        "5. 💰 Estimated Budget\n"
        "6. 💡 Final Recommendations\n\n"
        "Rules:\n"
        "- Use proper Markdown tables where appropriate (e.g. hotel comparison, budget breakdown).\n"
        "- Keep flight section factual; note that live flight API does not provide ticket prices.\n"
        "- Be practical, budget-aware, and easy to follow.\n"
        "- Avoid filler sentences."
    )

    prompt = (
        f"User Trip Request:\n{state['user_query']}\n\n"
        f"✈️ RAW FLIGHT DATA:\n{state['flight_results']}\n\n"
        f"🏨 RAW HOTEL DATA:\n{state['hotel_results']}\n\n"
        f"📅 ITINERARY:\n{state['itinerary']}\n\n"
        "Write the final Trip Swarm travel report using the sections above."
    )

    response = _llm_call(system, prompt)
    return {**state, "response": response}


# Build Langgraph Workflow

_graph = StateGraph(TravelState)

_graph.add_node("flight_agent",    flight_agent)
_graph.add_node("hotel_agent",     hotel_agent)
_graph.add_node("itinerary_agent", itinerary_agent)
_graph.add_node("final_agent",     final_agent)

_graph.set_entry_point("flight_agent")
_graph.add_edge("flight_agent",    "hotel_agent")
_graph.add_edge("hotel_agent",     "itinerary_agent")
_graph.add_edge("itinerary_agent", "final_agent")
_graph.add_edge("final_agent",     END)

travel_app = _graph.compile()   # no checkpointer argument


# Public API

async def run_travel_workflow(
    message: str,
    user_id: str = "",
):
    """
    Run the full travel planning workflow.
    Each call is completely stateless — no history, no checkpoints.
    Returns: { "response": str }
    """
    initial_state = TravelState(
        user_query=message,
        flight_results="",
        hotel_results="",
        itinerary="",
        response="",
    )
    result = await travel_app.ainvoke(initial_state)
    return {"response": result["response"]}