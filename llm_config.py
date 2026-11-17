from crewai import LLM
# from dotenv import load_dotenv

# load_dotenv() # Searches for .env file to load into the process's environment variables

local_llm = LLM(
    model="llama3.2", # Requires ollama pull llama3.2 before being able to use
    base_url="http://localhost:11434/v1", # This is ollama's default port
    api_key="ollama", # Placeholder, can't be empty
    custom_openai=True,
    #context_window_size=4096 #Needs to be adjusted based on device usage, uncomment for Simrandeep demo
)