import React from 'react';
import type { ImageBlock as ImageBlockType } from '../../types/report';

interface Props {
  block: ImageBlockType;
}

export const ImageBlock: React.FC<Props> = ({ block }) => {
  return (
    <div className="image-block">
      <img src={block.url} alt={block.alt} />
      {block.caption && (
        <p className="image-block-caption">{block.caption}</p>
      )}
    </div>
  );
};

