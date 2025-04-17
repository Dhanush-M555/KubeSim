import React, { useState, useEffect } from 'react';
import { X } from 'lucide-react';

interface ClusterEvent {
  id: string;
  message: string;
  type: 'info' | 'success' | 'warning' | 'error';
  timestamp: Date;
}

interface ClusterNotificationsProps {
  autoScaleEnabled: boolean;
}

const ClusterNotifications: React.FC<ClusterNotificationsProps> = ({ autoScaleEnabled }) => {
  const [events, setEvents] = useState<ClusterEvent[]>([]);

  // Poll for cluster events (auto-scaling actions, node failures, etc.)
  useEffect(() => {
    if (!autoScaleEnabled) return;

    // Add a demo event (in real implementation, we would poll the server for events)
    const demoEvent = {
      id: `event-${Date.now()}`,
      message: 'Auto-scaling is enabled and monitoring cluster resources',
      type: 'info' as const,
      timestamp: new Date(),
    };
    
    setEvents(prev => [demoEvent, ...prev]);

    // Cleanup
    return () => {
      // Clean up any subscriptions
    };
  }, [autoScaleEnabled]);

  // Add event handler - we'll export this as a function that can be called by parent component
  const addEvent = (message: string, type: 'info' | 'success' | 'warning' | 'error') => {
    const newEvent = {
      id: `event-${Date.now()}`,
      message,
      type,
      timestamp: new Date(),
    };
    
    setEvents(prev => [newEvent, ...prev.slice(0, 9)]); // Keep only the 10 most recent events
  };

  // Remove an event
  const removeEvent = (id: string) => {
    setEvents(prev => prev.filter(event => event.id !== id));
  };

  if (events.length === 0) {
    return null;
  }

  return (
    <div className="fixed bottom-4 right-4 z-50 space-y-2 max-w-md">
      {events.map(event => (
        <div 
          key={event.id} 
          className={`
            rounded-lg shadow-lg p-4 flex items-start gap-3 animate-in fade-in slide-in-from-right
            ${event.type === 'info' ? 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200' : ''}
            ${event.type === 'success' ? 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200' : ''}
            ${event.type === 'warning' ? 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200' : ''}
            ${event.type === 'error' ? 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200' : ''}
          `}
        >
          <div className="flex-1">
            <div className="font-medium">{event.message}</div>
            <div className="text-xs mt-1">
              {event.timestamp.toLocaleTimeString()}
            </div>
          </div>
          <button 
            onClick={() => removeEvent(event.id)}
            className="text-gray-500 hover:text-gray-800 dark:text-gray-400 dark:hover:text-gray-100"
          >
            <X size={16} />
          </button>
        </div>
      ))}
    </div>
  );
};

// Export the component and a factory function to create an event
export { ClusterNotifications };
export const createClusterEvent = (message: string, type: 'info' | 'success' | 'warning' | 'error') => ({
  id: `event-${Date.now()}`,
  message,
  type,
  timestamp: new Date(),
}); 