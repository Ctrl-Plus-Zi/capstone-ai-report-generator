import React from 'react';
import type { RowBlock as RowBlockType } from '../../types/report';
import { MarkdownBlock } from './MarkdownBlock';
import { ChartBlock } from './ChartBlock';
import { ImageBlock } from './ImageBlock';
import { TableBlock } from './TableBlock';

interface Props {
  block: RowBlockType;
}

export const RowBlock: React.FC<Props> = ({ block }) => {
  const renderChild = (child: RowBlockType['children'][number], idx: number) => {
    switch (child.type) {
      case 'markdown':
        return <MarkdownBlock key={idx} block={child} />;
      case 'chart':
        return <ChartBlock key={idx} block={child} />;
      case 'image':
        return <ImageBlock key={idx} block={child} />;
      case 'table':
        return <TableBlock key={idx} block={child} />;
      default:
        return null;
    }
  };

  return (
    <div className="row-block" style={{ gap: block.gap || '16px' }}>
      {block.children.map((child, idx) => renderChild(child, idx))}
    </div>
  );
};

