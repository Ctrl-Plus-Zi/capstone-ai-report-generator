import React, { useState } from 'react';

const API_BASE = 'http://localhost:8000';

interface GenerateReportResponse {
  organization_name: string;
  question: string;
  response: string;
  generated_at: string;
}

function App() {
  const [organizationName, setOrganizationName] = useState('');
  const [question, setQuestion] = useState('이 기관에 대해 종합적으로 분석해주세요.');
  const [response, setResponse] = useState<GenerateReportResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    setResponse(null);

    try {
      const res = await fetch(`${API_BASE}/report/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          organization_name: organizationName,
          question: question
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
          📊 AI 기관 분석 보고서
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
                질문
              </label>
              <textarea
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                placeholder="이 기관에 대해 알고 싶은 내용을 입력하세요"
                required
                style={{
                  width: '100%',
                  padding: '12px',
                  border: '1px solid #ddd',
                  borderRadius: '4px',
                  fontSize: '16px',
                  height: '100px',
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
            ❌ {error}
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
              📋 {response.organization_name} 분석 보고서
            </h2>
            
            <div style={{
              marginBottom: '15px',
              padding: '10px',
              backgroundColor: '#f8f9fa',
              borderRadius: '4px',
              fontSize: '14px',
              color: '#666'
            }}>
              <strong>질문:</strong> {response.question}
            </div>

            <div style={{
              lineHeight: '1.6',
              fontSize: '16px',
              color: '#333',
              whiteSpace: 'pre-wrap'
            }}>
              {response.response}
            </div>

            <div style={{
              marginTop: '20px',
              padding: '10px',
              backgroundColor: '#e8f5e9',
              borderRadius: '4px',
              fontSize: '12px',
              color: '#2e7d32'
            }}>
              📅 생성일시: {new Date(response.generated_at).toLocaleString('ko-KR')}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default App;
