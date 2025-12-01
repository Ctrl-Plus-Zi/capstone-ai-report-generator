# LLM 기반 AI 융합 분석 보고서 자동 생성 플랫폼

문화시설(공연장, 미술관, 관광지 등)에 대한 다차원 데이터를 수집·분석하여 Server-Driven UI 기반의 인터랙티브 보고서를 자동 생성하는 플랫폼입니다.

## 데모

### 사용 영상

https://github.com/Ctrl-Plus-Zi/capstone-ai-report-generator/raw/main/docs/video/video1.mp4

https://github.com/Ctrl-Plus-Zi/capstone-ai-report-generator/raw/main/docs/video/video2.mp4

### 스크린샷

<p align="center">
  <img src="docs/image/image1.png" width="80%" alt="스크린샷 1">
</p>

<p align="center">
  <img src="docs/image/image2.png" width="80%" alt="스크린샷 2">
</p>

## 프로젝트 개요

본 플랫폼은 LangGraph 기반의 멀티 에이전트 시스템을 활용하여 데이터 수집부터 보고서 레이아웃 구성까지 전 과정을 자동화합니다.

### 주요 기능

- **다중 데이터 소스 통합**: DB 쿼리, 공공 API(KCISA), Google Maps Platform API를 통한 종합적 데이터 수집
- **자동 블록 생성**: 차트, 테이블, 지도, 대기질 정보 등 다양한 시각화 블록 자동 생성
- **지능형 레이아웃**: LLM 기반 레이아웃 최적화로 가독성 높은 보고서 구성
- **Server-Driven UI**: 백엔드에서 정의된 블록 구조를 프론트엔드가 동적으로 렌더링

### 시스템 아키텍처

#### 데이터 흐름 요약

```mermaid
flowchart LR
    subgraph INPUT
        U[사용자 요청<br/>기관명 + 주제]
    end
    
    subgraph PROCESS
        S[Search<br/>20+ 데이터]
        A[Analyse<br/>30+ 블록]
        C[Compose<br/>18+ 블록]
    end
    
    subgraph OUTPUT
        F[Frontend<br/>보고서 렌더링]
    end
    
    U --> S --> A --> C --> F
    
    style INPUT fill:#e3f2fd
    style PROCESS fill:#fff9c4
    style OUTPUT fill:#ffccbc
```

#### 전체 워크플로우

```mermaid
flowchart LR
    A[사용자 요청] --> B[Search Agent]
    B --> C[Analyse Agent]
    C --> D[Compose Agent]
    D --> E[Frontend]
    
    B --> |research_payload| C
    C --> |block_drafts| D
    D --> |blocks| E
    
    style A fill:#e3f2fd
    style B fill:#fff8e1
    style C fill:#f3e5f5
    style D fill:#e8f5e9
    style E fill:#fce4ec
```

| 에이전트 | 역할 |
|---------|------|
| Search Agent | DB 쿼리 실행, KCISA API 호출, Google API 번들 실행 |
| Analyse Agent | 데이터 분석, 차트/테이블/마크다운 블록 생성 |
| Compose Agent | 블록 레이아웃 배치, 최종 보고서 구조 확정 |

#### Search Agent 상세

```mermaid
flowchart TD
    subgraph SEARCH["Search Agent"]
        S1[단계 1: DB 쿼리 계획<br/>LLM + query_bundles.json]
        S2[단계 2: API 선택<br/>KCISA API 결정]
        S3[단계 3: DB 쿼리 실행<br/>Query Executor]
        S4[단계 4: KCISA API 실행<br/>전시/공연 정보]
        S5[단계 5: Google API 실행<br/>api_bundles.json]
        
        S1 --> S2 --> S3 --> S4 --> S5
    end
    
    DB[(PostgreSQL)] -.-> S3
    KCISA[/KCISA API/] -.-> S4
    GOOGLE[/Google API/] -.-> S5
    
    S5 --> OUT[research_payload 출력]
    
    style SEARCH fill:#fff8e1
```

#### Analyse Agent 상세

```mermaid
flowchart TD
    subgraph ANALYSE["Analyse Agent"]
        A1[단계 1: 사전계산 통계<br/>→ 차트 블록 직접 생성]
        A2[단계 1.5: Google API<br/>→ map/air_quality 블록]
        A3[단계 1.6: KCISA API<br/>→ 테이블/이미지 블록]
        A4[단계 2-6: LLM 도구 호출<br/>추가 블록 생성]
        A5[단계 7: 블록 ID 부여]
        A6[단계 8: 짝 마크다운 생성]
        A7[단계 9: 총체적 분석 생성]
        
        A1 --> A2 --> A3 --> A4 --> A5 --> A6 --> A7
    end
    
    IN[research_payload 입력] --> A1
    A7 --> OUT[block_drafts 출력]
    
    style ANALYSE fill:#f3e5f5
```

#### 블록 생성 도구

```mermaid
flowchart LR
    subgraph TOOLS["LLM 블록 생성 도구"]
        T1[create_chart_block<br/>doughnut/bar/pie<br/>line/radar/polarArea]
        T2[create_table_block]
        T3[create_markdown_block]
        T4[create_image_block]
        T5[create_map_block]
        T6[create_air_quality_block]
    end
    
    LLM[LLM 도구 호출] --> TOOLS
    TOOLS --> BLOCKS[블록 배열]
    
    style TOOLS fill:#e1bee7
```

#### Compose Agent 상세

```mermaid
flowchart TD
    subgraph COMPOSE["Compose Agent"]
        C1[블록 목록 수신<br/>30개+]
        C2[LLM 레이아웃 결정]
        C3[create_row_layout<br/>여러 번 호출]
        C4[finalize_report_layout<br/>최종 확정]
        C5[누락 블록 자동 추가]
        C6[최종 blocks 생성<br/>18개+]
        
        C1 --> C2 --> C3 --> C4 --> C5 --> C6
    end
    
    IN[block_drafts 입력] --> C1
    C6 --> OUT[blocks 출력]
    
    style COMPOSE fill:#e8f5e9
```

## 기술 스택

### Backend
- **Framework**: FastAPI
- **AI/LLM**: LangChain, LangGraph, OpenAI GPT-4
- **Database**: PostgreSQL (Supabase)
- **External APIs**: KCISA 공공 API, Google Maps Platform

### Frontend
- **Framework**: React 18 + TypeScript
- **Build Tool**: Vite
- **Charting**: Chart.js, react-chartjs-2
- **Styling**: CSS Modules

## 설치 및 실행

### 사전 요구사항

- Python 3.10+
- Node.js 18+
- PostgreSQL 데이터베이스 접속 정보
- OpenAI API Key
- Google Maps Platform API Key (선택)

### 환경 변수 설정

```bash
cd backend
cp .env.example .env
```

`.env` 파일 설정:
```
# 필수
OPENAI_API_KEY=your_openai_api_key
DATABASE_URL=postgresql://user:password@host:port/database

# 선택 (Google API 사용 시)
GOOGLE_MAPS_API_KEY=your_google_maps_api_key
```

### Backend 실행

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend 실행

```bash
cd frontend
npm install
npm run dev
```

### 접속

브라우저에서 `http://localhost:5173` 접속

## 프로젝트 구조

```
├── backend/
│   ├── app/
│   │   ├── agents/           # LangGraph 에이전트 모듈
│   │   │   ├── search_agent.py
│   │   │   ├── analyse_agent.py
│   │   │   ├── compose_agent.py
│   │   │   ├── block_tools.py
│   │   │   ├── query_bundles.json
│   │   │   ├── api_bundles.json
│   │   │   └── ...
│   │   ├── api/              # FastAPI 라우터
│   │   ├── models/           # SQLAlchemy 모델
│   │   ├── schemas/          # Pydantic 스키마
│   │   └── services/         # 비즈니스 로직
│   └── requirements.txt
│
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   └── report/       # 블록 렌더링 컴포넌트
│   │   │       ├── Block.tsx
│   │   │       ├── ChartBlock.tsx
│   │   │       ├── TableBlock.tsx
│   │   │       ├── MapBlock.tsx
│   │   │       └── ...
│   │   └── types/            # TypeScript 타입 정의
│   └── package.json
│
└── README.md
```

## 지원 블록 타입

| 블록 타입 | 설명 |
|----------|------|
| `markdown` | 분석 텍스트, 요약, 인사이트 |
| `chart` | doughnut, bar, pie, line, radar, polarArea 차트 |
| `table` | 데이터 테이블 |
| `image` | 이미지 (전시 포스터, Street View 등) |
| `map` | Google Maps 기반 위치 지도 |
| `air_quality` | 대기질 정보 카드 |
| `row` | 블록 그룹 컨테이너 |

## API 엔드포인트

| Method | Endpoint | 설명 |
|--------|----------|------|
| POST | `/report/v2` | 새 보고서 생성 |
| GET | `/report/v2` | 보고서 목록 조회 |
| GET | `/report/{id}/children` | 보고서 블록 조회 |

## 라이선스

본 프로젝트는 한성대학교 기업연계 AI 캡스톤디자인 과목의 일환으로 개발되었습니다.
