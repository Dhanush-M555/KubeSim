import React, { useEffect, useState } from 'react';
import { Bar } from 'react-chartjs-2';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  Title,
  Tooltip,
  Legend,
} from 'chart.js';
import { api, Node } from '../services/api';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from '../components/ui/card';
import { Trash, Plus, LineChart } from 'lucide-react';
import useUsageHistory from '../hooks/useUsageHistory';
import UsageChartModal from '../components/UsageChartModal';
import { notifyNodeAdded, notifyNodeDeleted, notifyNodeError } from '../lib/toast';

// Register Chart.js components
ChartJS.register(
  CategoryScale,
  LinearScale,
  BarElement,
  Title,
  Tooltip,
  Legend
);

const NodeManager: React.FC = () => {
  const [nodes, setNodes] = useState<Node[]>([]);
  const [podStatus, setPodStatus] = useState<Record<string, Record<string, { cpu_usage: number; healthy: boolean }>>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedNodeId, setSelectedNodeId] = useState<string>('');
  const [isAddingNode, setIsAddingNode] = useState(false);
  const [isDeletingNode, setIsDeletingNode] = useState(false);
  const [nodeCores, setNodeCores] = useState<number>(4);
  
  // Chart state
  const [chartNode, setChartNode] = useState<Node | null>(null);
  const [isChartModalOpen, setIsChartModalOpen] = useState(false);

  // Format node data for usage history tracking
  const nodeUsageHistoryData = nodes.map(node => {
    const nodePods = podStatus[node.node_id] || {};
    const usage = Object.values(nodePods).reduce((total, pod) => total + pod.cpu_usage, 0);
    return {
      id: node.node_id,
      usage
    };
  });
  
  // Track node usage history with improved hook
  const { getChartData, getResourceStats } = useUsageHistory('node', nodeUsageHistoryData, 3000); // 1 second interval

  // Show chart modal for a node
  const showNodeChart = (node: Node) => {
    setChartNode(node);
    setIsChartModalOpen(true);
  };

  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true);
        const [nodesData, podData] = await Promise.all([
          api.listNodes(),
          api.getPodStatus(),
        ]);
        setNodes(nodesData);
        setPodStatus(podData);
      } catch (err) {
        setError('Failed to fetch node data');
        console.error(err);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
    const interval = setInterval(fetchData, 3000); // Poll every 1s
    return () => clearInterval(interval);
  }, []);

  // Add a new node
  const handleAddNode = async () => {
    try {
      setIsAddingNode(true);
      setError(null);
      
      const response = await api.addNode(nodeCores);
      
      // Refresh the node list
      const [nodesData, podData] = await Promise.all([
        api.listNodes(),
        api.getPodStatus(),
      ]);
      setNodes(nodesData);
      setPodStatus(podData);
      
      // Show success notification
      if (response && response.node_id) {
        notifyNodeAdded(response.node_id, nodeCores);
      } else {
        notifyNodeAdded(`node_${nodesData.length}`, nodeCores);
      }
    } catch (err: any) {
      setError('Failed to add node');
      console.error(err);
      // Show error notification
      notifyNodeError(err?.response?.data?.message || 'Failed to add node');
    } finally {
      setIsAddingNode(false);
    }
  };

  // Delete a node
  const handleDeleteNode = async () => {
    if (!selectedNodeId) return;
    
    try {
      setIsDeletingNode(true);
      setError(null);
      
      const response = await api.deleteNode(selectedNodeId);
      
      // Show detailed notification based on pod rescheduling status
      if (response && response.partial_rescheduling === true) {
        // Some pods couldn't be rescheduled
        const rescheduledCount = response.rescheduled_pods_count || 0;
        const pendingCount = response.pending_pods_count || 0;
        const message = `Node ${selectedNodeId} deleted. ${rescheduledCount} pods rescheduled, ${pendingCount} pods queued due to insufficient resources.`;
        notifyNodeDeleted(selectedNodeId, message);
      } else if (response && response.rescheduled_pods_count) {
        // All pods were successfully rescheduled
        const rescheduledCount = response.rescheduled_pods_count || 0;
        const message = `Node ${selectedNodeId} deleted. All ${rescheduledCount} pods successfully rescheduled.`;
        notifyNodeDeleted(selectedNodeId, message);
      } else {
        // No pods needed rescheduling
        notifyNodeDeleted(selectedNodeId);
      }
      
      // Refresh the node list
      const [nodesData, podData] = await Promise.all([
        api.listNodes(),
        api.getPodStatus(),
      ]);
      setNodes(nodesData);
      setPodStatus(podData);
      setSelectedNodeId('');
    } catch (err: any) {
      setError('Failed to delete node');
      console.error(err);
      // Show error notification
      notifyNodeError(err?.response?.data?.message || 'Failed to delete node');
    } finally {
      setIsDeletingNode(false);
    }
  };

  // Prepare node usage data for bar chart
  const nodeUsageData = {
    labels: nodes.map(node => node.node_id),
    datasets: [
      {
        label: 'CPU Used',
        data: nodes.map(node => {
          // Calculate total CPU usage for this node
          const nodePods = podStatus[node.node_id] || {};
          return Object.values(nodePods).reduce((total, pod) => total + pod.cpu_usage, 0);
        }),
        backgroundColor: '#3b82f6',
      },
      {
        label: 'CPU Available',
        data: nodes.map(node => {
          // Calculate remaining CPU capacity using node's actual capacity
          const nodePods = podStatus[node.node_id] || {};
          const usedCpu = Object.values(nodePods).reduce((total, pod) => total + pod.cpu_usage, 0);
          return Math.max(0, node.capacity - usedCpu); // Use node.capacity instead of hardcoded value
        }),
        backgroundColor: '#d1d5db',
      },
    ],
  };

  // Options for stacked bar chart
  const nodeUsageOptions = {
    responsive: true,
    scales: {
      x: {
        stacked: true,
      },
      y: {
        stacked: true,
        // Use the maximum capacity across all nodes instead of hardcoded value
        max: Math.max(...nodes.map(node => node.capacity || nodeCores), nodeCores),
        title: {
          display: true,
          text: 'CPU Cores',
        },
      },
    },
    plugins: {
      tooltip: {
        callbacks: {
          footer: (tooltipItems: any) => {
            // Calculate and show total usage in tooltip
            const dataIndex = tooltipItems[0].dataIndex;
            const nodeId = nodes[dataIndex]?.node_id;
            if (!nodeId) return '';
            
            const nodePods = podStatus[nodeId] || {};
            const podCount = Object.keys(nodePods).length;
            return `Total Pods: ${podCount}`;
          },
        },
      },
    },
  };

  return (
    <div className="container mx-auto px-4 py-8">
      <header className="flex flex-col md:flex-row justify-between items-center mb-8">
        <div>
          <h1 className="text-3xl font-bold">Node Manager</h1>
          <p className="text-gray-600 dark:text-gray-400">
            Add, remove, and monitor Docker container nodes
          </p>
        </div>
      </header>

      <Card className="mb-8">
        <CardHeader>
          <CardTitle>Node Operations</CardTitle>
          <CardDescription>
            Add or remove nodes from your cluster
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Add Node Section */}
            <div className="space-y-4 p-4 border rounded-lg border-gray-200 dark:border-gray-800">
              <h3 className="text-md font-medium">Add New Node</h3>
              <div className="flex flex-col gap-4">
                <div>
                  <label className="block text-sm font-medium mb-1">CPU Cores</label>
                  <input
                    type="number"
                    min="1"
                    value={nodeCores}
                    onChange={(e) => setNodeCores(parseInt(e.target.value) || 1)}
                    className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
                  />
                </div>
                <Button 
                  onClick={handleAddNode}
                  disabled={isAddingNode}
                  className="w-full flex items-center justify-center"
                >
                  <Plus className="mr-2 h-4 w-4" />
                  {isAddingNode ? 'Adding Node...' : 'Add Node'}
                </Button>
              </div>
            </div>
            
            {/* Delete Node Section */}
            <div className="space-y-4 p-4 border rounded-lg border-gray-200 dark:border-gray-800">
              <h3 className="text-md font-medium">Remove Node</h3>
              <div className="flex flex-col gap-4">
                <div>
                  <label className="block text-sm font-medium mb-1">Select Node</label>
                  <select
                    className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
                    value={selectedNodeId}
                    onChange={(e) => setSelectedNodeId(e.target.value)}
                    disabled={nodes.length === 0}
                  >
                    <option value="">Select a node to delete</option>
                    {nodes.map((node) => (
                      <option key={node.node_id} value={node.node_id}>
                        {node.node_id}
                      </option>
                    ))}
                  </select>
                  {nodes.length === 0 && (
                    <p className="text-xs text-gray-500 mt-1">No nodes available</p>
                  )}
                </div>
                <Button 
                  variant="destructive"
                  onClick={handleDeleteNode}
                  disabled={!selectedNodeId || isDeletingNode}
                  className="w-full flex items-center justify-center"
                >
                  <Trash className="mr-2 h-4 w-4" />
                  {isDeletingNode ? 'Deleting...' : 'Delete Node'}
                </Button>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {error && (
        <div className="bg-red-100 dark:bg-red-900 text-red-800 dark:text-red-200 p-4 rounded-md mb-6">
          {error}
        </div>
      )}

      {loading && nodes.length === 0 ? (
        <p className="text-center">Loading nodes...</p>
      ) : nodes.length === 0 ? (
        <div className="text-center py-10">
          <h3 className="text-xl font-medium mb-2">No Nodes Available</h3>
          <p className="text-gray-600 dark:text-gray-400 mb-6">
            You haven't added any nodes to your cluster yet.
          </p>
          <Button onClick={handleAddNode} disabled={isAddingNode}>
            {isAddingNode ? 'Adding Node...' : 'Add Your First Node'}
          </Button>
        </div>
      ) : (
        <>
          <Card className="mb-8">
            <CardHeader>
              <CardTitle>Node Usage</CardTitle>
              <CardDescription>CPU utilization across all nodes</CardDescription>
            </CardHeader>
            <CardContent className="h-[28rem] px-4 py-4">
              <div className="flex justify-center w-full h-full">
                <div className="w-10/12 h-full">
                  <Bar data={nodeUsageData} options={{
                    ...nodeUsageOptions,
                    maintainAspectRatio: false,
                    responsive: true,
                    layout: {
                      padding: {
                        left: 10,
                        right: 30,
                        top: 20,
                        bottom: 10
                      }
                    }
                  }} />
                </div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Node List</CardTitle>
              <CardDescription>All nodes in the cluster</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse">
                  <thead>
                    <tr className="border-b">
                      <th className="py-3 px-4">Node ID</th>
                      <th className="py-3 px-4">Status</th>
                      <th className="py-3 px-4">Pods Hosted</th>
                      <th className="py-3 px-4">CPU Usage</th>
                      <th className="py-3 px-4">Avg Performance</th>
                    </tr>
                  </thead>
                  <tbody>
                    {nodes.map((node) => {
                      const nodePods = podStatus[node.node_id] || {};
                      const podCount = Object.keys(nodePods).length;
                      // Only count CPU usage from healthy pods or use value 0 for unhealthy pods
                      const cpuUsage = Object.values(nodePods).reduce(
                        (total, pod) => total + (pod.healthy ? pod.cpu_usage : 0),
                        0
                      );
                      const avgPerformance = podCount > 0 ? cpuUsage / podCount : 0;
                      
                      return (
                        <tr 
                          key={node.node_id} 
                          className="border-b hover:bg-gray-50 dark:hover:bg-gray-800 cursor-pointer"
                          onClick={() => showNodeChart(node)}
                        >
                          <td className="py-3 px-4 font-medium">{node.node_id}</td>
                          <td className="py-3 px-4">
                            <Badge variant={node.healthy ? "success" : "destructive"}>
                              {node.healthy ? "Active" : "Inactive"}
                            </Badge>
                          </td>
                          <td className="py-3 px-4">{podCount}</td>
                          <td className="py-3 px-4">
                            <div className="flex items-center">
                              <span className="mr-2">{cpuUsage.toFixed(2)} / {node.capacity} cores</span>
                              <LineChart className="h-4 w-4 text-blue-500" />
                            </div>
                          </td>
                          <td className="py-3 px-4">
                            {avgPerformance.toFixed(2)} cores/pod
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>
        </>
      )}
      
      {/* Node Details Modal */}
      {chartNode && (
        <UsageChartModal
          isOpen={isChartModalOpen}
          onClose={() => setIsChartModalOpen(false)}
          resourceId={chartNode.node_id}
          resourceType="node"
          resourceName={chartNode.node_id}
          data={getChartData(chartNode.node_id).values}
          labels={getChartData(chartNode.node_id).labels}
          capacity={chartNode.capacity}
          stats={getResourceStats(chartNode.node_id)}
        />
      )}
    </div>
  );
};

export default NodeManager; 