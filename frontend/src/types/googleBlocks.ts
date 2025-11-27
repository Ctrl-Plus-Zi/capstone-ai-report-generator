/**
 * Google API 관련 블록 타입 정의
 * 
 * 백엔드 google_utils.py, block_tools.py와 매칭되는 타입입니다.
 */

// 지도 마커
export interface MapMarker {
  lat: number;
  lng: number;
  label: string;
  type?: 'facility' | 'restaurant' | 'attraction' | 'transit';
}

// 지도 블록
export interface MapBlock {
  type: 'map';
  title: string;
  center: {
    lat: number;
    lng: number;
  };
  zoom: number;
  markers: MapMarker[];
  description?: string;
}

// 대기질 블록
export interface AirQualityBlock {
  type: 'air_quality';
  title: string;
  aqi: number;
  category: string;
  category_color: string;
  pollutants: {
    pm25?: number;
    pm10?: number;
  };
  recommendation?: string;
  description?: string;
}

// Google 블록 타입 유니온
export type GoogleBlockType = MapBlock | AirQualityBlock;

