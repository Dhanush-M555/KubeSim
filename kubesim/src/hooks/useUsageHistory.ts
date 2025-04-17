import { useState, useEffect, useCallback, useRef } from 'react';

// Define types
export type ResourceType = 'node' | 'pod';

export interface UsageDataPoint {
  timestamp: string;
  value: number;
}

export interface UsageHistoryMap {
  [resourceId: string]: UsageDataPoint[];
}

export interface ResourceStats {
  min: number;
  max: number;
  average: number;
  allTimeMin: number;
  allTimeMax: number;
}

export interface UsageHistoryStats {
  [resourceId: string]: ResourceStats;
}

// Set up global store on window object for true persistence
declare global {
  interface Window {
    _kubeSimUsageHistory: {
      usageHistory: UsageHistoryMap;
      usageStats: UsageHistoryStats;
      allTimeValues: { [resourceId: string]: { min: number; max: number } };
    };
  }
}

// Initialize global store if it doesn't exist
if (typeof window !== 'undefined') {
  if (!window._kubeSimUsageHistory) {
    window._kubeSimUsageHistory = {
      usageHistory: {},
      usageStats: {},
      allTimeValues: {}
    };
  }
}

// Helper to get global store safely
const getGlobalStore = () => {
  if (typeof window !== 'undefined') {
    return window._kubeSimUsageHistory;
  }
  return {
    usageHistory: {},
    usageStats: {},
    allTimeValues: {}
  };
};

const MAX_HISTORY_POINTS = 25;
const MIN_INTERVAL_MS = 1000; // Minimum 1 second between data points

export const useUsageHistory = (
  resourceType: ResourceType,
  currentData: Array<{ id: string; usage: number }>,
  refreshInterval = 5000
) => {
  // Initialize with data from global store
  const globalStore = getGlobalStore();
  const [usageHistory, setUsageHistory] = useState<UsageHistoryMap>(globalStore.usageHistory);
  const [timeLabels, setTimeLabels] = useState<string[]>([]);
  const [usageStats, setUsageStats] = useState<UsageHistoryStats>(globalStore.usageStats);
  
  // Use ref to prevent too frequent updates
  const lastUpdateRef = useRef<number>(0);

  // Add a new data point to the history
  const addDataPoint = useCallback((data: Array<{ id: string; usage: number }>) => {
    const now = Date.now();
    
    // Ensure minimum interval between updates
    if (now - lastUpdateRef.current < MIN_INTERVAL_MS) {
      return;
    }
    
    lastUpdateRef.current = now;
    
    const currentTime = new Date();
    const timeLabel = `${currentTime.getHours().toString().padStart(2, '0')}:${currentTime.getMinutes().toString().padStart(2, '0')}:${currentTime.getSeconds().toString().padStart(2, '0')}`;
    
    // Update time labels
    setTimeLabels(prev => {
      const newLabels = [...prev, timeLabel];
      return newLabels.length > MAX_HISTORY_POINTS 
        ? newLabels.slice(-MAX_HISTORY_POINTS) 
        : newLabels;
    });
    
    // Update usage history
    setUsageHistory(prev => {
      const globalStore = getGlobalStore();
      const newHistory = { ...prev };
      
      // Add new data points
      data.forEach(item => {
        const id = item.id;
        const value = item.usage;
        
        if (!newHistory[id]) {
          newHistory[id] = [];
        }
        
        newHistory[id] = [
          ...newHistory[id], 
          { timestamp: timeLabel, value }
        ];
        
        // Keep only the last MAX_HISTORY_POINTS points
        if (newHistory[id].length > MAX_HISTORY_POINTS) {
          newHistory[id] = newHistory[id].slice(-MAX_HISTORY_POINTS);
        }
        
        // Update all-time min and max in global store
        if (!globalStore.allTimeValues[id]) {
          globalStore.allTimeValues[id] = { min: value, max: value };
        } else {
          globalStore.allTimeValues[id] = {
            min: Math.min(globalStore.allTimeValues[id].min, value),
            max: Math.max(globalStore.allTimeValues[id].max, value)
          };
        }
      });
      
      // Remove items that no longer exist in the data
      const currentIds = data.map(item => item.id);
      Object.keys(newHistory).forEach(id => {
        if (!currentIds.includes(id)) {
          // Keep in global store but remove from current view
          delete newHistory[id];
        }
      });
      
      // Update global store
      globalStore.usageHistory = { ...globalStore.usageHistory, ...newHistory };
      return newHistory;
    });
    
    // Update usage statistics
    setUsageStats(prev => {
      const globalStore = getGlobalStore();
      const newStats = { ...prev };
      
      data.forEach(item => {
        const id = item.id;
        const currentValue = item.usage;
        
        // Get or initialize all-time values
        if (!globalStore.allTimeValues[id]) {
          globalStore.allTimeValues[id] = { min: currentValue, max: currentValue };
        }
        
        // Initialize stats if this is a new resource
        if (!newStats[id]) {
          newStats[id] = {
            min: currentValue,
            max: currentValue,
            average: currentValue,
            allTimeMin: globalStore.allTimeValues[id].min,
            allTimeMax: globalStore.allTimeValues[id].max
          };
        } else {
          // Get recent values for this resource including current
          const recentValues = [
            ...usageHistory[id]?.map(point => point.value) || [],
            currentValue
          ];
          
          // Calculate recent stats from visible data points
          const recentMin = Math.min(...recentValues);
          const recentMax = Math.max(...recentValues);
          
          // Use global all-time min/max values
          newStats[id] = {
            min: recentMin,
            max: recentMax,
            average: calculateAverage(recentValues),
            allTimeMin: globalStore.allTimeValues[id].min,
            allTimeMax: globalStore.allTimeValues[id].max
          };
        }
      });
      
      // Remove items that no longer exist from current view
      const currentIds = data.map(item => item.id);
      Object.keys(newStats).forEach(id => {
        if (!currentIds.includes(id)) {
          delete newStats[id];
        }
      });
      
      // Update global store
      globalStore.usageStats = { ...globalStore.usageStats, ...newStats };
      return newStats;
    });
  }, [usageHistory]);
  
  // Calculate average of an array of numbers
  const calculateAverage = (values: number[]): number => {
    if (values.length === 0) return 0;
    return values.reduce((sum, val) => sum + val, 0) / values.length;
  };
  
  // Update history when data changes
  useEffect(() => {
    addDataPoint(currentData);
    
    // Set up polling for continuous updates
    const interval = setInterval(() => {
      addDataPoint(currentData);
    }, Math.max(refreshInterval, MIN_INTERVAL_MS)); // Ensure minimum interval
    
    return () => {
      clearInterval(interval);
    };
  }, [currentData, refreshInterval, addDataPoint]);
  
  // Get data formatted for charts
  const getChartData = useCallback((id: string) => {
    const globalStore = getGlobalStore();
    const localHistory = usageHistory[id] || [];
    const globalHistory = globalStore.usageHistory[id] || [];
    
    // Use history from local state if available, otherwise from global store
    const history = localHistory.length > 0 ? localHistory : globalHistory;
    
    return {
      labels: history.map(item => item.timestamp),
      values: history.map(item => item.value)
    };
  }, [usageHistory]);
  
  // Get stats for a specific resource
  const getResourceStats = useCallback((id: string) => {
    const globalStore = getGlobalStore();
    const localStats = usageStats[id];
    
    // If no local stats, build from global all-time values
    if (!localStats) {
      const allTimeValues = globalStore.allTimeValues[id];
      if (allTimeValues) {
        return {
          min: 0,
          max: 0,
          average: 0,
          allTimeMin: allTimeValues.min,
          allTimeMax: allTimeValues.max
        };
      }
      return { min: 0, max: 0, average: 0, allTimeMin: 0, allTimeMax: 0 };
    }
    
    // Ensure all-time values from global store take precedence
    if (globalStore.allTimeValues[id]) {
      return {
        ...localStats,
        allTimeMin: globalStore.allTimeValues[id].min,
        allTimeMax: globalStore.allTimeValues[id].max
      };
    }
    
    return localStats;
  }, [usageStats]);
  
  return {
    usageHistory,
    timeLabels,
    getChartData,
    getResourceStats,
    usageStats
  };
};

export default useUsageHistory; 