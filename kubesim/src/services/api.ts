import axios from 'axios';

const API_URL = 'http://localhost:5000';

// Types
export interface Pod {
  pod_id: string;
  node_id: string;
  cpu_usage: number;
  healthy: boolean;
  cpu_request: number;
}

export interface Node {
  node_id: string;
  healthy: boolean;
  pod_health: Record<string, boolean>;
  last_heartbeat: number;
  capacity: number;
}

export interface ClusterStatus {
  nodes: Node[];
  pods: Pod[];
  totalCpuUsage: number;
  totalCpuRequested: number;
  autoScaleEnabled: boolean;
  schedulingAlgo: string;
}

interface ConfigFile {
  AUTO_SCALE: boolean;
  SCHEDULING_ALGO: string;
  DEFAULT_NODE_CAPACITY: number;
  AUTO_SCALE_HIGH_THRESHOLD: number;
  AUTO_SCALE_LOW_THRESHOLD: number;
}

// API client
const apiClient = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// API functions
export const api = {
  // Config operations
  async getConfig(): Promise<ConfigFile> {
    try {
      const response = await axios.get<ConfigFile>('/config.json');
      return response.data;
    } catch (error) {
      console.error('Failed to load config file:', error);
      // Return default values if config fetch fails
      return {
        AUTO_SCALE: false,
        SCHEDULING_ALGO: 'first-fit',
        DEFAULT_NODE_CAPACITY: 4,
        AUTO_SCALE_HIGH_THRESHOLD: 80,
        AUTO_SCALE_LOW_THRESHOLD: 20
      };
    }
  },

  // Node operations
  async addNode(cores?: number) {
    const response = await apiClient.post('/add-node', cores ? { cores } : undefined);
    return response.data;
  },

  async deleteNode(nodeId: string) {
    const response = await apiClient.delete('/delete-node', {
      data: { node_id: nodeId },
    });
    return response.data;
  },

  async listNodes() {
    const response = await apiClient.get('/list-nodes');
    return response.data as Node[];
  },

  // Pod operations
  async launchPod(podId?: string, cpuRequest: number = 1) {
    const response = await apiClient.post('/launch-pod', {
      pod_id: podId,
      cpu: cpuRequest
    });
    return response.data;
  },

  async deletePod(nodeId: string, podId: string) {
    const response = await apiClient.delete('/delete-pod', {
      data: { node_id: nodeId, pod_id: podId },
    });
    return response.data;
  },

  async getPodStatus() {
    const response = await apiClient.get('/pod-status');
    return response.data;
  },

  // Get cluster status (combined data)
  async getClusterStatus(): Promise<ClusterStatus> {
    const [nodesResponse, podsResponse, config] = await Promise.all([
      this.listNodes(),
      this.getPodStatus(),
      this.getConfig()
    ]);

    const nodes = nodesResponse;
    
    // Format pods data
    const pods: Pod[] = [];
    let totalCpuUsage = 0;
    let totalCpuRequested = 0;

    for (const nodeId in podsResponse) {
      for (const podId in podsResponse[nodeId]) {
        const podData = podsResponse[nodeId][podId];
        
        // Use the actual cpu_request value from the backend instead of approximating
        const pod: Pod = {
          pod_id: podId,
          node_id: nodeId,
          cpu_usage: podData.cpu_usage,
          healthy: podData.healthy,
          cpu_request: podData.cpu_request || 1 // Use the backend provided value with fallback
        };
        
        pods.push(pod);
        totalCpuUsage += podData.cpu_usage;
        totalCpuRequested += podData.cpu_request || 1; // Use actual request value, not an approximation
      }
    }

    return {
      nodes,
      pods,
      totalCpuUsage,
      totalCpuRequested,
      autoScaleEnabled: config.AUTO_SCALE,
      schedulingAlgo: config.SCHEDULING_ALGO,
    };
  },
}; 