
from crewai import Agent
from llm_config import local_llm
try:
    from tools.course_tools import retrieve_courses, search_courses, get_course
except ModuleNotFoundError:
    import course_tools


planning_agent = Agent(
    role="Graduation Planning Specialist",
    goal=(
        "Turn verified course information and student priorities "
        "into a useful preliminary graduation plan."
    ),
    backstory=(
        "You help students organize courses into a potential "
        "academic plan. You distinguish required courses from "
        "recommended courses, respect prerequisites when verified, "
        "and clearly identify missing degree information. "
        "You never invent degree requirements or course availability."
    ),
    tools=[retrieve_courses, search_courses, get_course],
    llm=local_llm,
    allow_delegation=False,
    verbose=True,
)

