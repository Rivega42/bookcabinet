import { useQuery } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { Switch } from "@/components/ui/switch";
import { apiRequest, queryClient } from "@/lib/queryClient";
import type { SystemLog, Statistics, SystemStatus } from "@shared/schema";
import {
  AlertTriangle, CheckCircle, XCircle, Wifi, WifiOff, Database,
  Cpu, Radio, CreditCard, MonitorDot,
} from "lucide-react";

interface DashboardTabProps {
  onReaderTest: (readerId: string) => void;
}

export function DashboardTab({ onReaderTest }: DashboardTabProps) {
  const { data: status } = useQuery<SystemStatus>({
    queryKey: ['/api/status'],
    refetchInterval: 2000,
  });
  const { data: statistics } = useQuery<Statistics>({
    queryKey: ['/api/statistics'],
    refetchInterval: 5000,
  });
  const { data: rfidReaders = [] } = useQuery<any[]>({
    queryKey: ['/api/rfid-readers'],
    refetchInterval: 3000,
  });
  const { data: logs = [] } = useQuery<SystemLog[]>({
    queryKey: ['/api/logs'],
    refetchInterval: 3000,
  });

  const toggleMaintenance = async () => {
    await apiRequest('POST', '/api/maintenance', { enabled: !status?.maintenanceMode });
    queryClient.invalidateQueries({ queryKey: ['/api/status'] });
  };

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-4 gap-4">
        <Card data-testid="stat-card-issues">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-slate-500">Выдачи сегодня</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold">{statistics?.issuesToday || 0}</div>
            <p className="text-xs text-slate-500">Всего: {statistics?.issuesTotal || 0}</p>
          </CardContent>
        </Card>

        <Card data-testid="stat-card-returns">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-slate-500">Возвраты сегодня</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold">{statistics?.returnsToday || 0}</div>
            <p className="text-xs text-slate-500">Всего: {statistics?.returnsTotal || 0}</p>
          </CardContent>
        </Card>

        <Card data-testid="stat-card-cells">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-slate-500">Заполненность</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold">
              {statistics?.occupiedCells || 0}/{statistics?.totalCells || 0}
            </div>
            <p className="text-xs text-slate-500">
              {statistics?.totalCells ? Math.round((statistics.occupiedCells / statistics.totalCells) * 100) : 0}%
            </p>
          </CardContent>
        </Card>

        <Card data-testid="stat-card-extraction">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-slate-500">Требуют изъятия</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold text-orange-500">{statistics?.booksNeedExtraction || 0}</div>
          </CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-2 gap-6">
        <Card>
          <CardHeader>
            <CardTitle>Состояние системы</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-center justify-between">
              <span>Статус</span>
              <Badge variant={status?.state === 'idle' ? 'default' : status?.state === 'error' ? 'destructive' : 'secondary'}>
                {status?.state || 'unknown'}
              </Badge>
            </div>
            <div className="flex items-center justify-between">
              <span>ИРБИС64</span>
              {status?.irbisConnected ? (
                <Badge variant="default" className="flex items-center gap-1">
                  <Wifi className="w-3 h-3" /> Подключен
                </Badge>
              ) : (
                <Badge variant="secondary" className="flex items-center gap-1">
                  <WifiOff className="w-3 h-3" /> Автономный режим
                </Badge>
              )}
            </div>
            <div className="flex items-center justify-between">
              <span>Режим обслуживания</span>
              <Switch checked={status?.maintenanceMode} onCheckedChange={toggleMaintenance} data-testid="switch-maintenance" />
            </div>
            <Separator />
            <div className="text-sm text-slate-500">
              Позиция: X={status?.position.x}, Y={status?.position.y}, Tray={status?.position.tray}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Датчики</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 gap-2 text-sm">
              {Object.entries(status?.sensors || {}).map(([name, value]) => (
                <div key={name} className="flex items-center justify-between p-2 bg-slate-50 rounded">
                  <span>{name.replace('_', ' ')}</span>
                  {value ? (
                    <CheckCircle className="w-4 h-4 text-green-500" />
                  ) : (
                    <XCircle className="w-4 h-4 text-slate-300" />
                  )}
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Radio className="w-4 h-4" />
              RFID Считыватели
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {rfidReaders.map((reader: any) => (
              <div key={reader.id} className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-2 flex-1">
                  {reader.id === 'acr1281' ? <CreditCard className="w-4 h-4 text-slate-400" /> : <Cpu className="w-4 h-4 text-slate-400" />}
                  <div>
                    <div className="text-sm font-medium">{reader.name}</div>
                    <div className="text-xs text-slate-400">{reader.role} · {reader.port}</div>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  {reader.connected ? (
                    <Badge variant="default" className="flex items-center gap-1 bg-green-600">
                      <CheckCircle className="w-3 h-3" /> Подключён
                    </Badge>
                  ) : (
                    <Badge variant="destructive" className="flex items-center gap-1">
                      <XCircle className="w-3 h-3" /> {reader.error || 'Отключён'}
                    </Badge>
                  )}
                  <Button size="sm" variant="outline" className="h-7 px-2 text-xs"
                    disabled={!reader.connected}
                    onClick={() => onReaderTest(reader.id)}>
                    <MonitorDot className="w-3 h-3 mr-1" /> Тест
                  </Button>
                </div>
              </div>
            ))}
            {rfidReaders.length === 0 && (
              <p className="text-sm text-slate-400">Загрузка...</p>
            )}
          </CardContent>
        </Card>

      </div>

      <Card>
        <CardHeader>
          <CardTitle>Последние события</CardTitle>
        </CardHeader>
        <CardContent>
          <ScrollArea className="h-48">
            {logs.slice(0, 10).map((log) => (
              <div key={log.id} className="flex items-center gap-3 py-2 border-b last:border-0">
                {log.level === 'ERROR' && <XCircle className="w-4 h-4 text-red-500" />}
                {log.level === 'WARNING' && <AlertTriangle className="w-4 h-4 text-yellow-500" />}
                {log.level === 'SUCCESS' && <CheckCircle className="w-4 h-4 text-green-500" />}
                {log.level === 'INFO' && <Database className="w-4 h-4 text-blue-500" />}
                <span className="text-sm">{log.message}</span>
                <span className="text-xs text-slate-400 ml-auto">
                  {new Date(log.timestamp).toLocaleTimeString()}
                </span>
              </div>
            ))}
          </ScrollArea>
        </CardContent>
      </Card>
    </div>
  );
}
