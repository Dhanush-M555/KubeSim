import React, { useEffect, useState, useRef } from 'react';
import { Line, Bar } from 'react-chartjs-2';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  Title,
  Tooltip,
  Legend,
} from 'chart.js';
import { api, ClusterStatus } from '../services/api';
import { Button } from '../components/ui/button';
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
  CardFooter,
} from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { 
  TrendingUp, 
  TrendingDown, 
  Server, 
  Package, 
  RefreshCw, 
  Settings
} from 'lucide-react';

// Register Chart.js components
ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  Title,
  Tooltip,
  Legend
);

// Chart theme configuration
const getChartOptions = (isDark: boolean) => ({
  responsive: true,
  interaction: {
    mode: 'index' as const,
    intersect: false,
  },
  stacked: false,
  plugins: {
    legend: {
      position: 'top' as const,
      labels: {
        color: isDark ? '#e5e7eb' : '#1f2937',
        font: {
          family: "'Inter', sans-serif",
        }
      },
    },
    tooltip: {
      usePointStyle: true,
      backgroundColor: isDark ? 'rgba(17, 24, 39, 0.8)' : 'rgba(255, 255, 255, 0.8)',
      titleColor: isDark ? '#e5e7eb' : '#1f2937',
      bodyColor: isDark ? '#e5e7eb' : '#1f2937',
      borderColor: isDark ? 'rgba(55, 65, 81, 0.2)' : 'rgba(229, 231, 235, 0.2)',
      borderWidth: 1,
    },
  },
  scales: {
    y: {
      type: 'linear' as const,
      display: true,
      position: 'left' as const,
      grid: {
        color: isDark ? 'rgba(75, 85, 99, 0.2)' : 'rgba(209, 213, 219, 0.2)',
      },
      ticks: {
        color: isDark ? '#9ca3af' : '#4b5563',
      },
    },
    x: {
      grid: {
        color: isDark ? 'rgba(75, 85, 99, 0.2)' : 'rgba(209, 213, 219, 0.2)',
      },
      ticks: {
        color: isDark ? '#9ca3af' : '#4b5563',
      },
    },
  },
});

const Cluster: React.FC = () => {
  const [clusterStatus, setClusterStatus] = useState<ClusterStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [isDark, setIsDark] = useState(document.documentElement.classList.contains('dark'));
  
  // For CPU usage over time chart
  const [cpuHistory, setCpuHistory] = useState<number[]>([]);
  const [cpuRequestHistory, setCpuRequestHistory] = useState<number[]>([]);
  const [nodeCountHistory, setNodeCountHistory] = useState<number[]>([]);
  const [timeLabels, setTimeLabels] = useState<string[]>([]);
  
  // For rolling average
  const cpuHistoryRef = useRef<number[]>([]);

  // Watch for theme changes
  useEffect(() => {
    const observer = new MutationObserver((mutations) => {
      mutations.forEach((mutation) => {
        if (mutation.attributeName === 'class') {
          const isDarkMode = document.documentElement.classList.contains('dark');
          setIsDark(isDarkMode);
        }
      });
    });
    
    observer.observe(document.documentElement, { attributes: true });
    
    return () => {
      observer.disconnect();
    };
  }, []);
  
  const fetchData = async () => {
    try {
      setRefreshing(true);
      const status = await api.getClusterStatus();
      setClusterStatus(status);
      
      // Update CPU history (keep last 40 data points = 10 minutes)
      const now = new Date();
      const timeLabel = `${now.getHours()}:${now.getMinutes().toString().padStart(2, '0')}:${now.getSeconds().toString().padStart(2, '0')}`;
      
      setCpuHistory(prev => {
        const newHistory = [...prev, status.totalCpuUsage];
        return newHistory.slice(-40); // Keep only the last 40 points
      });
      
      setCpuRequestHistory(prev => {
        const newHistory = [...prev, status.totalCpuRequested];
        return newHistory.slice(-40);
      });
      
      setNodeCountHistory(prev => {
        const newHistory = [...prev, status.nodes.length];
        return newHistory.slice(-40);
      });
      
      setTimeLabels(prev => {
        const newLabels = [...prev, timeLabel];
        return newLabels.slice(-40); // Keep only the last 40 points
      });
      
      // Update ref for calculations
      cpuHistoryRef.current = [...cpuHistoryRef.current, status.totalCpuUsage].slice(-40);
    } catch (err) {
      setError('Failed to fetch cluster data');
      console.error(err);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 15000); // Poll every 15s
    return () => clearInterval(interval);
  }, []);

  // Manual refresh handler
  const handleRefresh = () => {
    fetchData();
  };

  // Prepare node distribution data
  const nodeDistributionData = {
    labels: clusterStatus?.nodes.map(node => node.node_id) || [],
    datasets: [
      {
        label: 'Pods per Node',
        data: clusterStatus?.nodes.map(node => {
          // Count pods on this node
          const nodePods = clusterStatus.pods.filter(pod => pod.node_id === node.node_id);
          return nodePods.length;
        }) || [],
        backgroundColor: isDark ? '#3b82f6' : '#3b82f6',
        borderRadius: 4,
      },
    ],
  };

  // Prepare CPU usage line chart data
  const cpuUsageData = {
    labels: timeLabels,
    datasets: [
      {
        label: 'Total CPU Usage (cores)',
        data: cpuHistory,
        borderColor: '#3b82f6',
        backgroundColor: isDark ? 'rgba(59, 130, 246, 0.2)' : 'rgba(59, 130, 246, 0.2)',
        borderWidth: 2,
        tension: 0.4,
        fill: true,
        yAxisID: 'y',
      },
      {
        label: 'Total CPU Requested (cores)',
        data: cpuRequestHistory,
        borderColor: '#f97316',
        backgroundColor: isDark ? 'rgba(249, 115, 22, 0.2)' : 'rgba(249, 115, 22, 0.2)',
        borderWidth: 2,
        borderDash: [5, 5],
        tension: 0.4,
        fill: false,
        yAxisID: 'y',
      },
      {
        label: 'Node Count',
        data: nodeCountHistory,
        borderColor: '#10b981',
        backgroundColor: isDark ? 'rgba(16, 185, 129, 0.2)' : 'rgba(16, 185, 129, 0.2)',
        borderWidth: 2,
        tension: 0.4,
        fill: false,
        yAxisID: 'y1',
      },
    ],
  };

  // Extended options for CPU chart
  const chartOptions = getChartOptions(isDark);
  const cpuLineOptions = {
    ...chartOptions,
    maintainAspectRatio: false,
    responsive: true,
    layout: {
      padding: {
        left: 10,
        right: 30,
        top: 20,
        bottom: 10
      }
    },
    plugins: {
      ...chartOptions.plugins,
      title: {
        display: false,
        text: 'Cluster Resource Usage Over Time',
        color: isDark ? '#e5e7eb' : '#1f2937',
        font: {
          size: 16,
          weight: 'bold' as const,
          family: "'Inter', sans-serif",
        },
        padding: {
          top: 10,
          bottom: 20
        }
      },
    },
    scales: {
      ...chartOptions.scales,
      y: {
        ...chartOptions.scales.y,
        title: {
          display: true,
          text: 'CPU Cores',
          color: isDark ? '#9ca3af' : '#4b5563',
        },
        beginAtZero: true,
        suggestedMax: Math.max(8, ...cpuHistory, ...cpuRequestHistory) * 1.2,
        ticks: {
          padding: 10,
          color: isDark ? '#9ca3af' : '#4b5563',
        }
      },
      y1: {
        type: 'linear' as const,
        display: true,
        position: 'right' as const,
        grid: {
          drawOnChartArea: false,
          color: isDark ? 'rgba(75, 85, 99, 0.2)' : 'rgba(209, 213, 219, 0.2)',
        },
        beginAtZero: true,
        suggestedMax: Math.max(2, ...nodeCountHistory) + 1,
        title: {
          display: true,
          text: 'Node Count',
          color: isDark ? '#9ca3af' : '#4b5563',
        },
        ticks: {
          padding: 10,
          color: isDark ? '#10b981' : '#10b981',
          stepSize: 1,
        },
      },
    },
  };

  // Calculate statistics
  const calculateAvg = (arr: number[]) => {
    if (arr.length === 0) return 0;
    return arr.reduce((a, b) => a + b, 0) / arr.length;
  };

  const avgCpuPerNode = clusterStatus && clusterStatus.nodes.length > 0
    ? clusterStatus.totalCpuUsage / clusterStatus.nodes.length
    : 0;
    
  const avgCpuPerPod = clusterStatus && clusterStatus.pods.length > 0
    ? clusterStatus.totalCpuUsage / clusterStatus.pods.length
    : 0;
    
  const avgCpuPerMinute = calculateAvg(cpuHistoryRef.current);
  
  const clusterUtilization = clusterStatus && clusterStatus.totalCpuRequested > 0
    ? (clusterStatus.totalCpuUsage / clusterStatus.totalCpuRequested) * 100
    : 0;

  // Update the Bar chart options
  const barChartOptions = {
    ...chartOptions,
    scales: {
      ...chartOptions.scales,
      y: {
        ...chartOptions.scales.y,
        beginAtZero: true,
        title: {
          display: true,
          text: 'Pod Count',
          color: isDark ? '#9ca3af' : '#4b5563',
        },
      },
    },
  };

  return (
    <div className="container mx-auto px-4 py-8">
      <header className="flex flex-col md:flex-row justify-between items-center mb-8">
        <div>
          <h1 className="text-3xl font-bold">Cluster Overview</h1>
          <p className="text-gray-600 dark:text-gray-400">
            Monitor cluster resources and node distribution
          </p>
        </div>
        <div className="mt-4 md:mt-0 space-x-2 flex">
          <Button variant="outline" onClick={handleRefresh} disabled={refreshing}>
            <RefreshCw className={`h-4 w-4 mr-2 ${refreshing ? 'animate-spin' : ''}`} />
            {refreshing ? 'Refreshing...' : 'Refresh'}
          </Button>
        </div>
      </header>

      {loading && !clusterStatus && (
        <div className="flex items-center justify-center p-12">
          <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-primary"></div>
        </div>
      )}
      
      {error && (
        <div className="bg-red-100 dark:bg-red-900/20 text-red-800 dark:text-red-200 p-4 rounded-md mb-6">
          {error}
        </div>
      )}

      {clusterStatus && (
        <>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-lg font-medium">Active Nodes</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="flex items-center">
                  <Server className="h-5 w-5 mr-2 text-blue-500" />
                  <span className="text-3xl font-bold">{clusterStatus.nodes.length}</span>
                </div>
              </CardContent>
              <CardFooter className="pt-0 text-sm text-gray-500 dark:text-gray-400">
                {clusterStatus.nodes.filter(n => n.healthy).length} healthy nodes
              </CardFooter>
            </Card>

            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-lg font-medium">Pods Deployed</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="flex items-center">
                  <Package className="h-5 w-5 mr-2 text-green-500" />
                  <span className="text-3xl font-bold">{clusterStatus.pods.length}</span>
                </div>
              </CardContent>
              <CardFooter className="pt-0 text-sm text-gray-500 dark:text-gray-400">
                {clusterStatus.pods.filter(p => p.healthy).length} healthy pods
              </CardFooter>
            </Card>

            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-lg font-medium">Auto-Scaling</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="flex items-center">
                  <Settings className="h-5 w-5 mr-2 text-purple-500" />
                  <Badge className={clusterStatus.autoScaleEnabled ? "bg-green-500" : "bg-red-500"}>
                    {clusterStatus.autoScaleEnabled ? "ENABLED" : "DISABLED"}
                  </Badge>
                </div>
              </CardContent>
              <CardFooter className="pt-0 text-sm text-gray-500 dark:text-gray-400">
                Algorithm: <span className="capitalize">{clusterStatus.schedulingAlgo.replace("-", " ")}</span>
              </CardFooter>
            </Card>

            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-lg font-medium">Utilization</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="flex items-center">
                  {clusterUtilization > 80 ? (
                    <TrendingUp className="h-5 w-5 mr-2 text-red-500" />
                  ) : clusterUtilization > 50 ? (
                    <TrendingUp className="h-5 w-5 mr-2 text-yellow-500" />
                  ) : (
                    <TrendingDown className="h-5 w-5 mr-2 text-green-500" />
                  )}
                  <span className="text-3xl font-bold">{clusterUtilization.toFixed(0)}%</span>
                </div>
              </CardContent>
              <CardFooter className="pt-0 text-sm text-gray-500 dark:text-gray-400">
                {clusterStatus.totalCpuUsage.toFixed(1)} used of {clusterStatus.totalCpuRequested.toFixed(1)} allocated cores
              </CardFooter>
            </Card>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
            <Card className="col-span-1 lg:col-span-2 mx-auto w-full">
              <CardHeader>
                <CardTitle>Cluster Resource Utilization</CardTitle>
                <CardDescription>
                  CPU usage, requests, and node count over time
                </CardDescription>
              </CardHeader>
              <CardContent className="h-[32rem] px-4 py-4">
                <div className="flex justify-center w-full h-full">
                  <div className="w-10/12 h-full">
                    <Line options={cpuLineOptions} data={cpuUsageData} />
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Pod Distribution by Node</CardTitle>
                <CardDescription>
                  Number of pods running on each node
                </CardDescription>
              </CardHeader>
              <CardContent className="h-80">
                <Bar 
                  data={nodeDistributionData} 
                  options={barChartOptions} 
                />
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Cluster Statistics</CardTitle>
                <CardDescription>Performance metrics for the cluster</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex justify-between border-b dark:border-gray-700 pb-2">
                  <span className="font-medium">Avg CPU Cores per Node:</span>
                  <span className="font-bold">{avgCpuPerNode.toFixed(2)}</span>
                </div>
                <div className="flex justify-between border-b dark:border-gray-700 pb-2">
                  <span className="font-medium">Avg CPU Usage per Pod:</span>
                  <span className="font-bold">{avgCpuPerPod.toFixed(2)}</span>
                </div>
                <div className="flex justify-between border-b dark:border-gray-700 pb-2">
                  <span className="font-medium">Avg CPU Usage per Minute:</span>
                  <span className="font-bold">{avgCpuPerMinute.toFixed(2)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="font-medium">Total CPU Cores Used:</span>
                  <span className="font-bold">{clusterStatus.totalCpuUsage.toFixed(2)}</span>
                </div>
              </CardContent>
            </Card>
          </div>
        </>
      )}
    </div>
  );
};

export default Cluster; 