import { useState, useEffect } from 'react';
import { Wifi, ServerIcon } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { ConnectionPanel } from '@/components/connection-panel';
import { TagDataPanel } from '@/components/tag-data-panel';
import { LogPanel } from '@/components/log-panel';
import { useWebSocket } from '@/hooks/use-websocket';
import { apiRequest } from '@/lib/queryClient';
import type { RfidTag, SystemLog, RfidReaderStatus, WebSocketMessage } from '@shared/schema';

export default function RfidDashboard() {
  const [tags, setTags] = useState<RfidTag[]>([]);
  const [logs, setLogs] = useState<SystemLog[]>([]);
  const [readerStatus, setReaderStatus] = useState<RfidReaderStatus>({ connected: false });
  const [statistics, setStatistics] = useState({
    totalReads: 0,
    uniqueTags: 0,
    readRate: 0,
  });

  // WebSocket connection
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  const wsUrl = `${protocol}//${window.location.host}/ws`;
  const { isConnected: wsConnected, lastMessage } = useWebSocket(wsUrl);

  // Load initial data
  const loadTags = async () => {
    try {
      const response = await apiRequest('GET', '/api/tags');
      const data = await response.json();
      setTags(data);
    } catch (error) {
      console.error('Failed to load tags:', error);
    }
  };

  const loadLogs = async () => {
    try {
      const response = await apiRequest('GET', '/api/logs');
      const data = await response.json();
      setLogs(data);
    } catch (error) {
      console.error('Failed to load logs:', error);
    }
  };

  const loadStatistics = async () => {
    try {
      const response = await apiRequest('GET', '/api/statistics');
      const data = await response.json();
      setStatistics(data);
    } catch (error) {
      console.error('Failed to load statistics:', error);
    }
  };

  useEffect(() => {
    loadTags();
    loadLogs();
    loadStatistics();
    
    // Refresh data periodically
    const interval = setInterval(() => {
      loadTags();
      loadLogs();
      loadStatistics();
    }, 10000);

    return () => clearInterval(interval);
  }, []);

  // Handle WebSocket messages
  useEffect(() => {
    if (!lastMessage) return;

    const message = lastMessage as WebSocketMessage;
    
    switch (message.type) {
      case 'tag_read':
        // Refresh tags when new tag is read
        loadTags();
        break;
        
      case 'reader_status':
        setReaderStatus(message.data as RfidReaderStatus);
        break;
        
      case 'log_entry':
        // Refresh logs when new entry is added
        loadLogs();
        break;
        
      case 'statistics':
        setStatistics(message.data as typeof statistics);
        break;
    }
  }, [lastMessage]);

  const getConnectionStatusText = () => {
    if (readerStatus.connected) return 'Connected';
    return 'Disconnected';
  };

  const getConnectionStatusColor = () => {
    if (readerStatus.connected) return 'text-green-400';
    return 'text-red-400';
  };

  return (
    <div className="min-h-screen bg-background text-foreground">
      {/* Header */}
      <header className="border-b border-border bg-card">
        <div className="container mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-4">
              <div className="flex items-center space-x-2">
                <Wifi className="text-primary text-2xl" />
                <h1 className="text-2xl font-bold text-foreground">RRU9816 RFID Interface</h1>
              </div>
              <Badge variant="secondary">
                UHF Desktop Reader
              </Badge>
            </div>
            <div className="flex items-center space-x-4">
              <div className="flex items-center space-x-2">
                <div className={`w-3 h-3 rounded-full ${readerStatus.connected ? 'bg-green-500 animate-pulse' : 'bg-red-500'}`} />
                <span className={`text-sm font-medium ${getConnectionStatusColor()}`} data-testid="text-connection-status">
                  {getConnectionStatusText()}
                </span>
              </div>
              <div className="flex items-center space-x-2">
                <ServerIcon className="h-4 w-4 text-muted-foreground" />
                <span className="text-sm text-muted-foreground">localhost:5000</span>
              </div>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="container mx-auto px-6 py-8">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          
          {/* Connection Panel */}
          <div className="lg:col-span-1">
            <ConnectionPanel 
              readerStatus={readerStatus}
              wsConnected={wsConnected}
            />
          </div>

          {/* Tag Data Panel */}
          <div className="lg:col-span-2">
            <TagDataPanel 
              tags={tags}
              onTagsUpdate={loadTags}
              statistics={statistics}
            />
          </div>
        </div>

        {/* Log Panel */}
        <div className="mt-8">
          <LogPanel 
            logs={logs}
            onLogsUpdate={loadLogs}
          />
        </div>
      </main>
    </div>
  );
}
