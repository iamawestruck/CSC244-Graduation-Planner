from pydantic import BaseModel, Field


class PlannedCourse(BaseModel):
    code: str = Field(description="Course code, such as CS 201")
    name: str = Field(description="Course name verified in the catalog")
    credit_hours: int = Field(
        description="The number of credit hours selected for this plan"
    )
    reason: str = Field(description="Why this course is included in the plan")


class GraduationPlan(BaseModel):
    courses: list[PlannedCourse] = Field(
        description="Courses recommended for the plan"
    )
    assumptions: list[str] = Field(
        description="Assumptions made when building the plan"
    )
    unresolved_questions: list[str] = Field(
        description="Information that still needs confirmation"
    )