import React from 'react';
import type { BlockType } from '../../types/report';
import { Block } from './Block';
import './report.css';

interface Props {
  blocks: BlockType[];
  title?: string;
  createdAt?: string;
}

export const ReportRenderer: React.FC<Props> = ({ blocks, title, createdAt }) => {
  return (
    <div className="report-container">
      {title && (
        <div className="report-header">
          <h2 className="report-title">{title}</h2>
          {createdAt && (
            <p className="report-meta">생성일: {new Date(createdAt).toLocaleString('ko-KR')}</p>
          )}
        </div>
      )}
      <div className="report-blocks">
        {blocks.map((block, idx) => (
          <Block key={idx} block={block} />
        ))}
      </div>
    </div>
  );
};

