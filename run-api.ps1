# FastAPI 엔진 서버 실행 (터미널 1)
# 사용: 프로젝트 폴더에서  ./run-api.ps1
& "$PSScriptRoot\.venv\Scripts\python.exe" -m uvicorn api.server:app --port 8000 --reload
