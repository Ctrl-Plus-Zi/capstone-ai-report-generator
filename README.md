# 데이터 수집, 정제, 최적화를 통한 LLM 기반 AI 융합 분석 보고서 생성 자동 플랫폼 개발

## 실행 방법

### 1. 백엔드 실행
```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 2. 프론트엔드 실행
```bash
cd frontend  
npm install
npm run dev
```

### 3. 웹사이트 접속
``` http://localhost:5173```

## 설정

### 환경변수 설정
```bash
cd backend
cp .env.example .env
```

`.env` 파일에 OpenAI API 키를 설정:
```
OPENAI_API_KEY=your_api_key_here
```

## 기술 스택

- **백엔드**: FastAPI + Python
- **프론트엔드**: React + TypeScript  
- **AI**: OpenAI GPT API
- **데이터베이스**: PostgreSQL

