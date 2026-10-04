$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
if (-not (Test-Path -LiteralPath '.venv\Scripts\python.exe')) { throw 'Run the setup commands in README.md first.' }
& '.\.venv\Scripts\python.exe' -m uvicorn main:app --host 127.0.0.1 --port 8765
