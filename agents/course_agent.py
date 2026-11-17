from crewai import Agent
from llm_config import local_llm
from tools.course_tools import search_courses, get_course



course_agent = Agent(
    role="Course Catalog Researcher",
    goal=(
        "Find relevant courses and verify their details "
        "using the provided course catalog tools."
    ),
    backstory=(
        "You specialize in university course catalogs. "
        "You use search_courses and get_course to verify course information. "
        "The supplied CSV is a Fall 2026 catalog snapshot."
    ),
    tools=[search_courses, get_course],
    llm=local_llm,
    allow_delegation=False,
    verbose=True,
)

