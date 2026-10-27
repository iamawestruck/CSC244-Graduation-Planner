from tools.course_tools import retrieve_courses

result = retrieve_courses.run(
    query="courses related to machine learning and artificial intelligence"
)

print(result)