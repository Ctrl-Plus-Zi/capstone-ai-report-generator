import React from 'react';
import type { TableBlock as TableBlockType } from '../../types/report';

interface Props {
  block: TableBlockType;
}

export const TableBlock: React.FC<Props> = ({ block }) => {
  return (
    <div className="table-block">
      <h4 className="table-block-title">{block.title}</h4>
      <table>
        <thead>
          <tr>
            {block.headers.map((header, idx) => (
              <th key={idx}>{header}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {block.rows.map((row, rowIdx) => (
            <tr key={rowIdx}>
              {row.map((cell, cellIdx) => (
                <td key={cellIdx}>{cell}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {block.description && (
        <p className="table-block-description">{block.description}</p>
      )}
    </div>
  );
};

