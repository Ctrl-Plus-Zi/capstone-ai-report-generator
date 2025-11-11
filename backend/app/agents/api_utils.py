from __future__ import annotations 
import json
import os
import re
import calendar
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup


def load_api_registry(config_path: Optional[str] = None) -> Dict:
    """API 설정 파일을 로드합니다."""
    if config_path is None:
        # 현재 파일의 디렉토리 경로를 기준으로 api_configs.json 찾기
        current_dir = Path(__file__).parent
        config_path = current_dir / "api_configs.json"
    
    with open(config_path, "r", encoding="utf-8") as f:
        configs = json.load(f)
    
    return configs


def filter_field(result: Dict, filter_rules: Optional[List[Dict]]) -> bool:
    """필터 규칙에 따라 데이터를 필터링합니다."""
    if filter_rules is None:
        return True  # 필터 규칙이 없으면 모든 데이터 통과
    
    flag = False
    for filter_rule in filter_rules:
        field = filter_rule["field"]
        operator = filter_rule["operator"]
        value = filter_rule["value"]
        
        if operator == "==":
            if result.get(field) == value:
                flag = True
        
        elif operator == "!=":
            if result.get(field) != value:
                flag = True
        
        elif operator == "substring":
            if result.get(field) is None:
                continue
            if re.search(re.escape(value), result[field], flags=re.IGNORECASE):
                flag = True
            else:
                if re.search(value, result[field]):
                    flag = True
    
    return flag


def xml_to_dict(root: ET.Element, fields: List[str], filter_rules: Optional[List[Dict]] = None) -> List[Dict]:
    """XML 응답을 딕셔너리 리스트로 변환합니다."""
    result_list = []
    
    for item in root.findall('.//item'):
        result = {}
        
        for field in fields:
            field_value = item.findtext(f'.//{field}')
            result[field] = field_value if field_value else None
        
        if filter_field(result, filter_rules):
            result_list.append(result)
    
    return result_list


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

        # --- 안전한 필터 적용 ---
        # 항상 '지역 변수'로 먼저 정의해두면 UnboundLocalError 방지됨
        filter_rules = list(cfg.get("filter_rules") or [])
        
        # filter_value가 제공되면 동적으로 필터 추가/수정
        if filter_value:
            # 기관명 필터링을 위한 동적 필터 추가
            # CNTC_INSTT_NM 필드가 있으면 기관명으로 필터링
            if any(f in fields for f in ["CNTC_INSTT_NM", "cntc_instt_nm"]):
                filter_rules.append({
                    "field": "CNTC_INSTT_NM",
                    "op": "icontains",
                    "value": filter_value
                })
            # URL 필드가 있으면 URL로도 필터링 시도
            elif any(f in fields for f in ["URL", "url"]):
                filter_rules.append({
                    "field": "URL",
                    "op": "icontains",
                    "value": filter_value
                })

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
    
    except requests.exceptions.RequestException as e:
        return {
            "success": False,
            "api_name": api_name,
            "error": f"API 호출 실패: {str(e)}",
            "data": [],
            "count": 0
        }
    
    except ET.ParseError as e:
        return {
            "success": False,
            "api_name": api_name,
            "error": f"XML 파싱 실패: {str(e)}",
            "data": [],
            "count": 0
        }
    
    except Exception as e:
        return {
            "success": False,
            "api_name": api_name,
            "error": f"예상치 못한 오류: {str(e)}",
            "data": [],
            "count": 0
        }



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

    except requests.exceptions.RequestException as e:
        return {
            "success": False,
            "api_name": "KMA_ASOS_DAILY",
            "error": f"API 호출 실패: {str(e)}",
            "data": [],
            "count": 0
        }
    except ValueError as e:
        return {
            "success": False,
            "api_name": "KMA_ASOS_DAILY",
            "error": f"입력값 오류: {str(e)}",
            "data": [],
            "count": 0
        }
    except Exception as e:
        return {
            "success": False,
            "api_name": "KMA_ASOS_DAILY",
            "error": f"예상치 못한 오류: {str(e)}",
            "data": [],
            "count": 0
        }


def month_range(year: int, month: int) -> tuple[str, str]:
    """
    사용자 월 입력
    """
    if not (1 <= month <= 12):
        raise ValueError(f"월은 1~12 이어야 합니다. 현재 값: {month}")
    if year < 1900 or year > 2100:
        raise ValueError(f"연도 범위를 확인하세요: {year}")

    last_day = calendar.monthrange(year, month)[1]
    start = f"{year:04d}{month:02d}01"
    end   = f"{year:04d}{month:02d}{last_day:02d}"
    return start, end

