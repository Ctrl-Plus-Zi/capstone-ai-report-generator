# 개발 항목별 명세서

## 1단계: DB 스키마 변경

### 현재 프로젝트의 문제점
- `advanced_reports` 테이블에 `report_type`과 `analysis_target_dates` 필드가 없음
- 하위 보고서 생성 시 부모 보고서의 날짜 정보를 상속받을 수 없음
- 보고서 유형('user' 또는 'operator')을 구분할 수 없음
- 여러 날짜에 대한 비교 분석을 수행할 수 없음

### 개선방법 (개발방법)

#### 1.1 모델 파일 수정
- `backend/app/models/advanced_report.py` 파일의 `AdvancedReport` 클래스에 두 개의 필드 추가
  - `report_type`: String(20) 타입, 기본값 "user", nullable=False
  - `analysis_target_dates`: Text 타입, nullable=True (JSON 배열 문자열 저장)

#### 1.2 마이그레이션 스크립트 작성
- Python 스크립트 생성 (`backend/add_report_type_and_dates_columns.py`)
- SQLAlchemy를 사용하여 기존 테이블에 컬럼 추가
- 기존 데이터 마이그레이션:
  - `report_type`: 모든 기존 레코드에 "user" 기본값 설정
  - `analysis_target_dates`: 기존 레코드는 NULL로 유지 (또는 user_command에서 날짜 추출 시도)

#### 1.3 마이그레이션 실행
- 스크립트를 직접 실행하여 DB 스키마 변경
- 기존 데이터 무결성 확인

### 개선시 기대효과
- 하위 보고서 생성 시 부모 보고서의 날짜 정보를 DB에서 조회 가능
- 보고서 유형별로 구분하여 저장 및 조회 가능
- 여러 날짜에 대한 비교 분석 데이터를 저장할 수 있는 기반 마련
- 향후 날짜 기반 필터링 및 검색 기능 확장 가능

---

## 2단계: API 스키마 변경

### 현재 프로젝트의 문제점
- `AdvancedReportRequest`에 `analysis_target_dates`와 `additional_dates` 필드가 없음
- `AdvancedReportResponse`에 `report_type`과 `analysis_target_dates` 필드가 없음
- API 엔드포인트에서 날짜 배열을 받아서 처리할 수 없음
- 하위 보고서 생성 시 추가 날짜를 전달할 수 없음

### 개선방법 (개발방법)

#### 2.1 Request 스키마 수정
- `backend/app/schemas/advanced_report.py`의 `AdvancedReportRequest` 클래스에 필드 추가:
  - `analysis_target_dates`: Optional[List[str]] 타입, 기본값 None
  - `additional_dates`: Optional[List[str]] 타입, 기본값 None (하위 보고서 생성 시 추가할 날짜들)
  - `report_type`은 이미 존재하므로 유지

#### 2.2 Response 스키마 수정
- `AdvancedReportResponse` 클래스에 필드 추가:
  - `report_type`: Optional[str] 타입
  - `analysis_target_dates`: Optional[List[str]] 타입

#### 2.3 API 엔드포인트 수정
- `backend/app/api/agent_report.py`의 `generate_advanced_report` 함수 수정:
  - 요청에서 `analysis_target_dates`, `additional_dates`, `report_type` 받기
  - 부모 보고서가 있으면 부모의 `analysis_target_dates`와 `report_type` 가져오기
  - `agent_report_service.generate_report` 호출 시 새 파라미터들 전달
  - DB 저장 시 `report_type`과 `analysis_target_dates` (JSON 문자열로 변환) 저장
  - 응답 생성 시 `report_type`과 `analysis_target_dates` (JSON 파싱) 포함

#### 2.4 하위 보고서 조회 엔드포인트 수정
- `get_child_reports` 함수 수정:
  - 조회한 하위 보고서들의 `report_type`과 `analysis_target_dates`를 응답에 포함
  - JSON 파싱하여 리스트로 변환

### 개선시 기대효과
- 프론트엔드에서 날짜 배열을 API로 전달 가능
- 하위 보고서 생성 시 부모 날짜 상속 및 추가 날짜 전달 가능
- API 응답에서 보고서 유형과 분석 대상 날짜 확인 가능
- 클라이언트-서버 간 데이터 구조 일관성 확보

---

## 3단계: AgentReportService 수정

### 현재 프로젝트의 문제점
- `_build_initial_state` 메서드가 날짜 배열을 처리하지 않음
- 부모 보고서의 날짜를 상속받는 로직이 없음
- 추가 날짜를 합치는 로직이 없음
- `request_context`에 `analysis_target_dates` 배열과 `is_multi_date_analysis` 플래그가 없음
- 여러 날짜 분석 여부를 판단하는 로직이 없음

### 개선방법 (개발방법)

#### 3.1 메서드 시그니처 수정
- `_build_initial_state` 메서드에 파라미터 추가:
  - `analysis_target_dates`: Optional[List[str]] (부모 보고서의 날짜 배열 또는 일반 보고서 생성 시 전달된 날짜)
  - `additional_dates`: Optional[List[str]] (하위 보고서 생성 시 추가할 날짜들)

#### 3.2 날짜 배열 구성 로직 구현
- 부모 보고서가 있는 경우:
  - 부모 보고서의 `analysis_target_dates` 필드를 JSON 파싱하여 리스트로 변환
  - `additional_dates`가 있으면 부모 날짜와 합치기 (중복 제거, 정렬)
  - 날짜가 없으면 현재 날짜의 "YYYY-MM" 형식 사용
- 부모 보고서가 없는 경우:
  - `analysis_target_dates` 파라미터가 있으면 사용
  - 없으면 현재 날짜의 "YYYY-MM" 형식 사용

#### 3.3 여러 날짜 분석 여부 판단
- 최종 날짜 배열의 길이가 1보다 크면 `is_multi_date_analysis = True`
- 그렇지 않으면 `is_multi_date_analysis = False`

#### 3.4 request_context 업데이트
- `request_context` 딕셔너리에 다음 필드 추가:
  - `analysis_target_dates`: 최종 구성된 날짜 배열
  - `is_multi_date_analysis`: 여러 날짜 분석 여부 불린 값

#### 3.5 generate_report 메서드 수정
- 메서드 시그니처에 `analysis_target_dates`와 `additional_dates` 파라미터 추가
- `_build_initial_state` 호출 시 새 파라미터들 전달

### 개선시 기대효과
- 하위 보고서 생성 시 부모 보고서의 날짜를 자동으로 상속
- 사용자가 추가한 날짜를 부모 날짜와 합쳐서 분석 가능
- 단일 날짜와 여러 날짜 분석을 자동으로 구분
- 리서치 에이전트가 날짜 배열을 받아서 처리할 수 있는 기반 마련

---

## 4단계: Search Agent 수정

### 현재 프로젝트의 문제점
- `search_agent_node` 함수가 단일 날짜만 처리함
- 여러 날짜에 대한 데이터를 수집하는 로직이 없음
- `is_multi_date_analysis` 플래그를 확인하지 않음
- 여러 날짜의 차트 데이터를 수집하고 저장하는 로직이 없음
- 날짜별로 순차적으로 데이터를 수집하는 메커니즘이 없음

### 개선방법 (개발방법)

#### 4.1 request_context에서 날짜 정보 추출
- `request_context`에서 `analysis_target_dates` 배열과 `is_multi_date_analysis` 플래그 가져오기
- 날짜 배열이 비어있으면 기본값 처리

#### 4.2 여러 날짜 분석 분기 처리
- `is_multi_date_analysis`가 True인 경우:
  - 날짜 배열을 순회하며 각 날짜별로 데이터 수집
  - 각 날짜에서 "YYYY-MM" 형식을 파싱하여 year, month 추출
  - `get_monthly_age_gender_ratio_data`를 각 날짜별로 호출 (year, month 지정)
  - 기관별 API 호출도 각 날짜 기준으로 수행 (필요시)
  - 수집한 데이터를 날짜별로 구분하여 저장
  - 차트 데이터도 여러 날짜 모두 수집하여 저장
- `is_multi_date_analysis`가 False인 경우:
  - 기존 로직 유지 (단일 날짜 기준 데이터 수집)
  - 첫 번째 날짜만 사용하여 데이터 수집

#### 4.3 차트 데이터 구조 변경
- 여러 날짜인 경우:
  - 차트 데이터를 날짜별로 구분하여 저장
  - 예: `{"2025-01": [...], "2025-02": [...], ...}` 형식
  - 또는 기존 형식 유지하되 모든 날짜의 데이터를 배열에 포함
- 단일 날짜인 경우:
  - 기존 형식 유지

#### 4.4 자동 호출 로직 수정
- `get_monthly_age_gender_ratio_data` 자동 호출 시:
  - 여러 날짜인 경우 각 날짜별로 순차 호출
  - 단일 날짜인 경우 기존 로직 유지
- `get_google_map_rating_statistics`는 날짜와 무관하므로 기존 로직 유지

#### 4.5 데이터 수집 순서 보장
- 여러 날짜 데이터 수집 시 순차 처리 (병렬 처리 대신)
- 각 날짜별 데이터 수집이 완료된 후 다음 날짜로 진행
- 에러 발생 시 로깅하고 다음 날짜로 계속 진행

### 개선시 기대효과
- 여러 날짜에 대한 비교 분석 데이터 수집 가능
- 날짜별 차트 데이터를 모두 수집하여 트렌드 분석 가능
- 단일 날짜와 여러 날짜 분석을 자동으로 구분하여 처리
- 하위 보고서에서 부모 날짜 + 추가 날짜 모두 분석 가능

---

## 5단계: 프론트엔드 UI 수정

### 현재 프로젝트의 문제점
- 하위 보고서 생성 시 날짜 추가 UI가 없음
- 부모 보고서의 날짜를 표시하지 않음
- 사용자가 여러 날짜를 선택할 수 있는 인터페이스가 없음
- 추가한 날짜를 삭제하는 기능이 없음
- API 요청 시 `additional_dates`를 전달하지 않음

### 개선방법 (개발방법)

#### 5.1 날짜 상태 관리 추가
- `ReportQuestionForm` 컴포넌트에 상태 추가:
  - `additionalDates`: 추가한 날짜 배열 (useState)
  - 부모 보고서의 날짜는 props로 받아서 표시만 (읽기 전용)

#### 5.2 날짜 표시 UI 구현
- 부모 보고서의 날짜 표시 영역:
  - "분석 대상 날짜" 라벨과 함께 부모 날짜들을 태그 형태로 표시
  - 읽기 전용 스타일 적용 (회색 배경, 삭제 버튼 없음)
- 추가한 날짜 표시 영역:
  - 추가한 날짜들을 태그 형태로 표시
  - 각 태그에 삭제 버튼(X) 추가

#### 5.3 날짜 추가 기능 구현
- "날짜 추가" 버튼 클릭 시:
  - 날짜 선택 모달 또는 인라인 날짜 입력 필드 표시
  - 년도와 월을 선택할 수 있는 UI 제공 (예: `<input type="month">`)
  - 선택한 날짜를 "YYYY-MM" 형식으로 변환
  - 중복 체크: 이미 추가된 날짜나 부모 날짜와 중복되면 경고
  - 중복이 아니면 `additionalDates` 배열에 추가
  - 날짜 배열 자동 정렬 (오름차순)

#### 5.4 날짜 삭제 기능 구현
- 추가한 날짜 태그의 삭제 버튼 클릭 시:
  - 해당 날짜를 `additionalDates` 배열에서 제거
  - 부모 날짜는 삭제 불가 (읽기 전용)

#### 5.5 API 요청 수정
- `handleCreateChildReport` 함수 수정:
  - API 요청 시 `additional_dates` 필드에 `additionalDates` 배열 전달
  - 부모 보고서의 `report_type`도 함께 전달

#### 5.6 UI 레이아웃 배치
- 질문 입력 필드 위에 날짜 관련 UI 배치:
  - 부모 날짜 표시 영역
  - "날짜 추가" 버튼
  - 추가한 날짜 표시 영역
  - 질문 입력 필드

### 개선시 기대효과
- 사용자가 하위 보고서 생성 시 여러 날짜를 선택하여 비교 분석 가능
- 부모 보고서의 날짜를 시각적으로 확인 가능
- 직관적인 날짜 추가/삭제 인터페이스 제공
- 날짜 선택 오류 방지 (중복 체크, 자동 정렬)

---

## 6단계: 프론트엔드 차트 표시 수정

### 현재 프로젝트의 문제점
- 여러 날짜의 차트 데이터를 표시하지 않음
- 날짜별로 차트를 연달아 표시하는 로직이 없음
- 각 날짜의 분석 내용을 차트 아래에 표시하지 않음
- 여러 날짜 비교 분석 내용을 표시하지 않음

### 개선방법 (개발방법)

#### 6.1 차트 데이터 구조 확인
- `chart_data`에서 `age_gender_ratio` 배열 확인
- 여러 날짜인 경우 날짜별로 구분된 데이터 구조 파악
- 또는 모든 날짜의 데이터가 하나의 배열에 포함된 구조인지 확인

#### 6.2 날짜별 차트 렌더링 로직 구현
- `analysis_target_dates` 배열이 2개 이상인 경우:
  - 각 날짜별로 차트 컴포넌트 렌더링
  - 날짜별로 해당 날짜의 차트 데이터 필터링
  - 각 차트 위에 날짜 라벨 표시 (예: "2025년 1월")
  - 각 차트 아래에 해당 날짜의 분석 내용 표시
- 단일 날짜인 경우:
  - 기존 로직 유지 (하나의 차트만 표시)

#### 6.3 분석 내용 표시 로직 구현
- 여러 날짜인 경우:
  - 각 날짜별 분석 내용을 차트 아래에 표시
  - 마지막에 전체 비교 분석 내용 표시 (final_report에서 추출 또는 별도 필드)
- 단일 날짜인 경우:
  - 기존 로직 유지

#### 6.4 차트 컴포넌트 재사용
- 기존 `AgeGenderChart` 컴포넌트를 날짜별로 여러 번 렌더링
- 각 차트에 해당 날짜의 데이터만 전달
- 차트 간 간격 및 레이아웃 조정

#### 6.5 반응형 레이아웃 고려
- 여러 차트가 세로로 연달아 표시될 때 스크롤 가능하도록
- 각 차트 섹션에 구분선 또는 배경색으로 시각적 구분

### 개선시 기대효과
- 여러 날짜의 차트를 한 화면에서 비교 가능
- 날짜별 트렌드 변화를 시각적으로 파악 가능
- 각 날짜의 분석 내용을 차트와 함께 확인 가능
- 비교 분석 보고서의 가독성 향상

---

## 전체 개발 완료 후 기대효과

### 기능적 효과
- 하위 보고서 생성 시 부모 보고서의 날짜를 자동 상속
- 사용자가 여러 날짜를 선택하여 비교/동향 분석 가능
- 단일 날짜와 여러 날짜 분석을 자동으로 구분하여 처리
- 날짜별 차트와 분석 내용을 한 화면에서 확인 가능

### 사용자 경험 개선
- 직관적인 날짜 추가/삭제 인터페이스
- 부모 보고서의 날짜 정보를 시각적으로 확인 가능
- 여러 날짜 비교 분석 결과를 한눈에 파악 가능
- 보고서 계층 구조를 유지하면서 날짜 기반 분석 확장 가능

### 기술적 효과
- DB 스키마 확장으로 향후 날짜 기반 기능 추가 용이
- API 스키마 일관성 확보
- 에이전트 로직의 유연성 향상 (단일/다중 날짜 자동 처리)
- 프론트엔드 컴포넌트 재사용성 향상

