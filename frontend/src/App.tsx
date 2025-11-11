import React, { useState, useMemo } from 'react';
import './App.css'; 
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { marked } from 'marked';

// marked 옵션 설정
marked.use({
  breaks: true, // 줄바꿈을 <br>로 변환
  gfm: true, // GitHub Flavored Markdown 지원
});
// 필요한 아이콘: 건물/기관, 물음표/정보, 분석
import { 
    faBuilding, 
    faQuestionCircle, 
    faCircleInfo
} from '@fortawesome/free-solid-svg-icons'; 

const API_BASE = 'http://localhost:8000';

interface AdvancedReportResponse {
  id: number;
  organization_name: string;
  report_topic: string;
  final_report: string;
  research_sources: string[];
  analysis_summary: string;
  generated_at: string;
  generation_time_seconds: number;
}

// 보고서 생성 시간 포맷팅 함수
function formatGenerationTime(seconds: number): string {
  if (seconds < 60) {
    return `${seconds}초`;
  } else {
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = Math.floor(seconds % 60);
    if (remainingSeconds === 0) {
      return `${minutes}분`;
    } else {
      return `${minutes}분 ${remainingSeconds}초`;
    }
  }
}

function App() {
  const [organizationName, setOrganizationName] = useState('');
  const [userCommand, setUserCommand] = useState('');
  const [response, setResponse] = useState<AdvancedReportResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
/* 사용자가 생성한 보고서 저장 */
  const [savedReports, setSavedReports] = useState<AdvancedReportResponse[]>(
  JSON.parse(localStorage.getItem("savedReports") || "[]")
);

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
        /* 사용자가 생성한 보고서 저장 */
        const updated = [...savedReports, result];
        setSavedReports(updated);
        localStorage.setItem("savedReports", JSON.stringify(updated));
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

  const submitButtonClass = `submit-button ${loading ? 'submit-button-disabled' : 'submit-button-active'}`;

  // 텍스트 영역의 예시 문구
  const userCommandPlaceholder = 
  `예: 2030 세대의 관람객 유입을 위한 이벤트 기획에 대해 분석하고, 최근 전시 정보와 대표 소장품을 조사해서 보고서를 작성해줘`;

  // 분석 요약 마크다운을 HTML로 변환
  const analysisSummaryHtml = useMemo(() => {
    if (!response?.analysis_summary) return '';
    try {
      const html = marked.parse(response.analysis_summary) as string;
      return html;
    } catch (error) {
      console.error('Analysis summary markdown parsing error:', error);
      return response.analysis_summary.replace(/\n/g, '<br/>');
    }
  }, [response?.analysis_summary]);

  // 최종 보고서 마크다운을 HTML로 변환
  const finalReportHtml = useMemo(() => {
    if (!response?.final_report) {
      return '<p>보고서 내용이 없습니다.</p>';
    }
    try {
      // 코드 블록 마커 제거 (```markdown, ``` 등)
      let markdownText = response.final_report.trim();
      
      // 앞뒤의 코드 블록 마커 제거
      if (markdownText.startsWith('```')) {
        const lines = markdownText.split('\n');
        if (lines[0].startsWith('```')) {
          lines.shift(); // 첫 번째 줄 제거
        }
        if (lines[lines.length - 1].trim() === '```') {
          lines.pop(); // 마지막 줄 제거
        }
        markdownText = lines.join('\n').trim();
      }
      
      const html = marked.parse(markdownText) as string;
      return html;
    } catch (error) {
      console.error('Final report markdown parsing error:', error);
      return response.final_report.replace(/\n/g, '<br/>');
    }
  }, [response?.final_report]);

  return (
    <div className="app-container">
      <div className="content-wrapper">
        
        {/* 제목 및 서브타이틀 */}
        <h1 className="main-title">
          분석 보고서 생성
        </h1>
        <p className="subtitle">
            분석하고자 하는 기관명과 구체적인 질문을 입력해주세요
        </p>

        {/* 입력 폼 */}
        <div className="card-form">
          <form onSubmit={handleSubmit}>
            
            {/* 분석 대상 기관명 필드 */}
            <div className="form-group">
              <div className="label-container">
                <FontAwesomeIcon icon={faBuilding} color="#4285f4" />
                <label className="form-label">
                  분석 대상 기관명 <span style={{color: 'red'}}>*</span>
                </label>
              </div>
              <input
                type="text"
                value={organizationName}
                onChange={(e) => setOrganizationName(e.target.value)}
                placeholder="예: 국립중앙박물관, 윤동주문학관, 서울시립미술관"
                required={true}
                className="form-input"
              />
              <div className="guidance-text">
                <FontAwesomeIcon icon={faCircleInfo} className="icon" />
                정확한 기관명을 입력하면 더 정밀한 분석이 가능합니다
              </div>
            </div>

            {/* 분석 질문 필드 */}
            <div className="form-group">
              <div className="label-container">
                <FontAwesomeIcon icon={faQuestionCircle} color="#4285f4" />
                <label className="form-label">
                  분석 질문 <span style={{color: 'red'}}>*</span>
                </label>
              </div>
              <textarea
                value={userCommand}
                onChange={(e) => setUserCommand(e.target.value)}
                placeholder={userCommandPlaceholder}
                required={true}
                className="form-input form-textarea"
              />
              <div className="guidance-text" style={{justifyContent: 'space-between'}}>
                <span style={{display: 'flex', alignItems: 'center'}}>
                    <FontAwesomeIcon icon={faCircleInfo} className="icon" />
                    구체적이고 명확한 질문일수록 더 유용한 분석 결과를 얻을 수 있습니다
                </span>
              </div>
            </div>

            {/* 버튼 (이미지에 없지만 기능 유지를 위해 포함) */}
            <button
  type="submit"
  disabled={loading}
  className={submitButtonClass}
  style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', marginTop: '20px' }}
>
  {loading ? (
    <>
      <div className="loading-spinner"></div>
      분석 요청중...
    </>
  ) : (
    '보고서 생성'
  )}
</button>

          </form>
        </div>

{/* 저장된 보고서 목록 사이드바 */}
<div className="saved-list-sidebar">
  <h3 className="saved-title">최근 생성된 보고서</h3>

  {savedReports.length === 0 && (
    <div className="saved-empty">아직 저장된 보고서가 없습니다.</div>
  )}

  {savedReports.map((r) => (
    <div 
      key={r.id} 
      className="saved-card"
      onClick={() => setResponse(r)}
    >
      <div className="saved-card-top">
        <div className="saved-left">
          <div className="saved-organization">{r.organization_name}</div>
          <div className="saved-topic">{r.report_topic}</div>
        </div>
        <span className="saved-status">완료</span>
      </div>


      <div className="saved-card-bottom">
        <span className="saved-date">
          {new Date(r.generated_at).toLocaleDateString('ko-KR')}
        </span>
        <span className="saved-tag">종합 분석</span>
      </div>
    </div>
  ))}
</div>


        {/* 오류 메시지 */}
        {error && (
          <div className="error-message">
            {error}
          </div>
        )}

        {/* 결과 출력 */}
        {response && (
          <div className="result-card">
            <h2 className="result-title">
              {response.organization_name} 분석 보고서
            </h2>
            
            <div className="info-summary">
              <div style={{ marginBottom: '10px' }}>
                <strong>주제:</strong> {response.report_topic}
              </div>
              <div>
                <strong>보고서 ID:</strong> {response.id}
              </div>
            </div>

            {response.research_sources.length > 0 && (
              <div className="sources-section">
                <strong className="sources-title">
                  참고 출처
                </strong>
                <ul className="sources-list">
                  {response.research_sources.slice(0, 5).map((source, idx) => (
                    <li key={idx}>
                      <a href={source} target="_blank" rel="noopener noreferrer" className="source-link">
                        {source}
                      </a>
                    </li>
                  ))}
                </ul>
                {response.research_sources.length > 5 && (
                  <div className="more-sources">
                    외 {response.research_sources.length - 5}개
                  </div>
                )}
              </div>
            )}

            {response.analysis_summary && (
              <div className="analysis-summary">
                <strong className="analysis-title">
                  분석 요약
                </strong>
                <div 
                  className="analysis-content"
                  dangerouslySetInnerHTML={{ __html: analysisSummaryHtml }}
                />
              </div>
            )}

            <div className="final-report-section">
              <strong className="final-report-title">
                최종 보고서
              </strong>
              <div 
                className="final-report-content"
                dangerouslySetInnerHTML={{ __html: finalReportHtml }}
              />
            </div>

            <div className="generated-at">
              생성일시: {new Date(response.generated_at).toLocaleString('ko-KR')}
              {response.generation_time_seconds > 0 && (
                <span> (소요 시간: {formatGenerationTime(response.generation_time_seconds)})</span>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default App;