import React from 'react';
import type { BlockType } from '../../types/report';
import { MarkdownBlock } from './MarkdownBlock';
import { ChartBlock } from './ChartBlock';
import { ImageBlock } from './ImageBlock';
import { TableBlock } from './TableBlock';
import { RowBlock } from './RowBlock';

interface Props {
  block: BlockType;
}

export const Block: React.FC<Props> = ({ block }) => {
  switch (block.type) {
    case 'markdown':
      return <MarkdownBlock block={block} />;
    case 'chart':
      return <ChartBlock block={block} />;
    case 'image':
      return <ImageBlock block={block} />;
    case 'table':
      return <TableBlock block={block} />;
    case 'row':
      return <RowBlock block={block} />;
    default:
      return null;
  }
};

