$ErrorActionPreference = 'Stop'

$env:PYTHONPATH = 'D:\CodeProjects\knowledge-platform\.venv\Lib\site-packages;D:\CodeProjects\knowledge-platform\.venv\Lib\site-packages\win32;D:\CodeProjects\knowledge-platform\.venv\Lib\site-packages\win32\lib;D:\CodeProjects\knowledge-platform\.venv\Lib\site-packages\pywin32_system32;D:\CodeProjects\knowledge-platform'
$env:PATH = 'D:\CodeProjects\knowledge-platform\.venv\Lib\site-packages\pywin32_system32;' + $env:PATH

Set-Location 'D:\CodeProjects\knowledge-platform'

& 'C:\Users\tuongnm.TECHNICA\AppData\Local\Programs\Python\Python312\python.exe' -m uvicorn apps.api.server:app --host 127.0.0.1 --port 8000
