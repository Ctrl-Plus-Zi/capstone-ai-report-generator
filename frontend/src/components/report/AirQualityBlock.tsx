import React from 'react';
import type { AirQualityBlock as AirQualityBlockType } from '../../types/report';
import './report.css';

interface Props {
  block: AirQualityBlockType;
}

/**
 * 대기질 정보 블록 컴포넌트
 * 
 * AQI 지수와 PM2.5/PM10 농도를 카드 형태로 표시
 */
export const AirQualityBlock: React.FC<Props> = ({ block }) => {
  const { title, aqi, category, category_color, pollutants, recommendation, description } = block;
  
  // AQI 레벨에 따른 배경 그라데이션
  const getAqiBackground = (aqiValue: number): string => {
    if (aqiValue <= 50) return 'linear-gradient(135deg, #a8e063 0%, #56ab2f 100%)';
    if (aqiValue <= 100) return 'linear-gradient(135deg, #f5af19 0%, #f12711 100%)';
    if (aqiValue <= 150) return 'linear-gradient(135deg, #ff7e5f 0%, #feb47b 100%)';
    return 'linear-gradient(135deg, #8e2de2 0%, #4a00e0 100%)';
  };

  // AQI 레벨에 따른 아이콘
  const getAqiIcon = (categoryText: string): string => {
    switch (categoryText) {
      case '좋음': return '😊';
      case '보통': return '😐';
      case '민감군나쁨': return '😷';
      case '나쁨': return '😣';
      case '매우나쁨': return '🚨';
      default: return '🌫️';
    }
  };

  return (
    <div className="air-quality-block">
      <h3 className="air-quality-title">{title}</h3>
      
      <div className="air-quality-card">
        {/* AQI 메인 디스플레이 */}
        <div 
          className="aqi-main"
          style={{ background: getAqiBackground(aqi) }}
        >
          <div className="aqi-icon">{getAqiIcon(category)}</div>
          <div className="aqi-value">{aqi}</div>
          <div 
            className="aqi-category"
            style={{ color: category_color }}
          >
            {category}
          </div>
        </div>
        
        {/* 오염물질 정보 */}
        <div className="pollutants-grid">
          {pollutants.pm25 !== undefined && pollutants.pm25 !== null && (
            <div className="pollutant-item">
              <span className="pollutant-label">PM2.5</span>
              <span className="pollutant-value">{pollutants.pm25.toFixed(1)}</span>
              <span className="pollutant-unit">µg/m³</span>
            </div>
          )}
          {pollutants.pm10 !== undefined && pollutants.pm10 !== null && (
            <div className="pollutant-item">
              <span className="pollutant-label">PM10</span>
              <span className="pollutant-value">{pollutants.pm10.toFixed(1)}</span>
              <span className="pollutant-unit">µg/m³</span>
            </div>
          )}
        </div>
        
        {/* 건강 권고 */}
        {recommendation && (
          <div className="air-quality-recommendation">
            <span className="recommendation-icon">💡</span>
            <span>{recommendation}</span>
          </div>
        )}
      </div>
      
      {description && (
        <p className="air-quality-description">{description}</p>
      )}
    </div>
  );
};

