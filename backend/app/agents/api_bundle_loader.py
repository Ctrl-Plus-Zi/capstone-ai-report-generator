"""
API Bundle Loader - Google API 번들 관리

api_bundles.json에서 API 번들을 로드하고,
기관명/preset에 따라 적절한 API 호출과 블록 설정을 반환합니다.

## 번들 유형
- api_only: Google API만 사용
- mixed: DB 쿼리 + Google API 결합

## 변수 치환
- $org: 기관명
- $lat, $lng: 시설 좌표
- $address: 시설 주소
- $ref.key.field: 이전 결과 참조 (예: $ref.facility.slta_xcrd)
"""

import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from app.agents import google_utils

logger = logging.getLogger("uvicorn.error")

# 설정 캐싱
_API_BUNDLES_CONFIG: Optional[Dict] = None


# =============================================================================
# 설정 로드
# =============================================================================

def _load_config() -> Dict:
    """설정 파일 로드 (캐싱)"""
    global _API_BUNDLES_CONFIG
    if _API_BUNDLES_CONFIG is None:
        config_path = Path(__file__).parent / "api_bundles.json"
        with open(config_path, "r", encoding="utf-8") as f:
            _API_BUNDLES_CONFIG = json.load(f)
        api_count = len(_API_BUNDLES_CONFIG.get("api_bundles", {}))
        mixed_count = len(_API_BUNDLES_CONFIG.get("mixed_bundles", {}))
        logger.info(f"[API_BUNDLE_LOADER] 설정 로드: API {api_count}개, 혼합 {mixed_count}개")
    return _API_BUNDLES_CONFIG


def reload_config() -> None:
    """설정 파일 강제 리로드 (개발용)"""
    global _API_BUNDLES_CONFIG
    _API_BUNDLES_CONFIG = None
    _load_config()


# =============================================================================
# Preset 조회
# =============================================================================

def get_preset_for_org(org_name: str) -> str:
    """기관명에 맞는 API preset 반환"""
    config = _load_config()
    mapping = config.get("org_api_preset_mapping", {})
    
    for keyword, preset in mapping.items():
        if keyword in org_name:
            logger.info(f"[API_BUNDLE_LOADER] '{org_name}' → preset: {preset}")
            return preset
    
    # 기본값
    logger.info(f"[API_BUNDLE_LOADER] '{org_name}' → preset: 빠른조회 (기본)")
    return "빠른조회"


def get_bundles_for_preset(preset_name: str) -> List[str]:
    """preset에 포함된 bundle 목록 반환"""
    config = _load_config()
    preset = config.get("presets", {}).get(preset_name, {})
    bundles = preset.get("bundles", [])
    
    if not bundles:
        # 기본 preset
        default_preset = config.get("presets", {}).get("빠른조회", {})
        bundles = default_preset.get("bundles", [])
    
    return bundles


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
    result = {}
    
    # API 번들
    for name, bundle in config.get("api_bundles", {}).items():
        result[name] = f"[API] {bundle.get('description', '')}"
    
    # 혼합 번들
    for name, bundle in config.get("mixed_bundles", {}).items():
        result[name] = f"[혼합] {bundle.get('description', '')}"
    
    return result


# =============================================================================
# 변수 치환
# =============================================================================

def _substitute_vars(value: Any, context: Dict[str, Any]) -> Any:
    """
    변수 치환
    
    context 예시:
    {
        "org": "예술의전당",
        "lat": 37.4784,
        "lng": 127.0147,
        "address": "서울시 서초구...",
        "facility": {"slta_xcrd": 127.01, "slta_ycrd": 37.47, ...}
    }
    """
    if isinstance(value, str):
        result = value
        
        # 단순 변수 치환
        result = result.replace("$org", str(context.get("org", "")))
        result = result.replace("$lat", str(context.get("lat", "")))
        result = result.replace("$lng", str(context.get("lng", "")))
        result = result.replace("$address", str(context.get("address", "")))
        
        # $ref.key.field → context[key][field] 치환
        def replace_ref(match):
            path = match.group(1)  # "facility.slta_xcrd"
            parts = path.split(".")
            val = context
            for part in parts:
                if isinstance(val, dict):
                    val = val.get(part, "")
                else:
                    return ""
            return str(val) if val else ""
        
        result = re.sub(r'\$ref\.([a-zA-Z_][a-zA-Z0-9_.]*)', replace_ref, result)
        
        # 숫자 문자열 → 숫자 변환 시도
        if result.replace(".", "").replace("-", "").isdigit():
            try:
                return float(result) if "." in result else int(result)
            except ValueError:
                pass
        
        return result
    
    elif isinstance(value, dict):
        return {k: _substitute_vars(v, context) for k, v in value.items()}
    
    elif isinstance(value, list):
        return [_substitute_vars(item, context) for item in value]
    
    return value


# =============================================================================
# API 호출 매핑
# =============================================================================

# API 이름 → google_utils 함수 매핑
API_FUNCTION_MAP = {
    "geocoding": google_utils.geocode_address,
    "reverse_geocoding": google_utils.reverse_geocode,
    "nearby_search": google_utils.search_nearby_places,
    "place_details": google_utils.get_place_details,
    "directions": google_utils.get_directions,
    "distance_matrix": google_utils.get_distance_matrix,
    "street_view": google_utils.get_street_view_url,
    "static_map": google_utils.get_static_map_url,
    "air_quality": google_utils.get_air_quality,
    # maps_javascript는 프론트엔드에서 처리 (블록 데이터만 반환)
}


def _call_api(api_name: str, params: Dict) -> Dict[str, Any]:
    """
    API 이름과 파라미터로 google_utils 함수 호출
    
    Returns:
        API 응답 또는 에러 정보
    """
    func = API_FUNCTION_MAP.get(api_name)
    
    if api_name == "maps_javascript":
        # 지도 블록은 프론트엔드에서 렌더링하므로 데이터만 반환
        return {
            "success": True,
            "type": "map",
            "center": {"lat": params.get("center_lat"), "lng": params.get("center_lng")},
            "zoom": params.get("zoom", 15),
            "markers": params.get("markers", [])
        }
    
    if not func:
        logger.warning(f"[API_BUNDLE_LOADER] 알 수 없는 API: {api_name}")
        return {"success": False, "error": f"Unknown API: {api_name}"}
    
    try:
        # 파라미터 매핑 (API별 파라미터 이름 조정)
        if api_name == "nearby_search":
            result = func(
                lat=params.get("lat"),
                lng=params.get("lng"),
                radius=params.get("radius", 1000),
                types=params.get("types", []),
                max_results=params.get("max_results", 10)
            )
        elif api_name == "air_quality":
            result = func(
                lat=params.get("lat"),
                lng=params.get("lng")
            )
        elif api_name == "street_view":
            url = func(
                lat=params.get("lat"),
                lng=params.get("lng"),
                size=params.get("size", "600x400"),
                heading=params.get("heading", 0)
            )
            result = {"success": True, "url": url}
        elif api_name == "directions":
            result = func(
                origin=params.get("origin"),
                destination=params.get("destination"),
                mode=params.get("mode", "transit")
            )
        elif api_name == "distance_matrix":
            # destinations가 문자열이면 배열로 변환
            destinations = params.get("destinations", [])
            if isinstance(destinations, str):
                destinations = [destinations]
            result = func(
                origins=params.get("origins", []),
                destinations=destinations,
                mode=params.get("mode", "transit")
            )
        elif api_name == "place_details":
            result = func(
                place_id=params.get("place_id")
            )
        else:
            # 일반적인 호출
            result = func(**params)
        
        logger.info(f"[API_BUNDLE_LOADER] API 호출 성공: {api_name}")
        return result
    
    except Exception as e:
        logger.error(f"[API_BUNDLE_LOADER] API 호출 실패 ({api_name}): {e}")
        return {"success": False, "error": str(e)}


# =============================================================================
# 번들 실행
# =============================================================================

def execute_api_bundle(
    bundle_name: str,
    context: Dict[str, Any]
) -> Tuple[Dict[str, Any], Dict]:
    """
    단일 API 번들 실행
    
    Args:
        bundle_name: 번들 이름
        context: 변수 컨텍스트 (org, lat, lng, address, 이전 결과 등)
    
    Returns:
        (api_result, block_config)
        - api_result: API 응답 데이터
        - block_config: 블록 설정 (type, title 등)
    """
    config = _load_config()
    
    # API 번들에서 찾기
    bundle = config.get("api_bundles", {}).get(bundle_name)
    if not bundle:
        # 혼합 번들에서 찾기
        bundle = config.get("mixed_bundles", {}).get(bundle_name)
    
    if not bundle:
        logger.warning(f"[API_BUNDLE_LOADER] 번들 없음: {bundle_name}")
        return {"success": False, "error": f"Bundle not found: {bundle_name}"}, {}
    
    bundle_type = bundle.get("type", "api_only")
    
    if bundle_type == "api_only":
        # API 전용 번들
        api_name = bundle.get("api", "")
        params = _substitute_vars(bundle.get("params", {}), context)
        
        result = _call_api(api_name, params)
        block_config = bundle.get("block", {})
        
        return result, block_config
    
    elif bundle_type == "mixed":
        # 혼합 번들은 별도 처리 필요
        logger.info(f"[API_BUNDLE_LOADER] 혼합 번들 실행: {bundle_name}")
        return _execute_mixed_bundle(bundle, context)
    
    return {"success": False, "error": "Unknown bundle type"}, {}


def _execute_mixed_bundle(
    bundle: Dict,
    context: Dict[str, Any]
) -> Tuple[Dict[str, Any], Dict]:
    """
    혼합 번들 실행 (DB + API)
    
    Note: DB 쿼리는 search_agent에서 별도로 처리해야 함.
          여기서는 API 부분만 실행하고, DB 결과는 context에서 가져옴.
    """
    results = {
        "success": True,
        "api_results": [],
        "db_bundle": bundle.get("db_bundle"),
        "merge_strategy": bundle.get("merge_strategy", "union")
    }
    
    # 단일 API 번들
    api_bundle_name = bundle.get("api_bundle")
    if api_bundle_name:
        api_result, _ = execute_api_bundle(api_bundle_name, context)
        results["api_results"].append({
            "bundle": api_bundle_name,
            "data": api_result
        })
    
    # 복수 API 번들
    api_bundle_names = bundle.get("api_bundles", [])
    for name in api_bundle_names:
        api_result, _ = execute_api_bundle(name, context)
        results["api_results"].append({
            "bundle": name,
            "data": api_result
        })
    
    block_config = bundle.get("block", {})
    
    return results, block_config


def execute_bundles(
    bundle_names: List[str],
    context: Dict[str, Any]
) -> Dict[str, Tuple[Dict, Dict]]:
    """
    여러 번들 실행
    
    Args:
        bundle_names: 실행할 번들 이름 목록
        context: 변수 컨텍스트
    
    Returns:
        {bundle_name: (api_result, block_config), ...}
    """
    results = {}
    
    for name in bundle_names:
        api_result, block_config = execute_api_bundle(name, context)
        results[name] = (api_result, block_config)
    
    return results


# =============================================================================
# 고수준 함수
# =============================================================================

def get_all_for_org(
    org_name: str,
    lat: Optional[float] = None,
    lng: Optional[float] = None,
    address: Optional[str] = None,
    extra_context: Optional[Dict] = None
) -> Dict[str, Tuple[Dict, Dict]]:
    """
    기관명으로 preset을 찾고, 모든 API 번들 실행
    
    편의 함수: get_preset_for_org + get_bundles_for_preset + execute_bundles
    
    Args:
        org_name: 기관명
        lat, lng: 시설 좌표 (없으면 Geocoding으로 조회)
        address: 시설 주소
        extra_context: 추가 컨텍스트 (이전 쿼리 결과 등)
    
    Returns:
        {bundle_name: (api_result, block_config), ...}
    """
    # 좌표가 없으면 Geocoding
    if lat is None or lng is None:
        if address:
            geo_result = google_utils.geocode_address(address)
            if geo_result.get("success"):
                lat = geo_result["lat"]
                lng = geo_result["lng"]
                address = geo_result.get("formatted_address", address)
        elif org_name:
            geo_result = google_utils.geocode_address(org_name)
            if geo_result.get("success"):
                lat = geo_result["lat"]
                lng = geo_result["lng"]
                address = geo_result.get("formatted_address", "")
    
    # 컨텍스트 구성
    context = {
        "org": org_name,
        "lat": lat,
        "lng": lng,
        "address": address or "",
        **(extra_context or {})
    }
    
    # preset 조회 및 번들 실행
    preset = get_preset_for_org(org_name)
    bundle_names = get_bundles_for_preset(preset)
    
    logger.info(f"[API_BUNDLE_LOADER] '{org_name}' → preset '{preset}', 번들: {bundle_names}")
    
    return execute_bundles(bundle_names, context)


def get_bundle_info(bundle_name: str) -> Optional[Dict]:
    """번들 상세 정보 조회"""
    config = _load_config()
    
    # API 번들에서 찾기
    bundle = config.get("api_bundles", {}).get(bundle_name)
    if bundle:
        return {**bundle, "category": "api_only"}
    
    # 혼합 번들에서 찾기
    bundle = config.get("mixed_bundles", {}).get(bundle_name)
    if bundle:
        return {**bundle, "category": "mixed"}
    
    return None

