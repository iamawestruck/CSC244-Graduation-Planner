**Project Overview**
The goal for the project is to create a course plan for the students upcoming semester using the Python framework CrewAI and local Ollama model. Currently, the project uses two types of csv files: California state University's Computer Science course catalog and a mock student profile. Python supplies catalog details and checks the selection against supported pre-req conditions, completed courses and the requested unit range.

<img width="975" height="336" alt="image" src="https://github.com/user-attachments/assets/6c58f1f7-7568-4d56-8441-7e4cb3b81b57" />


**Current features**
1. Student Profile loading
2. Semester unit selection
3. AI-assisted recommendation
4. Catalog-backend course details
5. Eligibility and validation details
6. Automatic subset selection
7. Browser results
8. Course count tools (SQL)
   
**Workflow**
1. User enters student ID and optional range on the webpage
2. the server checks the submitted inputs and load the matching student profile
3. Python filters the course catalog and prepare the required course
4. PLANNING agent proposes course code and reason by using the students profile
5. Python supplies catalog names and credits, checks the proposal, and selects a valid subset when needed. It prioritizes unfinished required courses and uses the AI’s proposal order to break ties.
6. system allows one correction attempt if the result fails
7. the server returns the plan on the webpage
<img width="979" height="232" alt="image" src="https://github.com/user-attachments/assets/5512f134-3f0f-4135-b86c-07e4effca06f" />

**Demo Screenshot and Video**
<img width="1917" height="861" alt="image" src="https://github.com/user-attachments/assets/c1fd4379-c61a-41ac-9f9a-4f4c0d12e00d" />

<img width="1917" height="865" alt="image" src="https://github.com/user-attachments/assets/d1081d73-53ef-4600-893a-9130c51a3519" />

<img width="1892" height="863" alt="image" src="https://github.com/user-attachments/assets/4ca71d0d-b4e0-48d2-a205-0141198ac0cb" />

https://github.com/user-attachments/assets/82658560-a2aa-4694-8a59-c261c0ba2ff4





**Installation instruction**

Required software:
•	Python 3.11
•	Ollama
The current working demo is on Simran2.0(for now, not merged into main)

Option 1: DOWNLOADING USING THE TERMINAL
1.	Clone the working branch in the folder where you want to download the project
git clone https://github.com/iamawestruck/CSC244-Graduation-Planner.git
2.	Change the directory to CSC244-Graduation-Planner
cd CSC244-Graduation-Planner
3.	Continue with the environment setup given below.
Download the ZIP and extract it. Open a terminal in the extracted folder containing main.py and requirements.txt

Option 2: DOWNLOAD USING GitHub DESKTOP(main)
1.	Select File > Clone Repository > URL
2.	Enter the repo URL: https://github.com/iamawestruck/CSC244-Graduation-Planner/tree/main
3.	Choose local path and Clone
4.	Once the repository is saved locally, you can pull it to your device. Preferably through the “Open in Visual Studio Code”  

SET UP THE ENVIRONMENT
1.	Create a virtual environment
py -3.11 -m venv .venv
2.	Activate the virtual environment
.\.venv\Scripts\Activate.ps1
3.	Install the project packages
python -m pip install -r requirements.txt
4.	Download the planner’s AI model
5.	With Ollama running:
ollama pull llama3.2

RUN THE BROWSER VERSION
python frontend/server.py --port 8765
KEEP THE TERMINAL RUNNING AND CLICK THE HTTP LINK PROVIDED IN THE TERMINAL
TEST INPUT:
Student ID: SYNTHETIC_001
College: California State University, Sacramento
Minimum units:12
Maximum units: 18
Click Submit. Generating a plan may take several minutes. The webpage displays the recommended courses, total units, and validation report.
<img width="506" height="461" alt="image" src="https://github.com/user-attachments/assets/3b4167c5-e771-4394-a918-5d277ca931c8" />

To stop the server, press Ctrl + C in the terminal

RUN THE TERMINAL VERSION
1.	as an alternative to the webpage:
python main.py --student-id SYNTHETIC_001
2.	To additionally compare the final course count with a department target: 
python main.py --student-id SYNTHETIC_001 --dept-course-count 5


**Testing**
1. Expand testing with more student profiles and catalogs for other majors and campuses
   

**Limitatation**
1. Verify AI-generated reasons and assumptions against catalog data
2. Connect current course offering and integrate meeting time conflict checks.


**References**
OpenAI’s ChatGPT assisted with CSV dataset preparation, debugging, and images used in presentation.
