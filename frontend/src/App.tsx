import React, { useState, useMemo } from 'react';
import './App.css'; 
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { marked } from 'marked';

import { 
    faBuilding, 
    faQuestionCircle, 
    faCircleInfo,
    faCalendarAlt, 
    faFileCode,
} from '@fortawesome/free-solid-svg-icons'; 

marked.use({
  breaks: true,
  gfm: true,
});

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

const ORG_LIST = [
  "국립중앙박물관", "국립현대미술관", "대한민국역사박물관",
  "서울역사박물관", "전쟁기념관", "서울시립과학관",
  "서울시립미술관", "예술의전당"
];

function App() {
  const [organizationName, setOrganizationName] = useState('');
  const [userCommand, setUserCommand] = useState('');
  const [response, setResponse] = useState<AdvancedReportResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [selectedMonth, setSelectedMonth] = useState('');
  const [savedReports, setSavedReports] = useState<AdvancedReportResponse[]>(
    JSON.parse(localStorage.getItem("savedReports") || "[]")
  );

  // 사이드바 열림/접힘 상태
  const [savedOpen, setSavedOpen] = useState(true);

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

  /** -----------------------------
   * 보고서 제출 핸들러
   * ---------------------------- */
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

        const updated = [...savedReports, result];
        setSavedReports(updated);
        localStorage.setItem("savedReports", JSON.stringify(updated));
      } else {
        const errorData = await res.json();
        setError(errorData.detail || '보고서 생성 실패');
      }
    } catch {
      setError('서버 연결 오류');
    } finally {
      setLoading(false);
    }
  };

  const submitButtonClass = `submit-button ${loading ? 'submit-button-disabled' : 'submit-button-active'}`;

  const userCommandPlaceholder = 
    `예: 2030 세대의 관람객 유입을 위한 이벤트 기획에 대해 분석하고, 최근 전시 정보와 대표 소장품을 조사해서 보고서를 작성해줘`;

  const analysisSummaryHtml = useMemo(() => {
    if (!response?.analysis_summary) return '';
    try {
      return marked.parse(response.analysis_summary) as string;
    } catch {
      return response.analysis_summary.replace(/\n/g, '<br/>');
    }
  }, [response?.analysis_summary]);

  const finalReportHtml = useMemo(() => {
    if (!response?.final_report) return '<p>보고서 내용이 없습니다.</p>';

    try {
      let markdownText = response.final_report.trim();
      if (markdownText.startsWith('```')) {
        const lines = markdownText.split('\n');
        if (lines[0].startsWith('```')) lines.shift();
        if (lines[lines.length - 1].trim() === '```') lines.pop();
        markdownText = lines.join('\n').trim();
      }
      return marked.parse(markdownText) as string;
    } catch {
      return response.final_report.replace(/\n/g, '<br/>');
    }
  }, [response?.final_report]);

  const handleDeleteReport = (id: number) => {
    const updated = savedReports.filter(report => report.id !== id);
    setSavedReports(updated);
    localStorage.setItem("savedReports", JSON.stringify(updated));
    if (response?.id === id) setResponse(null);
  };

  return (
    <div className="app-container">
      <div className="content-wrapper">

        {/* 제목 */}
        <h1 className="main-title">분석 보고서 생성</h1>
        <p className="subtitle">분석하고자 하는 기관명과 구체적인 질문을 입력해주세요</p>

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
                />
              </div>
            </div>

            {/* 분석 질문 */}
            <div className="form-group">
              <div className="label-container">
                <FontAwesomeIcon icon={faQuestionCircle} color="#4285f4" />
                <label className="form-label">분석 질문 <span style={{color: 'red'}}>*</span></label>
              </div>
              <textarea
                value={userCommand}
                onChange={e => setUserCommand(e.target.value)}
                placeholder={userCommandPlaceholder}
                required
                className="form-input form-textarea"
              />
              <div className="guidance-text" style={{justifyContent: 'space-between'}}>
                <span style={{display: 'flex', alignItems: 'center'}}>
                  <FontAwesomeIcon icon={faCircleInfo} className="icon" />
                  구체적이고 명확한 질문일수록 더 유용한 분석 결과를 얻을 수 있습니다
                </span>
              </div>
            </div>

            {/* 제출 버튼 */}
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
    {savedOpen ? '◀' : '▶'}
  </button>

  <div className="saved-content">
    <h3 className="saved-title">최근 생성된 보고서</h3>

    {savedReports.length === 0 ? (
      <div className="saved-empty">아직 저장된 보고서가 없습니다.</div>
    ) : (
      <div className="saved-cards">
        {savedReports.map(r => (
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
                    downloadReportHTML(finalReportHtml, `${r.organization_name}_분석보고서.html`);
                  }}
                >
                  <FontAwesomeIcon icon={faFileCode} />
                </button>
              </div>
            </div>
          </div>
        ))}
      </div>
    )}
  </div>

</div>


        {/* 사이드바 열기/닫기 버튼 */}
        <button 
          className="saved-toggle-btn"
          onClick={() => setSavedOpen(!savedOpen)}
        >
          {savedOpen ? '◀' : '▶'}
        </button>

        {/* 오류 메시지 */}
        {error && <div className="error-message">{error}</div>}

        {/* 최종 보고서 */}
        {response && (
  <div className="result-card">
    {/* 제목 */}
    <h2 className="result-title">{response.organization_name} 분석 보고서</h2>

    {/* 기본 정보 카드 */}
    <div className="info-summary">
      <div><strong>주제:</strong> {response.report_topic}</div>
      <div><strong>보고서 ID:</strong> {response.id}</div>
      <div><strong>생성일시:</strong> {new Date(response.generated_at).toLocaleString('ko-KR')}</div>
    </div>

    {/* 참고 출처 */}
    {response.research_sources.length > 0 && (
      <div className="sources-section">
        <strong className="sources-title">참고 출처</strong>
        <ul className="sources-list">
          {response.research_sources.slice(0, 5).map((source, idx) => (
            <li key={idx}>
              <a href={source} target="_blank" rel="noopener noreferrer" className="source-link">
                {source}
              </a>
            </li>
          ))}
          {response.research_sources.length > 5 && (
            <li className="more-sources">
              외 {response.research_sources.length - 5}개
            </li>
          )}
        </ul>
      </div>
    )}

    {/* 분석 요약 */}
    {response.analysis_summary && (
      <div className="analysis-summary">
        <strong className="analysis-title">분석 요약</strong>
        <div className="analysis-content" dangerouslySetInnerHTML={{ __html: analysisSummaryHtml }} />
      </div>
    )}

    {/* 최종 보고서 */}
    <div className="final-report-section">
      <strong className="final-report-title">최종 보고서</strong>
      <div className="final-report-content" dangerouslySetInnerHTML={{ __html: finalReportHtml }} />
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
  </div>
)}


      </div>
    </div>
  );
}

export default App;
