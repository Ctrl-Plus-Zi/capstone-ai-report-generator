import React from 'react';
import ReactMarkdown from 'react-markdown';
import type { MarkdownBlock as MarkdownBlockType } from '../../types/report';

interface Props {
  block: MarkdownBlockType;
}

export const MarkdownBlock: React.FC<Props> = ({ block }) => {
  return (
    <div className="markdown-block">
      <ReactMarkdown>{block.content}</ReactMarkdown>
    </div>
  );
};

