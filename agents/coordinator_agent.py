from crewai import Agent
from llm_config import local_llm


coordinator = Agent(
    role="Graduation Planner Coordinator",
    goal=(
        "Coordinate the specialists to produce an accurate, organized "
        "graduation plan."
    ),
    backstory=(
        "You coordinate the course catalog researcher and planning "
        "specialist. Make sure the final plan separates verified facts "
        "from assumptions, identifies missing information, and reports "
        "any failed checks. Never claim a course is offered or a degree "
        "requirement is met without supporting catalog information."
    ),
    llm=local_llm,
    allow_delegation=True,
    verbose=True,
)