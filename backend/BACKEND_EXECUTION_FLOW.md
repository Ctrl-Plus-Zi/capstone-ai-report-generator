# 백엔드 실행 흐름 문서

이 문서는 백엔드 코드의 실행 순서를 노드 단위로 설명합니다. 각 코드 블록이 어떤 입력을 받고, 어떤 작업을 수행하며, 어떤 출력을 생성하는지 순차적으로 기술합니다.

---

## 전체 실행 흐름 개요

```
HTTP 요청 → FastAPI 라우팅 → API 엔드포인트 → 서비스 레이어 → 그래프 실행 → 에이전트 노드들 → 데이터베이스 저장 → HTTP 응답
```

---

## 노드 1: FastAPI 애플리케이션 시작

**파일**: `backend/app/main.py`

**코드 블록**: `app = FastAPI(...)` 및 미들웨어 설정

**실제 코드**:
```19:33:backend/app/main.py
app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:4173"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(simple_report.router)
app.include_router(agent_report.router)
```

**입력**:
- 없음 (애플리케이션 시작 시점)

**작업**:
1. FastAPI 애플리케이션 인스턴스 생성
2. CORS 미들웨어 설정 (프론트엔드와의 통신 허용)
3. 라우터 등록 (`simple_report.router`, `agent_report.router`)
4. 하트비트 태스크 시작 (서버 상태 모니터링)

**출력**:
- `app` 객체: FastAPI 애플리케이션 인스턴스
- 서버가 HTTP 요청을 수신할 준비 완료 상태

**다음 노드**: HTTP 요청이 들어오면 라우터로 전달

---

## 노드 2: HTTP 요청 라우팅

**파일**: `backend/app/main.py` (라인 32-33)

**코드 블록**: `app.include_router(agent_report.router)`

**실제 코드**:
```32:33:backend/app/main.py
app.include_router(simple_report.router)
app.include_router(agent_report.router)
```

**입력**:
- HTTP POST 요청: `/report/advanced`
- 요청 본문 (JSON):
  ```json
  {
    "organization_name": "국립중앙박물관",
    "user_command": "2025년 1월 전시 현황 분석"
  }
  ```

**작업**:
- FastAPI가 요청 경로를 분석하여 `agent_report.router`로 라우팅
- 요청 본문을 Pydantic 스키마로 검증

**출력**:
- 검증된 요청 데이터가 `agent_report.py`의 엔드포인트 함수로 전달됨

**다음 노드**: `backend/app/api/agent_report.py`의 `generate_advanced_report` 함수

---

## 노드 3: API 엔드포인트 - 요청 수신 및 검증

**파일**: `backend/app/api/agent_report.py`

**코드 블록**: `generate_advanced_report` 함수 (라인 17-55)

**실제 코드**:
```17:55:backend/app/api/agent_report.py
@router.post("/advanced", response_model=AdvancedReportResponse)
async def generate_advanced_report(
    request: AdvancedReportRequest,
    db: Session = Depends(get_db)
):
    try:
        result = await agent_report_service.generate_report(
            organization_name=request.organization_name,
            user_command=request.user_command
        )
        
        advanced_report = AdvancedReport(
            organization_name=request.organization_name,
            user_command=request.user_command,
            report_topic=result["report_topic"],
            final_report=result["final_report"],
            research_sources_json=json.dumps(result["research_sources"], ensure_ascii=False),
            analysis_summary=result["analysis_summary"]
        )
        
        db.add(advanced_report)
        db.commit()
        db.refresh(advanced_report)
        
        return AdvancedReportResponse(
            id=advanced_report.id,
            organization_name=advanced_report.organization_name,
            report_topic=advanced_report.report_topic,
            final_report=advanced_report.final_report,
            research_sources=json.loads(advanced_report.research_sources_json) if advanced_report.research_sources_json else [],
            analysis_summary=advanced_report.analysis_summary or "",
            generated_at=advanced_report.created_at,
            generation_time_seconds=result.get("generation_time_seconds", 0.0)
        )
        
    except Exception as e:
        logger.error(f"Advanced report generation failed: {e}", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Report generation failed: {str(e)}")
```

**입력**:
- `request: AdvancedReportRequest` (Pydantic 모델)
  - `organization_name: str` (기관명)
  - `user_command: str` (사용자 요청 명령)
- `db: Session` (데이터베이스 세션, FastAPI 의존성 주입)

**작업**:
1. 요청 데이터를 Pydantic 스키마로 검증
2. 서비스 레이어 호출 준비

**출력**:
- 검증된 `organization_name`과 `user_command` 값
- 데이터베이스 세션 객체

**다음 노드**: `backend/app/services/agent_report_service.py`의 `generate_report` 메서드

---

## 노드 4: 서비스 레이어 - 초기 상태 생성

**파일**: `backend/app/services/agent_report_service.py`

**코드 블록**: `_build_initial_state` 메서드 (라인 24-58)

**실제 코드**:
```24:58:backend/app/services/agent_report_service.py
    def _build_initial_state(
        self, 
        organization_name: str, 
        user_command: str
    ) -> Dict:
        # 오늘 날짜 가져오기
        today = datetime.now()
        current_date = today.strftime("%Y-%m-%d")
        current_year = today.year
        current_month = today.month
        
        initial_message = f"""
{organization_name}에 대한 보고서를 작성해주세요.

사용자 요청:
{user_command}

오늘 날짜: {current_date}
현재 진행 중인 공연/전시만 포함해주세요.

위 요청을 바탕으로 필요한 데이터를 수집하고 분석하여 전문적인 보고서를 작성하세요.
""".strip()

        return {
            "request_context": {
                "organization_name": organization_name,
                "report_topic": user_command,
                "questions": [user_command],
                "current_date": current_date,  # 오늘 날짜 추가
                "current_year": current_year,
                "current_month": current_month,
                "filter_active_only": True,  # 현재 진행 중인 것만 필터링 플래그
            },
            "messages": [HumanMessage(content=initial_message)],
        }
```

**입력**:
- `organization_name: str` (예: "국립중앙박물관")
- `user_command: str` (예: "2025년 1월 전시 현황 분석")

**작업**:
1. 현재 날짜/시간 정보 추출 (`datetime.now()`)
2. 초기 메시지 생성 (사용자 요청을 포함한 프롬프트)
3. 요청 컨텍스트 딕셔너리 구성:
   - `organization_name`: 기관명
   - `report_topic`: 사용자 명령 (보고서 주제)
   - `questions`: 사용자 명령을 리스트로 변환
   - `current_date`: 오늘 날짜 (YYYY-MM-DD 형식)
   - `current_year`, `current_month`: 현재 연도/월
   - `filter_active_only`: True (현재 진행 중인 것만 필터링)

**출력**:
```python
{
    "request_context": {
        "organization_name": "국립중앙박물관",
        "report_topic": "2025년 1월 전시 현황 분석",
        "questions": ["2025년 1월 전시 현황 분석"],
        "current_date": "2025-01-15",
        "current_year": 2025,
        "current_month": 1,
        "filter_active_only": True
    },
    "messages": [HumanMessage(content="...")]
}
```

**다음 노드**: `generate_report` 메서드의 그래프 실행 부분

---

## 노드 5: 그래프 초기화

**파일**: `backend/app/services/agent_report_service.py`

**코드 블록**: `_get_graph` 메서드 및 `ReportingGraph` 초기화 (라인 19-22, 70)

**실제 코드**:
```19:22:backend/app/services/agent_report_service.py
    def _get_graph(self) -> ReportingGraph:
        if self.reporting_graph is None:
            self.reporting_graph = ReportingGraph()
        return self.reporting_graph
```

그래프 실행 부분:
```70:73:backend/app/services/agent_report_service.py
            graph = self._get_graph()
            initial_state = self._build_initial_state(organization_name, user_command)
            
            result = graph.graph.invoke(initial_state)
```

**입력**:
- 없음 (서비스 인스턴스 생성 시 또는 첫 호출 시)

**작업**:
1. `ReportingGraph` 인스턴스 생성 (없는 경우)
2. LangGraph 그래프 컴파일

**출력**:
- `graph` 객체: 컴파일된 LangGraph 인스턴스

**다음 노드**: `backend/app/agents/reporting_graph.py`의 `ReportingGraph.__init__`

---

## 노드 6: ReportingGraph 초기화

**파일**: `backend/app/agents/reporting_graph.py`

**코드 블록**: `ReportingGraph.__init__` (라인 12-31)

**실제 코드**:
```12:31:backend/app/agents/reporting_graph.py
    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}

        self.research_llm = ChatOpenAI(
            model=self.config.get("research_llm_model", "gpt-5-nano"),
            temperature=self.config.get("research_llm_temperature", 0.2),
        )
        self.analysis_llm = ChatOpenAI(
            model=self.config.get("analysis_llm_model", "gpt-4o"),
            temperature=self.config.get("analysis_llm_temperature", 0.2),
        )

        self.toolkit = ReportingTools()

        self.graph_setup = SetGraph(
            self.research_llm,
            self.analysis_llm,
            self.toolkit,
        )
        self.graph = self.graph_setup.set_graph()
```

**입력**:
- `config: Optional[Dict]` (선택적 설정 딕셔너리)

**작업**:
1. LLM 인스턴스 생성:
   - `research_llm`: 조사용 LLM (기본값: "gpt-5-nano", temperature: 0.2)
   - `analysis_llm`: 분석용 LLM (기본값: "gpt-4o", temperature: 0.2)
2. `ReportingTools` 툴킷 인스턴스 생성
3. `SetGraph` 인스턴스 생성 및 그래프 설정

**출력**:
- `self.graph`: 컴파일된 LangGraph 그래프 객체

**다음 노드**: `backend/app/agents/graph_setup.py`의 `SetGraph.set_graph`

---

## 노드 7: 그래프 구조 설정

**파일**: `backend/app/agents/graph_setup.py`

**코드 블록**: `set_graph` 메서드 (라인 16-31)

**실제 코드**:
```16:31:backend/app/agents/graph_setup.py
    def set_graph(self):
        graph = StateGraph(ReportingAgentState)

        graph.add_node("Research Agent", create_search_agent(self.research_llm, self.toolkit))
        graph.add_node(
            "Analysis Agent",
            create_analyse_agent(self.analysis_llm, self.analysis_llm, self.toolkit),
        )
        graph.add_node("Compose Agent", create_final_report_compose_agent(self.analysis_llm))

        graph.add_edge(START, "Research Agent")
        graph.add_edge("Research Agent", "Analysis Agent")
        graph.add_edge("Analysis Agent", "Compose Agent")
        graph.add_edge("Compose Agent", END)

        return graph.compile()
```

**입력**:
- `self.research_llm`: 조사용 LLM
- `self.analysis_llm`: 분석용 LLM
- `self.toolkit`: ReportingTools 인스턴스

**작업**:
1. `StateGraph` 생성 (상태 타입: `ReportingAgentState`)
2. 노드 추가:
   - "Research Agent": 조사 에이전트 노드
   - "Analysis Agent": 분석 에이전트 노드
   - "Compose Agent": 보고서 작성 에이전트 노드
3. 엣지 추가 (실행 순서 정의):
   - START → Research Agent
   - Research Agent → Analysis Agent
   - Analysis Agent → Compose Agent
   - Compose Agent → END

**출력**:
- 컴파일된 그래프 객체 (`graph.compile()`)

**다음 노드**: 그래프 실행 시 첫 번째 노드인 "Research Agent"로 이동

---

## 노드 8: Research Agent 노드 - 데이터 수집

**파일**: `backend/app/agents/search_agent.py`

**코드 블록**: `search_agent_node` 함수 (라인 74-364)

**실제 코드** (주요 부분):

도구 필터링:
```94:118:backend/app/agents/search_agent.py
        # 기관별 사용 가능한 도구 필터링
        org = (request_context.get("organization_name") or "").strip().lower()
        
        # 기관별 API 매핑
        org_api_mapping = {
            "국립중앙박물관": [toolkit.search_museum_collection_api],
            "국립현대미술관": [toolkit.search_exhibition_info_api],
            "예술의전당": [toolkit.search_performance_info_api],
            "예술의 전당": [toolkit.search_performance_info_api],
        }
        
        # 기관명 매칭 (부분 일치 포함)
        tools = []
        for org_key, allowed_tools in org_api_mapping.items():
            if org_key.lower() in org or org in org_key.lower():
                tools = allowed_tools.copy()
                break
        
        # 매칭되지 않으면 모든 도구 사용 (기존 동작 유지)
        if not tools:
            tools = all_tools.copy()
        
        # 날씨 API는 항상 사용 가능 (요청이 있을 때만 사용)
        if toolkit.search_weather_daily_api not in tools:
            tools.append(toolkit.search_weather_daily_api)
```

LLM 호출 및 도구 실행:
```221:280:backend/app/agents/search_agent.py
        chain = prompt | llm.bind_tools(tools)
        ai_response = chain.invoke({"messages": messages})
        messages.append(ai_response)

        research_notes = state.get("research_notes")
        research_sources = list(state.get("research_sources", []))
        research_payload = list(state.get("research_payload", []))

        org = (request_context.get("organization_name") or "").strip()
        weather_params = request_context.get("weather_params") or state.get("weather_params") or {}

        called_tools: List[str] = []

        if hasattr(ai_response, "tool_calls"):
            for call in ai_response.tool_calls:
                tool_name = call.get("name")
                tool_args = dict(call.get("args", {}) or {})
                tool_fn = next((t for t in tools if t.name == tool_name), None)
                if tool_fn is None:
                    continue

                
                if tool_name == getattr(toolkit.search_weather_daily_api, "name", "search_weather_daily_api"):
                    merged = {**weather_params, **tool_args}

                elif tool_name in {
                    getattr(toolkit.search_performance_info_api, "name", "search_performance_info_api"),
                    getattr(toolkit.search_exhibition_info_api, "name", "search_exhibition_info_api"),
                }:
                    if not tool_args.get("keyword") and org:
                        tool_args["keyword"] = org

                tool_result = tool_fn.invoke(tool_args)
                called_tools.append(tool_name)
                
                # 날짜 필터링 적용 (공연/전시 정보인 경우)
                if isinstance(tool_result, dict):
                    current_date = request_context.get("current_date")
                    filter_active = request_context.get("filter_active_only", False)
                    
                    if filter_active and current_date and tool_name in {
                        getattr(toolkit.search_performance_info_api, "name", "search_performance_info_api"),
                        getattr(toolkit.search_exhibition_info_api, "name", "search_exhibition_info_api"),
                    }:
                        original_data = tool_result.get("data", [])
                        if original_data:
                            filtered_data = _filter_by_current_date(original_data, current_date)
                            if len(filtered_data) < len(original_data):
                                tool_result["data"] = filtered_data
                                tool_result["count"] = len(filtered_data)
                                # notes 업데이트
                                original_notes = tool_result.get("notes", "")
                                tool_result["notes"] = f"{original_notes} (날짜 필터링: {len(original_data)}개 → {len(filtered_data)}개)"

                messages.append(
                    ToolMessage(
                        tool_call_id=call.get("id"),
                        content=json.dumps(tool_result) if tool_result is not None else "{}",
                    )
                )
```

결과 수집:
```281:297:backend/app/agents/search_agent.py
                if isinstance(tool_result, dict):
                    notes = tool_result.get("notes")
                    if notes:
                        note_entry = f"- {notes}"
                        research_notes = (
                            f"{research_notes}\n{note_entry}".strip() if research_notes else note_entry
                        )
                    sources = tool_result.get("sources")
                    research_sources.extend(sources)
                    data = tool_result.get("data") or []
                    if data:
                        research_payload.append({
                            "tool": tool_name,
                            "args": tool_args,
                            "count": len(data),
                            "sample": data[:5],  # 과하지 않게 일부만
                        })
```

반환:
```359:364:backend/app/agents/search_agent.py
        return {
            "messages": messages,
            "research_notes": research_notes,
            "research_sources": research_sources,
            "research_payload": research_payload,
        }
```

**입력**:
- `state: ReportingAgentState` 딕셔너리:
  - `request_context`: 요청 컨텍스트 (기관명, 주제, 날짜 등)
  - `messages`: 대화 메시지 리스트 (초기 사용자 메시지 포함)

**작업**:
1. **도구 필터링** (라인 94-118):
   - 기관명에 따라 사용 가능한 API 도구 필터링
   - 국립중앙박물관 → `search_museum_collection_api`만
   - 국립현대미술관 → `search_exhibition_info_api`만
   - 예술의전당 → `search_performance_info_api`만
   - 날씨 API는 모든 기관에서 사용 가능

2. **프롬프트 생성** (라인 131-219):
   - 시스템 프롬프트 생성 (조사 에이전트 역할 정의)
   - 사용 가능한 도구 설명 포함
   - 요청 컨텍스트 정보 포함

3. **LLM 호출** (라인 221-223):
   - LLM이 도구를 선택하고 호출할 인자 생성

4. **도구 실행** (라인 234-280):
   - LLM이 선택한 도구들을 순차적으로 실행
   - 각 도구 결과를 `ToolMessage`로 변환하여 메시지에 추가
   - 날짜 필터링 적용 (현재 진행 중인 공연/전시만)

5. **결과 수집** (라인 225-297):
   - `research_notes`: 조사 메모 문자열
   - `research_sources`: 참고 출처 리스트
   - `research_payload`: 수집된 데이터 샘플

**출력**:
```python
{
    "messages": [...],  # 기존 메시지 + LLM 응답 + 도구 결과 메시지들
    "research_notes": "전시 정보 검색 완료: 총 15개의 전시 정보를 찾았습니다...",
    "research_sources": ["http://...", "http://..."],
    "research_payload": [
        {
            "tool": "search_exhibition_info_api",
            "args": {"keyword": "국립현대미술관", "num_of_rows": 50},
            "count": 15,
            "sample": [...]  # 데이터 샘플 5개
        }
    ]
}
```

**다음 노드**: "Analysis Agent" 노드로 상태 전달

---

## 노드 9: 도구 실행 - API 호출 (Research Agent 내부)

**파일**: `backend/app/agents/graph_util.py`

**코드 블록**: `ReportingTools` 클래스의 각 도구 메서드들

### 9-1. search_exhibition_info_api

**실제 코드**:
```11:35:backend/app/agents/graph_util.py
    @staticmethod
    @tool
    def search_exhibition_info_api(
        keyword: Annotated[str, "전시 정보를 검색할 키워드 (예: www.museum.go.kr)"] = "www.museum.go.kr",
        num_of_rows: Annotated[int, "조회할 데이터 행 수"] = 50
    ):
        """한국문화정보원 전시정보 통합 API (KCISA_CCA_145)를 검색합니다. 문화시설의 전시 정보, 이벤트, 프로그램 등을 조회합니다."""
        result = call_kcisa_api(
            api_name="KCISA_CCA_145",
            filter_value=keyword,
            num_of_rows=num_of_rows,
            filter_remove_fields=False  # DESCRIPTION 포함
        )
        
        if result["success"]:
            return {
                "notes": f"{result['api_description']} 검색 완료: 총 {result['count']}개의 전시 정보를 찾았습니다.",
                "sources": [item.get("URL") for item in result["data"] if item.get("URL")],
                "data": result["data"]
            }
        else:
            return {
                "notes": f"전시 정보 검색 실패: {result.get('error', '알 수 없는 오류')}",
                "sources": [],
                "data": []
            }
```

**입력**:
- `keyword: str` (예: "www.museum.go.kr")
- `num_of_rows: int` (기본값: 50)

**작업**:
- `call_kcisa_api` 호출 (API 이름: "KCISA_CCA_145")
- 전시 정보 검색

**출력**:
```python
{
    "notes": "전시정보 통합 API 검색 완료: 총 15개의 전시 정보를 찾았습니다.",
    "sources": ["http://...", ...],
    "data": [
        {
            "TITLE": "전시 제목",
            "PERIOD": "2025-01-01~2025-01-31",
            "DESCRIPTION": "...",
            "URL": "http://...",
            "CHARGE": "무료"
        },
        ...
    ]
}
```

### 9-2. search_museum_collection_api

**실제 코드**:
```37:63:backend/app/agents/graph_util.py
    @staticmethod
    @tool
    def search_museum_collection_api(
        keyword: Annotated[str, "소장품을 검색할 키워드 (예: 청자, 호랑이, 불상 등)"] = "청자",
        num_of_rows: Annotated[int, "조회할 데이터 행 수"] = 50
    ):
        """국립중앙박물관 소장품 검색 API (KCISA_CPM_003)를 검색합니다. 박물관 소장품의 상세 정보를 조회합니다."""
        result = call_kcisa_api(
            api_name="KCISA_CPM_003",
            filter_value=keyword,
            num_of_rows=num_of_rows,
            filter_remove_fields=False  # DESCRIPTION 포함
        )
        
        # 성공/실패 여부와 함께 API 결과를 그대로 반환
        if result["success"]:
            return {
                "notes": f"{result['api_description']} 검색 완료: 총 {result['count']}개의 소장품 정보를 찾았습니다.",
                "sources": [item.get("url") for item in result["data"] if item.get("url")],
                "data": result["data"]
            }
        else:
            return {
                "notes": f"소장품 검색 실패: {result.get('error', '알 수 없는 오류')}",
                "sources": [],
                "data": []
            }
```

**입력**:
- `keyword: str` (예: "청자")
- `num_of_rows: int` (기본값: 50)

**작업**:
- `call_kcisa_api` 호출 (API 이름: "KCISA_CPM_003")
- 박물관 소장품 정보 검색

**출력**:
```python
{
    "notes": "소장품 검색 API 검색 완료: 총 20개의 소장품 정보를 찾았습니다.",
    "sources": ["http://...", ...],
    "data": [
        {
            "title": "청자 항아리",
            "description": "...",
            "artist": "...",
            "issuedDate": "조선시대"
        },
        ...
    ]
}
```

### 9-3. search_performance_info_api

**실제 코드**:
```109:146:backend/app/agents/graph_util.py
    @staticmethod
    @tool
    def search_performance_info_api(
        keyword: Annotated[str, "공연 정보를 검색할 키워드 (예: 예술의전당, 연극, 콘서트 등)"] = "예술의전당",
        num_of_rows: Annotated[int, "조회할 데이터 행 수"] = 50
    ):
        """
        한국문화정보원 공연정보 통합 API(KCISA_CCA_144)를 조회합니다.
        fields 예: TITLE, DESCRIPTION, IMAGE_OBJECT, LOCAL_ID, EVENT_SITE, GENRE, DURATION,
                  AUTHOR, ACTOR, CONTRIBUTOR, AUDIENCE, CHARGE, PERIOD, EVENT_PERIOD
        """
        result = call_kcisa_api(
            api_name="KCISA_CCA_144",
            keyword=keyword,     # filter_rules[0].value(CNTC_INSTT_NM)로도 필터링 됨
            num_of_rows=num_of_rows,
            filter_remove_fields=False  # DESCRIPTION 포함
        )

        if result.get("success"):
            data = result.get("data", [])

            # URL이 응답에 없을 수도 있으므로(확실하지 않음) 대체 가능 키로 소스 구성
            def pick_source(it: dict):
                return it.get("URL") or it.get("IMAGE_OBJECT") or it.get("LOCAL_ID")

            sources = [pick_source(it) for it in data if pick_source(it)]

            return {
                "notes": f"{result.get('api_description','공연정보')} 검색 완료: 총 {result.get('count', 0)}개의 공연 정보를 찾았습니다.",
                "sources": sources,
                "data": data
            }
        else:
            return {
                "notes": f"공연 정보 검색 실패: {result.get('error', '알 수 없는 오류')}",
                "sources": [],
                "data": []
            }
```

**입력**:
- `keyword: str` (예: "예술의전당")
- `num_of_rows: int` (기본값: 50)

**작업**:
- `call_kcisa_api` 호출 (API 이름: "KCISA_CCA_144")
- 공연 정보 검색

**출력**:
```python
{
    "notes": "공연정보 통합 API 검색 완료: 총 10개의 공연 정보를 찾았습니다.",
    "sources": ["http://...", ...],
    "data": [
        {
            "TITLE": "공연 제목",
            "PERIOD": "2025-01-15~2025-01-20",
            "GENRE": "연극",
            "CHARGE": "30000원"
        },
        ...
    ]
}
```

### 9-4. search_weather_daily_api

**실제 코드**:
```148:166:backend/app/agents/graph_util.py
    @staticmethod
    @tool
    def search_weather_daily_api(
        year: Annotated[int, "연도"] = 2025,
        month: Annotated[int, "월(1~12)"] = 1,
        stn_ids: Annotated[str, "지점코드(예: 108=서울)"] = "108",
        num_of_rows: Annotated[int, "행 수"] = 999,
    ):
        """KMA ASOS 일자료(일별)를 월 단위로 조회하는 툴. tm/sumRn/maxTa/minTa 필드를 반환합니다."""
        try:
            start_dt, end_dt = month_range(year, month)  # ← 네 함수명과 일치
        except ValueError as e:
            return {"notes": f"입력 오류: {e}", "sources": [], "data": []}

        result = call_kma_asos_daily_api(start_dt, end_dt, stn_ids, num_of_rows)
        if result["success"]:
            return {"notes": f"{result['api_description']} {year}년 {month}월 조회 완료: 총 {result['count']}개의 일자료.", "sources": [], "data": result["data"]}
        else:
            return {"notes": f"날씨 데이터 조회 실패: {result.get('error', '알 수 없는 오류')}", "sources": [], "data": []}
```

**입력**:
- `year: int` (예: 2025)
- `month: int` (예: 1)
- `stn_ids: str` (예: "108" - 서울)
- `num_of_rows: int` (기본값: 999)

**작업**:
- `call_kma_asos_daily_api` 호출
- 기상청 ASOS 일자료 조회

**출력**:
```python
{
    "notes": "기상청 ASOS 일자료 2025년 1월 조회 완료: 총 31개의 일자료.",
    "sources": [],
    "data": [
        {
            "tm": "20250101",
            "sumRn": "0.0",
            "maxTa": "5.2",
            "minTa": "-2.1"
        },
        ...
    ]
}
```

**다음 노드**: 도구 실행 결과가 Research Agent 노드로 반환되어 상태에 추가됨

---

## 노드 10: API 유틸리티 - 외부 API 호출

**파일**: `backend/app/agents/api_utils.py`

### 10-1. call_kcisa_api (KCISA API 호출)

**코드 블록**: `call_kcisa_api` 함수 (라인 76-220)

**실제 코드** (주요 부분):
```76:125:backend/app/agents/api_utils.py
def call_kcisa_api(
    api_name: str,
    keyword: str | None = None,
    filter_value: Optional[str] = None,
    page_no: int = 1,
    num_of_rows: int = 50,
    filter_remove_fields: bool = True,
) -> dict:
    """
    KCISA XML API 공통 호출.
    - 서버 파라미터(keyword 등)만 사용하여 조회
    - 클라이언트 필터(filter_rules)는 있으면 '선택 적용' (없으면 건너뜀)
    - XML -> dict 리스트 표준화
    """
    try:
        registry = load_api_registry()
        if api_name not in registry:
            return {
                "success": False,
                "api_name": api_name,
                "error": f"API '{api_name}'를 찾을 수 없습니다.",
                "data": [],
                "count": 0,
                "url": None,
            }

        cfg = registry[api_name]
        base_url = cfg["base_url"]
        params = dict(cfg.get("default_params", {}))
        params["pageNo"] = str(page_no)
        params["numOfRows"] = str(num_of_rows)

        # 서버 검색 파라미터만 사용 (클라이언트 필터에 값 '주입' 금지)
        if keyword:
            params["keyword"] = keyword

        # 요청 (타임아웃 증가: connect 10s, read 30s)
        resp = requests.get(base_url, params=params, timeout=(10, 30))
        resp.raise_for_status()

        # XML 파싱
        root = ET.fromstring(resp.text)
        items = root.findall(".//item")

        fields = cfg.get("fields", [])
        rows = []
        for it in items:
            row = {f: (it.findtext(f".//{f}") or None) for f in fields}
            rows.append(row)
```

필터링 및 결과 반환:
```148:193:backend/app/agents/api_utils.py
        if filter_rules:
            def _passes(r: Dict[str, Any]) -> bool:
                for rule in filter_rules:
                    field = rule.get("field")
                    op = (rule.get("op") or rule.get("operator") or "contains").lower()
                    val = (rule.get("value") or "").strip()
                    if not field or not op or not val:
                        # 불완전 규칙은 통과
                        continue
                    target = str(r.get(field) or "")
                    if op == "contains" or op == "substring":
                        if val not in target:
                            return False
                    elif op == "icontains":
                        if val.lower() not in target.lower():
                            return False
                    elif op == "eq":
                        if target != val:
                            return False
                    else:
                        # 모르는 op는 무시
                        continue
                return True

            rows = [r for r in rows if _passes(r)]
        # --- /필터 적용 ---
        
        # 토큰 수 절감: 긴 텍스트 필드 제거 또는 요약
        # 운영자용 보고서이므로 DESCRIPTION 같은 상세 설명은 불필요
        # 단, filter_remove_fields가 False이면 필드 제거하지 않음 (디버깅용)
        if filter_remove_fields:
            fields_to_remove = ["DESCRIPTION", "description", "SUB_DESCRIPTION", "subDescription", 
                               "TABLE_OF_CONTENTS", "NUMBER_PAGES"]
            for row in rows:
                for field in fields_to_remove:
                    if field in row:
                        del row[field]

        return {
            "success": True,
            "api_name": api_name,
            "api_description": cfg.get("api_name", ""),
            "data": rows,
            "count": len(rows),
            "url": resp.url,  # 디버깅용
        }
```

### 10-2. call_kma_asos_daily_api (기상청 API 호출)

**코드 블록**: `call_kma_asos_daily_api` 함수 (라인 224-329)

**실제 코드**:
```224:304:backend/app/agents/api_utils.py
def call_kma_asos_daily_api(
    start_dt: str,
    end_dt: str,
    stn_ids: str = "108",
    num_of_rows: int = 999
) -> Dict:
    """
    기상청 ASOS 일자료(일별) 호출.
    api_configs.json[KMA_ASOS_DAILY]의 fields (예: ["tm","sumRn","maxTa","minTa"])에 맞춰 정규화.
    """
    try:
        api_registry = load_api_registry()
        api_name = "KMA_ASOS_DAILY"

        if api_name not in api_registry:
            return {
                "success": False,
                "api_name": api_name,
                "error": f"API '{api_name}'를 찾을 수 없습니다.",
                "data": [],
                "count": 0
            }

        config = api_registry[api_name]
        base_url = config["base_url"]

        # 파라미터: 기본값 + 오버라이드
        params = config["default_params"].copy()
        params["startDt"] = start_dt
        params["endDt"]   = end_dt
        params["stnIds"]  = stn_ids
        params["numOfRows"] = str(num_of_rows)

        # 환경변수 키가 있다면 우선(확실하지 않음: 선택)
        # os.getenv("KMA_SERVICE_KEY")가 있으면 그걸로 대체
        if "serviceKey" in params:
            params["serviceKey"] = os.getenv("KMA_SERVICE_KEY", params["serviceKey"])

        # 호출
        retries = 3
        last_exc = None
        resp = None
        for attempt in range(retries):
            try:
                # connect 5s, read 25s
                resp = requests.get(base_url, params=params, timeout=(5, 25))
                resp.raise_for_status()
                break
            except requests.exceptions.RequestException as e:
                last_exc = e
                if attempt < retries - 1:
                    time.sleep(1.5 ** attempt)  # 1.0s → 1.5s → …
                    continue
        if last_exc:
            return {"success": False, "api_name": api_name, "error": f"API 호출 실패: {last_exc}", "data": [], "count": 0, "url": (resp.url if resp else f"{base_url}?<params>")}

        # JSON 파싱 (일반적으로 response.body.items.item)
        payload = resp.json()
        body = payload.get("response", {}).get("body", {})
        items = body.get("items", {}).get("item", [])
        if not isinstance(items, list):
            items = [items] if items else []

        # 필요한 필드만 추출
        fields = config.get("fields", [])
        data = [{k: it.get(k) for k in fields} for it in items]

        # resultCode / resultMsg (있을 때만)
        header = payload.get("response", {}).get("header", {})
        result_code = header.get("resultCode")
        result_msg  = header.get("resultMsg")

        return {
            "success": True,
            "api_name": api_name,
            "api_description": config.get("api_name", ""),
            "result_code": result_code,
            "result_msg": result_msg,
            "data": data,
            "count": len(data)
        }
```

**입력**:
- `api_name: str` (예: "KCISA_CCA_145")
- `keyword: str | None` (검색 키워드)
- `filter_value: Optional[str]` (필터 값)
- `page_no: int` (기본값: 1)
- `num_of_rows: int` (기본값: 50)

**작업**:
1. API 설정 파일 로드 (`api_configs.json`)
2. API 기본 URL 및 파라미터 구성
3. HTTP GET 요청 전송 (타임아웃: connect 10s, read 30s)
4. XML 응답 파싱
5. 필드 추출 및 필터링 적용
6. 긴 텍스트 필드 제거 (토큰 수 절감)

**출력**:
```python
{
    "success": True,
    "api_name": "KCISA_CCA_145",
    "api_description": "전시정보 통합 API",
    "data": [...],  # 딕셔너리 리스트
    "count": 15,
    "url": "http://..."
}
```

**다음 노드**: 도구 함수로 결과 반환

---

## 노드 11: 날짜 필터링 함수

**파일**: `backend/app/agents/search_agent.py`

**코드 블록**: `_filter_by_current_date` 함수 (라인 15-72)

**실제 코드**:
```15:72:backend/app/agents/search_agent.py
    def _filter_by_current_date(data: List[dict], current_date: str, date_fields: List[str] = None) -> List[dict]:
        """현재 날짜 기준으로 진행 중인 공연/전시만 필터링"""
        if not current_date or not data:
            return data
        
        if date_fields is None:
            date_fields = ["PERIOD", "EVENT_PERIOD", "period", "event_period"]
        
        try:
            today = datetime.strptime(current_date, "%Y-%m-%d")
        except:
            return data  # 날짜 파싱 실패 시 필터링 안 함
        
        filtered = []
        for item in data:
            is_active = False
            for field in date_fields:
                period_str = item.get(field)
                if not period_str:
                    continue
                
                # 날짜 범위 파싱 (예: "2024-01-01~2024-12-31" 또는 "2024.01.01 - 2024.12.31")
                period_str = period_str.strip()
                # 다양한 구분자 처리
                for sep in ["~", " - ", "-", "~"]:
                    if sep in period_str:
                        parts = period_str.split(sep, 1)
                        if len(parts) == 2:
                            try:
                                start_str = parts[0].strip().replace(".", "-").replace("/", "-")
                                end_str = parts[1].strip().replace(".", "-").replace("/", "-")
                                
                                # 날짜 형식 정규화 (YYYY-MM-DD 형식으로)
                                start_str = re.sub(r'(\d{4})[.\-/](\d{1,2})[.\-/](\d{1,2})', r'\1-\2-\3', start_str)
                                end_str = re.sub(r'(\d{4})[.\-/](\d{1,2})[.\-/](\d{1,2})', r'\1-\2-\3', end_str)
                                
                                # 월/일이 한 자리 수인 경우 0 패딩
                                start_parts = start_str.split("-")
                                if len(start_parts) == 3:
                                    start_str = f"{start_parts[0]}-{start_parts[1].zfill(2)}-{start_parts[2].zfill(2)}"
                                end_parts = end_str.split("-")
                                if len(end_parts) == 3:
                                    end_str = f"{end_parts[0]}-{end_parts[1].zfill(2)}-{end_parts[2].zfill(2)}"
                                
                                start_date = datetime.strptime(start_str, "%Y-%m-%d")
                                end_date = datetime.strptime(end_str, "%Y-%m-%d")
                                
                                if start_date <= today <= end_date:
                                    is_active = True
                                    break
                            except:
                                continue
                        break
            
            if is_active:
                filtered.append(item)
        
        return filtered if filtered else data  # 필터링 결과가 없으면 원본 반환 (최소한의 데이터라도 유지)
```

**입력**:
- `data: List[dict]` (필터링할 데이터 리스트)
- `current_date: str` (현재 날짜, "YYYY-MM-DD" 형식)
- `date_fields: List[str]` (날짜 필드명 리스트, 기본값: ["PERIOD", "EVENT_PERIOD", "period", "event_period"])

**작업**:
1. 현재 날짜를 `datetime` 객체로 변환
2. 각 데이터 항목의 날짜 필드 확인
3. 날짜 범위 파싱 (다양한 구분자 처리: "~", " - ", "-")
4. 현재 날짜가 범위 내에 있는지 확인
5. 진행 중인 항목만 필터링

**출력**:
- `List[dict]`: 현재 날짜 기준으로 진행 중인 항목만 포함된 리스트
- 필터링 결과가 없으면 원본 데이터 반환 (최소한의 데이터 유지)

**다음 노드**: 필터링된 데이터가 도구 결과에 반영됨

---

## 노드 12: Analysis Agent 노드 - 데이터 분석

**파일**: `backend/app/agents/analyse_agent.py`

**코드 블록**: `analyse_agent_node` 함수 (라인 14-144)

**실제 코드**:
```14:144:backend/app/agents/analyse_agent.py
    def analyse_agent_node(state):
        tools = [
            toolkit.analyse_quantitative_metrics,
            toolkit.analyse_qualitative_feedback,
        ]

        request_context = state.get("request_context", {})
        research_notes = state.get("research_notes", "")
        research_sources = state.get("research_sources", [])
        messages: List = list(state.get("messages", []))

        system_text = textwrap.dedent(
            """
            # 역할
            당신은 문화시설 데이터 분석 전문가입니다. 수집된 데이터를 심층 분석하여 의미 있는 인사이트를 도출합니다.
            
            # 목표
            조사 에이전트가 수집한 데이터를 분석하고, 보고서 작성에 필요한 핵심 발견사항을 정리하세요.
            
            # 입력 데이터
            요청 컨텍스트: {request_context}
            조사 메모: {research_notes}
            참고 출처: {research_sources}
            
            # 분석 프레임워크
            1. 데이터 검토
               - 수집된 데이터의 양과 품질 평가
               - 전시 정보, 소장품 정보 등 데이터 유형 파악
               - 데이터 간 연관성 분석
            
            2. 패턴 및 트렌드 파악
               - 전시 기간, 주제, 관람료 등의 패턴
               - 소장품의 시대별, 유형별 분포
               - 기관의 특성과 강점 파악
            
            3. 보고서 주제와의 연결
               - 수집된 데이터가 report_topic과 어떻게 관련되는지 분석
               - questions 리스트의 각 질문에 대한 답변 도출
               - 부족한 정보나 추가 필요한 분석 식별
            
            4. 핵심 인사이트 도출
               - 데이터에서 발견한 주요 사실
               - 의미 있는 통찰과 해석
               - 보고서 작성에 활용할 수 있는 결론
            
            # 분석 도구 (현재 구현 예정)
            - analyse_quantitative_metrics: 정량적 지표 분석
            - analyse_qualitative_feedback: 정성적 피드백 분석
            
            # 출력 요구사항
            다음 내용을 포함한 분석 결과를 작성하세요:
            1. 데이터 요약: 수집된 데이터의 주요 특징
            2. 발견사항: 데이터 분석을 통해 발견한 중요한 사실들
            3. 인사이트: 데이터가 보고서 주제에 주는 시사점
            4. 제언: 보고서 작성 시 강조할 포인트
            
            # 주의사항
            - 수집된 데이터가 부족하더라도 가능한 한 의미 있는 분석을 제공하세요
            - 추측이 아닌 데이터 기반의 분석을 수행하세요
            - 보고서 독자(의사결정자)에게 유용한 정보에 집중하세요
            """
        ).strip()

        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", system_text),
                MessagesPlaceholder(variable_name="messages"),
            ]
        ).partial(
            request_context=json.dumps(request_context, ensure_ascii=False, indent=2),
            research_notes=research_notes,
            research_sources=json.dumps(research_sources, ensure_ascii=False, indent=2),
        )

        chain = prompt | tool_llm.bind_tools(tools)
        ai_response = chain.invoke({"messages": messages})
        messages.append(ai_response)

        analysis_outline = getattr(ai_response, "content", "").strip()
        analysis_findings = state.get("analysis_findings")

        if hasattr(ai_response, "tool_calls"):
            for call in ai_response.tool_calls:
                tool_fn = next((t for t in tools if t.name == call.get("name")), None)
                if tool_fn is None:
                    continue
                tool_args = call.get("args", {})
                tool_result = tool_fn.invoke(tool_args)
                messages.append(
                    ToolMessage(
                        tool_call_id=call.get("id"),
                        content=json.dumps(tool_result) if tool_result is not None else "{}",
                    )
                )
                if isinstance(tool_result, dict):
                    notes = tool_result.get("analysis_notes")
                    if notes:
                        note_entry = f"- {notes}"
                        analysis_outline = (
                            f"{analysis_outline}\n{note_entry}".strip() if analysis_outline else note_entry
                        )

        summary_input = analysis_outline or research_notes
        summary_messages = [
            SystemMessage(content=textwrap.dedent("""
                수집된 데이터와 분석 내용을 바탕으로 핵심 발견사항을 요약하세요.
                
                요약 시 포함할 내용:
                1. 주요 데이터 포인트 (전시 개수, 소장품 특성 등)
                2. 발견한 패턴이나 트렌드
                3. 보고서 주제와의 연결점
                4. 핵심 인사이트와 시사점
                
                간결하고 명확하게 작성하되, 중요한 정보는 누락하지 마세요.
            """).strip()),
            HumanMessage(content=summary_input or "분석 입력이 제공되지 않았습니다."),
        ]
        summary_response = summary_llm.invoke(summary_messages)
        messages.append(summary_response)
        analysis_findings = summary_response.content.strip() if summary_response else (analysis_findings or "")

        if not analysis_outline:
            analysis_outline = "도구와 LLM 분석이 완료되면 이 부분을 채워 주세요."
        if not analysis_findings:
            analysis_findings = "도구 통합이 완료되면 분석 결과가 생성됩니다."

        return {
            "messages": messages,
            "analysis_outline": analysis_outline,
            "analysis_findings": analysis_findings,
        }
```

**입력**:
- `state: ReportingAgentState`:
  - `request_context`: 요청 컨텍스트
  - `research_notes`: 조사 메모
  - `research_sources`: 참고 출처 리스트
  - `messages`: 이전 단계의 메시지들

**작업**:
1. **분석 도구 준비** (라인 15-18):
   - `analyse_quantitative_metrics`: 정량적 지표 분석 (구현 예정)
   - `analyse_qualitative_feedback`: 정성적 피드백 분석 (구현 예정)

2. **프롬프트 생성** (라인 25-86):
   - 분석 전문가 역할 정의
   - 데이터 검토, 패턴 파악, 인사이트 도출 프레임워크 제공
   - 요청 컨텍스트, 조사 메모, 참고 출처 포함

3. **LLM 호출** (라인 88-90):
   - 도구를 바인딩한 LLM으로 분석 요청
   - 도구 호출이 필요한 경우 도구 실행

4. **요약 생성** (라인 116-133):
   - 분석 결과를 요약 LLM으로 재요약
   - 핵심 발견사항 추출

**출력**:
```python
{
    "messages": [...],  # 기존 메시지 + 분석 응답 + 도구 결과
    "analysis_outline": "데이터 분석 개요 및 구조...",
    "analysis_findings": "핵심 발견사항 요약:\n1. 주요 데이터 포인트...\n2. 패턴 및 트렌드...\n3. 인사이트..."
}
```

**다음 노드**: "Compose Agent" 노드로 상태 전달

---

## 노드 13: Compose Agent 노드 - 최종 보고서 작성

**파일**: `backend/app/agents/compose_agent.py`

**코드 블록**: `compose_report_node` 함수 (라인 10-105)

**실제 코드**:
```10:105:backend/app/agents/compose_agent.py
    def compose_report_node(state):
        request_context = state.get("request_context", {})
        analysis_outline = state.get("analysis_outline", "")
        analysis_findings = state.get("analysis_findings", "")
        research_notes = state.get("research_notes", "")
        messages: List = list(state.get("messages", []))

        prompt = textwrap.dedent(
            """
            # 역할
            당신은 문화시설 전문 보고서 작성자입니다. 경영진이나 의사결정자를 위한 고품질 보고서를 작성합니다.
            
            # 목표
            조사 및 분석 단계에서 수집한 데이터와 인사이트를 바탕으로 실행 가능한 최종 보고서를 작성하세요.
            
            # 입력 자료
            요청 컨텍스트:
            {request_context}
            
            분석 개요:
            {analysis_outline}
            
            핵심 분석 결과:
            {analysis_findings}
            
            조사 메모:
            {research_notes}
            
            # 보고서 구조 (Markdown 형식)
            
            ## Executive Summary (핵심 요약)
            - 보고서의 목적과 주요 발견사항을 2-3 문단으로 요약
            - 의사결정자가 가장 먼저 읽는 섹션임을 고려
            - 핵심 메시지와 결론을 명확하게 제시
            
            ## Key Insights (주요 인사이트)
            - 데이터 분석을 통해 발견한 핵심 사실들을 번호나 불릿으로 정리
            - 각 인사이트는 구체적이고 데이터에 기반해야 함
            - 전시 정보, 소장품 정보 등 수집된 데이터를 적극 활용
            - 보고서 주제({report_topic})와 직접 연결
            
            ## Recommendations (제안사항)
            - 인사이트를 바탕으로 실행 가능한 제안을 제시
            - 각 제안은 구체적이고 측정 가능해야 함
            - 우선순위를 고려하여 정리
            - 문화시설의 특성과 현실을 반영
            
            ## Next Steps (향후 계획)
            - 제안사항을 실행하기 위한 구체적인 행동 계획
            - 단기/중기/장기 관점으로 구분 가능
            - 필요한 리소스나 협력 사항 명시
            - 실현 가능성을 고려한 로드맵
            
            # 작성 원칙
            1. 명확성: 전문 용어는 최소화하고 명확한 표현 사용
            2. 구체성: 모호한 표현 대신 구체적인 사실과 데이터 활용
            3. 실행 가능성: 실제로 실행할 수 있는 제안 제시
            4. 근거 기반: 모든 주장과 제안은 데이터와 분석에 근거
            5. 독자 중심: 의사결정자가 필요로 하는 정보에 집중
            
            # 형식 요구사항
            - Markdown 문법 사용 (제목, 불릿, 번호 목록 등)
            - 각 섹션은 명확하게 구분
            - 필요시 표나 리스트로 정보 정리
            - 한국어로 작성 (전문적이고 격식 있는 문체)
            - **중요**: 마크다운 코드 블록(```markdown 또는 ```)으로 감싸지 말고, 바로 마크다운 형식으로 작성하세요
            
            # 주의사항
            - 수집된 데이터를 최대한 활용하되, 없는 내용은 억지로 만들지 말 것
            - 일반론이나 상투적인 표현보다는 구체적인 내용에 집중
            - 보고서 주제와 질문들에 명확하게 답변할 것
            - 실제 전시 정보나 소장품 정보가 있다면 구체적으로 언급
            - **절대 코드 블록(```)으로 감싸지 말 것**: 보고서는 바로 마크다운 형식으로 시작해야 합니다
            
            위 구조와 원칙을 따라 완성도 높은 Markdown 보고서를 작성하세요. 
            보고서는 # 제목으로 바로 시작하고, 코드 블록 마커(```)를 사용하지 마세요.
            """
        ).format(
            request_context=json.dumps(request_context, ensure_ascii=False, indent=2),
            report_topic=request_context.get("report_topic", "보고서 주제"),
            analysis_outline=analysis_outline,
            analysis_findings=analysis_findings,
            research_notes=research_notes,
        ).strip()

        response = llm.invoke(prompt)
        messages.append(response)
        final_report = response.content.strip() if response else "Report drafting is pending tool integration."

        return {
            "messages": messages,
            "final_report": final_report,
            "compose_prompt": prompt,
        }
```

**입력**:
- `state: ReportingAgentState`:
  - `request_context`: 요청 컨텍스트
  - `analysis_outline`: 분석 개요
  - `analysis_findings`: 핵심 분석 결과
  - `research_notes`: 조사 메모
  - `messages`: 이전 단계의 모든 메시지

**작업**:
1. **보고서 프롬프트 생성** (라인 17-93):
   - 문화시설 전문 보고서 작성자 역할 정의
   - 보고서 구조 정의:
     - Executive Summary (핵심 요약)
     - Key Insights (주요 인사이트)
     - Recommendations (제안사항)
     - Next Steps (향후 계획)
   - 입력 자료 통합 (요청 컨텍스트, 분석 결과, 조사 메모)

2. **LLM 호출** (라인 95-96):
   - 보고서 작성 프롬프트를 LLM에 전달
   - Markdown 형식의 최종 보고서 생성

**출력**:
```python
{
    "messages": [...],  # 기존 메시지 + 최종 보고서 메시지
    "final_report": "# 보고서 제목\n\n## Executive Summary\n...\n\n## Key Insights\n...\n\n## Recommendations\n...\n\n## Next Steps\n...",
    "compose_prompt": "..."  # 사용된 프롬프트 전문
}
```

**다음 노드**: 그래프 실행 완료, 서비스 레이어로 결과 반환

---

## 노드 14: 서비스 레이어 - 결과 수집 및 반환

**파일**: `backend/app/services/agent_report_service.py`

**코드 블록**: `generate_report` 메서드의 결과 처리 부분 (라인 60-91)

**실제 코드**:
```60:91:backend/app/services/agent_report_service.py
    async def generate_report(
        self,
        organization_name: str,
        user_command: str
    ) -> Dict:
        try:
            # 시작 시간 기록
            start_time = time.time()
            logger.info(f"Starting report generation for {organization_name}")
            
            graph = self._get_graph()
            initial_state = self._build_initial_state(organization_name, user_command)
            
            result = graph.graph.invoke(initial_state)
            
            # 종료 시간 기록 및 소요 시간 계산
            end_time = time.time()
            generation_time_seconds = round(end_time - start_time, 2)
            
            logger.info(f"Report generation completed in {generation_time_seconds} seconds")
            
            return {
                "final_report": result.get("final_report", ""),
                "research_sources": result.get("research_sources", []),
                "analysis_summary": result.get("analysis_findings", ""),
                "report_topic": user_command,
                "generation_time_seconds": generation_time_seconds,
            }
            
        except Exception as e:
            logger.error(f"Report generation failed: {e}", exc_info=True)
            raise
```

**입력**:
- `result`: 그래프 실행 결과 딕셔너리
  - `final_report`: 최종 보고서
  - `research_sources`: 참고 출처 리스트
  - `analysis_findings`: 분석 요약
  - 기타 상태 정보

**작업**:
1. 실행 시간 계산 (시작 시간과 종료 시간 차이)
2. 결과 딕셔너리 구성

**출력**:
```python
{
    "final_report": "# 보고서 제목\n\n...",
    "research_sources": ["http://...", ...],
    "analysis_summary": "핵심 발견사항 요약...",
    "report_topic": "2025년 1월 전시 현황 분석",
    "generation_time_seconds": 45.23
}
```

**다음 노드**: API 엔드포인트로 결과 반환

---

## 노드 15: 데이터베이스 저장

**파일**: `backend/app/api/agent_report.py`

**코드 블록**: 데이터베이스 저장 부분 (라인 28-39)

**실제 코드**:
```28:39:backend/app/api/agent_report.py
        advanced_report = AdvancedReport(
            organization_name=request.organization_name,
            user_command=request.user_command,
            report_topic=result["report_topic"],
            final_report=result["final_report"],
            research_sources_json=json.dumps(result["research_sources"], ensure_ascii=False),
            analysis_summary=result["analysis_summary"]
        )
        
        db.add(advanced_report)
        db.commit()
        db.refresh(advanced_report)
```

**입력**:
- `result`: 서비스 레이어에서 반환된 결과 딕셔너리
- `request`: 원본 요청 데이터
- `db: Session`: 데이터베이스 세션

**작업**:
1. `AdvancedReport` 모델 인스턴스 생성
2. 데이터베이스에 저장 (`db.add()`)
3. 커밋 (`db.commit()`)
4. 저장된 레코드 새로고침 (`db.refresh()`)

**출력**:
- `advanced_report`: 저장된 데이터베이스 레코드 객체 (ID 포함)

**다음 노드**: 응답 생성

---

## 노드 16: 응답 생성 및 반환

**파일**: `backend/app/api/agent_report.py`

**코드 블록**: 응답 생성 부분 (라인 41-50)

**실제 코드**:
```41:50:backend/app/api/agent_report.py
        return AdvancedReportResponse(
            id=advanced_report.id,
            organization_name=advanced_report.organization_name,
            report_topic=advanced_report.report_topic,
            final_report=advanced_report.final_report,
            research_sources=json.loads(advanced_report.research_sources_json) if advanced_report.research_sources_json else [],
            analysis_summary=advanced_report.analysis_summary or "",
            generated_at=advanced_report.created_at,
            generation_time_seconds=result.get("generation_time_seconds", 0.0)
        )
```

**입력**:
- `advanced_report`: 저장된 데이터베이스 레코드
- `result`: 서비스 레이어 결과 (생성 시간 포함)

**작업**:
1. `AdvancedReportResponse` Pydantic 모델 인스턴스 생성
2. JSON 직렬화 가능한 형태로 변환

**출력**:
```python
AdvancedReportResponse(
    id=1,
    organization_name="국립중앙박물관",
    report_topic="2025년 1월 전시 현황 분석",
    final_report="# 보고서 제목\n\n...",
    research_sources=["http://...", ...],
    analysis_summary="핵심 발견사항 요약...",
    generated_at=datetime(2025, 1, 15, 10, 30, 0),
    generation_time_seconds=45.23
)
```

**다음 노드**: FastAPI가 자동으로 JSON 응답으로 변환하여 클라이언트에 반환

---

## 노드 17: HTTP 응답 반환

**파일**: `backend/app/main.py` (FastAPI 프레임워크)

**코드 블록**: FastAPI의 자동 응답 처리

**입력**:
- `AdvancedReportResponse` 객체

**작업**:
1. Pydantic 모델을 JSON으로 직렬화
2. HTTP 200 OK 상태 코드와 함께 응답 본문 생성
3. CORS 헤더 추가 (설정된 경우)

**출력**:
- HTTP 응답:
  - Status Code: 200
  - Content-Type: application/json
  - Body:
    ```json
    {
      "id": 1,
      "organization_name": "국립중앙박물관",
      "report_topic": "2025년 1월 전시 현황 분석",
      "final_report": "# 보고서 제목\n\n...",
      "research_sources": ["http://...", ...],
      "analysis_summary": "핵심 발견사항 요약...",
      "generated_at": "2025-01-15T10:30:00",
      "generation_time_seconds": 45.23
    }
    ```

**다음 노드**: 프론트엔드로 응답 전달 (프로세스 종료)

---

## 상태 관리: ReportingAgentState

**파일**: `backend/app/agents/agent_state.py`

**실제 코드**:
```1:19:backend/app/agents/agent_state.py
from typing import Annotated, List, TypedDict
from langchain_core.messages import BaseMessage


# 보고서 자동화 에이전트들이 공유하는 상태
class ReportingAgentState(TypedDict, total=False):

    request_context: Annotated[dict, "보고서 요청에서 전달된 메타데이터(문화시설명, 질문 등)."]
    messages: Annotated[List[BaseMessage], "LLM과 주고받은 전체 대화 메시지 기록."]

    research_notes: Annotated[str, "조사 에이전트가 수집하여 정리한 주요 메모."]
    research_sources: Annotated[List[str], "조사 단계에서 확인된 참고 출처 목록."]

    analysis_outline: Annotated[str, "보고서 구조를 잡기 위한 분석 개요."]
    analysis_findings: Annotated[str, "분석 단계에서 도출한 핵심 인사이트 요약."]

    final_report: Annotated[str, "최종적으로 작성된 보고서 본문."]
    compose_prompt: Annotated[str, "작성 에이전트가 사용한 프롬프트 전문."]
```

**상태 구조**:
```python
{
    "request_context": dict,           # 요청 메타데이터
    "messages": List[BaseMessage],      # 대화 메시지 기록
    "research_notes": str,              # 조사 메모
    "research_sources": List[str],      # 참고 출처
    "research_payload": List[dict],     # 수집된 데이터 샘플
    "analysis_outline": str,            # 분석 개요
    "analysis_findings": str,           # 핵심 인사이트
    "final_report": str,                # 최종 보고서
    "compose_prompt": str               # 작성 프롬프트
}
```

**상태 전달 흐름**:
1. 초기 상태 생성 (서비스 레이어) → Research Agent
2. Research Agent 실행 → 상태에 `research_notes`, `research_sources`, `research_payload` 추가 → Analysis Agent
3. Analysis Agent 실행 → 상태에 `analysis_outline`, `analysis_findings` 추가 → Compose Agent
4. Compose Agent 실행 → 상태에 `final_report`, `compose_prompt` 추가 → 종료

---

## 에러 처리

각 노드에서 발생할 수 있는 에러와 처리 방식:

1. **API 호출 실패** (`api_utils.py`):
   - `requests.exceptions.RequestException`: 재시도 로직 또는 에러 메시지 반환
   - `ET.ParseError`: XML 파싱 실패 시 빈 데이터 반환

2. **데이터베이스 오류** (`agent_report.py`):
   - `db.rollback()` 호출
   - HTTP 500 에러 반환

3. **그래프 실행 오류** (`agent_report_service.py`):
   - 예외 로깅
   - 상위로 예외 전파

---

## 주요 의존성

- **FastAPI**: 웹 프레임워크
- **LangChain/LangGraph**: 에이전트 및 그래프 실행
- **SQLAlchemy**: 데이터베이스 ORM
- **Pydantic**: 데이터 검증
- **requests**: HTTP API 호출
- **OpenAI API**: LLM 호출

---

## 실행 시간 추적

- 시작 시간: `agent_report_service.py`의 `generate_report` 메서드 시작 시점
- 종료 시간: 그래프 실행 완료 시점
- 소요 시간: `generation_time_seconds` 필드에 저장되어 응답에 포함됨

