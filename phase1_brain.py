import os
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

# 1. Load Environment Variables
# Make sure you have a .env file with GOOGLE_API_KEY="your_key_here"
load_dotenv()

# 2. Initialize the Model (The "Brain")
# We use Gemini-1.5-Flash as it is fast and efficient for chat interactions.
llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    temperature=0.7  # Slightly creative for travel ideas, but still focused
)

# 3. Define the Persona (The "Prompt")
# This tells the AI *who* it is (System Message) and accepts user input (Human Message).
prompt = ChatPromptTemplate.from_messages([
    ("system", "You are an  AI Travel Planner named 'Voyage'. "
               "Your goal is to plan personalized itineraries based on user preferences. "
               "Be enthusiastic, practical, and always ask clarifying questions if the user's request is vague."),
    ("human", "{user_input}"),
])

# 4. Create the Chain (LCEL Syntax)
# We connect the Prompt -> Model -> Output Parser (to get clean text string)
chain = prompt | llm | StrOutputParser()

# 5. Test Function
def test_travel_planner():
    print("--- ✈️ AI Travel Planner (Phase 1) Initialized ✈️ ---")
    
    # Test Query 1: Vague request (To test if it asks clarifying questions)
    user_query = "I want to go to Japan for a week."
    print(f"\n👤 User: {user_query}")
    
    response = chain.invoke({"user_input": user_query})
    print(f"🤖 Voyage: {response}")

    # Test Query 2: Specific request
    user_query_2 = "Plan a 3-day romantic trip to Paris with a budget of $2000."
    print(f"\n👤 User: {user_query_2}")
    
    response_2 = chain.invoke({"user_input": user_query_2})
    print(f"🤖 Voyage: {response_2}")

if __name__ == "__main__":
    test_travel_planner()