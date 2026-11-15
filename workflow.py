from crewai import Crew, Process, Task
from agents.planning_agent import planning_agent
from models import DraftPlan


def make_planning_crew():
    task = Task(
        description=(
            "Create ONE preliminary semester plan for "
            "{intended_semester}.\n"
            "Major: {major}\n"
            "Interests: {preferences}\n"
            "Completed courses: {completed_courses}\n"
            "Unfinished required courses: {required_courses}\n"
            "Remaining choice groups: {remaining_choice_groups}\n"
            "Allowed credits: {min_unit_load} to {max_unit_load}.\n\n"

            "CANDIDATES:\n{course_candidates}\n\n"

            "Select only codes from these candidates. "
            "Do not repeat courses. Prioritize unfinished required "
            "courses, then relevant choice-group courses. "
            "Choose a subset within the allowed credit range.\n"

            "If a prerequisite explicitly permits concurrent "
            "enrollment, include that prerequisite in this plan "
            "unless it is already completed.\n"

            "Return code and reason for each selection. "
            "Python supplies catalog names and credits. "
            "Do not claim confirmed course availability or "
            "official graduation eligibility.\n"

            "If a supported plan cannot meet the requested range, "
            "explain the shortfall in unresolved_questions.\n\n"

            "CORRECTION FEEDBACK:\n{revision_feedback}"
        ),
        expected_output=(
            "A DraftPlan containing courses with code and reason, "
            "plus assumptions and unresolved_questions."
        ),
        output_pydantic=DraftPlan,
        agent=planning_agent,
        tools=[],
    )

    return Crew(
        agents=[planning_agent],
        tasks=[task],
        process=Process.sequential,
        verbose=True,
    )