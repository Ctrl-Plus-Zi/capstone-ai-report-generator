import json
import os
import re
from pathlib import Path
from typing import Dict, List, Optional

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
    filter_value: Optional[str] = None,
    page_no: int = 1,
    num_of_rows: int = 100
) -> Dict:

    try:
        # API 설정 로드
        api_registry = load_api_registry()
        
        if api_name not in api_registry:
            return {
                "success": False,
                "api_name": api_name,
                "error": f"API '{api_name}'를 찾을 수 없습니다.",
                "data": [],
                "count": 0
            }
        
        config = api_registry[api_name]
        
        # 파라미터 설정
        params = config["default_params"].copy()
        params["pageNo"] = str(page_no)
        params["numOfRows"] = str(num_of_rows)
        
        # 필터 규칙 설정 
        filter_rules = config.get("filter_rules")
        if filter_value and filter_rules:
            filter_rules = [rule.copy() for rule in filter_rules]
            if len(filter_rules) > 0:
                filter_rules[0]["value"] = filter_value
        
        # API 호출
        response = requests.get(config["base_url"], params=params, timeout=30)
        response.raise_for_status()
        
        # XML 파싱
        root = ET.fromstring(response.text)
        
        # 결과 코드 확인
        result_code = root.findtext('.//resultCode')
        result_msg = root.findtext('.//resultMsg')
        
        # xml_to_dict로 데이터 추출 및 필터링 
        result_data = xml_to_dict(root, config["fields"], filter_rules)
        
        # HTML 태그 정리
        for item in result_data:
            if "DESCRIPTION" in item and item["DESCRIPTION"]:
                soup = BeautifulSoup(item["DESCRIPTION"], 'html.parser')
                item["DESCRIPTION_TEXT"] = soup.get_text(" ", strip=True)
        
        return {
            "success": True,
            "api_name": api_name,
            "api_description": config.get("api_name", ""),
            "result_code": result_code,
            "result_msg": result_msg,
            "data": result_data,  
            "count": len(result_data)
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

