Installation Instructions:
Required software:
•	Python 3.11
•	Ollama
The current working demo is on Simran2.0(for now, not merged into main)

Option 1: DOWNLOADING USING THE TERMINAL
1.	Clone the working branch  in the folder where you want to download the project
git clone --branch simran2.0 https://github.com/iamawestruck/CSC244-Graduation-Planner.git
2.	Change the directory to CSC244-Graduation-Planner
cd CSC244-Graduation-Planner
3.	Continue with the environment setup given below.
Download the ZIP and extract it. Open a terminal in the extracted folder containing main.py and requirements.txt

Option 2: DOWNLOAD USING GitHub DESKTOP(main)
1.	Select File  Clone Repository  URL
2.	Enter the repo URL: https://github.com/iamawestruck/CSC244-Graduation-Planner/tree/simran2.0
3.	Once the repository is saved locally, you can pull it to your device. Preferably through the “Open in Visual Studio Code”  

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

