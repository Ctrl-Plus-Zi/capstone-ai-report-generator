import React, { useMemo } from 'react';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  Title,
  Tooltip,
  Legend,
} from 'chart.js';
import { Bar } from 'react-chartjs-2';

ChartJS.register(
  CategoryScale,
  LinearScale,
  BarElement,
  Title,
  Tooltip,
  Legend
);

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

interface RatingChartProps {
  statistics: RatingStatistics;
  organizationName?: string;
}

export const RatingChart: React.FC<RatingChartProps> = ({ statistics, organizationName }) => {
  const chartData = useMemo(() => {
    // 하나의 막대에 스택으로 표시하기 위해 각 평점을 별도의 dataset으로 생성
    return {
      labels: [''], // 왼쪽 라벨 제거
      datasets: [
        {
          label: '5점',
          data: [statistics.rating_percentages["5"]],
          backgroundColor: 'rgba(46, 204, 113, 0.8)',  // 5점 - 초록색
          borderColor: 'rgba(46, 204, 113, 1)',
          borderWidth: 1,
        },
        {
          label: '4점',
          data: [statistics.rating_percentages["4"]],
          backgroundColor: 'rgba(52, 152, 219, 0.8)',  // 4점 - 파란색
          borderColor: 'rgba(52, 152, 219, 1)',
          borderWidth: 1,
        },
        {
          label: '3점',
          data: [statistics.rating_percentages["3"]],
          backgroundColor: 'rgba(241, 196, 15, 0.8)',  // 3점 - 노란색
          borderColor: 'rgba(241, 196, 15, 1)',
          borderWidth: 1,
        },
        {
          label: '2점',
          data: [statistics.rating_percentages["2"]],
          backgroundColor: 'rgba(230, 126, 34, 0.8)',  // 2점 - 주황색
          borderColor: 'rgba(230, 126, 34, 1)',
          borderWidth: 1,
        },
        {
          label: '1점',
          data: [statistics.rating_percentages["1"]],
          backgroundColor: 'rgba(231, 76, 60, 0.8)',   // 1점 - 빨간색
          borderColor: 'rgba(231, 76, 60, 1)',
          borderWidth: 1,
        },
      ],
    };
  }, [statistics]);

  const options = {
    indexAxis: 'y' as const, // 가로 막대 그래프
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        display: true,
        position: 'top' as const,
        labels: {
          usePointStyle: true,
          padding: 15,
          font: {
            size: 12,
          },
        },
      },
      title: {
        display: true,
        text: organizationName 
          ? `${organizationName} 리뷰 평점 분포 (총 ${statistics.total_reviews.toLocaleString()}개, 평균 ${statistics.average_rating}/5.0)`
          : `리뷰 평점 분포 (총 ${statistics.total_reviews.toLocaleString()}개, 평균 ${statistics.average_rating}/5.0)`,
        font: {
          size: 16,
          weight: 'bold' as const,
        },
      },
      tooltip: {
        callbacks: {
          label: function(context: any) {
            const datasetLabel = context.dataset.label || '';
            const value = context.parsed.x || 0;
            const rating = datasetLabel.replace('점', '');
            const count = statistics.rating_distribution[rating as "5" | "4" | "3" | "2" | "1"] || 0;
            return `${datasetLabel}: ${value.toFixed(1)}% (${count.toLocaleString()}개)`;
          }
        }
      }
    },
    scales: {
      x: {
        stacked: true, // 스택 바 차트
        beginAtZero: true,
        max: 100,
        ticks: {
          display: false, // 퍼센트 표시 제거
        },
        grid: {
          display: false, // 그리드 제거
        },
        title: {
          display: false, // x축 제목 제거
        }
      },
      y: {
        stacked: true, // 스택 바 차트
        ticks: {
          display: false, // y축 라벨 제거
        },
        grid: {
          display: false, // 그리드 제거
        },
        title: {
          display: false,
        }
      }
    }
  };

  return (
    <div style={{ width: '100%', height: '100px', marginTop: '20px', padding: '10px 0' }}>
      <Bar data={chartData} options={options} />
    </div>
  );
};

