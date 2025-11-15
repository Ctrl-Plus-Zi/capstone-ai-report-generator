// ReportDownload.tsx
import React from "react";

interface ReportDownloadProps {
  reportHtml: string;
  fileName: string;
}

const ReportDownload: React.FC<ReportDownloadProps> = ({ reportHtml, fileName }) => {
  const handleDownload = () => {
    const blob = new Blob([reportHtml], { type: "text/html;charset=utf-8" });
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = fileName.replace(/\.pdf$/, ".html"); // PDF 대신 HTML로 저장
    link.click();
    URL.revokeObjectURL(link.href);
  };

  return (
    <button className="download-btn" onClick={handleDownload}>
      HTML 다운로드
    </button>
  );
};

export default ReportDownload;
