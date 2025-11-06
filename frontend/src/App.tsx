import React, { useState } from 'react';

const API_BASE = 'http://localhost:8000';

interface AdvancedReportResponse {
  id: number;
  organization_name: string;
  report_topic: string;
  final_report: string;
  research_sources: string[];
  analysis_summary: string;
  generated_at: string;
}

function App() {
  const [organizationName, setOrganizationName] = useState('');
  const [userCommand, setUserCommand] = useState('');
  const [response, setResponse] = useState<AdvancedReportResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    setResponse(null);

    try {
      const res = await fetch(`${API_BASE}/report/advanced`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          organization_name: organizationName,
          user_command: userCommand
        })
      });

      if (res.ok) {
        const result = await res.json();
        setResponse(result);
      } else {
        const errorData = await res.json();
        setError(errorData.detail || '보고서 생성 실패');
      }
    } catch (err) {
      setError('서버 연결 오류');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ 
      minHeight: '100vh', 
      backgroundColor: '#f5f5f5', 
      padding: '20px',
      fontFamily: 'Arial, sans-serif'
    }}>
      <div style={{ maxWidth: '800px', margin: '0 auto' }}>
        
        {/* 제목 */}
        <h1 style={{ 
          textAlign: 'center', 
          marginBottom: '30px',
          color: '#333'
        }}>
          AI 기관 분석 보고서
        </h1>

        {/* 입력 폼 */}
        <div style={{
          backgroundColor: 'white',
          padding: '30px',
          borderRadius: '8px',
          boxShadow: '0 2px 4px rgba(0,0,0,0.1)',
          marginBottom: '20px'
        }}>
          <form onSubmit={handleSubmit}>
            <div style={{ marginBottom: '20px' }}>
              <label style={{ 
                display: 'block', 
                marginBottom: '8px',
                fontWeight: 'bold',
                color: '#333'
              }}>
                기관명
              </label>
              <input
                type="text"
                value={organizationName}
                onChange={(e) => setOrganizationName(e.target.value)}
                placeholder="예: 국립중앙박물관, 윤동주문학관, 서울시립미술관"
                required
                style={{
                  width: '100%',
                  padding: '12px',
                  border: '1px solid #ddd',
                  borderRadius: '4px',
                  fontSize: '16px',
                  boxSizing: 'border-box'
                }}
              />
            </div>

            <div style={{ marginBottom: '20px' }}>
              <label style={{ 
                display: 'block', 
                marginBottom: '8px',
                fontWeight: 'bold',
                color: '#333'
              }}>
                사용자 명령
              </label>
              <textarea
                value={userCommand}
                onChange={(e) => setUserCommand(e.target.value)}
                placeholder="예: 2030 세대의 관람객 유입을 위한 이벤트 기획에 대해 분석하고, 최근 전시 정보와 대표 소장품을 조사해서 보고서를 작성해줘"
                required
                style={{
                  width: '100%',
                  padding: '12px',
                  border: '1px solid #ddd',
                  borderRadius: '4px',
                  fontSize: '16px',
                  height: '120px',
                  resize: 'vertical',
                  boxSizing: 'border-box'
                }}
              />
            </div>

            <button
              type="submit"
              disabled={loading}
              style={{
                width: '100%',
                padding: '15px',
                backgroundColor: loading ? '#ccc' : '#007bff',
                color: 'white',
                border: 'none',
                borderRadius: '4px',
                fontSize: '16px',
                fontWeight: 'bold',
                cursor: loading ? 'not-allowed' : 'pointer'
              }}
            >
              {loading ? '🔄 분석 중...' : '📊 보고서 생성'}
            </button>
          </form>
        </div>

        {/* 오류 메시지 */}
        {error && (
          <div style={{
            backgroundColor: '#ffebee',
            color: '#c62828',
            padding: '15px',
            borderRadius: '4px',
            marginBottom: '20px',
            border: '1px solid #ef5350'
          }}>
            {error}
          </div>
        )}

        {/* 결과 출력 */}
        {response && (
          <div style={{
            backgroundColor: 'white',
            padding: '30px',
            borderRadius: '8px',
            boxShadow: '0 2px 4px rgba(0,0,0,0.1)'
          }}>
            <h2 style={{ 
              marginTop: 0, 
              marginBottom: '20px',
              color: '#333',
              borderBottom: '2px solid #007bff',
              paddingBottom: '10px'
            }}>
              {response.organization_name} 분석 보고서
            </h2>
            
            <div style={{
              marginBottom: '20px',
              padding: '15px',
              backgroundColor: '#f8f9fa',
              borderRadius: '4px',
              fontSize: '14px',
              color: '#666'
            }}>
              <div style={{ marginBottom: '10px' }}>
                <strong>주제:</strong> {response.report_topic}
              </div>
              <div>
                <strong>보고서 ID:</strong> {response.id}
              </div>
            </div>

            {response.research_sources.length > 0 && (
              <div style={{
                marginBottom: '20px',
                padding: '15px',
                backgroundColor: '#e3f2fd',
                borderRadius: '4px'
              }}>
                <strong style={{ display: 'block', marginBottom: '10px', color: '#1976d2' }}>
                  참고 출처
                </strong>
                <ul style={{ margin: 0, paddingLeft: '20px' }}>
                  {response.research_sources.slice(0, 5).map((source, idx) => (
                    <li key={idx} style={{ marginBottom: '5px' }}>
                      <a href={source} target="_blank" rel="noopener noreferrer" style={{ color: '#1976d2', textDecoration: 'none' }}>
                        {source}
                      </a>
                    </li>
                  ))}
                </ul>
                {response.research_sources.length > 5 && (
                  <div style={{ marginTop: '10px', fontSize: '12px', color: '#666' }}>
                    외 {response.research_sources.length - 5}개
                  </div>
                )}
              </div>
            )}

            {response.analysis_summary && (
              <div style={{
                marginBottom: '20px',
                padding: '15px',
                backgroundColor: '#fff3e0',
                borderRadius: '4px'
              }}>
                <strong style={{ display: 'block', marginBottom: '10px', color: '#f57c00' }}>
                  분석 요약
                </strong>
                <div style={{ lineHeight: '1.6', whiteSpace: 'pre-wrap' }}>
                  {response.analysis_summary}
                </div>
              </div>
            )}

            <div style={{
              marginBottom: '20px',
              padding: '20px',
              backgroundColor: '#fafafa',
              borderRadius: '4px',
              borderLeft: '4px solid #007bff'
            }}>
              <strong style={{ display: 'block', marginBottom: '15px', fontSize: '18px', color: '#333' }}>
                최종 보고서
              </strong>
              <div 
                style={{
                  lineHeight: '1.8',
                  fontSize: '16px',
                  color: '#333',
                  whiteSpace: 'pre-wrap'
                }}
                dangerouslySetInnerHTML={{ __html: response.final_report.replace(/\n/g, '<br/>') }}
              />
            </div>

            <div style={{
              padding: '10px',
              backgroundColor: '#e8f5e9',
              borderRadius: '4px',
              fontSize: '12px',
              color: '#2e7d32'
            }}>
              생성일시: {new Date(response.generated_at).toLocaleString('ko-KR')}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default App;
