import React, { useState, useMemo } from 'react';
import './App.css'; 
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { marked } from 'marked';
import { AgeGenderChart } from './AgeGenderChart';
import { RatingChart } from './RatingChart';

// marked 옵션 설정
marked.use({
  breaks: true, // 줄바꿈을 <br>로 변환
  gfm: true, // GitHub Flavored Markdown 지원
});
// 필요한 아이콘: 건물/기관, 물음표/정보, 분석
import { 
    faBuilding, 
    faQuestionCircle, 
    faCircleInfo,
    faChevronRight,
    faChevronLeft,
    faCalendarAlt,
    faFileCode
} from '@fortawesome/free-solid-svg-icons'; 

const API_BASE = 'http://localhost:8000';

interface ChartData {
  age_gender_ratio?: Array<{
    cri_ym: string;
    male_20s: number;
    male_30s: number;
    male_40s: number;
    male_50s: number;
    male_60s: number;
    male_70s: number;
    female_20s: number;
    female_30s: number;
    female_40s: number;
    female_50s: number;
    female_60s: number;
    female_70s: number;
  }>;
}

interface RatingStatistics {
  total_reviews: number;
  average_rating: number;
  rating_distribution: {
    "5": number;
    "4": number;
    "3": number;
    "2": number;
    "1": number;
  };
  rating_percentages: {
    "5": number;
    "4": number;
    "3": number;
    "2": number;
    "1": number;
  };
}

interface AdvancedReportResponse {
  id: number;
  organization_name: string;
  report_topic: string;
  final_report: string;
  research_sources: string[];
  analysis_summary: string;
  generated_at: string;
  generation_time_seconds: number;
  chart_data: ChartData;
  rating_statistics?: RatingStatistics;
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

const ORG_LIST = [
  "국립중앙박물관", 
  "국립현대미술관", 
  "대한민국역사박물관",
  "서울역사박물관", 
  "전쟁기념관", 
  "서울시립과학관",
  "서울시립미술관", 
  "예술의전당"
];

function App() {
  const [organizationName, setOrganizationName] = useState('');
  const [userCommand, setUserCommand] = useState('');
  const [selectedMonth, setSelectedMonth] = useState('');
  const [reportType, setReportType] = useState<'user' | 'operator'>('user');
  const [response, setResponse] = useState<AdvancedReportResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [savedOpen, setSavedOpen] = useState(true); // 사이드바 열림/닫힘 상태
/* 사용자가 생성한 보고서 저장 */
  const [savedReports, setSavedReports] = useState<AdvancedReportResponse[]>(
  JSON.parse(localStorage.getItem("savedReports") || "[]")
);

  /** -----------------------------
   * HTML 파일 다운로드
   * ---------------------------- */
  const downloadReportHTML = (reportHtml: string, fileName: string) => {
    const blob = new Blob([reportHtml], { type: "text/html;charset=utf-8" });
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = fileName.replace(/\.pdf$/, ".html");
    link.click();
    URL.revokeObjectURL(link.href);
  };

  const handleDeleteReport = (id: number) => {
    const updated = savedReports.filter(report => report.id !== id);
    setSavedReports(updated);
    localStorage.setItem("savedReports", JSON.stringify(updated));
    if (response?.id === id) setResponse(null);
  };

  // 월 선택값을 "2025년 1월" 형식으로 변환
  const formatMonthForQuery = (monthValue: string): string => {
    if (!monthValue) return '';
    const [year, month] = monthValue.split('-');
    return `${year}년 ${parseInt(month)}월`;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    setResponse(null);

    // 선택값을 질문에 포함
    let finalCommand = userCommand;
    if (organizationName) {
      finalCommand = `${organizationName}, ${finalCommand}`;
    }
    if (selectedMonth) {
      const monthText = formatMonthForQuery(selectedMonth);
      finalCommand = `${finalCommand} (분석 기간: ${monthText})`;
    }

    try {
      const res = await fetch(`${API_BASE}/report/advanced`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          organization_name: organizationName,
          user_command: finalCommand,
          report_type: reportType
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
            
            {/* 기관 선택 */}
            <div className="form-group">
              <div className="label-container">
                <FontAwesomeIcon icon={faBuilding} color="#4285f4" />
                <label className="form-label">
                  분석 대상 기관명 <span style={{color: 'red'}}>*</span>
                </label>
              </div>
              <div className="org-button-group">
                {ORG_LIST.map(org => (
                  <button
                    key={org}
                    type="button"
                    className={`org-select-button ${organizationName === org ? "selected" : ""}`}
                    onClick={() => setOrganizationName(org)}
                  >
                    {org}
                  </button>
                ))}
              </div>
              <input
                type="text"
                className="form-input"
                placeholder="선택 (직접 입력)"
                value={organizationName}
                onChange={e => setOrganizationName(e.target.value)}
                style={{ marginTop: "8px" }}
                required
              />
              <div className="guidance-text">
                <FontAwesomeIcon icon={faCircleInfo} className="icon" />
                정확한 기관명을 입력하면 더 정밀한 분석이 가능합니다
              </div>
            </div>

            {/* 월 선택 */}
            <div className="form-group">
              <div className="label-container">
                <FontAwesomeIcon icon={faCalendarAlt} color="#4285f4" />
                <label className="form-label">월 선택 <span style={{color: 'red'}}>*</span></label>
              </div>
              <div className="input-with-icon">
                <input
                  type="month"
                  className="form-input"
                  value={selectedMonth}
                  onChange={e => setSelectedMonth(e.target.value)}
                  required
                />
              </div>
            </div>

            {/* 보고서 타입 선택 (사용자/운영자) */}
            <div className="form-group">
              <div className="label-container">
                <FontAwesomeIcon icon={faCircleInfo} color="#4285f4" />
                <label className="form-label">보고서 유형 <span style={{color: 'red'}}>*</span></label>
              </div>
              <div className="report-type-toggle">
                <button
                  type="button"
                  className={`toggle-option ${reportType === 'user' ? 'active' : ''}`}
                  onClick={() => setReportType('user')}
                >
                  <span className="toggle-label">사용자</span>
                  <span className="toggle-description">기관 이용자를 위한 정보 제공</span>
                </button>
                <button
                  type="button"
                  className={`toggle-option ${reportType === 'operator' ? 'active' : ''}`}
                  onClick={() => setReportType('operator')}
                >
                  <span className="toggle-label">운영자</span>
                  <span className="toggle-description">운영 인사이트 및 의사결정 지원</span>
                </button>
              </div>
              <div className="guidance-text">
                <FontAwesomeIcon icon={faCircleInfo} className="icon" />
                {reportType === 'user' 
                  ? '일반 이용자에게 유용한 정보와 서비스 안내 중심의 보고서를 생성합니다'
                  : '운영진을 위한 데이터 분석, 인사이트, 전략 제안 중심의 보고서를 생성합니다'}
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

        {/* 최근 생성된 보고서 사이드바 */}
        <div className={`saved-list-sidebar ${savedOpen ? '' : 'closed'}`}>
          {/* 사이드바 상단 토글 버튼 */}
          <button 
            className="saved-toggle-btn"
            onClick={() => setSavedOpen(!savedOpen)}
          >
            {savedOpen ? '▶' : '◀'}
          </button>

          <div className="saved-content">
            <h3 className="saved-title">최근 생성된 보고서</h3>

            {savedReports.length === 0 ? (
              <div className="saved-empty">아직 저장된 보고서가 없습니다.</div>
            ) : (
              <div className="saved-cards">
                {savedReports.map(r => {
                  // 각 보고서의 HTML 변환 헬퍼 함수
                  const getReportHtml = (report: string) => {
                    if (!report) return '<p>보고서 내용이 없습니다.</p>';
                    try {
                      let markdownText = report.trim();
                      if (markdownText.startsWith('```')) {
                        const lines = markdownText.split('\n');
                        if (lines[0].startsWith('```')) lines.shift();
                        if (lines[lines.length - 1].trim() === '```') lines.pop();
                        markdownText = lines.join('\n').trim();
                      }
                      return marked.parse(markdownText) as string;
                    } catch {
                      return report.replace(/\n/g, '<br/>');
                    }
                  };

                  return (
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
                        <button
                          className="saved-delete-btn"
                          onClick={e => {
                            e.stopPropagation();
                            handleDeleteReport(r.id);
                          }}
                        >
                          삭제
                        </button>
                      </div>

                      <div className="saved-card-bottom">
                        <span className="saved-date">
                          {new Date(r.generated_at).toLocaleDateString("ko-KR")}
                        </span>
                        <div className="saved-tag-actions">
                          <span className="saved-tag">종합 분석</span>
                          <button
                            className="download-btn"
                            onClick={e => {
                              e.stopPropagation();
                              const reportHtml = getReportHtml(r.final_report);
                              downloadReportHTML(reportHtml, `${r.organization_name}_분석보고서.html`);
                            }}
                          >
                            <FontAwesomeIcon icon={faFileCode} />
                          </button>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>

        {/* 사이드바 열기/닫기 버튼 (사이드바가 닫혔을 때 표시) */}
        {!savedOpen && (
          <button 
            className="saved-toggle-btn-external"
            onClick={() => setSavedOpen(!savedOpen)}
          >
            ▶
          </button>
        )}

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

            {/* 차트 데이터 표시 */}
            <div className="chart-section" style={{ marginBottom: '30px', padding: '20px', backgroundColor: '#f9fafb', borderRadius: '8px' }}>
              <h3 style={{ marginBottom: '20px', fontSize: '20px', fontWeight: '600' }}>
                월별 연령대별 성별 비율
              </h3>
              {response.chart_data?.age_gender_ratio && response.chart_data.age_gender_ratio.length > 0 ? (
                response.chart_data.age_gender_ratio.map((data, idx) => (
                  <AgeGenderChart 
                    key={idx} 
                    data={data}
                  />
                ))
              ) : (
                <div style={{ padding: '20px', textAlign: 'center', color: '#666' }}>
                  <p>차트 데이터가 없습니다.</p>
                  <p style={{ fontSize: '12px', marginTop: '10px' }}>
                    {response.chart_data ? 'chart_data는 있지만 age_gender_ratio가 없습니다.' : 'chart_data가 없습니다.'}
                  </p>
                  {process.env.NODE_ENV === 'development' && (
                    <pre style={{ marginTop: '10px', fontSize: '10px', textAlign: 'left', backgroundColor: '#fff', padding: '10px', borderRadius: '4px', overflow: 'auto' }}>
                      {JSON.stringify(response.chart_data, null, 2)}
                    </pre>
                  )}
                </div>
              )}
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

            {/* 평점 차트 */}
            <div className="rating-chart-section" style={{ marginBottom: '30px', padding: '20px', backgroundColor: '#f9fafb', borderRadius: '8px' }}>
              <h3 style={{ marginBottom: '20px', fontSize: '20px', fontWeight: '600' }}>
                리뷰 평점 분포
              </h3>
              {response.rating_statistics && response.rating_statistics.total_reviews > 0 ? (
                <RatingChart 
                  statistics={response.rating_statistics} 
                  organizationName={response.organization_name}
                />
              ) : (
                <div style={{ padding: '20px', textAlign: 'center', color: '#666' }}>
                  <p>평점 통계 데이터가 없습니다.</p>
                  <p style={{ fontSize: '12px', marginTop: '10px' }}>
                    {response.rating_statistics ? '평점 통계는 있지만 리뷰가 없습니다.' : '평점 통계 데이터가 수집되지 않았습니다.'}
                  </p>
                  {process.env.NODE_ENV === 'development' && (
                    <pre style={{ marginTop: '10px', fontSize: '10px', textAlign: 'left', backgroundColor: '#fff', padding: '10px', borderRadius: '4px', overflow: 'auto' }}>
                      {JSON.stringify(response.rating_statistics, null, 2)}
                    </pre>
                  )}
                </div>
              )}
            </div>

            <div className="final-report-section">
              <strong className="final-report-title">
                최종 보고서
              </strong>
              <div 
                className="final-report-content"
                dangerouslySetInnerHTML={{ __html: finalReportHtml }}
              />
            </div>

            {/* 다운로드 버튼 */}
            <div className="download-btn-wrapper">
              <button
                className="download-btn"
                onClick={() => downloadReportHTML(finalReportHtml, `${response.organization_name}_분석보고서.html`)}
              >
                <FontAwesomeIcon icon={faFileCode} /> HTML 다운로드
              </button>
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