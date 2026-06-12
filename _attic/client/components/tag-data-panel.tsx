import { useState, useEffect } from 'react';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Trash2, Play, Copy, Wifi, Eye, Tag, Gauge } from 'lucide-react';
import { useToast } from '@/hooks/use-toast';
import { apiRequest } from '@/lib/queryClient';
import type { RfidTag } from '@shared/schema';

interface TagDataPanelProps {
  tags: RfidTag[];
  onTagsUpdate: () => void;
  statistics: {
    totalReads: number;
    uniqueTags: number;
    readRate: number;
  };
}

export function TagDataPanel({ tags, onTagsUpdate, statistics }: TagDataPanelProps) {
  const { toast } = useToast();

  const handleClearTags = async () => {
    try {
      await apiRequest('DELETE', '/api/tags');
      onTagsUpdate();
      toast({
        title: "Success",
        description: "All tags cleared",
      });
    } catch (error) {
      toast({
        title: "Error",
        description: "Failed to clear tags",
        variant: "destructive",
      });
    }
  };

  const handleStartInventory = async () => {
    try {
      await apiRequest('POST', '/api/inventory');
      toast({
        title: "Success",
        description: "Inventory scan started",
      });
    } catch (error) {
      toast({
        title: "Error",
        description: "Failed to start inventory",
        variant: "destructive",
      });
    }
  };

  const copyEpcToClipboard = async (epc: string) => {
    try {
      await navigator.clipboard.writeText(epc);
      toast({
        title: "Copied",
        description: "EPC code copied to clipboard",
      });
    } catch (error) {
      toast({
        title: "Error",
        description: "Failed to copy EPC code",
        variant: "destructive",
      });
    }
  };

  const formatTimestamp = (timestamp: Date | string) => {
    const date = typeof timestamp === 'string' ? new Date(timestamp) : timestamp;
    return date.toLocaleTimeString();
  };

  const getRssiColor = (rssi: number) => {
    if (rssi > -40) return 'bg-green-500';
    if (rssi > -55) return 'bg-yellow-500';
    return 'bg-red-500';
  };

  return (
    <div className="space-y-6">
      <Card>
        <CardContent className="p-6">
          <div className="flex items-center justify-between mb-6">
            <div className="flex items-center space-x-3">
              <h2 className="text-lg font-semibold text-foreground">RFID Tag Readings</h2>
              <Badge variant="secondary" data-testid="badge-tag-count">
                {statistics.uniqueTags} tags detected
              </Badge>
            </div>
            <div className="flex items-center space-x-4">
              <Button 
                variant="secondary" 
                onClick={handleClearTags}
                data-testid="button-clear-tags"
              >
                <Trash2 className="h-4 w-4 mr-2" />
                Clear
              </Button>
              <Button onClick={handleStartInventory} data-testid="button-start-reading">
                <Play className="h-4 w-4 mr-2" />
                Start Reading
              </Button>
            </div>
          </div>

          <div className="bg-muted/20 border border-border rounded-lg p-4 mb-6">
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-3">
                <div className="w-4 h-4 rounded-full bg-green-500 animate-pulse" />
                <span className="text-sm font-medium text-foreground">Real-time Reading Active</span>
              </div>
              <div className="flex items-center space-x-4 text-sm text-muted-foreground">
                <div className="flex items-center space-x-1">
                  <span>Rate: <span className="font-mono" data-testid="text-read-rate">{statistics.readRate}/sec</span></span>
                </div>
              </div>
            </div>
          </div>

          {tags.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-border">
                    <th className="text-left py-3 px-4 font-medium text-muted-foreground text-sm">#</th>
                    <th className="text-left py-3 px-4 font-medium text-muted-foreground text-sm">EPC Code</th>
                    <th className="text-left py-3 px-4 font-medium text-muted-foreground text-sm">RSSI</th>
                    <th className="text-left py-3 px-4 font-medium text-muted-foreground text-sm">Count</th>
                    <th className="text-left py-3 px-4 font-medium text-muted-foreground text-sm">First Seen</th>
                    <th className="text-left py-3 px-4 font-medium text-muted-foreground text-sm">Last Seen</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {tags.map((tag, index) => (
                    <tr key={tag.id} className="hover:bg-muted/10 transition-colors" data-testid={`row-tag-${index}`}>
                      <td className="py-4 px-4 text-sm text-muted-foreground">{index + 1}</td>
                      <td className="py-4 px-4">
                        <div className="flex items-center space-x-2">
                          <code className="bg-secondary/50 text-primary px-2 py-1 rounded text-sm font-mono" data-testid={`text-epc-${index}`}>
                            {tag.epc}
                          </code>
                          <Button 
                            variant="ghost" 
                            size="sm"
                            onClick={() => copyEpcToClipboard(tag.epc)}
                            data-testid={`button-copy-epc-${index}`}
                          >
                            <Copy className="h-3 w-3" />
                          </Button>
                        </div>
                      </td>
                      <td className="py-4 px-4">
                        <div className="flex items-center space-x-2">
                          <div className={`w-2 h-2 rounded-full ${getRssiColor(parseFloat(tag.rssi || '0'))}`} />
                          <span className="text-sm font-mono" data-testid={`text-rssi-${index}`}>
                            {tag.rssi} dBm
                          </span>
                        </div>
                      </td>
                      <td className="py-4 px-4 text-sm font-mono" data-testid={`text-count-${index}`}>{tag.readCount}</td>
                      <td className="py-4 px-4 text-sm text-muted-foreground font-mono">
                        {formatTimestamp(tag.firstSeen)}
                      </td>
                      <td className="py-4 px-4 text-sm font-mono">
                        {formatTimestamp(tag.lastSeen)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="text-center py-12">
              <div className="w-24 h-24 mx-auto bg-muted/20 rounded-full flex items-center justify-center mb-4">
                <Wifi className="h-12 w-12 text-muted-foreground" />
              </div>
              <h3 className="text-lg font-medium text-foreground mb-2">No RFID Tags Detected</h3>
              <p className="text-muted-foreground text-sm mb-6">
                Place RFID tags near the reader antenna to start detection
              </p>
              <Button onClick={handleStartInventory} data-testid="button-start-scanning">
                <Play className="h-4 w-4 mr-2" />
                Start Scanning
              </Button>
            </div>
          )}
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <Card>
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-muted-foreground">Total Reads</p>
                <p className="text-2xl font-bold text-foreground" data-testid="text-total-reads">
                  {statistics.totalReads}
                </p>
              </div>
              <div className="w-12 h-12 bg-primary/20 rounded-lg flex items-center justify-center">
                <Eye className="h-6 w-6 text-primary" />
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-muted-foreground">Unique Tags</p>
                <p className="text-2xl font-bold text-foreground" data-testid="text-unique-tags">
                  {statistics.uniqueTags}
                </p>
              </div>
              <div className="w-12 h-12 bg-green-500/20 rounded-lg flex items-center justify-center">
                <Tag className="h-6 w-6 text-green-500" />
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-muted-foreground">Read Rate</p>
                <p className="text-2xl font-bold text-foreground" data-testid="text-read-rate-stat">
                  {statistics.readRate}/s
                </p>
              </div>
              <div className="w-12 h-12 bg-yellow-500/20 rounded-lg flex items-center justify-center">
                <Gauge className="h-6 w-6 text-yellow-500" />
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
