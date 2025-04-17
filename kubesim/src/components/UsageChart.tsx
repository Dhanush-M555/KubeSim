import React from 'react';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  ChartOptions,
  ChartData,
} from 'chart.js';
import { Line } from 'react-chartjs-2';

// Register Chart.js components
ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend
);

interface UsageChartProps {
  title: string;
  data: number[];
  labels: string[];
  maxValue?: number;
  colorHue?: number;
  allTimeMin?: number;
  allTimeMax?: number;
}

const UsageChart: React.FC<UsageChartProps> = ({ 
  title, 
  data, 
  labels, 
  maxValue,
  colorHue = 210,
  allTimeMin,
  allTimeMax
}) => {
  const chartData: ChartData<'line'> = {
    labels,
    datasets: [
      {
        label: title,
        data,
        fill: false,
        backgroundColor: `hsla(${colorHue}, 100%, 50%, 0.5)`,
        borderColor: `hsla(${colorHue}, 85%, 60%, 1)`,
        borderWidth: 2,
        pointBackgroundColor: `hsla(${colorHue}, 85%, 60%, 1)`,
        pointBorderColor: '#fff',
        pointHoverBackgroundColor: '#fff',
        pointHoverBorderColor: `hsla(${colorHue}, 85%, 60%, 1)`,
        pointRadius: 4,
        pointHoverRadius: 6,
        tension: 0.3,
      }
    ],
  };

  // Calculate a good suggested max to fit all data plus some headroom
  const dataMax = data.length > 0 ? Math.max(...data) : 0;
  const dataMin = data.length > 0 ? Math.min(...data) : 0;
  
  // If we have all-time max, use that to ensure chart scaling fits historical data
  let suggestedMax = maxValue;
  if (allTimeMax !== undefined) {
    suggestedMax = Math.max(allTimeMax * 1.1, maxValue || 0);
  } else if (dataMax > 0) {
    suggestedMax = Math.max(dataMax * 1.1, maxValue || 0);
  }
  
  // Set a min value that shows all historical data
  let suggestedMin = 0;
  if (allTimeMin !== undefined && allTimeMin < dataMin) {
    // Only adjust min if all-time min is less than current data min
    suggestedMin = Math.max(0, allTimeMin * 0.9);
  }

  const options: ChartOptions<'line'> = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        position: 'top',
        labels: {
          font: {
            size: 12,
          },
        },
      },
      tooltip: {
        backgroundColor: 'rgba(0, 0, 0, 0.8)',
        titleFont: {
          size: 14,
        },
        bodyFont: {
          size: 13,
        },
        displayColors: false,
        callbacks: {
          label: function(context) {
            return `${context.dataset.label}: ${context.parsed.y.toFixed(2)} ${title.includes('CPU') ? 'cores' : '%'}`;
          }
        }
      },
    },
    scales: {
      y: {
        beginAtZero: true,
        suggestedMin: suggestedMin,
        suggestedMax: suggestedMax,
        ticks: {
          stepSize: 1,
          callback: function(value) {
            return value + (title.includes('CPU') ? ' cores' : '%');
          }
        },
        title: {
          display: true,
          text: title.includes('CPU') ? 'CPU Usage (cores)' : 'Usage (%)'
        }
      },
      x: {
        title: {
          display: true,
          text: 'Time'
        }
      }
    },
    animation: {
      duration: 500,
    },
  };

  return (
    <div className="w-full h-[400px]">
      <Line data={chartData} options={options} />
    </div>
  );
};

export default UsageChart; 