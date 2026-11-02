from crewai import Agent, Crew, Process, Task, LLM
from agents import search_courses, get_course, check_user_requirements, retrieve_courses
from dotenv import load_dotenv

load_dotenv()

local_llm = LLM(
    model="llama3.2",
    base_url="http://localhost:11434/v1",
    api_key="ollama",
    custom_openai=True,
)

course_agent = Agent(
    role="Course Catalog Researcher",
    goal=(
        "Find relevant courses and verify their details "
        "using the provided course catalog tools."
    ),
    backstory=(
        "You specialize in this universitys course catalogs. "
        "You use retrieve_courses and search_courses to cross reference "
        "course information against the Graduation Planning Specialists plan. The available dataset is "
        "from Fall 2019, not the current catalog."
    ),
    tools=[retrieve_courses, search_courses, get_course],
    llm=local_llm,
    allow_delegation=False,
    verbose=True,
)

planning_agent = Agent(
    role="Graduation Planning Specialist",
    goal=(
        "Turn verified course information from the course_agent and student priorities "
        "into a useful preliminary graduation plan that fits the users requirements."
    ),
    backstory=(
        "You help students organize courses into a potential "
        "academic plan. You distinguish required courses from "
        "recommended courses, respect prerequisites when verified, "
        "and clearly identify missing degree information using the check_user_requirements tool. "
        "You never invent degree requirements or course availability." 
        "Never use duplicates in your final plan of the same course Subject and Number even if the start and end times are different."
    ),
    tools=[retrieve_courses, check_user_requirements],
    llm=local_llm,
    allow_delegation=True,
    verbose=True,
)

requirement_agent = Agent(
    role="Graduation Requirement Auditor",
    goal=(
        "Audit a preliminary graduation plan against "
        "the student's supplied degree requirements "
        "and identify missing courses or credit shortfalls."
    ),
    backstory=(
        "You independently review proposed graduation plans. "
        "You use the check_user_requirements tool for "
        "course-code and credit-hour comparisons. You report "
        "missing information, distinguish verified issues "
        "from unresolved questions, and never invent degree "
        "requirements or claim official graduation eligibility."
        "Just because a description or name doesn't match, as long as the subject and number are correct it should be fine."
    ),
    tools=[check_user_requirements],
    llm=local_llm,
    allow_delegation=False,
    verbose=True,
)


coordinator = Agent(
    role="Graduation Planner Coordinator",
    goal=(
        "Coordinate the specialist agents to answer the student's request with an accurate, organized graduation plan that lists the classes."
    ),
    backstory=(
        "You are responsible for coordinating a graduation-planning team. First determine what information the student needs. "
        "Delegate catalog research to the Course Catalog Researcher and planning analysis to the Graduation Planning Specialist. "
        "Let the Graduation Requirement Auditor check to make sure all the required courses are in the preliminary plan."
        "Check that the Graduation Requirement's checked plan  distinguishes verified facts from assumptions and identifies missing information. "
        "Do not claim that courses are currently offered or that degree requirements are satisfied without supporting data."
        "Ensure the requirement-checking task reviews the preliminary plan before presenting the final report. "
        "Clearly communicate any failures and unresolved checks."
    ),
    llm=local_llm,
    allow_delegation=True,
    verbose=True,
)

graduation_task = Task(
    description=(
        "Create a preliminary course plan for: {topic}.\n"
        "Student priorities: {priorities}\n"
        "Completed courses: {completed_courses}\n"
        "Required courses supplied by the student: {required_courses}\n"
        "Minimum planned credit hours: {minimum_credits}\n"
        "Planning constraints: {constraints}\n\n"
        "Include the date and end time of those courses identified."
        "Do not invent requirements or prerequisites. If the "
        "available information is insufficient, explain this in "
        "unresolved_questions.\n\n"
        "Return the result in the GraduationPlan schema. "
        "Do not add Markdown or commentary outside the structured output."
        "Create a graduation course plan based on the student's inputs.\n\n"
    ),
    expected_output=(
        "A structured preliminary graduation-planning report with "
        "course recommendations, supporting catalog information, "
        "planning rationale, assumptions, and limitations."
    ),
)

crew = Crew(
    agents=[course_agent, planning_agent, requirement_agent],
    tasks=[graduation_task],
    manager_agent=coordinator,
    process=Process.hierarchical,
    verbose=True,
)

if __name__ == "__main__":
    result = crew.kickoff(
        inputs={
            "topic": "machine learning",
            "priorities": "Prioritize required courses, then prerequisites.",
            "completed_courses": "Not provided",
            "constraints": "No confirmed degree audit or current course schedule.",
            "completed_courses": "CS 101",
            "required_courses": "CS 201, MATH 221",
            "minimum_credits": 30,
        }
    )

    print("\n===== GRADUATION PLAN =====\n")
    print(result)