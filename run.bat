@echo off
echo Starting TacitBridge-DXF Streamlit UI...
call .\venv\Scripts\activate.bat
streamlit run src/app.py
pause
