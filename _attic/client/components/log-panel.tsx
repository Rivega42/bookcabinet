import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Download, Trash2 } from 'lucide-react';
import { useToast } from '@/hooks/use-toast';
import { apiRequest } from '@/lib/queryClient';
import type { SystemLog } from '@shared/schema';

interface LogPanelProps {
  logs: SystemLog[];
  onLogsUpdate: () => void;
}

export function LogPanel({ logs, onLogsUpdate }: LogPanelProps) {
  const { toast } = useToast();

  const handleClearLogs = async () => {
    try {
      await apiRequest('DELETE', '/api/logs');
      onLogsUpdate();
      toast({
        title: "Success",
        description: "System logs cleared",
      });
    } catch (error) {
      toast({
        title: "Error",
        description: "Failed to clear logs",
        variant: "destructive",
      });
    }
  };

  const handleExportLogs = () => {
    const logText = logs.map(log => 
      `[${formatTimestamp(log.timestamp)}] [${log.level}] ${log.message}`
    ).join('\n');
    
    const blob = new Blob([logText], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `rfid-logs-${new Date().toISOString().split('T')[0]}.txt`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    
    toast({
      title: "Success",
      description: "Logs exported successfully",
    });
  };

  const formatTimestamp = (timestamp: Date | string) => {
    const date = typeof timestamp === 'string' ? new Date(timestamp) : timestamp;
    return date.toLocaleTimeString();
  };

  const getLevelColor = (level: string) => {
    switch (level.toUpperCase()) {
      case 'SUCCESS':
        return 'text-green-400';
      case 'ERROR':
        return 'text-red-400';
      case 'WARNING':
        return 'text-yellow-400';
      case 'INFO':
      default:
        return 'text-blue-400';
    }
  };

  return (
    <Card>
      <CardContent className="p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-foreground">System Log</h3>
          <div className="flex items-center space-x-2">
            <Button 
              variant="secondary" 
              size="sm"
              onClick={handleExportLogs}
              data-testid="button-export-logs"
            >
              <Download className="h-4 w-4 mr-1" />
              Export
            </Button>
            <Button 
              variant="secondary" 
              size="sm"
              onClick={handleClearLogs}
              data-testid="button-clear-logs"
            >
              <Trash2 className="h-4 w-4 mr-1" />
              Clear
            </Button>
          </div>
        </div>
        
        <div className="bg-background rounded border border-border p-4 font-mono text-sm h-32 overflow-y-auto" data-testid="log-container">
          {logs.length > 0 ? (
            logs.map((log, index) => (
              <div key={log.id} className="text-muted-foreground mb-1" data-testid={`log-entry-${index}`}>
                <span className="text-green-400">[{formatTimestamp(log.timestamp)}]</span>{' '}
                <span className={getLevelColor(log.level)}>[{log.level}]</span>{' '}
                {log.message}
              </div>
            ))
          ) : (
            <div className="text-muted-foreground italic">No log entries yet...</div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
