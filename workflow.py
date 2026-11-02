from crewai import Crew, Process, Task
from agents.planning_agent import planning_agent
from agents.requirement_agent import requirement_agent
from models import GraduationPlan

graduation_task = Task(
    description=(
        "Create a preliminary course plan for {intended_semester}.\n"
        "Major: {major}\n"
        "Catalog year: {catalog_year}\n"
        "Student interests: {preferences}\n"
        "Courses completed: {completed_courses}\n"
        "Courses currently in progress: {current_courses}\n"
        "Previously failed courses: {failed_courses}\n"
        "Remaining required courses: {required_courses}\n"
        "Remaining choice groups: {remaining_choice_groups}\n"
        "Allowed semester unit range: {min_unit_load} to {unit_limit} units.\n\n"
        "Required-course catalog lookup:\n"
        "{required_course_catalog}\n\n"
        "Use only course codes that appear exactly in the required-course "
        "lookup or retrieved catalog records. Do not invent course codes "
        "or names. Build a tentative plan of 12–18 units from verified "
        "courses. If prerequisites or Spring 2027 availability are unknown, "
        "mention that in unresolved_questions rather than inventing courses "
        "or returning an empty plan.\n\n"
        "Previous Python validation feedback:\n"
        "{revision_feedback}\n\n"
        "Use the course retrieval tool before recommending courses. "
        "Use only courses supported by the retrieved catalog records, "
        "with their exact course codes, names, and credit hours.\n"
        "Include a brief reason for each proposed course.\n"
        "Treat every course in Remaining required courses as unfinished. "
        "Never claim all requirements are complete while that list is nonempty.\n"
        "Call a course a remaining required course only if its exact code "
        "appears in that list. Label other courses as choice-group courses "
        "only when the catalog confirms the group.\n"
        "Schedule eligible remaining required courses first, then add "
        "verified choice-group courses that fit. Keep the total within the "
        "unit range above. If verified eligible courses cannot reach the "
        "minimum, explain why in unresolved_questions.\n"
        "Do not try to fit every remaining degree requirement into one "
        "semester. Treat current courses as not yet completed. Do not assume "
        "a failed course should be retaken unless the inputs say so. Do not "
        "claim a course is offered this semester unless the data confirms it. "
        "Put missing information and questions in unresolved_questions.\n"
    ),
    expected_output=(
        "A GraduationPlan with proposed courses, exact catalog details, "
        "reasons, assumptions, and unresolved questions."
    ),
    output_pydantic=GraduationPlan,
    agent=planning_agent,
)
#Crew + Running

planning_crew = Crew(
    agents=[planning_agent],
    tasks=[graduation_task],
    process=Process.sequential,
    verbose=True,
)
