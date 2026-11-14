from crewai import LLM
from dotenv import load_dotenv

load_dotenv()

local_llm = LLM(
    model="llama3.2",
    base_url="http://localhost:11434/v1",
    api_key="ollama",
    custom_openai=True,
    context_window_size=4096,
)