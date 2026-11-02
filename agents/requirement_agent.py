from crewai import Agent
from llm_config import local_llm
from tools.course_tools import check_user_requirements


requirement_agent = Agent(
    role="Graduation Requirement Auditor",
    goal=(
        "Audit a preliminary graduation plan against the student's "
        "supplied degree requirements and identify missing courses "
        "or credit shortfalls."
    ),
    backstory=(
        "You independently review graduation plans. You use the "
        "check_user_requirements tool for course-code and credit-hour "
        "comparisons. You report missing information, distinguish "
        "verified issues from unresolved questions, and never invent "
        "degree requirements or claim official graduation eligibility."
    ),
    tools=[check_user_requirements],
    llm=local_llm,
    allow_delegation=False,
    verbose=True,
)