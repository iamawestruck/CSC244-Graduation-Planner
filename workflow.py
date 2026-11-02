from crewai import Crew, Process, Task
from agents.planning_agent import planning_agent
from agents.requirement_agent import requirement_agent
from models import GraduationPlan

graduation_task = Task(
    description=(
        "Create a preliminary course plan for: {topic}.\n"
        "Student priorities: {priorities}\n"
        "Completed courses: {completed_courses}\n"
        "Required courses supplied by the student: {required_courses}\n"
        "Minimum planned credit hours: {minimum_credits}\n"
        "Planning constraints: {constraints}\n\n"
        "Previous Python validation feedback:\n"
        "{revision_feedback}\n\n"
        "Do not invent requirements or prerequisites. If the "
        "available information is insufficient, explain this in "
        "unresolved_questions.\n\n"
        "Return the result in the GraduationPlan schema. "
        "Do not add Markdown or commentary outside the structured output.\n\n"
        "Create a graduation course plan based on the student's inputs.\n\n"
        "Before recommending courses, use the Retrieve courses from "
        "vector database tool to search for courses relevant to the "
        "student's interests and requirements.\n\n"
        "Only recommend courses supported by the retrieved catalog "
        "records. Use the exact course codes, names, and credit hours "
        "from the catalog. Do not invent course information.\n\n"
        "If the retrieved records do not provide enough information, "
        "state what is missing rather than guessing. Include any "
        "assumptions and unresolved questions."
    ),
    expected_output=(
        "A GraduationPlan containing verified proposed courses, "
        "selected credit hours, reasons, assumptions, and unresolved questions."
    ),
    output_pydantic=GraduationPlan,
    agent=planning_agent,
)


requirement_check_task = Task(
    description=(
        "Audit the preliminary graduation plan produced "
        "by the planning workflow.\n\n"

        "Student-provided degree requirements: "
        "{required_courses}\n"
        "Student's completed courses: {completed_courses}\n"
        "Proposed courses: {planned_courses}\n"
        "Minimum required credit hours: {minimum_credits}\n"
        "Planned credit hours: {planned_credit_hours}\n\n"

        "Use the check_degree_requirements tool to compare "
        "the supplied course codes and credit hours.\n"
        "Do not assume that a course satisfies a degree "
        "requirement merely because its name sounds relevant.\n\n"

        "Also review the preliminary plan for prerequisite "
        "concerns, unsupported assumptions, and missing "
        "information. Flag these for verification rather "
        "than claiming that the tool checked them.\n\n"

        "Return a validation report containing passed checks, "
        "identified issues, unresolved questions, and "
        "recommended corrections. State clearly that this "
        "is not an official degree audit."
    ),
    expected_output=(
        "A requirement validation report with the results "
        "of the Python checks, identified issues, unresolved "
        "requirements, and recommended corrections."
    ),
    agent=requirement_agent,
    context=[graduation_task],
)


#Crew + Running

planning_crew = Crew(
    agents=[planning_agent],
    tasks=[graduation_task],
    process=Process.sequential,
    verbose=True,
)
