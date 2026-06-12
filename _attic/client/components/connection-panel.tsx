import { useState, useEffect } from 'react';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Badge } from '@/components/ui/badge';
import { Cog, Plug, X, RefreshCw, Wifi, Server } from 'lucide-react';
import { useToast } from '@/hooks/use-toast';
import { apiRequest } from '@/lib/queryClient';
import type { RfidReaderStatus, ReaderType, ReaderConfig } from '@shared/schema';

interface ConnectionPanelProps {
  readerStatus: RfidReaderStatus;
  wsConnected: boolean;
}

export function ConnectionPanel({ readerStatus, wsConnected }: ConnectionPanelProps) {
  const [availablePorts, setAvailablePorts] = useState<string[]>([]);
  const [selectedPort, setSelectedPort] = useState<string>('');
  const [selectedReaderType, setSelectedReaderType] = useState<ReaderType | ''>('');
  const [selectedBaudRate, setSelectedBaudRate] = useState<string>('');
  const [readerConfigs, setReaderConfigs] = useState<Record<ReaderType, ReaderConfig> | null>(null);
  const [isConnecting, setIsConnecting] = useState(false);
  const { toast } = useToast();

  const loadPorts = async () => {
    try {
      const response = await apiRequest('GET', '/api/ports');
      const data = await response.json();
      setAvailablePorts(data.ports || []);
    } catch (error) {
      toast({
        title: "Error",
        description: "Failed to load COM ports",
        variant: "destructive",
      });
    }
  };

  const loadReaderConfigs = async () => {
    try {
      const response = await apiRequest('GET', '/api/reader-configs');
      const data = await response.json();
      setReaderConfigs(data.configs || {});
    } catch (error) {
      toast({
        title: "Error",
        description: "Failed to load reader configurations",
        variant: "destructive",
      });
    }
  };

  useEffect(() => {
    loadPorts();
    loadReaderConfigs();
  }, []);

  // Update baud rate when reader type changes
  useEffect(() => {
    if (selectedReaderType && readerConfigs) {
      const config = readerConfigs[selectedReaderType as ReaderType];
      if (config && config.baudRate) {
        setSelectedBaudRate(config.baudRate.toString());
      }
    }
  }, [selectedReaderType, readerConfigs]);

  const handleConnect = async () => {
    if (!selectedPort) {
      toast({
        title: "Error",
        description: "Please select a COM port",
        variant: "destructive",
      });
      return;
    }

    if (!selectedReaderType) {
      toast({
        title: "Error",
        description: "Please select a reader type",
        variant: "destructive",
      });
      return;
    }

    setIsConnecting(true);
    try {
      await apiRequest('POST', '/api/connect', {
        port: selectedPort,
        readerType: selectedReaderType,
        baudRate: selectedBaudRate ? parseInt(selectedBaudRate) : undefined,
      });
      
      toast({
        title: "Success",
        description: `Connected to ${selectedReaderType} on ${selectedPort}`,
      });
    } catch (error) {
      toast({
        title: "Connection Failed",
        description: error instanceof Error ? error.message : "Failed to connect to RFID reader",
        variant: "destructive",
      });
    } finally {
      setIsConnecting(false);
    }
  };

  const handleDisconnect = async () => {
    try {
      await apiRequest('POST', '/api/disconnect');
      toast({
        title: "Disconnected",
        description: "RFID reader disconnected",
      });
    } catch (error) {
      toast({
        title: "Error",
        description: "Failed to disconnect",
        variant: "destructive",
      });
    }
  };

  const getStatusColor = () => {
    if (isConnecting) return 'bg-yellow-500';
    return readerStatus.connected ? 'bg-green-500' : 'bg-red-500';
  };

  const getStatusText = () => {
    if (isConnecting) return 'Connecting...';
    return readerStatus.connected ? 'Connected' : 'Disconnected';
  };

  return (
    <div className="space-y-6">
      <Card>
        <CardContent className="p-6">
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-lg font-semibold text-foreground">Connection Control</h2>
            <Cog className="h-5 w-5 text-muted-foreground" />
          </div>

          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-foreground mb-2">RFID Reader Type</label>
              <Select value={selectedReaderType} onValueChange={(value) => setSelectedReaderType(value as ReaderType)}>
                <SelectTrigger data-testid="select-reader-type">
                  <SelectValue placeholder="Select Reader Model..." />
                </SelectTrigger>
                <SelectContent>
                  {readerConfigs && Object.entries(readerConfigs).map(([type, config]) => (
                    <SelectItem key={type} value={type}>
                      {config.description}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div>
              <label className="block text-sm font-medium text-foreground mb-2">COM Port</label>
              <Select value={selectedPort} onValueChange={setSelectedPort}>
                <SelectTrigger data-testid="select-com-port">
                  <SelectValue placeholder="Select Port..." />
                </SelectTrigger>
                <SelectContent>
                  {availablePorts.map((port) => (
                    <SelectItem key={port} value={port}>
                      {port}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div>
              <label className="block text-sm font-medium text-foreground mb-2">Baud Rate</label>
              <Select value={selectedBaudRate} onValueChange={setSelectedBaudRate}>
                <SelectTrigger data-testid="select-baud-rate">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="9600">9600</SelectItem>
                  <SelectItem value="19200">19200</SelectItem>
                  <SelectItem value="38400">38400</SelectItem>
                  <SelectItem value="57600">57600</SelectItem>
                  <SelectItem value="115200">115200</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="flex space-x-3 pt-4">
              <Button 
                onClick={handleConnect}
                disabled={isConnecting || readerStatus.connected}
                className="flex-1"
                data-testid="button-connect"
              >
                <Plug className="h-4 w-4 mr-2" />
                Connect
              </Button>
              <Button 
                variant="destructive"
                onClick={handleDisconnect}
                disabled={!readerStatus.connected}
                className="flex-1"
                data-testid="button-disconnect"
              >
                <X className="h-4 w-4 mr-2" />
                Disconnect
              </Button>
            </div>

            <Button 
              variant="secondary" 
              onClick={loadPorts}
              className="w-full"
              data-testid="button-refresh-ports"
            >
              <RefreshCw className="h-4 w-4 mr-2" />
              Refresh Ports
            </Button>
          </div>

          <div className="mt-8 pt-6 border-t border-border">
            <h3 className="text-sm font-medium text-foreground mb-4">Device Information</h3>
            <div className="space-y-3 text-sm">
              {selectedReaderType && readerConfigs ? (
                <>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Model:</span>
                    <code className="text-foreground font-mono">{selectedReaderType}</code>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Description:</span>
                    <span className="text-foreground">{readerConfigs[selectedReaderType as ReaderType].description}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Frequency:</span>
                    <span className="text-foreground">{readerConfigs[selectedReaderType as ReaderType].frequency}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Protocol:</span>
                    <span className="text-foreground">{readerConfigs[selectedReaderType as ReaderType].protocol}</span>
                  </div>
                  {readerConfigs[selectedReaderType as ReaderType].baudRate && (
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Default Baud Rate:</span>
                      <span className="text-foreground">{readerConfigs[selectedReaderType as ReaderType].baudRate}</span>
                    </div>
                  )}
                </>
              ) : (
                <div className="text-center text-muted-foreground py-4">
                  Select a reader type to view device information
                </div>
              )}
              <div className="flex justify-between">
                <span className="text-muted-foreground">Status:</span>
                <div className="flex items-center space-x-2">
                  <div className={`w-2 h-2 rounded-full ${getStatusColor()} ${isConnecting || readerStatus.connected ? 'animate-pulse' : ''}`} />
                  <span className={`font-medium ${readerStatus.connected ? 'text-green-400' : 'text-red-400'}`} data-testid="text-device-status">
                    {getStatusText()}
                  </span>
                </div>
              </div>
              {readerStatus.connected && readerStatus.readerType && (
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Connected Reader:</span>
                  <code className="text-foreground font-mono">{readerStatus.readerType}</code>
                </div>
              )}
              {readerStatus.port && (
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Port:</span>
                  <code className="text-foreground font-mono">{readerStatus.port}</code>
                </div>
              )}
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="p-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <Server className="h-4 w-4 text-primary" />
              <span className="text-sm font-medium text-foreground">WebSocket</span>
            </div>
            <div className="flex items-center space-x-2">
              <div className={`w-2 h-2 rounded-full ${wsConnected ? 'bg-green-500 animate-pulse' : 'bg-red-500'}`} />
              <span className={`text-sm ${wsConnected ? 'text-green-400' : 'text-red-400'}`} data-testid="text-websocket-status">
                {wsConnected ? 'Connected' : 'Disconnected'}
              </span>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
