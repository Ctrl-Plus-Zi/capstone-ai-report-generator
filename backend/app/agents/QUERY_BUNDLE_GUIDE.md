# 📘 Query Bundle 작성 가이드

## 기본 구조

```json
"번들이름": {
  "description": "설명",
  "purpose": "수집 목적 (LLM에게 전달됨)",
  "queries": [ ... ],
  "stats": ["review", "demographics"],
  "requires": ["다른번들"],
  "block": { "type": "bar", "title": "차트 제목" }
}
```

---

## 쿼리 작성법

### 1️⃣ search - LIKE 검색

```json
["search", "테이블명", "컬럼명", "검색값", "저장키"]
```

**SQL 대응:**
```sql
SELECT * FROM 테이블명 WHERE 컬럼명 LIKE '%검색값%' LIMIT 10
```

**예시:**
```json
["search", "sns_buzz_master_tbl", "slta_nm", "$org", "facility"]
```
→ `SELECT * FROM sns_buzz_master_tbl WHERE slta_nm LIKE '%예술의전당%'`  
→ 결과를 `facility`에 저장

---

### 2️⃣ filter - 정확한 값 필터

```json
["filter", "테이블명", {"컬럼": "값"}, limit, "저장키"]
```

**SQL 대응:**
```sql
SELECT * FROM 테이블명 WHERE 컬럼 = '값' LIMIT limit
```

**예시:**
```json
["filter", "sns_buzz_extract_contents", {"slta_cd": "$ref.facility.slta_cd"}, 100, "reviews"]
```
→ `SELECT * FROM sns_buzz_extract_contents WHERE slta_cd = 'SLTA018' LIMIT 100`  
→ `facility.slta_cd` 값을 참조하여 필터링

---

## 변수

| 변수 | 설명 | 예시 |
|------|------|------|
| `$org` | 기관명 | "예술의전당" |
| `$ref.키.필드` | 이전 쿼리 결과 참조 | `$ref.facility.slta_cd` → "SLTA018" |

---

## 통계 옵션 (stats)

| 값 | 자동 계산 내용 |
|------|------|
| `"review"` | 리뷰 평점 분포, 평균 평점 |
| `"demographics"` | 연령대별/성별 방문자 비율 |

---

## 블록 타입 (block.type)

| 타입 | 결과 |
|------|------|
| `"bar"` | 막대 차트 (평점 분포 등) |
| `"doughnut"` | 도넛 차트 (비율 표시) |
| `"table"` | 테이블 |
| `"llm"` | LLM이 알아서 생성 |

---

## 실전 예시

### 리뷰 수집 번들

```json
"리뷰": {
  "description": "구글맵/SNS 리뷰 데이터 수집",
  "purpose": "리뷰 평점 분포와 고객 만족도 분석",
  "queries": [
    ["search", "sns_buzz_master_tbl", "slta_nm", "$org", "facility"],
    ["filter", "sns_buzz_extract_contents", {"slta_cd": "$ref.facility.slta_cd"}, 100, "reviews"]
  ],
  "stats": ["review"],
  "block": { "type": "bar", "title": "리뷰 평점 분포" }
}
```

**실행 흐름:**
```
1. sns_buzz_master_tbl에서 "예술의전당" 검색 → facility에 저장
2. facility.slta_cd (예: "SLTA018") 참조
3. sns_buzz_extract_contents에서 slta_cd = "SLTA018" 필터링 → reviews에 저장
4. reviews로 평점 통계 자동 계산
5. bar 차트로 블록 생성
```

---

## preset 설정

```json
"presets": {
  "기본": { "bundles": ["리뷰", "인구통계", "페르소나"] },
  "공연장": { "bundles": ["리뷰", "인구통계", "페르소나"] }
},
"org_preset_mapping": {
  "예술의전당": "공연장",
  "국립현대미술관": "미술관"
}
```

→ "예술의전당" 입력 시 자동으로 "공연장" preset 적용

---

## 새 번들 추가 예시

**티켓 판매 데이터 추가:**
```json
"티켓판매": {
  "description": "티켓 판매 데이터",
  "purpose": "티켓 판매 추이 분석",
  "queries": [
    ["filter", "ticket_sales", {"venue_name": "$org"}, 100, "tickets"]
  ],
  "block": { "type": "llm" }
}
```

**preset에 추가:**
```json
"상세분석": { "bundles": ["리뷰", "인구통계", "페르소나", "티켓판매"] }
```

