import React, { useState, useEffect } from 'react';
import { api, Pod, PendingPod } from '../services/api';
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
import { Play, Square, RefreshCw, AlertTriangle, Check, LineChart, Clock, ArchiveIcon } from 'lucide-react';
import useUsageHistory from '../hooks/useUsageHistory';
import UsageChartModal from '../components/UsageChartModal';
import { notifyPodLaunched, notifyPodTerminated, notifyPodError } from '../lib/toast';

const PodManager: React.FC = () => {
  const [pods, setPods] = useState<Pod[]>([]);
  const [pendingPods, setPendingPods] = useState<PendingPod[]>([]);
  const [nodes, setNodes] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isLaunchingPod, setIsLaunchingPod] = useState(false);
  const [isDeletingPod, setIsDeletingPod] = useState(false);
  const [podName, setPodName] = useState('');
  const [cpuRequest, setCpuRequest] = useState<number>(1);
  const [launchError, setLaunchError] = useState<string | null>(null);
  
  // Chart state
  const [selectedPod, setSelectedPod] = useState<Pod | null>(null);
  const [isChartModalOpen, setIsChartModalOpen] = useState(false);

  // Format pod data for usage history tracking
  const podUsageData = pods.map(pod => ({
    id: `${pod.node_id}_${pod.pod_id}`,
    usage: pod.cpu_usage
  }));

  // Track pod usage history with improved hook
  const { getChartData, getResourceStats } = useUsageHistory('pod', podUsageData, 3000); // 1 second interval

  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true);
        const [nodesData, podStatus, pendingPodsData] = await Promise.all([
          api.listNodes(),
          api.getPodStatus(),
          api.getPendingPods().catch(() => []),
        ]);
        
        setNodes(nodesData);
        setPendingPods(pendingPodsData);
        
        // Convert pod status to array
        const podArray: Pod[] = [];
        for (const nodeId in podStatus) {
          for (const podId in podStatus[nodeId]) {
            podArray.push({
              pod_id: podId,
              node_id: nodeId,
              cpu_usage: podStatus[nodeId][podId].cpu_usage,
              healthy: podStatus[nodeId][podId].healthy,
              cpu_request: podStatus[nodeId][podId].cpu_request || 1,
            });
          }
        }
        
        setPods(podArray);
      } catch (err) {
        setError('Failed to fetch pod data');
        console.error(err);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
    const interval = setInterval(fetchData, 3000); // Poll every 3s
    return () => clearInterval(interval);
  }, []);

  // Launch a new pod
  const handleLaunchPod = async () => {
    try {
      setIsLaunchingPod(true);
      setLaunchError(null);
      
      // Ensure CPU is an integer
      const intCpuRequest = Math.floor(cpuRequest);
      
      // Launch pod
      const response = await api.launchPod(podName || undefined, intCpuRequest);
      
      // Refresh pod data
      const [nodesData, podStatus, pendingPodsData] = await Promise.all([
        api.listNodes(),
        api.getPodStatus(),
        api.getPendingPods().catch(() => []),
      ]);
      
      setNodes(nodesData);
      setPendingPods(pendingPodsData);
      
      // Convert pod status to array
      const podArray: Pod[] = [];
      for (const nodeId in podStatus) {
        for (const podId in podStatus[nodeId]) {
          podArray.push({
            pod_id: podId,
            node_id: nodeId,
            cpu_usage: podStatus[nodeId][podId].cpu_usage,
            healthy: podStatus[nodeId][podId].healthy,
            cpu_request: podStatus[nodeId][podId].cpu_request || 1,
          });
        }
      }
      
      setPods(podArray);
      setPodName('');
      setCpuRequest(1);
      
      // Show success notification
      const actualPodId = response?.pod_id || (podName || `pod_${Date.now()}`);
      notifyPodLaunched(actualPodId, intCpuRequest);
    } catch (err: any) {
      console.error('Launch pod error:', err);
      setLaunchError(err.response?.data?.message || 'Failed to launch pod');
      // Show error notification
      notifyPodError(err.response?.data?.message || 'Failed to launch pod');
    } finally {
      setIsLaunchingPod(false);
    }
  };

  // Delete a pod
  const handleDeletePod = async (nodeId: string, podId: string) => {
    try {
      setIsDeletingPod(true);
      await api.deletePod(nodeId, podId);
      
      // Show success notification
      notifyPodTerminated(podId);
      
      // Remove from local state
      setPods(pods.filter(pod => !(pod.pod_id === podId && pod.node_id === nodeId)));
    } catch (err: any) {
      setError('Failed to delete pod');
      console.error(err);
      // Show error notification
      notifyPodError(err.response?.data?.message || 'Failed to terminate pod');
    } finally {
      setIsDeletingPod(false);
    }
  };

  // Show chart modal for a pod
  const showPodChart = (pod: Pod) => {
    setSelectedPod(pod);
    setIsChartModalOpen(true);
  };

  // Format timestamp to human-readable time
  const formatWaitTime = (timestamp: number) => {
    const now = Date.now() / 1000; // Convert to seconds
    const waitTime = now - timestamp;
    
    if (waitTime < 60) {
      return `${Math.floor(waitTime)} seconds`;
    } else if (waitTime < 3600) {
      return `${Math.floor(waitTime / 60)} minutes`;
    } else {
      return `${Math.floor(waitTime / 3600)} hours, ${Math.floor((waitTime % 3600) / 60)} minutes`;
    }
  };

  return (
    <div className="container mx-auto px-4 py-8">
      <header className="flex flex-col md:flex-row justify-between items-center mb-8">
        <div>
          <h1 className="text-3xl font-bold">Pod Manager</h1>
          <p className="text-gray-600 dark:text-gray-400">
            Launch and manage pods across the cluster
          </p>
        </div>
      </header>

      <Card className="mb-8">
        <CardHeader>
          <CardTitle>Launch New Pod</CardTitle>
          <CardDescription>
            Create a new pod and schedule it on a node
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium mb-1">Pod Name (optional)</label>
              <input
                type="text"
                value={podName}
                onChange={(e) => setPodName(e.target.value)}
                placeholder="Auto-generated if empty"
                className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
              />
            </div>
            
            <div>
              <label className="block text-sm font-medium mb-1">CPU Request (integer cores)</label>
              <input
                type="number"
                min="1"
                step="1"
                value={cpuRequest}
                onChange={(e) => setCpuRequest(Math.max(1, Math.floor(Number(e.target.value))))}
                className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
              />
              <p className="text-xs text-muted-foreground mt-1">
                Must be a positive integer value
              </p>
            </div>
          </div>
          
          {launchError && (
            <div className="mt-4 p-3 bg-red-100 dark:bg-red-900 text-red-800 dark:text-red-200 rounded-md flex items-center">
              <AlertTriangle className="h-4 w-4 mr-2" />
              {launchError}
            </div>
          )}
        </CardContent>
        <CardFooter>
          <Button
            onClick={handleLaunchPod}
            disabled={isLaunchingPod || loading || nodes.length === 0}
            className="w-full md:w-auto"
          >
            <Play className="h-4 w-4 mr-2" />
            {isLaunchingPod ? 'Launching...' : 'Launch Pod'}
          </Button>
          
          {nodes.length === 0 && (
            <p className="text-amber-600 dark:text-amber-400 text-sm ml-4">
              <AlertTriangle className="h-4 w-4 inline mr-1" />
              No nodes available. Add a node first.
            </p>
          )}
        </CardFooter>
      </Card>

      {error && (
        <div className="bg-red-100 dark:bg-red-900 text-red-800 dark:text-red-200 p-4 rounded-md mb-6">
          {error}
        </div>
      )}

      <Card className="mb-8">
        <CardHeader className="flex flex-row items-center justify-between">
          <div>
            <CardTitle>Running Pods</CardTitle>
            <CardDescription>
              All pods running across your cluster nodes
            </CardDescription>
          </div>
          <Button variant="outline" size="sm" onClick={() => setLoading(true)}>
            <RefreshCw className={`h-4 w-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </Button>
        </CardHeader>
        <CardContent>
          {loading && pods.length === 0 ? (
            <div className="flex justify-center p-6">
              <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-primary"></div>
            </div>
          ) : pods.length === 0 ? (
            <div className="text-center py-10">
              <h3 className="text-xl font-medium mb-2">No Pods Running</h3>
              <p className="text-gray-600 dark:text-gray-400 mb-6">
                You haven't launched any pods yet.
              </p>
              <Button onClick={handleLaunchPod} disabled={isLaunchingPod || nodes.length === 0}>
                <Play className="h-4 w-4 mr-2" />
                Launch Your First Pod
              </Button>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="border-b dark:border-gray-700">
                    <th className="py-3 px-4">Pod ID</th>
                    <th className="py-3 px-4">Node</th>
                    <th className="py-3 px-4">CPU Usage</th>
                    <th className="py-3 px-4">Status</th>
                    <th className="py-3 px-4">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {pods.map((pod) => (
                    <tr 
                      key={`${pod.node_id}-${pod.pod_id}`} 
                      className="border-b dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-800 cursor-pointer transition-colors"
                      onClick={() => showPodChart(pod)}
                    >
                      <td className="py-3 px-4 font-medium">{pod.pod_id}</td>
                      <td className="py-3 px-4">{pod.node_id}</td>
                      <td className="py-3 px-4">
                        <div className="flex items-center">
                          <span 
                            className={`mr-2 ${pod.cpu_usage > pod.cpu_request ? "text-red-500 font-semibold" : ""}`}
                          >
                            {pod.healthy ? pod.cpu_usage.toFixed(2) : 0} / {pod.cpu_request} cores
                            {pod.cpu_usage > pod.cpu_request && (
                              <span className="text-xs ml-1">(Limit exceeded)</span>
                            )}
                          </span>
                          <LineChart className="h-4 w-4 text-blue-500" />
                        </div>
                      </td>
                      <td className="py-3 px-4">
                        <Badge variant={pod.healthy ? "success" : "destructive"}>
                          {pod.healthy ? (
                            <span className="flex items-center">
                              <Check className="h-3 w-3 mr-1" />
                              Healthy
                            </span>
                          ) : (
                            <span className="flex items-center">
                              <AlertTriangle className="h-3 w-3 mr-1" />
                              Unhealthy
                            </span>
                          )}
                        </Badge>
                      </td>
                      <td className="py-3 px-4">
                        <Button
                          variant="destructive"
                          size="sm"
                          onClick={(e) => {
                            e.stopPropagation();
                            handleDeletePod(pod.node_id, pod.pod_id);
                          }}
                          disabled={isDeletingPod}
                        >
                          <Square className="h-3 w-3 mr-1" />
                          Terminate
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Pending Pods Section */}
      <Card className="mb-8">
        <CardHeader>
          <CardTitle className="flex items-center">
            <Clock className="h-5 w-5 mr-2" />
            Pending Pods
          </CardTitle>
          <CardDescription>
            Pods waiting to be scheduled when resources become available
          </CardDescription>
        </CardHeader>
        <CardContent>
          {loading && pendingPods.length === 0 ? (
            <div className="flex justify-center p-6">
              <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-primary"></div>
            </div>
          ) : pendingPods.length === 0 ? (
            <div className="text-center py-6">
              <h3 className="text-lg font-medium mb-2">No Pending Pods</h3>
              <p className="text-gray-600 dark:text-gray-400">
                All pods are currently scheduled and running.
              </p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="border-b dark:border-gray-700">
                    <th className="py-3 px-4">Pod ID</th>
                    <th className="py-3 px-4">CPU Request</th>
                    <th className="py-3 px-4">Origin Node</th>
                    <th className="py-3 px-4">Waiting Since</th>
                    <th className="py-3 px-4">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {pendingPods.map((pod) => (
                    <tr key={pod.pod_id} className="border-b dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-800">
                      <td className="py-3 px-4 font-medium">{pod.pod_id}</td>
                      <td className="py-3 px-4">{pod.cpu_request} cores</td>
                      <td className="py-3 px-4">{pod.origin_node}</td>
                      <td className="py-3 px-4">{formatWaitTime(pod.waiting_since)}</td>
                      <td className="py-3 px-4">
                        <Badge variant="secondary" className="bg-amber-100 dark:bg-amber-900 text-amber-800 dark:text-amber-200">
                          <span className="flex items-center">
                            <Clock className="h-3 w-3 mr-1" />
                            Pending
                          </span>
                        </Badge>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <div className="mt-4 p-4 bg-blue-50 dark:bg-blue-900/20 text-blue-800 dark:text-blue-200 rounded-md">
            <h4 className="text-sm font-medium flex items-center mb-2">
              <ArchiveIcon className="h-4 w-4 mr-2" />
              How Pending Pods Work
            </h4>
            <p className="text-sm">
              When a node is deleted or fails, pods that cannot be immediately rescheduled due to 
              insufficient resources are placed in a pending queue. When new nodes are added or 
              resources become available, these pods will be automatically rescheduled based on 
              their requirements.
            </p>
          </div>
        </CardContent>
      </Card>

      {/* Pod Usage Chart Modal */}
      {selectedPod && (
        <UsageChartModal
          isOpen={isChartModalOpen}
          onClose={() => setIsChartModalOpen(false)}
          resourceId={`${selectedPod.node_id}_${selectedPod.pod_id}`}
          resourceType="pod"
          resourceName={selectedPod.pod_id}
          data={getChartData(`${selectedPod.node_id}_${selectedPod.pod_id}`).values}
          labels={getChartData(`${selectedPod.node_id}_${selectedPod.pod_id}`).labels}
          stats={getResourceStats(`${selectedPod.node_id}_${selectedPod.pod_id}`)}
        />
      )}
    </div>
  );
};

export default PodManager; 