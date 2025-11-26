import React from 'react';
import { Chart as ChartJS, ArcElement, Tooltip, Legend, CategoryScale, LinearScale, BarElement, PointElement, LineElement, RadialLinearScale } from 'chart.js';
import { Doughnut, Bar, Line, Pie, Radar, PolarArea } from 'react-chartjs-2';
import type { ChartBlock as ChartBlockType } from '../../types/report';

ChartJS.register(ArcElement, Tooltip, Legend, CategoryScale, LinearScale, BarElement, PointElement, LineElement, RadialLinearScale);

interface Props {
  block: ChartBlockType;
}

const COLORS = [
  'rgba(255, 99, 132, 0.7)',
  'rgba(54, 162, 235, 0.7)',
  'rgba(255, 206, 86, 0.7)',
  'rgba(75, 192, 192, 0.7)',
  'rgba(153, 102, 255, 0.7)',
  'rgba(255, 159, 64, 0.7)',
  'rgba(199, 199, 199, 0.7)',
];

export const ChartBlock: React.FC<Props> = ({ block }) => {
  const chartData = {
    labels: block.data.labels,
    datasets: [
      {
        data: block.data.values,
        backgroundColor: COLORS.slice(0, block.data.labels.length),
        borderColor: COLORS.slice(0, block.data.labels.length).map(c => c.replace('0.7', '1')),
        borderWidth: 1,
      },
    ],
  };

  const options = {
    responsive: true,
    plugins: {
      legend: {
        position: 'bottom' as const,
      },
    },
  };

  const renderChart = () => {
    switch (block.chartType) {
      case 'doughnut':
        return <Doughnut data={chartData} options={options} />;
      case 'bar':
        return <Bar data={chartData} options={options} />;
      case 'line':
        return <Line data={chartData} options={options} />;
      case 'pie':
        return <Pie data={chartData} options={options} />;
      case 'radar':
        return <Radar data={chartData} options={options} />;
      case 'polarArea':
        return <PolarArea data={chartData} options={options} />;
      default:
        return <Doughnut data={chartData} options={options} />;
    }
  };

  return (
    <div className="chart-block">
      <h4 className="chart-block-title">{block.title}</h4>
      <div className="chart-block-container">
        {renderChart()}
      </div>
      {block.description && (
        <p className="chart-block-description">{block.description}</p>
      )}
    </div>
  );
};

