@echo off
echo =================================================================
echo  HCLTech Hackathon: Customer Loyalty and Engagement Assistant
echo =================================================================
echo Activating virtual environment and starting server...
call "%~dp0.venv\Scripts\activate.bat"
python "%~dp0run_server.py"
pause
