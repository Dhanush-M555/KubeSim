import React from 'react';
import { Modal } from './ui/modal';
import UsageChart from './UsageChart';
import { ResourceStats } from '../hooks/useUsageHistory';

interface UsageChartModalProps {
  isOpen: boolean;
  onClose: () => void;
  resourceId: string;
  resourceType: 'node' | 'pod';
  resourceName: string;
  labels: string[];
  data: number[];
  capacity?: number;
  stats?: ResourceStats;
}

const UsageChartModal: React.FC<UsageChartModalProps> = ({
  isOpen,
  onClose,
  resourceId,
  resourceType,
  resourceName,
  labels,
  data,
  capacity,
  stats
}) => {
  const isNode = resourceType === 'node';
  const chartTitle = `${isNode ? 'Node' : 'Pod'} CPU Usage`;
  const modalTitle = `${isNode ? 'Node' : 'Pod'} Usage History: ${resourceName}`;
  // Use different colors for nodes vs pods
  const colorHue = isNode ? 210 : 145; // blue for nodes, green for pods

  // Use stats from history if provided, otherwise calculate from current data
  let average, latest, allTimeMin, allTimeMax;
  
  if (stats) {
    // Use the persistent stats from history tracking
    average = stats.average.toFixed(2);
    allTimeMin = stats.allTimeMin.toFixed(2);
    allTimeMax = stats.allTimeMax.toFixed(2);
  } else {
    // Calculate from current data as fallback
    average = data.length > 0 
      ? (data.reduce((sum, val) => sum + val, 0) / data.length).toFixed(2) 
      : '0';
    allTimeMin = data.length > 0 ? Math.min(...data).toFixed(2) : '0';
    allTimeMax = data.length > 0 ? Math.max(...data).toFixed(2) : '0';
  }
  
  latest = data.length > 0 ? data[data.length - 1].toFixed(2) : '0';
  const latestValue = parseFloat(latest);

  return (
    <Modal isOpen={isOpen} onClose={onClose} title={modalTitle}>
      <div className="flex flex-col space-y-6">
        <div className="grid grid-cols-2 gap-4">
          <div className="bg-gray-100 dark:bg-gray-700 p-3 rounded-lg">
            <div className="text-sm text-gray-500 dark:text-gray-400">Latest</div>
            <div className="text-2xl font-medium">{latest} cores</div>
          </div>
          <div className="bg-gray-100 dark:bg-gray-700 p-3 rounded-lg">
            <div className="text-sm text-gray-500 dark:text-gray-400">Average</div>
            <div className="text-2xl font-medium">{average} cores</div>
          </div>
        </div>
        
        <div className="grid grid-cols-1 gap-4">
          <div className="bg-blue-50 dark:bg-blue-900/30 p-3 rounded-lg border border-blue-200 dark:border-blue-800">
            <div className="text-sm font-medium text-blue-800 dark:text-blue-300 mb-1">All-Time Statistics</div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <div className="text-sm text-gray-500 dark:text-gray-400">Minimum</div>
                <div className="text-xl font-medium">{allTimeMin} cores</div>
              </div>
              <div>
                <div className="text-sm text-gray-500 dark:text-gray-400">Maximum</div>
                <div className="text-xl font-medium">{allTimeMax} cores</div>
              </div>
            </div>
          </div>
        </div>

        {isNode && capacity && (
          <div className="flex items-center space-x-3 mb-2">
            <div className="text-sm font-medium">Node Capacity: {capacity} cores</div>
            <div className={`text-sm ${latestValue > capacity ? 'text-red-500' : 'text-green-500'}`}>
              {latestValue > capacity ? 'Overallocated' : 'Within capacity'}
            </div>
          </div>
        )}

        <div className="border p-4 rounded-lg bg-white dark:bg-gray-800">
          <UsageChart 
            title={chartTitle} 
            data={data} 
            labels={labels}
            maxValue={capacity} 
            colorHue={colorHue}
            allTimeMin={parseFloat(allTimeMin)}
            allTimeMax={parseFloat(allTimeMax)}
          />
        </div>

        <div className="text-sm text-gray-500 mt-4">
          This chart shows recent CPU usage over time. All-time statistics track the entire lifetime of this {isNode ? 'node' : 'pod'} even when switching between pages.
        </div>
      </div>
    </Modal>
  );
};

export default UsageChartModal; 