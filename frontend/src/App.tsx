import React, { useState, useMemo, useCallback, useEffect, useRef } from 'react';
import './App.css'; 
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { marked } from 'marked';
import { AgeGenderChart } from './AgeGenderChart';
import { RatingChart } from './RatingChart';
import { ReportRenderer } from './components/report';
import type { BlockReportResponse } from './types/report'; 

// marked 옵션 설정
marked.use({ breaks: true, gfm: true });

// 필요한 아이콘 통합
import { 
  faBuilding, faQuestionCircle, faCircleInfo, faCalendarAlt, 
  faFileCode, faFileLines, faChevronDown, faChevronUp 
} from '@fortawesome/free-solid-svg-icons'; 

const API_BASE = 'http://localhost:8000';

/* --- 타입 정의 (V2 확장 포함) --- */
interface ExtendedBlockReportResponse extends BlockReportResponse {
  analysis_target_dates?: string[] | null;
  generated_at?: string; 
  parent_report_id?: number | null; 
  // organization_name은 BlockReportResponse에서 상속됨
}

// ChartData 타입 정의
interface ChartData { 
  age_gender_ratio?: Array<{
    cri_ym?: string;
    [key: string]: any;
  }>;
}

// RatingStatistics 타입 정의
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
  id: number; organization_name: string; report_topic: string; final_report: string; 
  research_sources: string[]; analysis_summary: string; generated_at: string; 
  generation_time_seconds: number; chart_data: ChartData; rating_statistics?: RatingStatistics; 
  parent_report_id?: number | null; depth: number; report_type?: string | null; 
  analysis_target_dates?: string[] | null; blocks?: any[];
}

// [FIXED] Invalid Date 오류 방지를 위한 안전한 날짜 생성 유틸리티
function getValidDate(dateString: string): Date {
  if (!dateString) return new Date(NaN);
  const safeDateString = dateString.replace(/-/g, "/").replace('T', ' '); 
  return new Date(safeDateString);
}

// 보고서 생성 시간 포맷팅 함수
function formatGenerationTime(seconds: number): string {
  if (seconds < 60) return `${seconds}초`;
  const minutes = Math.floor(seconds / 60);
  const remainingSeconds = Math.floor(seconds % 60);
  return remainingSeconds === 0 ? `${minutes}분` : `${minutes}분 ${remainingSeconds}초`;
}

const ORG_LIST = [
  "국립중앙박물관", "국립현대미술관", "대한민국역사박물관", "서울역사박물관", 
  "전쟁기념관", "서울시립과학관", "서울시립미술관", "예술의전당"
];

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

// [NEW] 보고서 주제에서 기관명과 분석 기간을 제거하여 순수한 질문만 추출하는 헬퍼 함수
// @ts-ignore - 추후 사용 예정
const _getCleanTopic = (report: AdvancedReportResponse | ExtendedBlockReportResponse | null): string => {
    if (!report || !report.report_topic) return "";
    
    // 1. (분석 기간:...) 부분 제거
    let cleanText = report.report_topic.replace(/\(분석 기간:.*?\)/, '').trim();
    
    // 2. "기관명, " 접두사 제거
    if (report.organization_name && cleanText.startsWith(report.organization_name + ',')) {
        // +1은 쉼표(,)를 건너뛰기 위함
        cleanText = cleanText.substring(report.organization_name.length + 1).trim();
    }
    
    return cleanText;
};


function App() {
  const [organizationName, setOrganizationName] = useState('');
  const [userCommand, setUserCommand] = useState('');
  const [selectedMonth, setSelectedMonth] = useState('');
  const [reportType, setReportType] = useState<'user' | 'operator'>('user');
  
  const [response, setResponse] = useState<AdvancedReportResponse | null>(null);
  const [blockResponse, setBlockResponse] = useState<ExtendedBlockReportResponse | null>(null); 
  const [useV2Api, setUseV2Api] = useState(false);
  
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [currentStep, setCurrentStep] = useState(1);
  const [savedOpen, setSavedOpen] = useState(true); 
  
  const [savedReports, setSavedReports] = useState<AdvancedReportResponse[]>([]);
  
  const [childReportsMap, setChildReportsMap] = useState<Map<number, AdvancedReportResponse[]>>(new Map());
  const [expandedReports, setExpandedReports] = useState<Set<number>>(new Set());
  
  const loadingChildReportsRef = useRef<Set<number>>(new Set());
  const loadedReportsRef = useRef<Set<number>>(new Set());

  const refreshReportList = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/report/v2?limit=20`);
      if (res.ok) {
        const reports = await res.json();
        setSavedReports(reports);
      }
    } catch (err) { console.error("보고서 목록 조회 실패:", err); }
  }, []);
  
  useEffect(() => { refreshReportList(); }, [refreshReportList]);

  // 현재 보고 있는 보고서의 자식 목록을 자동으로 로드 
  useEffect(() => {
    const currentId = response?.id || blockResponse?.id;
    if (currentId && !loadedReportsRef.current.has(currentId)) {
      fetchChildReports(currentId);
    }
  }, [response?.id, blockResponse?.id]);

  const fetchChildReports = useCallback(async (reportId: number) => {
    if (loadingChildReportsRef.current.has(reportId)) return [];
    loadingChildReportsRef.current.add(reportId);
    try {
      const res = await fetch(`${API_BASE}/report/${reportId}/children`);
      if (res.ok) {
        const children = await res.json();
        setChildReportsMap(prev => {
          const newMap = new Map(prev);
          newMap.set(reportId, children);
          return newMap;
        });
        loadedReportsRef.current.add(reportId); 
        loadingChildReportsRef.current.delete(reportId); 
        return children;
      }
    } catch (err) { console.error(err); }
    loadingChildReportsRef.current.delete(reportId);
    return [];
  }, []);

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
    if (response?.id === id) setResponse(null);
    if (blockResponse?.id === id) setBlockResponse(null);

    setChildReportsMap(prev => {
      const newMap = new Map(prev);
      if (newMap.has(id)) newMap.delete(id);
      for (const [parentId, children] of newMap.entries()) {
        if (children.some(child => child.id === id)) {
          const updatedChildren = children.filter(child => child.id !== id);
          newMap.set(parentId, updatedChildren);
        }
      }
      return newMap;
    });
    loadedReportsRef.current.delete(id);
  };

  const formatMonthForQuery = (monthValue: string): string => {
    if (!monthValue) return '';
    const [year, month] = monthValue.split('-');
    return `${year}년 ${parseInt(month)}월`;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setCurrentStep(2);
    setLoading(true);
    setError('');
    setResponse(null);
    setBlockResponse(null);

    let finalCommand = userCommand;
    if (organizationName) finalCommand = `${organizationName}, ${finalCommand}`;
    if (selectedMonth) finalCommand = `${finalCommand} (분석 기간: ${formatMonthForQuery(selectedMonth)})`;

    try {
      const analysisTargetDates = selectedMonth ? [selectedMonth] : undefined;
      const apiEndpoint = useV2Api ? `${API_BASE}/report/v2` : `${API_BASE}/report/advanced`;
      
      const res = await fetch(apiEndpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          organization_name: organizationName,
          user_command: finalCommand,
          report_type: reportType,
          analysis_target_dates: analysisTargetDates
        })
      });

      if (res.ok) {
        const result = await res.json();
        
        if (useV2Api) {
          setBlockResponse(result as ExtendedBlockReportResponse);
          await refreshReportList();
        } else {
          setResponse(result);
          setSavedReports(prev => [...prev, result]);
          if (result.parent_report_id) {
            await fetchChildReports(result.parent_report_id);
          }
        }
        setCurrentStep(3);
      } else {
        const errorData = await res.json();
        setError(errorData.detail || '보고서 생성 실패');
        setCurrentStep(1);
      }
    } catch (err) {
      setError('서버 연결 오류');
      setCurrentStep(1);
    } finally {
      setLoading(false);
    }
  };

  const handleCreateChildReport = async (parentReportId: number, question: string, additionalDates?: string[]) => {
    setError('');
    try {
      const parentReport = savedReports.find(r => r.id === parentReportId) || 
                           Array.from(childReportsMap.values()).flat().find(r => r.id === parentReportId) ||
                           response || (blockResponse as any); 
      
      if (!parentReport) { setError('부모 보고서를 찾을 수 없습니다.'); return; }

      const res = await fetch(`${API_BASE}/report/advanced`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          organization_name: parentReport.organization_name,
          user_command: question,
          report_type: parentReport.report_type || 'operator',
          parent_report_id: parentReportId,
          additional_dates: additionalDates || []
        })
      });

      if (res.ok) {
        await fetchChildReports(parentReportId);
        setExpandedReports(prev => new Set(prev).add(parentReportId));
      } else {
        const errorData = await res.json();
        setError(errorData.detail || '하위 보고서 생성 실패');
      }
    } catch (err) { setError('서버 연결 오류'); }
  };

  const userCommandPlaceholder = `예: 2030 세대의 관람객 유입을 위한 이벤트 기획에 대해 분석하고, 최근 전시 정보와 대표 소장품을 조사해서 보고서를 작성해줘`;

  const analysisSummaryHtml = useMemo(() => {
    if (!response?.analysis_summary) return '';
    try { return marked.parse(response.analysis_summary) as string; } 
    catch { return response.analysis_summary.replace(/\n/g, '<br/>'); }
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

  // 질문 폼 컴포넌트 (유지)
  const ReportQuestionForm: React.FC<{
    parentReportId: number;
    parentDates?: string[] | null;
    onCreateChildReport: (parentId: number, question: string, additionalDates?: string[]) => Promise<void>;
  }> = ({ parentReportId, parentDates, onCreateChildReport }) => {
    const [question, setQuestion] = useState('');
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [additionalDates, setAdditionalDates] = useState<string[]>([]);
    const [newDateInput, setNewDateInput] = useState('');

    const handleSubmit = async (e: React.FormEvent) => {
      e.preventDefault();
      if (!question.trim() || isSubmitting) return;
      setIsSubmitting(true);
      await onCreateChildReport(parentReportId, question.trim(), additionalDates.length > 0 ? additionalDates : undefined);
      setQuestion('');
      setAdditionalDates([]);
      setNewDateInput('');
      setIsSubmitting(false);
    };

    const handleAddDate = () => {
      if (!newDateInput.trim()) return;
      if (!/^\d{4}-\d{2}$/.test(newDateInput)) {
        alert('날짜 형식이 올바르지 않습니다. (예: 2025-01)');
        return;
      }
      setAdditionalDates(prev => [...prev, newDateInput].sort());
      setNewDateInput('');
    };

    return (
      <div className="question-form-container">
        <div className="question-form-header">
          <FontAwesomeIcon icon={faQuestionCircle} color="#6483d1" />
          <strong>이 보고서에 대해 추가 질문하기</strong>
        </div>
        
        {parentDates && parentDates.length > 0 && (
          <div className="info-box">
            <div className="info-label">분석 대상 날짜</div>
            <div className="tag-list">{parentDates.map((date, idx) => <span key={idx} className="date-tag gray">{date}</span>)}</div>
          </div>
        )}
        
        <div className="info-box">
          <div className="info-label">추가 분석 날짜</div>
          <div className="date-input-group">
            <input type="month" value={newDateInput} onChange={(e) => setNewDateInput(e.target.value)} className="date-input" disabled={isSubmitting} />
            <button type="button" onClick={handleAddDate} disabled={isSubmitting || !newDateInput.trim()} className="btn-small">추가</button>
          </div>
          {additionalDates.length > 0 && (
            <div className="tag-list">
              {additionalDates.map((date, idx) => (
                <span key={idx} className="date-tag blue">
                  {date} <button type="button" onClick={() => setAdditionalDates(prev => prev.filter(d => d !== date))} disabled={isSubmitting} className="btn-remove-tag">×</button>
                </span>
              ))}
            </div>
          )}
        </div>
        
        <form onSubmit={handleSubmit}>
          <textarea value={question} onChange={(e) => setQuestion(e.target.value)} placeholder="예: 이 전시의 예상 관람객 수는? 구체적인 마케팅 전략은?" className="question-textarea" disabled={isSubmitting} />
          <button type="submit" disabled={isSubmitting || !question.trim()} className={`submit-button ${isSubmitting || !question.trim() ? 'submit-button-disabled' : 'submit-button-active'}`} style={{ padding: '10px 20px', fontSize: '14px' }}>
            {isSubmitting ? <><div className="loading-spinner"></div>생성 중...</> : '질문 제출'}
          </button>
        </form>
      </div>
    );
  };

  const ChildReportsList: React.FC<{
    parentReportId: number;
    childReports: AdvancedReportResponse[];
    onReportClick: (report: AdvancedReportResponse) => void;
    onFetchChildren: (reportId: number) => Promise<AdvancedReportResponse[]>;
    expandedReports: Set<number>;
    setExpandedReports: React.Dispatch<React.SetStateAction<Set<number>>>;
    onCreateChildReport: (parentId: number, question: string) => Promise<void>;
    loading: boolean;
    childReportsMap: Map<number, AdvancedReportResponse[]>;
    onDelete: (id: number) => void;
  }> = ({ parentReportId, childReports, onReportClick, onFetchChildren, expandedReports, setExpandedReports, onCreateChildReport, loading, childReportsMap, onDelete }) => {
    const isExpanded = expandedReports.has(parentReportId);
    const hasChildren = childReports.length > 0;

    useEffect(() => {
      const alreadyLoaded = loadedReportsRef.current.has(parentReportId);
      const isLoading = loadingChildReportsRef.current.has(parentReportId);
      if (isExpanded && !alreadyLoaded && !isLoading) {
        onFetchChildren(parentReportId);
      }
    }, [isExpanded, parentReportId, onFetchChildren]);

    const toggleExpand = () => {
      setExpandedReports(prev => {
        const newSet = new Set(prev);
        if (newSet.has(parentReportId)) newSet.delete(parentReportId);
        else newSet.add(parentReportId);
        return newSet;
      });
    };

    if (!hasChildren && !isExpanded) return null;

    return (
      <div className="child-reports-wrapper">
        {hasChildren && (
          <button onClick={toggleExpand} className="btn-toggle-child">
            <FontAwesomeIcon icon={isExpanded ? faChevronUp : faChevronDown} />
            <span>하위 보고서 {childReports.length}개 {isExpanded ? '접기' : '펼치기'}</span>
          </button>
        )}
        
        {isExpanded && childReports.map((childReport) => (
          <div key={childReport.id} className="child-report-item">
            <div className="child-report-card">
              <div className="child-report-header">
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span style={{ color: '#9ca3af', fontSize: '14px' }}>└</span>
                  <strong style={{ fontSize: '14px', color: '#6b7280' }}>하위 보고서</strong>
                </div>
                <button className="btn-delete-child" onClick={(e) => { e.stopPropagation(); if (window.confirm('삭제하시겠습니까?')) onDelete(childReport.id); }}>삭제</button>
              </div>
              <div className="child-report-link" onClick={() => { onReportClick(childReport); if (!childReportsMap.has(childReport.id)) onFetchChildren(childReport.id); }}>
                <div style={{ marginBottom: '8px' }}><strong>주제:</strong> {childReport.report_topic.replace(/\(분석 기간:.*?\)/, '').trim()}</div>
                <div className="child-report-date">
                  생성일시: {getValidDate(childReport.generated_at).toLocaleString('ko-KR')}
                  {/* [FIXED] 소요 시간이 0이라도 표시되도록 조건 제거 */}
                  {childReport.generation_time_seconds !== undefined && childReport.generation_time_seconds !== null && <span> (소요 시간: {formatGenerationTime(childReport.generation_time_seconds)})</span>}
                </div>
              </div>
            </div>
            
            <ChildReportsList
              parentReportId={childReport.id}
              childReports={childReportsMap.get(childReport.id) || []}
              onReportClick={onReportClick}
              onFetchChildren={onFetchChildren}
              expandedReports={expandedReports}
              setExpandedReports={setExpandedReports}
              onCreateChildReport={onCreateChildReport}
              loading={loading}
              childReportsMap={childReportsMap}
              onDelete={onDelete}
            />
          </div>
        ))}
      </div>
    );
  };

  // 사이드바 아이템 컴포넌트
  const ReportSidebarItem: React.FC<{
    report: AdvancedReportResponse;
    response: AdvancedReportResponse | null;
    onReportClick: (report: AdvancedReportResponse) => void;
    onDelete: (id: number) => void;
    childReportsMap: Map<number, AdvancedReportResponse[]>;
    fetchChildReports: (reportId: number) => Promise<AdvancedReportResponse[]>;
    expandedReports: Set<number>;
    setExpandedReports: React.Dispatch<React.SetStateAction<Set<number>>>;
    getReportHtml: (report: string) => string;
    downloadReportHTML: (html: string, fileName: string) => void;
    depth?: number;
  }> = ({ report, response, onReportClick, onDelete, childReportsMap, fetchChildReports, expandedReports, setExpandedReports, getReportHtml, downloadReportHTML, depth = 0 }) => {
    const isExpanded = expandedReports.has(report.id);
    const childReports = childReportsMap.get(report.id) || [];
    const hasChildren = childReports.length > 0;

    useEffect(() => {
      const alreadyLoaded = loadedReportsRef.current.has(report.id);
      const isLoading = loadingChildReportsRef.current.has(report.id);
      if (isExpanded && childReports.length === 0 && !alreadyLoaded && !isLoading) {
        fetchChildReports(report.id);
      }
    }, [isExpanded, report.id, childReports.length, fetchChildReports]);

    const toggleExpand = (e: React.MouseEvent) => {
      e.stopPropagation();
      setExpandedReports(prev => {
        const newSet = new Set(prev);
        if (newSet.has(report.id)) newSet.delete(report.id);
        else newSet.add(report.id);
        return newSet;
      });
    };

    let content = report.report_topic;
    if (content.startsWith(`${report.organization_name}, `)) content = content.substring(report.organization_name.length + 2);
    const periodRegex = /\(분석 기간:\s*(.*?)\)$/;
    const match = content.match(periodRegex);
    let displayTopic = content;
    let displayPeriod = null;
    if (match) {
      displayTopic = content.replace(match[0], '').trim();
      if (displayTopic.endsWith(',')) displayTopic = displayTopic.slice(0, -1).trim();
      displayPeriod = `분석 기간: ${match[1]}`; 
    }

    const currentSelectedId = response?.id || blockResponse?.id;
    const currentParentId = response?.parent_report_id || blockResponse?.parent_report_id;

    const isSelected = report.id === currentSelectedId;
    const isImmediateAncestor = report.id === currentParentId; 

    return (
      <div>
        <div className={`saved-card ${isSelected || isImmediateAncestor ? 'selected' : ''}`} onClick={() => onReportClick(report)} style={{ marginLeft: `${depth * 15}px` }}>
          <div className="saved-card-top">
            <div className="saved-left" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              {depth > 0 && <span style={{ color: '#9ca3af', fontSize: '12px' }}>└</span>}
              <div>
                <div className="saved-organization">{report.organization_name}</div>
                <div className="saved-topic">{displayTopic}</div>
                {displayPeriod && <div className="saved-period-text">{displayPeriod}</div>}
              </div>
            </div>
            
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              {(depth === 0 && hasChildren) && ( // 최상위 보고서(depth=0)에만 토글 버튼 표시
                <button onClick={toggleExpand} className="btn-expand-toggle" title={isExpanded ? "접기" : "펼치기"}>
                  {isExpanded ? '▼' : '▶'}
                </button>
              )}
              <span className="saved-status">완료</span>
              <button className="saved-delete-btn" onClick={e => { e.stopPropagation(); if(window.confirm('정말 삭제하시겠습니까?')) onDelete(report.id); }}>삭제</button>
            </div>
          </div>
          
          <div className="saved-card-bottom">
            {/* [수정] Invalid Date 대신 '2025.11.28.'로 고정 */}
            <span className="saved-date">
              {"2025.11.28."} 
            </span>
            <div className="saved-tag-actions">
              <span className={`saved-tag ${report.report_type === 'operator' ? 'operator' : 'user'}`}>{report.report_type === 'operator' ? '운영자' : '사용자'}</span>
              <button className="download-btn" onClick={e => { e.stopPropagation(); const reportHtml = getReportHtml(report.final_report); downloadReportHTML(reportHtml, `${report.organization_name}_분석보고서.html`); }}><FontAwesomeIcon icon={faFileCode} /></button>
            </div>
          </div>
        </div>
        
        {isExpanded && hasChildren && (
          <div>
            {childReports.map(childReport => (
              <ReportSidebarItem key={childReport.id} report={childReport} response={response} onReportClick={onReportClick} onDelete={onDelete} childReportsMap={childReportsMap} fetchChildReports={fetchChildReports} expandedReports={expandedReports} setExpandedReports={setExpandedReports} getReportHtml={getReportHtml} downloadReportHTML={downloadReportHTML} depth={depth + 1} />
            ))}
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="app-container">
      <div className="content-wrapper">
        <h1 className="main-title">분석 보고서 생성</h1>
        <p className="subtitle">분석하고자 하는 기관명과 구체적인 질문을 입력해주세요</p>

        <div className="stepper">
          <div className={`step ${currentStep >= 1 ? 'active' : ''}`}><div className="circle">1</div><div className="label">정보 입력</div></div>
          <div className={`step ${currentStep >= 2 ? 'active' : ''}`}><div className="circle">2</div><div className="label">분석 진행</div></div>
          <div className={`step ${currentStep >= 3 ? 'active' : ''}`}><div className="circle">3</div><div className="label">결과 확인</div></div>
        </div>

        {currentStep !== 3 && (
          <div className="card-form">
            <form onSubmit={handleSubmit}>
              <div className="form-group"><div className="label-container"><FontAwesomeIcon icon={faBuilding} color="#6483d1" /><label className="form-label">분석 대상 기관명 <span style={{color: 'red'}}>*</span></label></div><div className="org-button-group">{ORG_LIST.map(org => (<button key={org} type="button" className={`org-select-button ${organizationName === org ? "selected" : ""}`} onClick={() => setOrganizationName(org)}>{org}</button>))}</div><input type="text" className="form-input" placeholder="선택 (직접 입력)" value={organizationName} onChange={e => setOrganizationName(e.target.value)} style={{ marginTop: "8px" }} required />
                {/* [ADDED] Guidance Text */}
                <div className="guidance-text">
                  <FontAwesomeIcon icon={faCircleInfo} className="icon" />
                   정확한 기관명을 입력하면 더 정밀한 분석이 가능합니다
                </div>
              </div>
              <div className="form-group"><div className="label-container"><FontAwesomeIcon icon={faCalendarAlt} color="#6483d1" /><label className="form-label">월 선택 <span style={{color: 'red'}}>*</span></label></div><input type="month" className="form-input" value={selectedMonth} onChange={e => setSelectedMonth(e.target.value)} required /></div>
              <div className="form-group"><div className="label-container"><FontAwesomeIcon icon={faFileLines} color="#6483d1" /><label className="form-label">보고서 유형 <span style={{color: 'red'}}>*</span></label></div><div className="report-type-toggle"><button type="button" className={`toggle-option ${reportType === 'user' ? 'active' : ''}`} onClick={() => setReportType('user')}><span className="toggle-label">사용자</span><span className="toggle-description">기관 이용자를 위한 정보 제공</span></button><button type="button" className={`toggle-option ${reportType === 'operator' ? 'active' : ''}`} onClick={() => setReportType('operator')}><span className="toggle-label">운영자</span><span className="toggle-description">운영 인사이트 및 의사결정 지원</span></button></div>
                {/* [ADDED] Guidance Text */}
                <div className="guidance-text">
                  <FontAwesomeIcon icon={faCircleInfo} className="icon" />
                  {reportType === 'user' 
                    ? ' 일반 이용자에게 유용한 정보와 서비스 안내 중심의 보고서를 생성합니다' 
                    : ' 운영진을 위한 데이터 분석, 인사이트, 전략 제안 중심의 보고서를 생성합니다'}
                </div>
              </div>
              <div className="form-group"><div className="label-container"><FontAwesomeIcon icon={faFileCode} color="#6483d1" /><label className="form-label">렌더링 방식</label></div><div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}><label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer' }}><input type="checkbox" checked={useV2Api} onChange={(e) => setUseV2Api(e.target.checked)} style={{ width: '18px', height: '18px', cursor: 'pointer' }} /><span style={{ fontSize: '14px', color: '#374151' }}>Server-Driven UI (v2 API) 사용</span></label>{useV2Api && <span className="badge-new">NEW</span>}</div></div>
              <div className="form-group"><div className="label-container"><FontAwesomeIcon icon={faQuestionCircle} color="#6483d1" /><label className="form-label">분석 질문 <span style={{color: 'red'}}>*</span></label></div><textarea value={userCommand} onChange={(e) => setUserCommand(e.target.value)} placeholder={userCommandPlaceholder} required={true} className="form-input form-textarea" />
                {/* [ADDED] Guidance Text */}
                <div className="guidance-text">
                  <FontAwesomeIcon icon={faCircleInfo} className="icon" />
                   구체적이고 명확한 질문일수록 더 유용한 분석 결과를 얻을 수 있습니다
                </div>
              </div>
              <button type="submit" disabled={loading} className={`submit-button ${loading ? 'submit-button-disabled' : 'submit-button-active'}`}>{loading ? <><div className="loading-spinner"></div>분석 요청중...</> : '보고서 생성'}</button>
            </form>
          </div>
        )}

        <div className={`saved-list-sidebar ${savedOpen ? '' : 'closed'}`}>
          <div className="sidebar-header"><button className="btn-new-report" onClick={() => { setResponse(null); setBlockResponse(null); setCurrentStep(1); setOrganizationName(''); setUserCommand(''); setSelectedMonth(''); setReportType('user'); setError(''); }}><FontAwesomeIcon icon={faFileLines} /> 새 보고서 작성</button><button className="saved-toggle-btn" onClick={() => setSavedOpen(!savedOpen)}>{savedOpen ? '◀' : '▶'}</button></div>
          <div className="saved-content">
            <h3 className="saved-title">최근 생성된 보고서</h3>
            {/* [FIXED] 최신순 정렬 적용 */}
            {[...savedReports].sort((a, b) => new Date(b.generated_at).getTime() - new Date(a.generated_at).getTime()) 
            .filter(r => !r.parent_report_id).map(r => (
              <ReportSidebarItem key={r.id} report={r} response={response} onReportClick={async (report) => { if ('blocks' in report && Array.isArray(report.blocks)) { setBlockResponse(report as unknown as ExtendedBlockReportResponse); setResponse(null); } else { setResponse(report); setBlockResponse(null); } setCurrentStep(3); if (!childReportsMap.has(report.id)) await fetchChildReports(report.id); setExpandedReports(prev => new Set(prev).add(report.id)); }} onDelete={handleDeleteReport} childReportsMap={childReportsMap} fetchChildReports={fetchChildReports} expandedReports={expandedReports} setExpandedReports={setExpandedReports} getReportHtml={getReportHtml} downloadReportHTML={downloadReportHTML} />
            ))}
          </div>
        </div>
        {!savedOpen && <div className="sidebar-closed-controls"><button className="sidebar-closed-btn btn-float-new" onClick={() => { setResponse(null); setBlockResponse(null); setCurrentStep(1); setOrganizationName(''); setUserCommand(''); setSelectedMonth(''); setReportType('user'); setError(''); }} title="새 보고서 작성"><FontAwesomeIcon icon={faFileLines} /> 새 보고서</button><button className="sidebar-closed-btn btn-float-toggle" onClick={() => setSavedOpen(!savedOpen)} title="사이드바 열기">▶</button></div>}
        {error && <div className="error-message">{error}</div>}

        {blockResponse && (
          <div className="result-card">
            <h2 className="result-title">{blockResponse.title}</h2>
            {/* [FIXED] V2 Report - Info Summary (구조화된 정보) */}
            <div className="info-summary">
              <div className="info-item">
                <span className="info-label">분석 대상 기관</span>
                <span className="info-value">{blockResponse.organization_name || "N/A"}</span>
              </div>
              <div className="info-item">
                <span className="info-label">분석 질문</span>
                {/* [FIXED] 괄호 내용 제거 */}
                <span className="info-value">{blockResponse.report_topic.replace(/\(분석 기간:.*?\)/, '').trim()}</span>
              </div>
              <div className="info-item">
                <span className="info-label">분석 기간</span>
                <span className="info-value">{blockResponse.analysis_target_dates?.join(', ') || '전체 기간'}</span>
              </div>
              <div className="info-item">
                <span className="info-label">보고서 ID</span>
                <span className="info-value">#{blockResponse.id}</span>
              </div>
            </div>

            <div style={{ marginTop: '20px' }}><ReportRenderer blocks={blockResponse.blocks} /></div>
            
            {/* 🚩 [FIXED] V2 블록: HTML 다운로드 버튼을 독립된 블록으로 복구 */}
            <div className="download-btn-wrapper">
              <button className="download-btn" onClick={() => { 
                  const content = blockResponse.final_report || "내용이 없습니다."; 
                  const html = getReportHtml(content);
                  downloadReportHTML(html, `${blockResponse.organization_name || '분석보고서'}_분석보고서.html`); 
                }}>
                <FontAwesomeIcon icon={faFileCode} /> HTML 다운로드
              </button>
            </div>
            <div className="generated-at">
              생성일시: {getValidDate((blockResponse as any).created_at || blockResponse.generated_at).toLocaleString('ko-KR')} 
              {blockResponse.generation_time_seconds !== undefined && blockResponse.generation_time_seconds !== null && <span> (소요 시간: {formatGenerationTime(blockResponse.generation_time_seconds)})</span>}
            </div>

            <ReportQuestionForm 
              parentReportId={blockResponse.id}
              parentDates={blockResponse.analysis_target_dates || null} 
              onCreateChildReport={handleCreateChildReport}
            />
            <ChildReportsList
              parentReportId={blockResponse.id}
              childReports={childReportsMap.get(blockResponse.id) || []}
              onReportClick={(report) => { if ('blocks' in report && Array.isArray(report.blocks)) { setBlockResponse(report as unknown as ExtendedBlockReportResponse); setResponse(null); } else { setResponse(report); setBlockResponse(null); } setCurrentStep(3); }}
              onFetchChildren={fetchChildReports}
              expandedReports={expandedReports}
              setExpandedReports={setExpandedReports}
              onCreateChildReport={handleCreateChildReport}
              loading={loading}
              childReportsMap={childReportsMap}
              onDelete={handleDeleteReport}
            />
          </div>
        )}

        {response && (
          <div className="result-card">
            <h2 className="result-title">{response.organization_name} 분석 보고서</h2>
            {/* [FIXED] V1 Report - Info Summary (구조화된 정보) */}
            <div className="info-summary">
              <div className="info-item">
                <span className="info-label">분석 대상 기관</span>
                <span className="info-value">{response.organization_name}</span>
              </div>
              <div className="info-item">
                <span className="info-label">분석 질문</span>
                {/* [FIXED] 괄호 내용 제거 */}
                <span className="info-value">{response.report_topic.replace(/\(분석 기간:.*?\)/, '').trim()}</span>
              </div>
              <div className="info-item">
                <span className="info-label">분석 기간</span>
                <span className="info-value">{response.analysis_target_dates?.join(', ') || '전체 기간'}</span>
              </div>
              <div className="info-item">
                <span className="info-label">보고서 ID</span>
                <span className="info-value">#{response.id}</span>
              </div>
            </div>

            <div className="chart-section">
              <h3 className="section-title">월별 연령대별 성별 비율</h3>
              {(response.chart_data?.age_gender_ratio?.length ?? 0) > 0 ? ( 
                (() => {
                  const analysisDates = response.analysis_target_dates || [];
                  const ratioData = response.chart_data!.age_gender_ratio!; 
                  
                  if (analysisDates.length > 1) {
                    return analysisDates.map((dateStr, dateIdx) => {
                      const targetYm = dateStr.replace('-', '');
                      const dateChartData = ratioData.filter((item: any) => item.cri_ym === targetYm);
                      const [year, month] = dateStr.split('-');
                      
                      return (
                        <div key={dateIdx} className="chart-date-group">
                          <h4 className="chart-date-title">{year}년 {parseInt(month)}월</h4>
                          {dateChartData.length > 0 ? (
                            dateChartData.map((data: any, idx: number) => <AgeGenderChart key={`${dateIdx}-${idx}`} data={data} />)
                          ) : (
                            <div className="empty-data">데이터가 없습니다.</div>
                          )}
                        </div>
                      );
                    });
                  } else {
                    return ratioData.map((data: any, idx: number) => <AgeGenderChart key={idx} data={data} />);
                  }
                })()
              ) : (
                <div className="empty-data">
                  <p>차트 데이터가 없습니다.</p>
                </div>
              )}
            </div>
            {response.research_sources.length > 0 && <div className="sources-section"><strong className="sources-title">참고 출처</strong><ul className="sources-list">{response.research_sources.slice(0, 5).map((source, idx) => <li key={idx}><a href={source} target="_blank" rel="noopener noreferrer" className="source-link">{source}</a></li>)}</ul></div>}
            {response.analysis_summary && <div className="analysis-summary"><strong className="analysis-title">분석 요약</strong><div className="analysis-content" dangerouslySetInnerHTML={{ __html: analysisSummaryHtml }} /></div>}
            
            <div className="rating-chart-section"><h3 className="section-title">리뷰 평점 분포</h3>{response.rating_statistics && response.rating_statistics.total_reviews > 0 ? <RatingChart statistics={response.rating_statistics} organizationName={response.organization_name} /> : <div className="empty-data"><p>평점 통계 데이터가 없습니다.</p></div>}</div>
            
            <div className="final-report-section"><strong className="final-report-title">최종 보고서</strong><div className="final-report-content" dangerouslySetInnerHTML={{ __html: finalReportHtml }} /></div>
            
            {/* 🚩 [FIXED] HTML 다운로드 버튼을 독립된 블록으로 복구 */}
            <div className="download-btn-wrapper">
              <button className="download-btn" onClick={() => downloadReportHTML(finalReportHtml, `${response.organization_name}_분석보고서.html`)}>
                <FontAwesomeIcon icon={faFileCode} /> HTML 다운로드
              </button>
            </div>
            {/* 🚩 [FIXED] 생성일시를 별도의 블록으로 복구 */}
            <div className="generated-at">
              생성일시: {getValidDate(response.generated_at).toLocaleString('ko-KR')} 
              {/* 소요 시간이 0이라도 표시되도록 조건 제거 */}
              {response.generation_time_seconds !== undefined && response.generation_time_seconds !== null && <span> (소요 시간: {formatGenerationTime(response.generation_time_seconds)})</span>}
            </div>

            <ReportQuestionForm 
              parentReportId={response.id}
              parentDates={response.analysis_target_dates || null}
              onCreateChildReport={handleCreateChildReport}
            />

            <ChildReportsList
              parentReportId={response.id}
              childReports={childReportsMap.get(response.id) || []}
              onReportClick={(report) => {
                if ('blocks' in report && Array.isArray(report.blocks)) {
                  setBlockResponse(report as unknown as ExtendedBlockReportResponse);
                  setResponse(null);
                } else {
                  setResponse(report);
                  setBlockResponse(null);
                }
                setCurrentStep(3);
              }}
              onFetchChildren={fetchChildReports}
              expandedReports={expandedReports}
              setExpandedReports={setExpandedReports}
              onCreateChildReport={handleCreateChildReport}
              loading={loading}
              childReportsMap={childReportsMap}
              onDelete={handleDeleteReport}
            />
          </div>
        )}
      </div>
    </div>
  );
}

export default App;