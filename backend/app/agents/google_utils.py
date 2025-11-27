"""Google Cloud Platform API 유틸리티 모듈

Google Maps Platform API들을 호출하는 함수들을 제공합니다.
- Maps: Geocoding, Directions, Distance Matrix, Street View, Static Map
- Places: Nearby Search, Place Details, Place Photos
- Environment: Air Quality

설정:
    config.py의 Settings 클래스에서 환경변수 로드
    - GOOGLE_MAPS_API_KEY: Maps, Places, Geocoding, Air Quality 등
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

from app.config import settings

logger = logging.getLogger("uvicorn.error")

# =============================================================================
# 설정 로드
# =============================================================================

def load_google_config() -> Dict:
    """google_config.json 파일을 로드합니다."""
    config_path = Path(__file__).parent / "google_config.json"
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


def _get_api_key() -> str:
    """API 키를 반환합니다. 없으면 에러 로깅."""
    api_key = settings.google_maps_api_key or ""
    if not api_key:
        logger.warning("[GOOGLE_UTILS] GOOGLE_MAPS_API_KEY가 설정되지 않았습니다. config.py 확인 필요.")
    return api_key


# =============================================================================
# Geocoding API
# =============================================================================

def geocode_address(address: str) -> Dict[str, Any]:
    """
    주소를 좌표(위도/경도)로 변환합니다.
    
    Args:
        address: 변환할 주소 (예: "서울시 서초구 서초동 1650-3")
    
    Returns:
        {
            "success": True/False,
            "lat": 위도,
            "lng": 경도,
            "formatted_address": 정제된 주소,
            "place_id": Google Place ID
        }
    """
    url = "https://maps.googleapis.com/maps/api/geocode/json"
    params = {
        "address": address,
        "key": _get_api_key(),
        "language": "ko"
    }
    
    try:
        resp = requests.get(url, params=params, timeout=(5, 15))
        resp.raise_for_status()
        data = resp.json()
        
        if data.get("status") == "OK" and data.get("results"):
            result = data["results"][0]
            location = result["geometry"]["location"]
            
            logger.info(f"[GOOGLE_UTILS] Geocoding 성공: {address} → ({location['lat']}, {location['lng']})")
            return {
                "success": True,
                "lat": location["lat"],
                "lng": location["lng"],
                "formatted_address": result["formatted_address"],
                "place_id": result.get("place_id")
            }
        
        logger.warning(f"[GOOGLE_UTILS] Geocoding 실패: {data.get('status')}")
        return {"success": False, "error": data.get("status", "UNKNOWN_ERROR")}
    
    except requests.exceptions.RequestException as e:
        logger.error(f"[GOOGLE_UTILS] Geocoding 요청 실패: {e}")
        return {"success": False, "error": str(e)}


def reverse_geocode(lat: float, lng: float) -> Dict[str, Any]:
    """
    좌표를 주소로 변환합니다.
    
    Args:
        lat: 위도
        lng: 경도
    
    Returns:
        {"success": True, "formatted_address": "주소", "place_id": "..."}
    """
    url = "https://maps.googleapis.com/maps/api/geocode/json"
    params = {
        "latlng": f"{lat},{lng}",
        "key": _get_api_key(),
        "language": "ko"
    }
    
    try:
        resp = requests.get(url, params=params, timeout=(5, 15))
        resp.raise_for_status()
        data = resp.json()
        
        if data.get("status") == "OK" and data.get("results"):
            result = data["results"][0]
            return {
                "success": True,
                "formatted_address": result["formatted_address"],
                "place_id": result.get("place_id")
            }
        
        return {"success": False, "error": data.get("status", "UNKNOWN_ERROR")}
    
    except requests.exceptions.RequestException as e:
        return {"success": False, "error": str(e)}


# =============================================================================
# Places API (New)
# =============================================================================

def search_nearby_places(
    lat: float,
    lng: float,
    radius: int = 1000,
    types: Optional[List[str]] = None,
    max_results: int = 10
) -> Dict[str, Any]:
    """
    주변 장소를 검색합니다 (Places API New).
    
    Args:
        lat: 중심 위도
        lng: 중심 경도
        radius: 검색 반경 (미터)
        types: 장소 유형 배열 (예: ["restaurant", "cafe"])
        max_results: 최대 결과 수
    
    Returns:
        {
            "success": True,
            "count": 결과 수,
            "places": [{
                "name": 이름,
                "rating": 평점,
                "review_count": 리뷰 수,
                "address": 주소,
                "lat": 위도,
                "lng": 경도,
                "types": 유형 배열,
                "photo_name": 사진 리소스명
            }]
        }
    """
    url = "https://places.googleapis.com/v1/places:searchNearby"
    
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": _get_api_key(),
        "X-Goog-FieldMask": "places.displayName,places.rating,places.userRatingCount,places.formattedAddress,places.location,places.types,places.photos"
    }
    
    body = {
        "locationRestriction": {
            "circle": {
                "center": {"latitude": lat, "longitude": lng},
                "radius": radius
            }
        },
        "maxResultCount": max_results,
        "languageCode": "ko"
    }
    
    if types:
        body["includedTypes"] = types
    
    try:
        resp = requests.post(url, json=body, headers=headers, timeout=(5, 15))
        resp.raise_for_status()
        data = resp.json()
        
        places = []
        for p in data.get("places", []):
            place = {
                "name": p.get("displayName", {}).get("text", ""),
                "rating": p.get("rating"),
                "review_count": p.get("userRatingCount"),
                "address": p.get("formattedAddress", ""),
                "lat": p.get("location", {}).get("latitude"),
                "lng": p.get("location", {}).get("longitude"),
                "types": p.get("types", []),
            }
            
            # 첫 번째 사진 정보
            photos = p.get("photos", [])
            if photos:
                place["photo_name"] = photos[0].get("name")
            
            places.append(place)
        
        logger.info(f"[GOOGLE_UTILS] Nearby Search: {len(places)}개 장소 발견")
        return {
            "success": True,
            "count": len(places),
            "places": places
        }
    
    except requests.exceptions.RequestException as e:
        logger.error(f"[GOOGLE_UTILS] Nearby Search 실패: {e}")
        return {"success": False, "error": str(e), "places": []}


def get_place_details(place_id: str) -> Dict[str, Any]:
    """
    장소 상세 정보를 조회합니다.
    
    Args:
        place_id: Google Place ID
    
    Returns:
        {
            "success": True,
            "name": 이름,
            "rating": 평점,
            "review_count": 리뷰 수,
            "address": 주소,
            "phone": 전화번호,
            "website": 웹사이트,
            "opening_hours": 영업시간 배열,
            "reviews": [{rating, text}]
        }
    """
    url = f"https://places.googleapis.com/v1/places/{place_id}"
    
    headers = {
        "X-Goog-Api-Key": _get_api_key(),
        "X-Goog-FieldMask": "displayName,rating,userRatingCount,reviews,regularOpeningHours,websiteUri,nationalPhoneNumber,formattedAddress"
    }
    
    try:
        resp = requests.get(url, headers=headers, timeout=(5, 15))
        resp.raise_for_status()
        data = resp.json()
        
        reviews = []
        for r in data.get("reviews", [])[:5]:  # 상위 5개 리뷰
            reviews.append({
                "rating": r.get("rating"),
                "text": r.get("text", {}).get("text", "")[:300],  # 300자 제한
                "author": r.get("authorAttribution", {}).get("displayName", "")
            })
        
        return {
            "success": True,
            "name": data.get("displayName", {}).get("text", ""),
            "rating": data.get("rating"),
            "review_count": data.get("userRatingCount"),
            "address": data.get("formattedAddress", ""),
            "phone": data.get("nationalPhoneNumber", ""),
            "website": data.get("websiteUri", ""),
            "opening_hours": data.get("regularOpeningHours", {}).get("weekdayDescriptions", []),
            "reviews": reviews
        }
    
    except requests.exceptions.RequestException as e:
        logger.error(f"[GOOGLE_UTILS] Place Details 실패: {e}")
        return {"success": False, "error": str(e)}


def get_place_photo_url(photo_name: str, max_width: int = 400) -> str:
    """
    Place Photo URL을 생성합니다.
    
    Args:
        photo_name: 사진 리소스명 (places/xxx/photos/xxx)
        max_width: 최대 너비 (픽셀)
    
    Returns:
        이미지 URL
    """
    return f"https://places.googleapis.com/v1/{photo_name}/media?maxWidthPx={max_width}&key={_get_api_key()}"


# =============================================================================
# Directions API
# =============================================================================

def get_directions(
    origin: str,
    destination: str,
    mode: str = "transit"
) -> Dict[str, Any]:
    """
    경로 안내를 조회합니다.
    
    Args:
        origin: 출발지 (주소 또는 좌표)
        destination: 도착지 (주소 또는 좌표)
        mode: 이동 수단 (transit, driving, walking, bicycling)
    
    Returns:
        {
            "success": True,
            "distance": "거리 텍스트",
            "duration": "소요시간 텍스트",
            "start_address": 출발 주소,
            "end_address": 도착 주소,
            "steps": [{instruction, distance, duration, travel_mode}]
        }
    """
    url = "https://maps.googleapis.com/maps/api/directions/json"
    params = {
        "origin": origin,
        "destination": destination,
        "mode": mode,
        "language": "ko",
        "key": _get_api_key()
    }
    
    try:
        resp = requests.get(url, params=params, timeout=(5, 15))
        resp.raise_for_status()
        data = resp.json()
        
        if data.get("status") == "OK" and data.get("routes"):
            route = data["routes"][0]
            leg = route["legs"][0]
            
            steps = []
            for s in leg.get("steps", [])[:15]:  # 최대 15단계
                # HTML 태그 제거
                instruction = s.get("html_instructions", "")
                instruction = instruction.replace("<b>", "").replace("</b>", "")
                instruction = instruction.replace("<div>", " ").replace("</div>", "")
                
                steps.append({
                    "instruction": instruction,
                    "distance": s.get("distance", {}).get("text", ""),
                    "duration": s.get("duration", {}).get("text", ""),
                    "travel_mode": s.get("travel_mode", "")
                })
            
            logger.info(f"[GOOGLE_UTILS] Directions: {leg['distance']['text']}, {leg['duration']['text']}")
            return {
                "success": True,
                "distance": leg["distance"]["text"],
                "duration": leg["duration"]["text"],
                "distance_meters": leg["distance"]["value"],
                "duration_seconds": leg["duration"]["value"],
                "start_address": leg["start_address"],
                "end_address": leg["end_address"],
                "steps": steps
            }
        
        return {"success": False, "error": data.get("status", "NO_ROUTE")}
    
    except requests.exceptions.RequestException as e:
        logger.error(f"[GOOGLE_UTILS] Directions 실패: {e}")
        return {"success": False, "error": str(e)}


def get_distance_matrix(
    origins: List[str],
    destinations: List[str],
    mode: str = "transit"
) -> Dict[str, Any]:
    """
    다중 출발지-도착지 거리/시간을 계산합니다.
    
    Args:
        origins: 출발지 배열
        destinations: 도착지 배열
        mode: 이동 수단
    
    Returns:
        {
            "success": True,
            "results": [{
                "origin": 출발 주소,
                "destination": 도착 주소,
                "distance": 거리 텍스트,
                "duration": 소요시간 텍스트
            }]
        }
    """
    url = "https://maps.googleapis.com/maps/api/distancematrix/json"
    params = {
        "origins": "|".join(origins),
        "destinations": "|".join(destinations),
        "mode": mode,
        "language": "ko",
        "key": _get_api_key()
    }
    
    try:
        resp = requests.get(url, params=params, timeout=(5, 20))
        resp.raise_for_status()
        data = resp.json()
        
        if data.get("status") == "OK":
            results = []
            origin_addrs = data.get("origin_addresses", [])
            dest_addrs = data.get("destination_addresses", [])
            
            for i, row in enumerate(data.get("rows", [])):
                for j, elem in enumerate(row.get("elements", [])):
                    if elem.get("status") == "OK":
                        results.append({
                            "origin": origin_addrs[i] if i < len(origin_addrs) else origins[i],
                            "destination": dest_addrs[j] if j < len(dest_addrs) else destinations[j],
                            "distance": elem["distance"]["text"],
                            "duration": elem["duration"]["text"],
                            "distance_meters": elem["distance"]["value"],
                            "duration_seconds": elem["duration"]["value"]
                        })
            
            logger.info(f"[GOOGLE_UTILS] Distance Matrix: {len(results)}개 결과")
            return {"success": True, "results": results}
        
        return {"success": False, "error": data.get("status")}
    
    except requests.exceptions.RequestException as e:
        logger.error(f"[GOOGLE_UTILS] Distance Matrix 실패: {e}")
        return {"success": False, "error": str(e), "results": []}


# =============================================================================
# Street View & Static Map
# =============================================================================

def get_street_view_url(
    lat: float,
    lng: float,
    size: str = "600x400",
    heading: int = 0,
    pitch: int = 0,
    fov: int = 90
) -> str:
    """
    Street View 이미지 URL을 생성합니다.
    
    Args:
        lat: 위도
        lng: 경도
        size: 이미지 크기 (예: "600x400")
        heading: 방향 (0-360)
        pitch: 상하 각도 (-90~90)
        fov: 시야각 (10-120)
    
    Returns:
        이미지 URL
    """
    base_url = "https://maps.googleapis.com/maps/api/streetview"
    return f"{base_url}?size={size}&location={lat},{lng}&heading={heading}&pitch={pitch}&fov={fov}&key={_get_api_key()}"


def get_static_map_url(
    lat: float,
    lng: float,
    zoom: int = 15,
    size: str = "600x400",
    markers: Optional[List[Dict]] = None,
    maptype: str = "roadmap"
) -> str:
    """
    정적 지도 이미지 URL을 생성합니다.
    
    Args:
        lat: 중심 위도
        lng: 중심 경도
        zoom: 줌 레벨 (1-21)
        size: 이미지 크기
        markers: 마커 배열 [{lat, lng, label, color}]
        maptype: 지도 유형 (roadmap, satellite, terrain, hybrid)
    
    Returns:
        이미지 URL
    """
    base_url = "https://maps.googleapis.com/maps/api/staticmap"
    url = f"{base_url}?center={lat},{lng}&zoom={zoom}&size={size}&maptype={maptype}&key={_get_api_key()}"
    
    if markers:
        for m in markers:
            color = m.get("color", "red")
            label = m.get("label", "")
            marker_str = f"&markers=color:{color}|label:{label}|{m['lat']},{m['lng']}"
            url += marker_str
    
    return url


# =============================================================================
# Air Quality API
# =============================================================================

def get_air_quality(lat: float, lng: float) -> Dict[str, Any]:
    """
    대기질 정보를 조회합니다.
    
    Args:
        lat: 위도
        lng: 경도
    
    Returns:
        {
            "success": True,
            "aqi": 대기질 지수,
            "category": 등급 (좋음/보통/나쁨 등),
            "category_color": 등급 색상,
            "dominant_pollutant": 주요 오염물질,
            "pollutants": {
                "pm25": PM2.5 농도,
                "pm10": PM10 농도,
                "o3": 오존 농도,
                "no2": 이산화질소 농도
            },
            "health_recommendation": 건강 권고사항
        }
    """
    url = "https://airquality.googleapis.com/v1/currentConditions:lookup"
    headers = {"Content-Type": "application/json"}
    params = {"key": _get_api_key()}
    body = {
        "location": {"latitude": lat, "longitude": lng},
        "extraComputations": ["POLLUTANT_CONCENTRATION"],
        "languageCode": "ko"
    }
    
    try:
        resp = requests.post(url, json=body, params=params, headers=headers, timeout=(5, 15))
        resp.raise_for_status()
        data = resp.json()
        
        # UAQI (Universal AQI) 찾기
        indexes = data.get("indexes", [])
        uaqi = next((i for i in indexes if i.get("code") == "uaqi"), {})
        
        # AQI 카테고리 매핑
        config = load_google_config()
        aqi_categories = config.get("aqi_categories", {})
        aqi_value = uaqi.get("aqi", 0)
        
        # AQI 값에 따른 카테고리 결정
        if aqi_value <= 50:
            category_info = aqi_categories.get("1", {})
        elif aqi_value <= 100:
            category_info = aqi_categories.get("2", {})
        elif aqi_value <= 150:
            category_info = aqi_categories.get("3", {})
        elif aqi_value <= 200:
            category_info = aqi_categories.get("4", {})
        else:
            category_info = aqi_categories.get("5", {})
        
        # 오염물질 농도 추출
        pollutants = {}
        for p in data.get("pollutants", []):
            code = p.get("code", "").lower()
            pollutants[code] = {
                "concentration": p.get("concentration", {}).get("value"),
                "unit": p.get("concentration", {}).get("units", "")
            }
        
        # 건강 권고사항
        health_recs = data.get("healthRecommendations", {})
        general_rec = health_recs.get("generalPopulation", category_info.get("advice", ""))
        
        result = {
            "success": True,
            "aqi": aqi_value,
            "category": category_info.get("label", uaqi.get("category", "")),
            "category_color": category_info.get("color", ""),
            "dominant_pollutant": uaqi.get("dominantPollutant", ""),
            "pollutants": {
                "pm25": pollutants.get("pm25", {}).get("concentration"),
                "pm10": pollutants.get("pm10", {}).get("concentration"),
                "o3": pollutants.get("o3", {}).get("concentration"),
                "no2": pollutants.get("no2", {}).get("concentration"),
            },
            "health_recommendation": general_rec
        }
        
        logger.info(f"[GOOGLE_UTILS] Air Quality: AQI {result['aqi']}, {result['category']}")
        return result
    
    except requests.exceptions.RequestException as e:
        logger.error(f"[GOOGLE_UTILS] Air Quality 실패: {e}")
        return {"success": False, "error": str(e)}


# =============================================================================
# 고수준 유틸리티 함수
# =============================================================================

def get_facility_environment(
    address: Optional[str] = None,
    lat: Optional[float] = None,
    lng: Optional[float] = None
) -> Dict[str, Any]:
    """
    시설의 환경 정보를 종합 조회합니다 (날씨 + 대기질).
    
    Args:
        address: 시설 주소 (lat/lng 없을 때 사용)
        lat: 위도
        lng: 경도
    
    Returns:
        {
            "location": {lat, lng, address},
            "weather": {...},
            "air_quality": {...}
        }
    """
    # 좌표가 없으면 주소로 변환
    if lat is None or lng is None:
        if not address:
            return {"success": False, "error": "주소 또는 좌표가 필요합니다."}
        
        geo_result = geocode_address(address)
        if not geo_result.get("success"):
            return {"success": False, "error": f"Geocoding 실패: {geo_result.get('error')}"}
        
        lat = geo_result["lat"]
        lng = geo_result["lng"]
        address = geo_result["formatted_address"]
    
    # 날씨 & 대기질 조회
    weather = get_current_weather(lat, lng)
    air_quality = get_air_quality(lat, lng)
    
    return {
        "success": True,
        "location": {
            "lat": lat,
            "lng": lng,
            "address": address
        },
        "weather": weather if weather.get("success") else None,
        "air_quality": air_quality if air_quality.get("success") else None
    }


def get_nearby_info(
    lat: float,
    lng: float,
    include_restaurants: bool = True,
    include_attractions: bool = True,
    radius: int = 1000
) -> Dict[str, Any]:
    """
    주변 정보를 종합 조회합니다 (맛집 + 관광지).
    
    Args:
        lat: 위도
        lng: 경도
        include_restaurants: 맛집 포함 여부
        include_attractions: 관광지 포함 여부
        radius: 검색 반경 (미터)
    
    Returns:
        {
            "restaurants": [...],
            "attractions": [...]
        }
    """
    result = {"success": True}
    
    if include_restaurants:
        restaurants = search_nearby_places(
            lat, lng, radius=radius,
            types=["restaurant", "cafe", "bakery"],
            max_results=10
        )
        result["restaurants"] = restaurants.get("places", [])
    
    if include_attractions:
        attractions = search_nearby_places(
            lat, lng, radius=min(radius * 2, 5000),
            types=["tourist_attraction", "museum", "park", "art_gallery"],
            max_results=10
        )
        result["attractions"] = attractions.get("places", [])
    
    return result


def get_accessibility_info(
    destination_address: str,
    nearby_stations: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    접근성 정보를 조회합니다 (주변역에서 시설까지 거리/시간).
    
    Args:
        destination_address: 목적지 주소
        nearby_stations: 주변 역 이름 배열 (없으면 자동 검색)
    
    Returns:
        {
            "destination": 목적지 주소,
            "routes": [{
                "station": 역 이름,
                "distance": 거리,
                "duration": 소요시간
            }]
        }
    """
    # 목적지 좌표 확인
    geo = geocode_address(destination_address)
    if not geo.get("success"):
        return {"success": False, "error": "목적지 주소를 찾을 수 없습니다."}
    
    lat, lng = geo["lat"], geo["lng"]
    
    # 주변역이 없으면 자동 검색
    if not nearby_stations:
        stations_result = search_nearby_places(
            lat, lng,
            radius=2000,
            types=["subway_station", "train_station"],
            max_results=5
        )
        nearby_stations = [p["name"] for p in stations_result.get("places", [])]
    
    if not nearby_stations:
        return {"success": False, "error": "주변 역을 찾을 수 없습니다."}
    
    # Distance Matrix 조회
    dm_result = get_distance_matrix(
        origins=nearby_stations,
        destinations=[destination_address],
        mode="transit"
    )
    
    routes = []
    for r in dm_result.get("results", []):
        routes.append({
            "station": r["origin"],
            "distance": r["distance"],
            "duration": r["duration"],
            "distance_meters": r.get("distance_meters"),
            "duration_seconds": r.get("duration_seconds")
        })
    
    # 소요시간 기준 정렬
    routes.sort(key=lambda x: x.get("duration_seconds", float("inf")))
    
    return {
        "success": True,
        "destination": geo["formatted_address"],
        "routes": routes
    }

