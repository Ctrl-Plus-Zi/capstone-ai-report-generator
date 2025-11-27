import React, { useState } from 'react';
import type { MapBlock as MapBlockType } from '../../types/report';
import './report.css';

interface Props {
  block: MapBlockType;
}

/**
 * 지도 블록 컴포넌트
 * 
 * Google Static Maps API를 사용하여 실제 지도 이미지를 표시합니다.
 * API 키가 없거나 로드 실패 시 플레이스홀더를 표시합니다.
 */
export const MapBlock: React.FC<Props> = ({ block }) => {
  const { title, center, zoom, markers, description } = block;
  const [imageError, setImageError] = useState(false);
  
  // 환경 변수에서 API 키 가져오기 (Vite 방식)
  const apiKey = import.meta.env.VITE_GOOGLE_MAPS_API_KEY || '';
  
  // Static Map URL 생성
  const generateStaticMapUrl = (): string => {
    if (!apiKey) return '';
    
    const params = new URLSearchParams({
      center: `${center.lat},${center.lng}`,
      zoom: String(zoom || 15),
      size: '600x400',
      maptype: 'roadmap',
      key: apiKey,
    });
    
    // 중심 마커 추가
    params.append('markers', `color:red|${center.lat},${center.lng}`);
    
    // 추가 마커들
    if (markers && markers.length > 0) {
      markers.forEach((marker) => {
        const color = marker.type === 'restaurant' ? 'blue' : 
                      marker.type === 'attraction' ? 'green' : 
                      marker.type === 'transit' ? 'yellow' : 'red';
        params.append('markers', `color:${color}|label:${marker.label?.charAt(0) || ''}|${marker.lat},${marker.lng}`);
      });
    }
    
    return `https://maps.googleapis.com/maps/api/staticmap?${params.toString()}`;
  };
  
  // Google Maps 링크 (클릭 시 새 탭에서 열기)
  const googleMapsLink = `https://www.google.com/maps/search/?api=1&query=${center.lat},${center.lng}`;
  
  // 마커 타입별 이모지
  const markerIcon: Record<string, string> = {
    facility: '📍',
    restaurant: '🍽️',
    attraction: '🏛️',
    transit: '🚇',
  };

  const staticMapUrl = generateStaticMapUrl();

  return (
    <div className="map-block">
      <h3 className="map-title">{title}</h3>
      
      {/* 지도 영역 */}
      <div className="map-container">
        {staticMapUrl && !imageError ? (
          <a href={googleMapsLink} target="_blank" rel="noopener noreferrer" className="map-link">
            <img 
              src={staticMapUrl} 
              alt={`${title} 지도`}
              className="map-image"
              onError={() => setImageError(true)}
            />
            <div className="map-overlay">
              <span>🔗 Google Maps에서 보기</span>
            </div>
          </a>
        ) : (
          // API 키 없거나 로드 실패 시 플레이스홀더
          <a href={googleMapsLink} target="_blank" rel="noopener noreferrer" className="map-placeholder-link">
            <div className="map-placeholder">
              <div className="map-icon">🗺️</div>
              <div className="map-coords">
                위도: {center.lat.toFixed(4)}, 경도: {center.lng.toFixed(4)}
              </div>
              <div className="map-zoom">줌 레벨: {zoom}</div>
              <div className="map-link-hint">클릭하여 Google Maps에서 보기</div>
            </div>
          </a>
        )}
      </div>
      
      {/* 마커 목록 */}
      {markers && markers.length > 0 && (
        <div className="map-markers">
          <h4>주요 위치</h4>
          <ul>
            {markers.map((marker, idx) => (
              <li key={idx}>
                <span className="marker-icon">
                  {markerIcon[marker.type || 'facility']}
                </span>
                <span className="marker-label">{marker.label}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
      
      {description && (
        <p className="map-description">{description}</p>
      )}
    </div>
  );
};

