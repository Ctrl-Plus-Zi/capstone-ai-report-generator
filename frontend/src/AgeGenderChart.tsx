import React from 'react';
import { Doughnut } from 'react-chartjs-2';
import {
  Chart as ChartJS,
  ArcElement,
  Tooltip,
  Legend,
} from 'chart.js';

ChartJS.register(ArcElement, Tooltip, Legend);

interface AgeGenderChartProps {
  data: {
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
  };
  title?: string;
}

export const AgeGenderChart: React.FC<AgeGenderChartProps> = ({ data, title }) => {
  // 남성 데이터
  const maleData = [
    data.male_20s,
    data.male_30s,
    data.male_40s,
    data.male_50s,
    data.male_60s,
    data.male_70s,
  ];

  // 여성 데이터
  const femaleData = [
    data.female_20s,
    data.female_30s,
    data.female_40s,
    data.female_50s,
    data.female_60s,
    data.female_70s,
  ];

  const labels = ['20대', '30대', '40대', '50대', '60대', '70대+'];

  const maleChartData = {
    labels: labels.map(label => `남성 ${label}`),
    datasets: [
      {
        label: '비율',
        data: maleData,
        backgroundColor: [
          '#3B82F6', // 20대 - 파란색
          '#60A5FA', // 30대 - 밝은 파란색
          '#93C5FD', // 40대 - 더 밝은 파란색
          '#DBEAFE', // 50대 - 연한 파란색
          '#EFF6FF', // 60대 - 매우 연한 파란색
          '#F3F4F6', // 70대+ - 회색
        ],
        borderWidth: 1,
      },
    ],
  };

  const femaleChartData = {
    labels: labels.map(label => `여성 ${label}`),
    datasets: [
      {
        label: '비율',
        data: femaleData,
        backgroundColor: [
          '#EC4899', // 20대 - 핑크
          '#F472B6', // 30대 - 밝은 핑크
          '#F9A8D4', // 40대 - 더 밝은 핑크
          '#FBCFE8', // 50대 - 연한 핑크
          '#FCE7F3', // 60대 - 매우 연한 핑크
          '#FDF2F8', // 70대+ - 매우 연한 핑크
        ],
        borderWidth: 1,
      },
    ],
  };

  const chartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        position: 'bottom' as const,
        labels: {
          boxWidth: 12,
          padding: 10,
          font: {
            size: 11,
          },
        },
      },
      tooltip: {
        callbacks: {
          label: function(context: any) {
            const label = context.label || '';
            const value = context.parsed || 0;
            const percentage = ((value / context.dataset.data.reduce((a: number, b: number) => a + b, 0)) * 100).toFixed(1);
            return `${label}: ${(value * 100).toFixed(2)}% (전체 중 ${percentage}%)`;
          },
        },
      },
    },
  };

  const monthLabel = `${data.cri_ym.substring(0, 4)}년 ${parseInt(data.cri_ym.substring(4))}월`;

  return (
    <div style={{ marginBottom: '30px' }}>
      {title && <h3 style={{ marginBottom: '15px', fontSize: '18px', fontWeight: '600' }}>{title}</h3>}
      <div style={{ display: 'flex', gap: '30px', flexWrap: 'wrap' }}>
        <div style={{ flex: '1', minWidth: '300px' }}>
          <h4 style={{ marginBottom: '10px', fontSize: '16px', color: '#3B82F6' }}>남성 연령대별 비율 ({monthLabel})</h4>
          <div style={{ height: '300px' }}>
            <Doughnut data={maleChartData} options={chartOptions} />
          </div>
        </div>
        <div style={{ flex: '1', minWidth: '300px' }}>
          <h4 style={{ marginBottom: '10px', fontSize: '16px', color: '#EC4899' }}>여성 연령대별 비율 ({monthLabel})</h4>
          <div style={{ height: '300px' }}>
            <Doughnut data={femaleChartData} options={chartOptions} />
          </div>
        </div>
      </div>
    </div>
  );
};

