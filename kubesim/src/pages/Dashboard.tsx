import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { api, Node, PendingPod } from '../services/api';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
  CardFooter,
} from '../components/ui/card';
import { ClusterNotifications } from '../components/ClusterNotifications';
import { Clock, AlertTriangle } from 'lucide-react';

// Heartbeat status indicator component
const HeartbeatIndicator = ({ lastHeartbeat }: { lastHeartbeat: number }) => {
  // If last heartbeat was less than 10 seconds ago, it's healthy
  const isHealthy = lastHeartbeat < 10;
  
  return (
    <div className="flex items-center mt-1">
      <div className={`w-2 h-2 rounded-full mr-2 ${isHealthy ? 'bg-green-500 animate-pulse' : 'bg-red-500'}`}></div>
      <span className="text-xs">
        {isHealthy 
          ? `Heartbeat: ${lastHeartbeat}s ago` 
          : `Heartbeat lost: ${lastHeartbeat}s ago`}
      </span>
    </div>
  );
};

const Dashboard: React.FC = () => {
  const [nodes, setNodes] = useState<Node[]>([]);
  const [podStatus, setPodStatus] = useState<Record<string, Record<string, any>>>({});
  const [pendingPods, setPendingPods] = useState<PendingPod[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [autoScaleEnabled, setAutoScaleEnabled] = useState(false);

  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true);
        const [nodesData, podData, clusterStatus] = await Promise.all([
          api.listNodes(),
          api.getPodStatus(),
          api.getClusterStatus(),
        ]);
        setNodes(nodesData);
        setPodStatus(podData);
        setPendingPods(clusterStatus.pendingPods || []);
        setAutoScaleEnabled(clusterStatus.autoScaleEnabled);
      } catch (err) {
        setError('Failed to fetch cluster data');
        console.error(err);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
    const interval = setInterval(fetchData, 5000); // Poll every 5s
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="container mx-auto px-4 py-8">
      <header className="flex flex-col md:flex-row justify-between items-center mb-8">
        <div>
          <h1 className="text-3xl font-bold">Cluster Dashboard</h1>
          <p className="text-gray-600 dark:text-gray-400">
            Monitor your cluster health and activity
          </p>
        </div>
        <div className="mt-4 md:mt-0 space-x-2">
          <Link to="/nodes">
            <Button>Manage Nodes</Button>
          </Link>
          <Link to="/pods">
            <Button variant="outline">Manage Pods</Button>
          </Link>
        </div>
      </header>

      {error && (
        <div className="bg-red-100 dark:bg-red-900 text-red-800 dark:text-red-200 p-4 rounded-md mb-6">
          {error}
        </div>
      )}

      <Card className="mb-8">
        <CardHeader>
          <CardTitle>Cluster Overview</CardTitle>
          <CardDescription>Current status of your cluster</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div className="p-4 bg-gray-50 dark:bg-gray-800 rounded-lg">
              <div className="text-sm font-medium text-gray-500 dark:text-gray-400">Active Nodes</div>
              <div className="text-3xl font-bold mt-1">{nodes.filter(node => node.healthy).length}/{nodes.length}</div>
            </div>
            <div className="p-4 bg-gray-50 dark:bg-gray-800 rounded-lg">
              <div className="text-sm font-medium text-gray-500 dark:text-gray-400">Running Pods</div>
              <div className="text-3xl font-bold mt-1">
                {Object.values(podStatus).reduce((count, nodePods) => count + Object.keys(nodePods).length, 0)}
              </div>
            </div>
            <div className={`p-4 bg-gray-50 dark:bg-gray-800 rounded-lg ${pendingPods.length > 0 ? 'bg-amber-50 dark:bg-amber-900/20' : ''}`}>
              <div className="text-sm font-medium text-gray-500 dark:text-gray-400 flex items-center">
                Pending Pods
                {pendingPods.length > 0 && <Clock className="h-4 w-4 ml-1 text-amber-500" />}
              </div>
              <div className={`text-3xl font-bold mt-1 ${pendingPods.length > 0 ? 'text-amber-600 dark:text-amber-400' : ''}`}>
                {pendingPods.length}
              </div>
            </div>
            <div className="p-4 bg-gray-50 dark:bg-gray-800 rounded-lg">
              <div className="text-sm font-medium text-gray-500 dark:text-gray-400">Auto-Scaling</div>
              <div className={`text-3xl font-bold mt-1 ${autoScaleEnabled ? "text-green-500" : "text-red-500"}`}>
                {autoScaleEnabled ? "Enabled" : "Disabled"}
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Pending Pods Warning Card */}
      {pendingPods.length > 0 && (
        <Card className="mb-8 border-amber-300 dark:border-amber-700">
          <CardHeader className="bg-amber-50 dark:bg-amber-900/20">
            <CardTitle className="flex items-center text-amber-800 dark:text-amber-200">
              <AlertTriangle className="h-5 w-5 mr-2 text-amber-600 dark:text-amber-400" />
              Pending Pods Detected
            </CardTitle>
            <CardDescription className="text-amber-700 dark:text-amber-300">
              There are {pendingPods.length} pod(s) waiting to be rescheduled due to insufficient cluster resources
            </CardDescription>
          </CardHeader>
          <CardContent className="pt-4">
            <p className="text-sm">
              These pods were previously running but couldn't be rescheduled after a node was deleted. 
              They are waiting in a queue and will be automatically rescheduled when resources become available.
            </p>
            <div className="mt-4">
              <strong className="font-medium">Pending pods:</strong>
              <ul className="list-disc list-inside mt-2 pl-2">
                {pendingPods.slice(0, 3).map(pod => (
                  <li key={pod.pod_id} className="text-sm">
                    <span className="font-medium">{pod.pod_id}</span> ({pod.cpu_request} cores) from {pod.origin_node}
                  </li>
                ))}
                {pendingPods.length > 3 && (
                  <li className="text-sm italic">And {pendingPods.length - 3} more...</li>
                )}
              </ul>
            </div>
          </CardContent>
          <CardFooter className="bg-amber-50/50 dark:bg-amber-900/10">
            <div className="flex space-x-4">
              <Link to="/pod-manager">
                <Button variant="secondary" className="bg-amber-100 hover:bg-amber-200 dark:bg-amber-800 dark:hover:bg-amber-700">
                  View All Pending Pods
                </Button>
              </Link>
              <Link to="/nodes">
                <Button variant="outline">
                  Add Node
                </Button>
              </Link>
            </div>
          </CardFooter>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Node Status</CardTitle>
          <CardDescription>Health and activity of cluster nodes</CardDescription>
        </CardHeader>
        <CardContent>
          {loading && nodes.length === 0 ? (
            <div className="text-center py-10">
              <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-gray-900 dark:border-gray-100"></div>
              <p className="mt-2">Loading cluster data...</p>
            </div>
          ) : nodes.length === 0 ? (
            <div className="text-center py-10">
              <p className="text-lg font-medium mb-2">No Nodes Available</p>
              <p className="text-gray-600 dark:text-gray-400 mb-4">
                Your cluster doesn't have any nodes yet.
              </p>
              <Link to="/nodes">
                <Button>Add Your First Node</Button>
              </Link>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {nodes.map((node) => (
                <div key={node.node_id} className="p-4 border rounded-lg bg-card text-card-foreground shadow-sm">
                  <div className="flex justify-between items-center">
                    <div className="font-medium">{node.node_id}</div>
                    <Badge variant={node.healthy ? "success" : "destructive"}>
                      {node.healthy ? "Healthy" : "Unhealthy"}
                    </Badge>
                  </div>
                  <HeartbeatIndicator lastHeartbeat={node.last_heartbeat} />
                  <div className="mt-2 text-sm text-gray-600 dark:text-gray-400">
                    {Object.keys(podStatus[node.node_id] || {}).length} pods running
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Notifications component */}
      <ClusterNotifications autoScaleEnabled={autoScaleEnabled} />
    </div>
  );
};

export default Dashboard; 