import React, { useState, useMemo, useCallback, useEffect, useRef } from 'react';
import './App.css'; 
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { marked } from 'marked';
import { AgeGenderChart } from './AgeGenderChart';
import { RatingChart } from './RatingChart';
import { ReportRenderer } from './components/report';
import type { BlockReportResponse } from './types/report';

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
    faFileCode,
    faFileLines,
    faChevronDown,
    faChevronUp
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
  parent_report_id?: number | null;
  depth: number;
  report_type?: string | null;
  analysis_target_dates?: string[] | null;
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


function App() {
  const [organizationName, setOrganizationName] = useState('');
  const [userCommand, setUserCommand] = useState('');
  const [selectedMonth, setSelectedMonth] = useState('');
  const [reportType, setReportType] = useState<'user' | 'operator'>('user');
  const [response, setResponse] = useState<AdvancedReportResponse | null>(null);
  const [blockResponse, setBlockResponse] = useState<BlockReportResponse | null>(null); // v2 API 응답
  const [useV2Api, setUseV2Api] = useState(false); // v2 API 사용 여부
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  
  // 3단계 진행 표시 (from HEAD)
  const [currentStep, setCurrentStep] = useState(1);
  
  // 사이드바 열림/닫힘 상태 (from Incoming)
  const [savedOpen, setSavedOpen] = useState(true); 
  
  /* 사용자가 생성한 보고서 저장 */
  const [savedReports, setSavedReports] = useState<AdvancedReportResponse[]>(
    JSON.parse(localStorage.getItem("savedReports") || "[]")
  );

  // 하위 보고서 관리 (reportId -> childReports[])
  const [childReportsMap, setChildReportsMap] = useState<Map<number, AdvancedReportResponse[]>>(new Map());
  
  // 보고서 접기/펼치기 상태 (reportId -> isExpanded)
  const [expandedReports, setExpandedReports] = useState<Set<number>>(new Set());
  
  // 하위 보고서 로딩 상태 추적 (ref를 사용하여 무한 루프 방지)
  const loadingChildReportsRef = useRef<Set<number>>(new Set());
  const loadedReportsRef = useRef<Set<number>>(new Set());

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
   * 하위 보고서 조회
   * ---------------------------- */
  const fetchChildReports = useCallback(async (reportId: number) => {
    // 이미 로드된 경우 다시 호출하지 않음
    if (loadedReportsRef.current.has(reportId)) {
      // 이미 로드된 데이터는 childReportsMap에서 가져옴
      return [];
    }
    
    // 이미 로딩 중인 경우 다시 호출하지 않음
    if (loadingChildReportsRef.current.has(reportId)) {
      return [];
    }
    
    // 로딩 시작
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
        // 로드 완료 표시
        loadedReportsRef.current.add(reportId);
        loadingChildReportsRef.current.delete(reportId);
        return children;
      } else {
        loadingChildReportsRef.current.delete(reportId);
      }
    } catch (err) {
      console.error('Failed to fetch child reports:', err);
      loadingChildReportsRef.current.delete(reportId);
    }
    return [];
  }, []); // 의존성 배열 비움 - ref를 사용하므로 재생성 불필요

  /** -----------------------------
   * 보고서 삭제 핸들러
   * ---------------------------- */
  const handleDeleteReport = (id: number) => {
    const updated = savedReports.filter(report => report.id !== id);
    setSavedReports(updated);
    localStorage.setItem("savedReports", JSON.stringify(updated));
    if (response?.id === id) setResponse(null);
    // 하위 보고서 맵에서도 제거
    setChildReportsMap(prev => {
      const newMap = new Map(prev);
      newMap.delete(id);
      return newMap;
    });
    // ref에서도 제거
    loadedReportsRef.current.delete(id);
    loadingChildReportsRef.current.delete(id);
  };

  /** -----------------------------
   * 월 선택 포맷팅
   * ---------------------------- */
  const formatMonthForQuery = (monthValue: string): string => {
    if (!monthValue) return '';
    const [year, month] = monthValue.split('-');
    return `${year}년 ${parseInt(month)}월`;
  };

  /** -----------------------------
   * 보고서 제출 핸들러 (Merged)
   * ---------------------------- */
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setCurrentStep(2); // (from HEAD) 분석 진행 단계
    setLoading(true);
    setError('');
    setResponse(null);
    setBlockResponse(null); // v2 응답도 초기화

    // (from Incoming) 선택값을 질문에 포함
    let finalCommand = userCommand;
    if (organizationName) {
      finalCommand = `${organizationName}, ${finalCommand}`;
    }
    if (selectedMonth) {
      const monthText = formatMonthForQuery(selectedMonth);
      finalCommand = `${finalCommand} (분석 기간: ${monthText})`;
    }

    try {
      // selectedMonth를 analysis_target_dates 배열로 변환
      const analysisTargetDates = selectedMonth ? [selectedMonth] : undefined;
      
      // API 엔드포인트 선택 (v2 또는 기존)
      const apiEndpoint = useV2Api ? `${API_BASE}/report/v2` : `${API_BASE}/report/advanced`;
      
      const res = await fetch(apiEndpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          organization_name: organizationName,
          user_command: finalCommand,
          report_type: reportType,
          analysis_target_dates: analysisTargetDates // 선택한 월을 날짜 배열로 전달
        })
      });

      if (res.ok) {
        const result = await res.json();
        
        if (useV2Api) {
          // v2 API 응답 처리
          setBlockResponse(result as BlockReportResponse);
          setResponse(null); // 기존 응답 초기화
        } else {
          // 기존 API 응답 처리
          setResponse(result);
          setBlockResponse(null);
          
          /* 사용자가 생성한 보고서 저장 (기존 방식만) */
          const updated = [...savedReports, result];
          setSavedReports(updated);
          localStorage.setItem("savedReports", JSON.stringify(updated));
          
          // 하위 보고서인 경우 부모 보고서의 하위 보고서 목록 업데이트
          if (result.parent_report_id) {
            await fetchChildReports(result.parent_report_id);
          }
        }
        
        setCurrentStep(3); // 결과 확인 단계
      } else {
        const errorData = await res.json();
        setError(errorData.detail || '보고서 생성 실패');
        setCurrentStep(1); // 실패하면 다시 1단계
      }
    } catch (err) {
      setError('서버 연결 오류');
      setCurrentStep(1);
    } finally {
      setLoading(false);
    }
  };

  /** -----------------------------
   * 하위 보고서 생성 핸들러
   * ---------------------------- */
  const handleCreateChildReport = async (parentReportId: number, question: string, additionalDates?: string[]) => {
    // 상단 질문창의 loading 상태를 변경하지 않음 (UX 개선)
    setError('');
    
    try {
      // 부모 보고서 정보 가져오기
      const parentReport = savedReports.find(r => r.id === parentReportId) || 
                          Array.from(childReportsMap.values()).flat().find(r => r.id === parentReportId) ||
                          response; // 현재 보고서도 확인
      
      if (!parentReport) {
        setError('부모 보고서를 찾을 수 없습니다.');
        return;
      }

      const res = await fetch(`${API_BASE}/report/advanced`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          organization_name: parentReport.organization_name,
          user_command: question,
          report_type: parentReport.report_type || 'operator', // 부모 보고서의 타입 상속
          parent_report_id: parentReportId,
          additional_dates: additionalDates || [] // 추가 날짜 전달
        })
      });

      if (res.ok) {
        const result = await res.json();
        
        // 하위 보고서 목록 업데이트
        await fetchChildReports(parentReportId);
        
        // 새로 생성된 보고서를 현재 보고서로 설정
        setResponse(result);
        setCurrentStep(3); // 결과 확인 단계로 이동하여 상단 질문창 숨김
        
        // 저장된 보고서 목록에도 추가
        const updated = [...savedReports, result];
        setSavedReports(updated);
        localStorage.setItem("savedReports", JSON.stringify(updated));
        
        // ref에서 로드 상태 초기화 (새 보고서를 위해)
        loadedReportsRef.current.delete(result.id);
      } else {
        const errorData = await res.json();
        setError(errorData.detail || '하위 보고서 생성 실패');
      }
    } catch (err) {
      setError('서버 연결 오류');
    }
  };

  const submitButtonClass = `submit-button ${loading ? 'submit-button-disabled' : 'submit-button-active'}`;

  // 텍스트 영역의 예시 문구
  const userCommandPlaceholder = 
  `예: 2030 세대의 관람객 유입을 위한 이벤트 기획에 대해 분석하고, 최근 전시 정보와 대표 소장품을 조사해서 보고서를 작성해줘`;

  // (from Incoming) 분석 요약 마크다운을 HTML로 변환
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

  // (from Incoming) 최종 보고서 마크다운을 HTML로 변환 (더 나은 파싱 로직)
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

  // 보고서 질문 폼 컴포넌트
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
      
      // YYYY-MM 형식 검증
      const dateRegex = /^\d{4}-\d{2}$/;
      if (!dateRegex.test(newDateInput)) {
        alert('날짜 형식이 올바르지 않습니다. YYYY-MM 형식으로 입력해주세요. (예: 2025-01)');
        return;
      }
      
      // 중복 체크
      const allDates = [...(parentDates || []), ...additionalDates];
      if (allDates.includes(newDateInput)) {
        alert('이미 추가된 날짜입니다.');
        return;
      }
      
      // 추가 및 정렬
      const updated = [...additionalDates, newDateInput].sort();
      setAdditionalDates(updated);
      setNewDateInput('');
    };

    const handleRemoveDate = (dateToRemove: string) => {
      setAdditionalDates(additionalDates.filter(d => d !== dateToRemove));
    };

    return (
      <div style={{ 
        marginTop: '30px', 
        padding: '20px', 
        backgroundColor: '#f9fafb', 
        borderRadius: '8px',
        border: '1px solid #e5e7eb'
      }}>
        <div style={{ marginBottom: '15px', display: 'flex', alignItems: 'center', gap: '8px' }}>
          <FontAwesomeIcon icon={faQuestionCircle} color="#6483d1" />
          <strong style={{ fontSize: '16px' }}>이 보고서에 대해 추가 질문하기</strong>
        </div>
        
        {/* 부모 보고서의 날짜 표시 */}
        {parentDates && parentDates.length > 0 && (
          <div style={{ marginBottom: '15px', padding: '12px', backgroundColor: '#ffffff', borderRadius: '6px', border: '1px solid #e5e7eb' }}>
            <div style={{ marginBottom: '8px', fontSize: '13px', color: '#6b7280', fontWeight: '500' }}>
              분석 대상 날짜 (부모 보고서)
            </div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
              {parentDates.map((date, idx) => {
                // YYYY-MM 형식을 YYYY년 M월 형식으로 변환
                const formatDate = (dateStr: string) => {
                  if (!dateStr) return dateStr;
                  const parts = dateStr.split('-');
                  if (parts.length === 2) {
                    return `${parts[0]}년 ${parseInt(parts[1])}월`;
                  }
                  return dateStr;
                };
                
                return (
                  <span
                    key={idx}
                    style={{
                      padding: '4px 10px',
                      backgroundColor: '#e5e7eb',
                      color: '#374151',
                      borderRadius: '4px',
                      fontSize: '12px',
                      fontWeight: '500'
                    }}
                  >
                    {formatDate(date)}
                  </span>
                );
              })}
            </div>
          </div>
        )}
        
        {/* 날짜 추가 UI */}
        <div style={{ marginBottom: '15px', padding: '12px', backgroundColor: '#ffffff', borderRadius: '6px', border: '1px solid #e5e7eb' }}>
          <div style={{ marginBottom: '8px', fontSize: '13px', color: '#6b7280', fontWeight: '500' }}>
            추가 분석 날짜
          </div>
          <div style={{ display: 'flex', gap: '8px', marginBottom: '10px' }}>
            <input
              type="month"
              value={newDateInput}
              onChange={(e) => {
                const value = e.target.value;
                if (value) {
                  // YYYY-MM 형식으로 변환
                  setNewDateInput(value);
                }
              }}
              style={{
                padding: '6px 10px',
                borderRadius: '4px',
                border: '1px solid #d1d5db',
                fontSize: '13px',
                outline: 'none'
              }}
              disabled={isSubmitting}
            />
            <button
              type="button"
              onClick={handleAddDate}
              disabled={isSubmitting || !newDateInput.trim()}
              style={{
                padding: '6px 12px',
                backgroundColor: isSubmitting || !newDateInput.trim() ? '#9ca3af' : '#6483d1',
                color: 'white',
                border: 'none',
                borderRadius: '4px',
                cursor: isSubmitting || !newDateInput.trim() ? 'not-allowed' : 'pointer',
                fontSize: '13px',
                fontWeight: '500'
              }}
            >
              추가
            </button>
          </div>
          {additionalDates.length > 0 && (
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
              {additionalDates.map((date, idx) => (
                <span
                  key={idx}
                  style={{
                    padding: '4px 10px',
                    backgroundColor: '#dbeafe',
                    color: '#1e40af',
                    borderRadius: '4px',
                    fontSize: '12px',
                    fontWeight: '500',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '6px'
                  }}
                >
                  {date}
                  <button
                    type="button"
                    onClick={() => handleRemoveDate(date)}
                    disabled={isSubmitting}
                    style={{
                      background: 'none',
                      border: 'none',
                      color: '#1e40af',
                      cursor: isSubmitting ? 'not-allowed' : 'pointer',
                      fontSize: '14px',
                      padding: '0',
                      lineHeight: '1',
                      fontWeight: 'bold'
                    }}
                  >
                    ×
                  </button>
                </span>
              ))}
            </div>
          )}
        </div>
        
        <form onSubmit={handleSubmit}>
          <textarea
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="예: 이 전시의 예상 관람객 수는? 구체적인 마케팅 전략은?"
            style={{
              width: '100%',
              minHeight: '80px',
              padding: '12px',
              borderRadius: '6px',
              border: '1px solid #d1d5db',
              fontSize: '14px',
              fontFamily: 'inherit',
              resize: 'vertical',
              outline: 'none'
            }}
            disabled={isSubmitting}
            autoFocus={false}
          />
          <button
            type="submit"
            disabled={isSubmitting || !question.trim()}
            style={{
              marginTop: '10px',
              padding: '10px 20px',
              backgroundColor: isSubmitting || !question.trim() ? '#9ca3af' : '#6483d1',
              color: 'white',
              border: 'none',
              borderRadius: '6px',
              cursor: isSubmitting || !question.trim() ? 'not-allowed' : 'pointer',
              fontSize: '14px',
              fontWeight: '500'
            }}
          >
            {isSubmitting ? '생성 중...' : '질문 제출'}
          </button>
        </form>
      </div>
    );
  };

  // 하위 보고서 목록 컴포넌트 (재귀적)
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
  }> = ({ 
    parentReportId, 
    childReports, 
    onReportClick, 
    onFetchChildren,
    expandedReports,
    setExpandedReports,
    onCreateChildReport,
    loading,
    childReportsMap
  }) => {
    const isExpanded = expandedReports.has(parentReportId);
    const hasChildren = childReports.length > 0;

    useEffect(() => {
      // 확장되었고, 하위 보고서가 없고, 아직 로드되지 않은 경우에만 호출
      const alreadyLoaded = loadedReportsRef.current.has(parentReportId);
      const isLoading = loadingChildReportsRef.current.has(parentReportId);
      
      if (isExpanded && childReports.length === 0 && !alreadyLoaded && !isLoading) {
        onFetchChildren(parentReportId);
      }
      // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [isExpanded, parentReportId, childReports.length]); // onFetchChildren은 ref를 사용하므로 제외

    const toggleExpand = () => {
      setExpandedReports(prev => {
        const newSet = new Set(prev);
        if (newSet.has(parentReportId)) {
          newSet.delete(parentReportId);
        } else {
          newSet.add(parentReportId);
        }
        return newSet;
      });
    };

    if (!hasChildren && !isExpanded) return null;

    return (
      <div style={{ marginTop: '20px', marginLeft: '20px', borderLeft: '2px solid #e5e7eb', paddingLeft: '20px' }}>
        {hasChildren && (
          <button
            onClick={toggleExpand}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              marginBottom: '10px',
              padding: '6px 12px',
              backgroundColor: 'transparent',
              border: '1px solid #d1d5db',
              borderRadius: '6px',
              cursor: 'pointer',
              fontSize: '13px',
              color: '#6b7280'
            }}
          >
            <FontAwesomeIcon icon={isExpanded ? faChevronUp : faChevronDown} />
            <span>하위 보고서 {childReports.length}개 {isExpanded ? '접기' : '펼치기'}</span>
          </button>
        )}
        
        {isExpanded && childReports.map((childReport) => (
          <div key={childReport.id} style={{ marginBottom: '30px' }}>
            <div style={{ 
              padding: '15px', 
              backgroundColor: '#ffffff', 
              borderRadius: '8px',
              border: '1px solid #e5e7eb',
              marginBottom: '15px'
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '10px' }}>
                <span style={{ color: '#9ca3af', fontSize: '14px' }}>└</span>
                <strong style={{ fontSize: '14px', color: '#6b7280' }}>하위 보고서</strong>
              </div>
              <div 
                onClick={() => {
                  onReportClick(childReport);
                  // 하위 보고서의 하위 보고서도 로드
                  if (!childReportsMap.has(childReport.id)) {
                    onFetchChildren(childReport.id);
                  }
                }}
                style={{ cursor: 'pointer', marginBottom: '10px' }}
              >
                <div style={{ marginBottom: '8px' }}>
                  <strong>주제:</strong> {childReport.report_topic}
                </div>
                <div style={{ fontSize: '12px', color: '#6b7280' }}>
                  생성일시: {new Date(childReport.generated_at).toLocaleString('ko-KR')}
                </div>
              </div>
            </div>
            
            {/* 하위 보고서의 하위 보고서 (재귀) */}
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
            />
          </div>
        ))}
      </div>
    );
  };

  // 사이드바 보고서 아이템 컴포넌트 (재귀적)
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
  }> = ({ 
    report, 
    response, 
    onReportClick, 
    onDelete,
    childReportsMap,
    fetchChildReports,
    expandedReports,
    setExpandedReports,
    getReportHtml,
    downloadReportHTML,
    depth = 0
  }) => {
    const isExpanded = expandedReports.has(report.id);
    const childReports = childReportsMap.get(report.id) || [];
    const hasChildren = childReports.length > 0;

    useEffect(() => {
      // 확장되었고, 하위 보고서가 없고, 아직 로드되지 않은 경우에만 호출
      const alreadyLoaded = loadedReportsRef.current.has(report.id);
      const isLoading = loadingChildReportsRef.current.has(report.id);
      
      if (isExpanded && childReports.length === 0 && !alreadyLoaded && !isLoading) {
        fetchChildReports(report.id);
      }
      // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [isExpanded, report.id, childReports.length]); // fetchChildReports는 ref를 사용하므로 제외

    const toggleExpand = (e: React.MouseEvent) => {
      e.stopPropagation();
      setExpandedReports(prev => {
        const newSet = new Set(prev);
        if (newSet.has(report.id)) {
          newSet.delete(report.id);
        } else {
          newSet.add(report.id);
        }
        return newSet;
      });
    };

    return (
      <div>
        <div 
          className={`saved-card ${response?.id === report.id ? 'selected' : ''}`}
          onClick={() => onReportClick(report)}
          style={{ marginLeft: `${depth * 20}px` }}
        >
          <div className="saved-card-top">
            <div className="saved-left" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              {depth > 0 && <span style={{ color: '#9ca3af', fontSize: '12px' }}>└</span>}
              <div>
                <div className="saved-organization">{report.organization_name}</div>
                <div className="saved-topic">{report.report_topic}</div>
              </div>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              {hasChildren && (
                <button
                  onClick={toggleExpand}
                  style={{
                    padding: '4px 8px',
                    backgroundColor: 'transparent',
                    border: '1px solid #d1d5db',
                    borderRadius: '4px',
                    cursor: 'pointer',
                    fontSize: '12px'
                  }}
                >
                  {isExpanded ? '▼' : '▶'}
                </button>
              )}
              <span className="saved-status">완료</span>
              <button
                className="saved-delete-btn"
                onClick={e => {
                  e.stopPropagation();
                  onDelete(report.id);
                }}
              >
                삭제
              </button>
            </div>
          </div>
          
          <div className="saved-card-bottom">
            <span className="saved-date">
              {new Date(report.generated_at).toLocaleDateString("ko-KR")}
            </span>
            <div className="saved-tag-actions">
              <span className="saved-tag">종합 분석</span>
              <button
                className="download-btn"
                onClick={e => {
                  e.stopPropagation();
                  const reportHtml = getReportHtml(report.final_report);
                  downloadReportHTML(reportHtml, `${report.organization_name}_분석보고서.html`);
                }}
              >
                <FontAwesomeIcon icon={faFileCode} />
              </button>
            </div>
          </div>
        </div>
        
        {isExpanded && hasChildren && (
          <div>
            {childReports.map(childReport => (
              <ReportSidebarItem
                key={childReport.id}
                report={childReport}
                response={response}
                onReportClick={onReportClick}
                onDelete={onDelete}
                childReportsMap={childReportsMap}
                fetchChildReports={fetchChildReports}
                expandedReports={expandedReports}
                setExpandedReports={setExpandedReports}
                getReportHtml={getReportHtml}
                downloadReportHTML={downloadReportHTML}
                depth={depth + 1}
              />
            ))}
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="app-container">
      <div className="content-wrapper">

        {/* 제목 */}
        <h1 className="main-title">분석 보고서 생성</h1>
        <p className="subtitle">분석하고자 하는 기관명과 구체적인 질문을 입력해주세요</p>

        {/* (from HEAD) 진행 단계 표시 */}
        <div className="stepper">
          <div className={`step ${currentStep >= 1 ? 'active' : ''}`}>
            <div className="circle">1</div>
            <div className="label">정보 입력</div>
          </div>
          <div className={`step ${currentStep >= 2 ? 'active' : ''}`}>
            <div className="circle">2</div>
            <div className="label">분석 진행</div>
          </div>
          <div className={`step ${currentStep >= 3 ? 'active' : ''}`}>
            <div className="circle">3</div>
            <div className="label">결과 확인</div>
          </div>
        </div>

        {/* 입력 폼 - currentStep이 3이 아닐 때만 표시 */}
        {currentStep !== 3 && (
        <div className="card-form">
          <form onSubmit={handleSubmit}>
            
            {/* 기관 선택 */}
            <div className="form-group">
              <div className="label-container">
                <FontAwesomeIcon icon={faBuilding} color="#6483d1" />
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

            {/* (from Incoming) 월 선택 */}
            <div className="form-group">
              <div className="label-container">
                <FontAwesomeIcon icon={faCalendarAlt} color="#6483d1" />
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

            {/* (from Incoming) 보고서 타입 선택 */}
            <div className="form-group">
              <div className="label-container">
                <FontAwesomeIcon icon={faFileLines} color="#6483d1" />
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

            {/* v2 API 토글 (Server-Driven UI) */}
            <div className="form-group">
              <div className="label-container">
                <FontAwesomeIcon icon={faFileCode} color="#6483d1" />
                <label className="form-label">렌더링 방식</label>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer' }}>
                  <input
                    type="checkbox"
                    checked={useV2Api}
                    onChange={(e) => setUseV2Api(e.target.checked)}
                    style={{ width: '18px', height: '18px', cursor: 'pointer' }}
                  />
                  <span style={{ fontSize: '14px', color: '#374151' }}>
                    Server-Driven UI (v2 API) 사용
                  </span>
                </label>
                {useV2Api && (
                  <span style={{ 
                    fontSize: '12px', 
                    color: '#059669', 
                    backgroundColor: '#d1fae5', 
                    padding: '2px 8px', 
                    borderRadius: '4px' 
                  }}>
                    NEW
                  </span>
                )}
              </div>
              <div className="guidance-text">
                <FontAwesomeIcon icon={faCircleInfo} className="icon" />
                {useV2Api 
                  ? '백엔드에서 블록 기반으로 구조화된 보고서를 생성합니다 (실험적)'
                  : '기존 마크다운 방식의 보고서를 생성합니다'}
              </div>
            </div>

            {/* 분석 질문 필드 */}
            <div className="form-group">
              <div className="label-container">
                <FontAwesomeIcon icon={faQuestionCircle} color="#6483d1" />
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
        )}

        {/* (Merged) 최근 생성된 보고서 사이드바 */}
        <div className={`saved-list-sidebar ${savedOpen ? '' : 'closed'}`}>
          
          {/* 사이드바 상단 버튼들 */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '10px' }}>
            {/* 새 보고서 작성 버튼 */}
            <button
              onClick={() => {
                setResponse(null);
                setCurrentStep(1);
                setOrganizationName('');
                setUserCommand('');
                setSelectedMonth('');
                setReportType('user');
                setError('');
              }}
              style={{
                flex: 1,
                padding: '10px 16px',
                backgroundColor: '#6483d1',
                color: 'white',
                border: 'none',
                borderRadius: '6px',
                cursor: 'pointer',
                fontSize: '14px',
                fontWeight: '500',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '6px',
                transition: 'background-color 0.2s'
              }}
              onMouseEnter={(e) => e.currentTarget.style.backgroundColor = '#5a73b8'}
              onMouseLeave={(e) => e.currentTarget.style.backgroundColor = '#6483d1'}
            >
              <FontAwesomeIcon icon={faFileLines} />
              새 보고서 작성
            </button>
            
            {/* 사이드바 토글 버튼 */}
            <button 
              className="saved-toggle-btn"
              onClick={() => setSavedOpen(!savedOpen)}
              style={{ flexShrink: 0 }}
            >
              {savedOpen ? '◀' : '▶'}
            </button>
          </div>

          <div className="saved-content">
            <h3 className="saved-title">최근 생성된 보고서</h3>

            {savedReports.length === 0 ? (
              <div className="saved-empty">아직 저장된 보고서가 없습니다.</div>
            ) : (
              <div className="saved-cards">
                {/* (from HEAD) .reverse()로 최신순 정렬 */}
                {[...savedReports]
                  .filter(r => !r.parent_report_id) // 원본 보고서만 표시
                  .reverse()
                  .map(r => (
                  <ReportSidebarItem
                    key={r.id}
                    report={r}
                    response={response}
                    onReportClick={async (report) => {
                      setResponse(report);
                      setCurrentStep(3); // 결과 확인 단계로 이동하여 상단 질문창 숨김
                      // 하위 보고서 로드
                      if (!childReportsMap.has(report.id)) {
                        await fetchChildReports(report.id);
                      }
                      // 보고서를 확장 상태로 설정
                      setExpandedReports(prev => new Set(prev).add(report.id));
                    }}
                    onDelete={handleDeleteReport}
                    childReportsMap={childReportsMap}
                    fetchChildReports={fetchChildReports}
                    expandedReports={expandedReports}
                    setExpandedReports={setExpandedReports}
                    getReportHtml={getReportHtml}
                    downloadReportHTML={downloadReportHTML}
                  />
                ))}
              </div>
            )}
          </div>
        </div>

        {/* 사이드바 열기 버튼 및 새 보고서 작성 버튼 (닫혔을 때) */}
        {!savedOpen && (
          <div style={{ 
            position: 'fixed', 
            right: '0', 
            top: '20px',
            display: 'flex',
            flexDirection: 'column',
            gap: '8px',
            zIndex: 1000,
            alignItems: 'flex-end',
            pointerEvents: 'none'
          }}>
            <button
              onClick={() => {
                setResponse(null);
                setCurrentStep(1);
                setOrganizationName('');
                setUserCommand('');
                setSelectedMonth('');
                setReportType('user');
                setError('');
              }}
              style={{
                padding: '12px 16px',
                backgroundColor: '#6483d1',
                color: 'white',
                border: 'none',
                borderRadius: '6px 0 0 6px',
                cursor: 'pointer',
                fontSize: '13px',
                fontWeight: '500',
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                boxShadow: '0 2px 8px rgba(0,0,0,0.15)',
                transition: 'background-color 0.2s',
                whiteSpace: 'nowrap',
                pointerEvents: 'auto'
              }}
              onMouseEnter={(e) => e.currentTarget.style.backgroundColor = '#5a73b8'}
              onMouseLeave={(e) => e.currentTarget.style.backgroundColor = '#6483d1'}
              title="새 보고서 작성"
            >
              <FontAwesomeIcon icon={faFileLines} />
              새 보고서
            </button>
            <button 
              onClick={() => setSavedOpen(!savedOpen)}
              style={{
                padding: '10px 12px',
                backgroundColor: '#f3f4f6',
                color: '#374151',
                border: '1px solid #d1d5db',
                borderRadius: '6px 0 0 6px',
                cursor: 'pointer',
                fontSize: '14px',
                fontWeight: '500',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                boxShadow: '0 2px 8px rgba(0,0,0,0.15)',
                transition: 'background-color 0.2s',
                pointerEvents: 'auto',
                minWidth: '40px',
                minHeight: '40px'
              }}
              onMouseEnter={(e) => e.currentTarget.style.backgroundColor = '#e5e7eb'}
              onMouseLeave={(e) => e.currentTarget.style.backgroundColor = '#f3f4f6'}
              title="사이드바 열기"
            >
              ▶
            </button>
          </div>
        )}

        {/* 오류 메시지 */}
        {error && (
          <div className="error-message">
            {error}
          </div>
        )}

        {/* v2 API 응답 (Server-Driven UI) */}
        {blockResponse && (
          <div className="result-card">
            <h2 className="result-title">
              {blockResponse.title}
            </h2>
            
            <div className="info-summary">
              <div style={{ marginBottom: '10px' }}>
                <strong>주제:</strong> {blockResponse.report_topic}
              </div>
              <div>
                <strong>보고서 ID:</strong> {blockResponse.id}
              </div>
            </div>

            {/* Server-Driven UI 블록 렌더링 */}
            <div style={{ marginTop: '20px' }}>
              <ReportRenderer 
                blocks={blockResponse.blocks}
              />
            </div>

            {/* 참고 출처 */}
            {blockResponse.research_sources && blockResponse.research_sources.length > 0 && (
              <div className="sources-section">
                <strong className="sources-title">참고 출처</strong>
                <ul className="sources-list">
                  {blockResponse.research_sources.slice(0, 5).map((source, idx) => (
                    <li key={idx}>
                      <a href={source} target="_blank" rel="noopener noreferrer" className="source-link">
                        {source}
                      </a>
                    </li>
                  ))}
                </ul>
                {blockResponse.research_sources.length > 5 && (
                  <div className="more-sources">
                    외 {blockResponse.research_sources.length - 5}개
                  </div>
                )}
              </div>
            )}

            {/* 생성 시간 */}
            <div className="generated-at">
              생성일시: {new Date(blockResponse.created_at).toLocaleString('ko-KR')}
              {blockResponse.generation_time_seconds > 0 && (
                <span> (소요 시간: {formatGenerationTime(blockResponse.generation_time_seconds)})</span>
              )}
            </div>
          </div>
        )}

        {/* 기존 API 응답 (마크다운 방식) */}
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

            {/* 연령/성별 차트 */}
            <div className="chart-section" style={{ marginBottom: '30px', padding: '20px', backgroundColor: '#f9fafb', borderRadius: '8px' }}>
              <h3 style={{ marginBottom: '20px', fontSize: '20px', fontWeight: '600' }}>
                월별 연령대별 성별 비율
              </h3>
              {response.chart_data?.age_gender_ratio && response.chart_data.age_gender_ratio.length > 0 ? (
                (() => {
                  // 여러 날짜 분석인 경우 날짜별로 차트 표시
                  const analysisDates = response.analysis_target_dates || [];
                  const isMultiDate = analysisDates.length > 1;
                  
                  if (isMultiDate && analysisDates.length > 0) {
                    // 날짜별로 차트 데이터 필터링
                    return analysisDates.map((dateStr, dateIdx) => {
                      // YYYY-MM 형식을 YYYYMM 형식으로 변환
                      const targetYm = dateStr.replace('-', '');
                      const dateChartData = response.chart_data.age_gender_ratio.filter(
                        (item: any) => item.cri_ym === targetYm
                      );
                      
                      // 날짜 포맷팅 (예: "2025-01" -> "2025년 1월")
                      const [year, month] = dateStr.split('-');
                      const formattedDate = `${year}년 ${parseInt(month)}월`;
                      
                      return (
                        <div key={dateIdx} style={{ marginBottom: dateIdx < analysisDates.length - 1 ? '40px' : '0', paddingBottom: dateIdx < analysisDates.length - 1 ? '30px' : '0', borderBottom: dateIdx < analysisDates.length - 1 ? '2px solid #e5e7eb' : 'none' }}>
                          <h4 style={{ marginBottom: '15px', fontSize: '16px', fontWeight: '600', color: '#374151' }}>
                            {formattedDate}
                          </h4>
                          {dateChartData.length > 0 ? (
                            dateChartData.map((data: any, idx: number) => (
                              <AgeGenderChart 
                                key={`${dateIdx}-${idx}`} 
                                data={data}
                              />
                            ))
                          ) : (
                            <div style={{ padding: '20px', textAlign: 'center', color: '#666' }}>
                              <p>{formattedDate} 데이터가 없습니다.</p>
                            </div>
                          )}
                        </div>
                      );
                    });
                  } else {
                    // 단일 날짜 또는 날짜 정보가 없는 경우 기존 로직 유지
                    return response.chart_data.age_gender_ratio.map((data: any, idx: number) => (
                      <AgeGenderChart 
                        key={idx} 
                        data={data}
                      />
                    ));
                  }
                })()
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

            {/* 참고 출처 */}
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

            {/* 분석 요약 */}
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

            {/* (from Incoming) 평점 차트 */}
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

            {/* 최종 보고서 */}
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

            {/* 생성 시간 */}
            <div className="generated-at">
              생성일시: {new Date(response.generated_at).toLocaleString('ko-KR')}
              {response.generation_time_seconds > 0 && (
                <span> (소요 시간: {formatGenerationTime(response.generation_time_seconds)})</span>
              )}
            </div>

            {/* 하위 보고서 질문창 */}
            <ReportQuestionForm 
              parentReportId={response.id}
              parentDates={response.analysis_target_dates || null}
              onCreateChildReport={handleCreateChildReport}
            />

            {/* 하위 보고서 목록 */}
            <ChildReportsList
              parentReportId={response.id}
              childReports={childReportsMap.get(response.id) || []}
              onReportClick={(report) => {
                setResponse(report);
                setCurrentStep(3); // 결과 확인 단계로 이동하여 상단 질문창 숨김
              }}
              onFetchChildren={fetchChildReports}
              expandedReports={expandedReports}
              setExpandedReports={setExpandedReports}
              onCreateChildReport={handleCreateChildReport}
              loading={loading}
              childReportsMap={childReportsMap}
            />
          </div>
        )}
      </div>
    </div>
  );
}

export default App;