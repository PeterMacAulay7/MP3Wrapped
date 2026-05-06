@echo off
setlocal enabledelayedexpansion

set ROOT=%~dp0
set SCRIPTS=%ROOT%scripts

python "%SCRIPTS%\music_script.py"
python "%SCRIPTS%\logupdate.py"
python "%SCRIPTS%\newWrapped.py"
python "%SCRIPTS%\export_monthly_albums.py"

:: Use Python to safely read wrapped_html from config.json (handles colons in paths)
for /f "delims=" %%a in ('python -c "import json; c=json.load(open(r'%ROOT%config.json')); print(c.get('wrapped_html', c['output_dir'] + '/wrapped.html'))"') do set WRAPPED=%%a

start "" "!WRAPPED!"
pause
