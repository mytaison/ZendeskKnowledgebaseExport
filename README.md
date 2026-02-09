## Install Python ( In Win 11)
Open Powershell and type python and press enter, it will open MS Store and install Python 3.x 
## Enable Virual Environment
python -m venv .venv
## Install Requests and Python-dotenv modules
pip install requests python-dotenv
## Set Script Execusion Policy
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process
## Activate Virtual env 
.\.venv\Scripts\Activate.ps1
## Run the script
python script.py




