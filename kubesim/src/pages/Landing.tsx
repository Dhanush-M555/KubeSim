import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Pie } from 'react-chartjs-2';
import { Chart as ChartJS, ArcElement, Tooltip, Legend } from 'chart.js';
import { api, Node } from '../services/api';
import { Button } from '../components/ui/button';
import { 
  Card, 
  CardContent, 
  CardHeader, 
  CardTitle, 
  CardDescription
} from '../components/ui/card';
import { ArrowRight, Server, Layers, Activity, Zap, Cpu, PieChart } from 'lucide-react';

// Register Chart.js components
ChartJS.register(ArcElement, Tooltip, Legend);

const Landing: React.FC = () => {
  const [nodes, setNodes] = useState<Node[]>([]);
  const [podCount, setPodCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [autoScaleEnabled, setAutoScaleEnabled] = useState(false);
  const [totalCapacity, setTotalCapacity] = useState(0);
  const [totalUsage, setTotalUsage] = useState(0);

  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true);
        const status = await api.getClusterStatus();
        setNodes(status.nodes);
        setPodCount(status.pods.length);
        setAutoScaleEnabled(status.autoScaleEnabled);
        setTotalCapacity(status.nodes.reduce((sum, node) => sum + node.capacity, 0));
        setTotalUsage(status.totalCpuUsage);
      } catch (err) {
        setError('Failed to fetch cluster data');
        console.error(err);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
    const interval = setInterval(fetchData, 15000); // Poll every 15s
    return () => clearInterval(interval);
  }, []);

  // Count healthy vs unhealthy nodes
  const healthyNodes = nodes.filter(node => node.healthy).length;
  const unhealthyNodes = nodes.length - healthyNodes;

  // Prepare chart data
  const chartData = {
    labels: ['Healthy Nodes', 'Unhealthy Nodes'],
    datasets: [
      {
        data: [healthyNodes, unhealthyNodes],
        backgroundColor: ['#22c55e', '#ef4444'],
        borderColor: ['#16a34a', '#dc2626'],
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
          padding: 15,
          color: document.documentElement.classList.contains('dark') ? '#e5e7eb' : '#1f2937'
        }
      },
      tooltip: {
        usePointStyle: true,
      },
    },
  };

  return (
    <div className="container mx-auto px-4 py-8">
      {/* Hero Section */}
      <section className="text-center py-16 bg-gradient-to-b from-gray-50 to-gray-100 dark:from-gray-900 dark:to-gray-800 rounded-xl mb-12 shadow-lg">
        <h1 className="text-5xl font-extrabold mb-4 text-gray-900 dark:text-white">Welcome to KubeSim</h1>
        <p className="text-xl mb-8 text-gray-600 dark:text-gray-400 max-w-2xl mx-auto">
          Explore and manage a simulated Kubernetes-like cluster. Launch pods, scale nodes, and monitor performance in real-time.
        </p>
        <Link to="/cluster">
          <Button size="lg" className="bg-blue-600 hover:bg-blue-700 text-white">
            View Cluster Overview <ArrowRight className="ml-2 h-5 w-5" />
          </Button>
        </Link>
      </section>

      {loading && <p className="text-center py-8">Loading cluster data...</p>}
      {error && <p className="text-center text-red-500 py-8">{error}</p>}

      {!loading && !error && (
        <>
          {/* Quick Stats Section */}
          <section className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6 mb-12">
            <StatCard title="Active Nodes" value={nodes.length} icon={<Server className="h-6 w-6 text-blue-500" />} />
            <StatCard title="Running Pods" value={podCount} icon={<Layers className="h-6 w-6 text-green-500" />} />
            <StatCard title="Total Capacity" value={`${totalCapacity} Cores`} icon={<Cpu className="h-6 w-6 text-purple-500" />} />
            <StatCard title="Auto-Scaling" value={autoScaleEnabled ? "ON" : "OFF"} icon={<Zap className="h-6 w-6 text-yellow-500" />} className={autoScaleEnabled ? "text-green-500" : "text-red-500"} />
          </section>

          {/* Node Health & Management Section */}
          <section className="grid grid-cols-1 lg:grid-cols-2 gap-8 mb-12">
            <Card className="shadow-lg">
              <CardHeader>
                <CardTitle className="flex items-center">
                  <PieChart className="h-5 w-5 mr-2" />
                  Node Health Distribution
                </CardTitle>
                <CardDescription>Current status of nodes in the cluster</CardDescription>
              </CardHeader>
              <CardContent className="h-72 flex items-center justify-center">
                {nodes.length > 0 ? (
                  <Pie data={chartData} options={chartOptions} />
                ) : (
                  <p className="text-gray-500">No nodes currently active.</p>
                )}
              </CardContent>
            </Card>

            <Card className="shadow-lg">
              <CardHeader>
                <CardTitle className="flex items-center">
                  <Activity className="h-5 w-5 mr-2" />
                  Cluster Management Actions
                </CardTitle>
                <CardDescription>Quick access to cluster management tools</CardDescription>
              </CardHeader>
              <CardContent className="flex flex-col space-y-4 pt-6">
                <ManagementButton to="/cluster" icon={<PieChart className="h-5 w-5" />} text="View Cluster Overview" description="Detailed graphs and metrics" />
                <ManagementButton to="/nodes" icon={<Server className="h-5 w-5" />} text="Manage Nodes" description="Add, remove, and inspect nodes" />
                <ManagementButton to="/pod-manager" icon={<Layers className="h-5 w-5" />} text="Manage Pods" description="Deploy and delete application pods" />
              </CardContent>
            </Card>
          </section>
        </>
      )}
    </div>
  );
};

// Helper component for Stat Cards
interface StatCardProps {
  title: string;
  value: string | number;
  icon: React.ReactNode;
  className?: string;
}
const StatCard: React.FC<StatCardProps> = ({ title, value, icon, className }) => (
  <Card className="shadow-lg hover:shadow-xl transition-shadow duration-300">
    <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
      <CardTitle className="text-sm font-medium text-gray-600 dark:text-gray-400">{title}</CardTitle>
      {icon}
    </CardHeader>
    <CardContent>
      <div className={`text-2xl font-bold ${className}`}>{value}</div>
    </CardContent>
  </Card>
);

// Helper component for Management Buttons
interface ManagementButtonProps {
  to: string;
  icon: React.ReactNode;
  text: string;
  description: string;
}
const ManagementButton: React.FC<ManagementButtonProps> = ({ to, icon, text, description }) => (
  <Link to={to}>
    <Button variant="outline" className="w-full justify-start h-auto py-3 px-4 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors duration-200">
      <div className="flex items-center w-full">
        <div className="mr-4 text-blue-600 dark:text-blue-400">{icon}</div>
        <div className="flex-grow text-left">
          <p className="font-medium text-base text-gray-900 dark:text-white">{text}</p>
          <p className="text-sm text-gray-500 dark:text-gray-400">{description}</p>
        </div>
        <ArrowRight className="h-4 w-4 text-gray-400" />
      </div>
    </Button>
  </Link>
);

export default Landing; 