"""
Query Bundle Loader - 설정 기반 쿼리 번들 관리

query_bundles.json에서 쿼리 번들을 로드하고,
기관명/preset에 따라 적절한 쿼리와 블록 설정을 반환합니다.
"""

import json
import logging
import re
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple

logger = logging.getLogger("uvicorn.error")

# 설정 캐싱
_BUNDLES_CONFIG: Optional[Dict] = None


def _load_config() -> Dict:
    """설정 파일 로드 (캐싱)"""
    global _BUNDLES_CONFIG
    if _BUNDLES_CONFIG is None:
        config_path = Path(__file__).parent / "query_bundles.json"
        with open(config_path, "r", encoding="utf-8") as f:
            _BUNDLES_CONFIG = json.load(f)
        logger.info(f"[BUNDLE_LOADER] 설정 파일 로드 완료: {len(_BUNDLES_CONFIG.get('bundles', {}))}개 번들")
    return _BUNDLES_CONFIG


def reload_config() -> None:
    """설정 파일 강제 리로드 (개발용)"""
    global _BUNDLES_CONFIG
    _BUNDLES_CONFIG = None
    _load_config()


def get_preset_for_org(org_name: str) -> str:
    """기관명에 맞는 preset 반환"""
    config = _load_config()
    mapping = config.get("org_preset_mapping", {})
    
    # 키워드 매칭
    for keyword, preset in mapping.items():
        if keyword in org_name:
            logger.info(f"[BUNDLE_LOADER] '{org_name}' → preset: {preset}")
            return preset
    
    # 기본값
    logger.info(f"[BUNDLE_LOADER] '{org_name}' → preset: 기본 (매칭 없음)")
    return "기본"


def get_bundles_for_preset(preset_name: str) -> List[str]:
    """preset에 포함된 bundle 목록 반환"""
    config = _load_config()
    preset = config.get("presets", {}).get(preset_name, {})
    bundles = preset.get("bundles", [])
    
    if not bundles:
        # preset이 없으면 기본 preset 사용
        default_preset = config.get("presets", {}).get("기본", {})
        bundles = default_preset.get("bundles", [])
    
    return bundles


def _substitute_vars(value: Any, org_name: str) -> Any:
    """변수 치환: $org → 기관명, $ref.x.y → {x.y}"""
    if isinstance(value, str):
        result = value.replace("$org", org_name)
        # $ref.key.field → {key.field} 변환 (query_executor 형식)
        result = re.sub(r'\$ref\.([a-zA-Z_][a-zA-Z0-9_.]*)', r'{\1}', result)
        return result
    elif isinstance(value, dict):
        return {k: _substitute_vars(v, org_name) for k, v in value.items()}
    elif isinstance(value, list):
        return [_substitute_vars(item, org_name) for item in value]
    return value


def _parse_query_array(arr: List, org_name: str) -> Dict[str, Any]:
    """배열 형식 쿼리를 dict로 변환
    
    형식:
    - search: ["search", table, column, value, save_as]
    - filter: ["filter", table, {filters}, limit, save_as]
    """
    if len(arr) < 3:
        logger.warning(f"[BUNDLE_LOADER] 잘못된 쿼리 형식: {arr}")
        return {}
    
    action = arr[0]
    table = arr[1]
    save_as = arr[-1]
    
    if action == "search":
        # ["search", table, column, value, save_as]
        if len(arr) != 5:
            logger.warning(f"[BUNDLE_LOADER] search 쿼리 형식 오류: {arr}")
            return {}
        
        column = arr[2]
        value = _substitute_vars(arr[3], org_name)
        
        return {
            "action": "search",
            "table": table,
            "params": {
                "search_column": column,
                "search_value": value
            },
            "save_as": save_as
        }
    
    elif action == "filter":
        # ["filter", table, {filters}, limit, save_as]
        if len(arr) != 5:
            logger.warning(f"[BUNDLE_LOADER] filter 쿼리 형식 오류: {arr}")
            return {}
        
        filters = _substitute_vars(arr[2], org_name)
        limit = arr[3] if isinstance(arr[3], int) else 50
        
        return {
            "action": "filter",
            "table": table,
            "params": {
                "filters": filters,
                "limit": limit
            },
            "save_as": save_as
        }
    
    elif action == "aggregate":
        # ["aggregate", table, {params}, save_as] - 확장용
        return {
            "action": "aggregate",
            "table": table,
            "params": _substitute_vars(arr[2], org_name),
            "save_as": save_as
        }
    
    else:
        logger.warning(f"[BUNDLE_LOADER] 알 수 없는 action: {action}")
        return {}


def resolve_bundles(
    bundle_names: List[str],
    org_name: str
) -> Tuple[List[Dict], List[str], Dict[str, Dict]]:
    """
    번들 목록에서 쿼리 배열, 통계 목록, 블록 설정 생성
    
    Args:
        bundle_names: 로드할 번들 이름 목록
        org_name: 기관명 ($org 치환용)
    
    Returns:
        (queries, stats_to_calculate, block_configs)
        - queries: 실행할 쿼리 배열
        - stats_to_calculate: 계산할 통계 목록 (예: ["review", "demographics"])
        - block_configs: 번들별 블록 설정 (예: {"리뷰": {"type": "bar", ...}})
    """
    config = _load_config()
    bundles = config.get("bundles", {})
    
    all_queries = []
    all_stats = []
    block_configs = {}
    loaded_bundles = set()
    
    def _load_bundle(name: str):
        if name in loaded_bundles:
            return
        
        bundle = bundles.get(name)
        if not bundle:
            logger.warning(f"[BUNDLE_LOADER] 번들 없음: {name}")
            return
        
        # 의존성 먼저 로드
        for dep in bundle.get("requires", []):
            _load_bundle(dep)
        
        # 쿼리 파싱 및 추가
        for query_arr in bundle.get("queries", []):
            parsed = _parse_query_array(query_arr, org_name)
            if parsed:
                all_queries.append(parsed)
        
        # 통계 추가
        for stat in bundle.get("stats", []):
            if stat not in all_stats:
                all_stats.append(stat)
        
        # 블록 설정 저장
        block_config = bundle.get("block", {})
        if block_config:
            # purpose 추가
            block_config = dict(block_config)
            block_config["purpose"] = bundle.get("purpose", bundle.get("description", ""))
        block_configs[name] = block_config
        
        loaded_bundles.add(name)
        logger.info(f"[BUNDLE_LOADER] 번들 로드: {name} ({len(bundle.get('queries', []))}개 쿼리)")
    
    # 모든 번들 로드
    for bundle_name in bundle_names:
        _load_bundle(bundle_name)
    
    logger.info(f"[BUNDLE_LOADER] 총 {len(all_queries)}개 쿼리, {len(all_stats)}개 통계, {len(block_configs)}개 블록 설정")
    
    return all_queries, all_stats, block_configs


def get_all_for_org(org_name: str) -> Tuple[List[Dict], List[str], Dict[str, Dict]]:
    """
    기관명으로 preset을 찾고, 해당 preset의 모든 쿼리/통계/블록 설정 반환
    
    편의 함수: get_preset_for_org + get_bundles_for_preset + resolve_bundles
    """
    preset = get_preset_for_org(org_name)
    bundle_names = get_bundles_for_preset(preset)
    return resolve_bundles(bundle_names, org_name)


def get_available_presets() -> Dict[str, str]:
    """사용 가능한 preset 목록과 설명"""
    config = _load_config()
    return {
        name: preset.get("description", "")
        for name, preset in config.get("presets", {}).items()
    }


def get_available_bundles() -> Dict[str, str]:
    """사용 가능한 bundle 목록과 설명"""
    config = _load_config()
    return {
        name: bundle.get("description", "")
        for name, bundle in config.get("bundles", {}).items()
        if not name.startswith("_")  # _guide 등 제외
    }

