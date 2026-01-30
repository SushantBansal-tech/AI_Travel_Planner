# import os
# from dotenv import load_dotenv
# from langchain_google_genai import ChatGoogleGenerativeAI
# from langchain.agents import create_agent  # New v1 API
# from langchain_core.tools import Tool, tool
# from langchain_community.utilities import SerpAPIWrapper
# from pydantic import BaseModel, Field
# from typing import List

# # Import your RAG setup from Phase 2
# from phase2_rag import setup_rag_pipeline

# # 1. Load Environment
# load_dotenv()

# # 2. Define Tools (The "Hands")

# # Tool A: Google Search (unchanged)
# search = SerpAPIWrapper()
# # FIXED Tool names (lines ~25, ~45)
# search_tool = Tool(
#     name="google_search",  # ✅ No spaces
#     func=search.run,
#     description="Useful for finding live flight prices, weather, and current events."
# )

# @tool  # @tool auto-generates valid name from function
# def calculate_trip_cost(flight_price: float, hotel_price: float, days: int) -> str:
#     """Calculates the total trip cost given flight price, hotel price per night, and number of days."""
#     total = flight_price + (hotel_price * days)
#     return f"The total estimated cost is ${total:.2f}."


# # Tool C: RAG (FIXED - converts Documents to string)
# vectorstore = setup_rag_pipeline()
# retriever = vectorstore.as_retriever()
# # Tool C: RAG (FIXED NAME + func)
# def rag_func(query: str) -> str:
#     """Search Paris travel guide for relevant information."""
#     docs = retriever.invoke(query)
#     return "\n\n".join([doc.page_content for doc in docs])

# rag_tool = Tool(
#     name="paris_guide",  # ✅ Valid for Gemini
#     func=rag_func,
#     description="Useful for finding hidden gems, visa rules, and specific tips about Paris from the guide."
# )



# # Combine all tools
# tools = [search_tool, calculate_trip_cost, rag_tool]



# # 3. Initialize the Agent (UPDATED for LangChain v1)
# llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0)

# # This is PHASE 4: We define exactly what the JSON should look like.

# class DailyActivity(BaseModel):
#     day: int = Field(description="The day number of the trip")
#     morning: str = Field(description="Activity for the morning")
#     afternoon: str = Field(description="Activity for the afternoon")
#     evening: str = Field(description="Activity for the evening")

# class TripItinerary(BaseModel):
#     destination: str = Field(description="The city being visited")
#     total_cost_estimate: str = Field(description="The calculated total cost")
#     hidden_gem_visited: str = Field(description="Name of the hidden gem from the guide")
#     daily_plan: List[DailyActivity] = Field(description="List of daily activities")

# # We create a specific LLM instance just for formatting
# llm_formatter = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0)
# # We force it to output our Pydantic class
# structured_llm = llm_formatter.with_structured_output(TripItinerary)

# # ReAct system prompt (replaces deprecated hub.pull)
# system_prompt = """You MUST use tools to answer accurately.

# AVAILABLE TOOLS:
# 1. google_search: Current flight prices, weather, events
# 2. calculate_trip_cost: Total cost calculator
# 3. paris_guide: Paris travel info from guide

# STEPS:
# 1. Use paris_guide for "hidden gems"
# 2. Use google_search for "NYC to Paris flight price"  
# 3. Use calculate_trip_cost with flight + $150/night * 5 days

# Format exactly:
# Thought: [your reasoning]
# Action: [exact tool name]
# Action Input: [input for tool]
# Observation: [tool result - don't make up]
# ...

# Final Answer: [only after all tools used]

# QUERY: {input}"""

# # Create agent (no AgentExecutor needed)
# agent = create_agent(
#     llm,
#     tools,
#     system_prompt=system_prompt
# )

# # 4. Run the Agent (UPDATED input format)
# def test_agent():
#     print("\n--- 🕵️ Agent Activated ---")
    
#     # Complex Query: Requires Search + Calculation + RAG
#     query = (
#          "Find NYC-Paris flight price and calculate total with $150/night hotel for 5 days"

#     )
    
#     # New input format: {"messages": [...]}
#     print("\n[1/2] 🕵️ Agent is researching and planning...")
#     response = agent.invoke({
#         "messages": [{"role": "user", "content": query}]
#     })
#     message_object= response["messages"][-1]
#     if isinstance(message_object.content, list):
#      raw_text = message_object.content[0]['text']
#     else:
#      raw_text = message_object.content
    
#     print(f"\n--- Raw Agent Output ---\n{raw_text}\n------------------------")
    
#      # 3. Run the Formatter (Structuring Phase)
#     print("\n[2/2] 📝 Formatting into JSON...")
    
#     # We ask the LLM to parse the previous raw text into our Class
#     final_json = structured_llm.invoke(f"Extract the itinerary details from this text: {raw_text}")
    
#     # 4. Display Result
#     print("\n--- ✅ FINAL STRUCTURED JSON ---")
#     print(final_json.model_dump_json(indent=2))
    
#     # Extract final answer from messages
#     # final_message = response["messages"][-1]
#     # print(f"\n🤖 Final Answer: {final_message.content}")

# if __name__ == "__main__":
#     test_agent()


import os
from dotenv import load_dotenv
from typing import Annotated, List, Literal, TypedDict, Annotated
import operator
from pydantic import BaseModel, Field

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_community.utilities import SerpAPIWrapper
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, SystemMessage, AnyMessage
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode

# --- 1. Load Environment ---
load_dotenv()

# --- 2. Tools ---
search = SerpAPIWrapper()

@tool
def google_search(query: str):
    """
    Use this tool to find:
    1. Flight & Hotel prices.
    2. OPENING HOURS of attractions.
    3. LOCATIONS (e.g. 'Is Senso-ji near Tokyo Skytree?').
    """
    return search.run(query)

tools = [google_search]

# --- 3. Schema (Unchanged) ---
class Activity(BaseModel):
    time_slot: str = Field(description="e.g., '09:00 AM - 11:30 AM'")
    activity_name: str = Field(description="Name of the place or activity")
    description: str = Field(description="What to do there")
    location_zone: str = Field(description="Neighborhood name (e.g., 'Shibuya', 'Downtown')")
    price_estimate: str = Field(description="Cost of ticket/entry if any")

class DayPlan(BaseModel):
    day_number: int
    theme: str = Field(description="Theme of the day")
    schedule: List[Activity] = Field(description="Chronological list of activities")

class TripLogistics(BaseModel):
    flight_details: str = Field(description="Cheapest flight found with price and airline")
    hotel_details: str = Field(description="Budget hotel found with price and location")
    total_trip_cost: str = Field(description="Total estimated cost")

class FinalItinerary(BaseModel):
    destination: str
    logistics: TripLogistics
    daily_itinerary: List[DayPlan]
    travel_tips: str = Field(description="Tips for saving money")

# --- 4. The Brain (Unchanged) ---
SYSTEM_PROMPT_TEXT = """
You are a Master Travel Logistics Planner. 

RULES FOR ITINERARY CREATION:
1. **CLUSTERING**: You MUST group activities by location. Do not make the user travel back and forth across the city.
2. **REALISM**: Check opening hours. Don't schedule a museum at 8:00 AM if it opens at 10:00 AM.
3. **MINIMAL BUDGET**: Always prioritize the cheapest viable flights and hotels.
4. **COMPLETENESS**: If the user asked for specific "important places," you MUST include them.

PROCESS:
1. Search for flight/hotel prices first.
2. Search for the location/neighborhood of top attractions.
3. Group attractions into "Zones" for each day.
4. Generate the final schedule.
"""

llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash", 
    temperature=0,
    system_instruction=SYSTEM_PROMPT_TEXT 
)

llm_with_tools = llm.bind_tools(tools)

# --- 5. FIXED State ---
class AgentState(TypedDict):
    messages: Annotated[list[AnyMessage], operator.add]  # Proper accumulation
    final_output: FinalItinerary

# NODE 1: Planner (Unchanged)
def planner_node(state: AgentState):
    response = llm_with_tools.invoke(state['messages'])
    return {"messages": [response]}

# NODE 2: FIXED Formatter
def formatter_node(state: AgentState):
    structured_llm = llm.with_structured_output(FinalItinerary)
    
    # Clear synthesis instruction using full research history
    synthesis_prompt = HumanMessage(content="""Based on ALL the research above about flights, hotels, locations, opening hours, and prices:

Generate the complete Final Itinerary in the exact structured format.
- Cluster by location zones (no criss-crossing)
- Respect opening hours and budget  
- Include all must-visit places
- Chronological schedule per day""")
    
    final_json = structured_llm.invoke(state['messages'] + [synthesis_prompt])
    return {"final_output": final_json}

# NODE 3: FIXED Router
def router(state: AgentState) -> Literal["tools", "formatter"]:
    last_message = state['messages'][-1]
    if last_message.tool_calls:
        return "tools"
    return "formatter"

# --- 6. FIXED Graph ---
workflow = StateGraph(AgentState)

workflow.add_node("planner", planner_node)
workflow.add_node("tools", ToolNode(tools))  # Now works with annotated state
workflow.add_node("formatter", formatter_node)

workflow.set_entry_point("planner")
workflow.add_conditional_edges("planner", router, {"tools": "tools", "formatter": "formatter"})
workflow.add_edge("tools", "planner") 
workflow.add_edge("formatter", END)

app = workflow.compile()

# --- 7. Execution (Unchanged) ---
if __name__ == "__main__":
    user_request = """
    Plan a 3-day trip to Paris for a student.
    Budget: Minimal.
    Must Visit: Eiffel Tower, Louvre, Montmartre, and Versailles.
    """
    
    print(f"User Request: {user_request}")
    print("\n--- 🧠 Agent is Thinking (Checking Locations & Prices)... ---")
    
    inputs = {"messages": [HumanMessage(content=user_request)]}
    
    # Run the graph
    try:
        # Stream progress
        for output in app.stream(inputs):
            for key, value in output.items():
                print(f"✅ Finished Node: {key}")
                
        # Get final result
        result = app.invoke(inputs)
        print("\n--- ✅ SMART ITINERARY GENERATED ---")
        print(result["final_output"].model_dump_json(indent=2))
        
    except Exception as e:
        print(f"\n❌ Error Occurred: {e}")
        import traceback
        traceback.print_exc()