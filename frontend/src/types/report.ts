// Block Types for Server-Driven UI

// Google API 블록 타입 임포트
import type { MapBlock, AirQualityBlock } from './googleBlocks';
export type { MapBlock, AirQualityBlock } from './googleBlocks';

export interface MarkdownBlock {
  type: 'markdown';
  content: string;
}

export interface ChartData {
  labels: string[];
  values: number[];
}

export interface ChartBlock {
  type: 'chart';
  chartType: 'doughnut' | 'bar' | 'line' | 'pie' | 'radar' | 'polarArea';
  title: string;
  data: ChartData;
  description?: string;
}

export interface ImageBlock {
  type: 'image';
  url: string;
  alt: string;
  caption?: string;
}

export interface TableBlock {
  type: 'table';
  title: string;
  headers: string[];
  rows: string[][];
  description?: string;
}

export interface RowBlock {
  type: 'row';
  gap?: string;
  children: (MarkdownBlock | ChartBlock | ImageBlock | TableBlock | MapBlock | AirQualityBlock)[];
}

export type BlockType = MarkdownBlock | ChartBlock | ImageBlock | TableBlock | RowBlock | MapBlock | AirQualityBlock;

export interface BlockReportResponse {
  id: number;
  title: string;
  organization_name: string;
  report_topic: string;
  created_at: string;
  generation_time_seconds: number;
  blocks: BlockType[];
  report_type: string;
  research_sources: string[];
  final_report?: string;
}

