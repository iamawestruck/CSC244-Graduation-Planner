from crewai import Crew, Process, Task
from agents.planning_agent import planning_agent
from agents.course_agent import course_agent
from agents.coordinator_agent import coordinator
from models import GraduationPlan

#Need to be as specific as possible, but not so specific its rigid
graduation_task = Task(
    description=(
        "Create a preliminary course plan for {intended_semester}.\n"
        "Major: {major}\n"
        "Catalog year: {catalog_year}\n"
        "Student interests: {preferences}\n"
        "Courses completed: {completed_courses}\n"
        "Remaining required courses: {required_courses}\n"
        "Remaining choice groups: {remaining_choice_groups}\n"
        "Allowed semester unit range: {min_unit_load} to {max_unit_load} units.\n\n"
        "Verified required-course lookup:\n{required_course_catalog}\n\n"
        "CSV-derived course candidates (the allowed source for this plan):\n"
        "{course_candidates}\n\n"
        #"Previous Python validation feedback:\n{revision_feedback}\n\n"
        "Choose courses from the candidate list above. Do not create or alter "
        "course codes, names, credits, prerequisites, or requirement groups. "
        "Prioritize eligible unfinished required courses, then use eligible "
        "choice-group candidates only as needed to reach the minimum load.\n"
        "The listed prerequisite conditions must be satisfied by completed "
        "courses. Treat a prerequisite as concurrent only when the catalog "
        "explicitly says it may be concurrent and the course is also in this "
        "plan. Do not include courses with unmet or non-course prerequisite "
        "conditions.\n"
        "Give each course a short reason. Keep the total within the allowed "
        "range. The course CSV is a catalog snapshot and its schedule rows are "
        "synthetic, so do not claim an actual Spring 2027 section is available. "
        "Put unresolved offering, prerequisite, or degree-rule details in "
        "unresolved_questions. Do not claim official graduation eligibility.\n"
    ),
    expected_output=(
        "A GraduationPlan containing a preliminary semester course list, exact "
        "catalog details, reasons, assumptions, and unresolved questions."
    ),
    output_pydantic=GraduationPlan, # Formats Crew's final response to match this model
    agent=planning_agent,
)

# This could be a few different files, kept here for simplification
planning_crew = Crew(
    agents=[planning_agent, course_agent],
    #manager_agent=[coordinator],
    tasks=[graduation_task],
    process=Process.sequential, # Process.sequential required
    verbose=True,
)
