import { useQuery, useMutation } from "@tanstack/react-query";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Settings, ArrowLeft, Package, Activity, Play, RotateCcw, Move, Lock, Unlock, Home, ArrowUp, ArrowDown, ArrowRight } from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import { apiRequest, queryClient } from "@/lib/queryClient";
import type { SystemStatus } from "@shared/schema";

export function MechanicsTest() {
  const { toast } = useToast();
  const { data: systemStatus } = useQuery<SystemStatus>({ queryKey: ['/api/status'] });
  const { data: diagnostics } = useQuery<{ sensors: Record<string, boolean>; motors: string; rfid: Record<string, string> }>({
    queryKey: ['/api/diagnostics'],
  });

  const testMotorMutation = useMutation({
    mutationFn: async (params: { command: string; axis?: string; steps?: number; speed?: number }) => {
      const response = await apiRequest('POST', '/api/test/motor', params);
      return response.json();
    },
    onSuccess: () => {
      toast({ title: 'Успех', description: 'Команда мотора выполнена' });
      queryClient.invalidateQueries({ queryKey: ['/api/diagnostics'] });
    },
    onError: (error: any) => {
      toast({ title: 'Ошибка', description: error.message, variant: 'destructive' });
    },
  });

  const testTrayMutation = useMutation({
    mutationFn: async (command: string) => {
      const response = await apiRequest('POST', '/api/test/tray', { command });
      return response.json();
    },
    onSuccess: () => {
      toast({ title: 'Успех', description: 'Команда лотка выполнена' });
    },
    onError: (error: any) => {
      toast({ title: 'Ошибка', description: error.message, variant: 'destructive' });
    },
  });

  const testServoMutation = useMutation({
    mutationFn: async (params: { servo: string; command: string }) => {
      const response = await apiRequest('POST', '/api/test/servo', params);
      return response.json();
    },
    onSuccess: () => {
      toast({ title: 'Успех', description: 'Команда сервопривода выполнена' });
      queryClient.invalidateQueries({ queryKey: ['/api/diagnostics'] });
    },
    onError: (error: any) => {
      toast({ title: 'Ошибка', description: error.message, variant: 'destructive' });
    },
  });

  const testShutterMutation = useMutation({
    mutationFn: async (params: { shutter: string; command: string }) => {
      const response = await apiRequest('POST', '/api/test/shutter', params);
      return response.json();
    },
    onSuccess: () => {
      toast({ title: 'Успех', description: 'Команда шторки выполнена' });
      queryClient.invalidateQueries({ queryKey: ['/api/diagnostics'] });
    },
    onError: (error: any) => {
      toast({ title: 'Ошибка', description: error.message, variant: 'destructive' });
    },
  });

  const emergencyStopMutation = useMutation({
    mutationFn: async () => {
      const response = await apiRequest('POST', '/api/emergency-stop', {});
      return response.json();
    },
    onSuccess: () => {
      toast({ title: 'СТОП', description: 'Экстренная остановка выполнена', variant: 'destructive' });
      queryClient.invalidateQueries({ queryKey: ['/api/status'] });
      queryClient.invalidateQueries({ queryKey: ['/api/diagnostics'] });
    },
  });

  return (
    <div className="min-h-screen bg-slate-100 pt-28 p-6" data-testid="screen-mechanics-test">
      <div className="max-w-5xl mx-auto">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-3xl font-bold text-slate-800">Тестирование механики</h2>
          <Button
            variant="destructive"
            size="lg"
            className="h-14 px-8 text-lg font-bold bg-red-600 hover:bg-red-700 animate-none"
            onClick={() => emergencyStopMutation.mutate()}
            aria-label="Экстренная остановка"
          >
            СТОП
          </Button>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
          <Card className="p-6">
            <h3 className="text-xl font-bold mb-4 flex items-center gap-2">
              <Move className="w-5 h-5" />
              Управление моторами XY
            </h3>
            <div className="space-y-4">
              <div className="grid grid-cols-3 gap-2">
                <div />
                <Button 
                  className="h-14"
                  onClick={() => testMotorMutation.mutate({ command: 'move', axis: 'y', steps: -500 })}
                  disabled={testMotorMutation.isPending}
                  data-testid="button-motor-y-minus"
                >
                  <ArrowUp className="w-6 h-6" />
                </Button>
                <div />
                <Button 
                  className="h-14"
                  onClick={() => testMotorMutation.mutate({ command: 'move', axis: 'x', steps: -500 })}
                  disabled={testMotorMutation.isPending}
                  data-testid="button-motor-x-minus"
                >
                  <ArrowLeft className="w-6 h-6" />
                </Button>
                <Button 
                  variant="outline"
                  className="h-14"
                  onClick={() => testMotorMutation.mutate({ command: 'home' })}
                  disabled={testMotorMutation.isPending}
                  data-testid="button-motor-home"
                >
                  <Home className="w-5 h-5" />
                </Button>
                <Button 
                  className="h-14"
                  onClick={() => testMotorMutation.mutate({ command: 'move', axis: 'x', steps: 500 })}
                  disabled={testMotorMutation.isPending}
                  data-testid="button-motor-x-plus"
                >
                  <ArrowRight className="w-6 h-6" />
                </Button>
                <div />
                <Button 
                  className="h-14"
                  onClick={() => testMotorMutation.mutate({ command: 'move', axis: 'y', steps: 500 })}
                  disabled={testMotorMutation.isPending}
                  data-testid="button-motor-y-plus"
                >
                  <ArrowDown className="w-6 h-6" />
                </Button>
                <div />
              </div>
              <div className="text-center text-slate-500">
                Позиция: X={systemStatus?.position?.x || 0}, Y={systemStatus?.position?.y || 0}
              </div>
            </div>
          </Card>

          <Card className="p-6">
            <h3 className="text-xl font-bold mb-4 flex items-center gap-2">
              <Package className="w-5 h-5" />
              Управление лотком
            </h3>
            <div className="space-y-4">
              <div className="flex gap-3">
                <Button 
                  className="flex-1 h-14"
                  onClick={() => testTrayMutation.mutate('extend')}
                  disabled={testTrayMutation.isPending}
                  data-testid="button-tray-extend"
                >
                  <Play className="w-5 h-5 mr-2" />
                  Выдвинуть
                </Button>
                <Button 
                  variant="outline"
                  className="flex-1 h-14"
                  onClick={() => testTrayMutation.mutate('retract')}
                  disabled={testTrayMutation.isPending}
                  data-testid="button-tray-retract"
                >
                  <RotateCcw className="w-5 h-5 mr-2" />
                  Задвинуть
                </Button>
              </div>
              <div className="text-center text-slate-500">
                Лоток: {systemStatus?.position?.tray || 0} шагов
              </div>
            </div>
          </Card>

          <Card className="p-6">
            <h3 className="text-xl font-bold mb-4 flex items-center gap-2">
              <Lock className="w-5 h-5" />
              Замки (сервоприводы)
            </h3>
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <span className="font-medium">Передний замок</span>
                <div className="flex gap-2">
                  <Button 
                    size="sm"
                    onClick={() => testServoMutation.mutate({ servo: 'front', command: 'open' })}
                    disabled={testServoMutation.isPending}
                    data-testid="button-lock-front-open"
                  >
                    <Unlock className="w-4 h-4 mr-1" /> Открыть
                  </Button>
                  <Button 
                    size="sm"
                    variant="outline"
                    onClick={() => testServoMutation.mutate({ servo: 'front', command: 'close' })}
                    disabled={testServoMutation.isPending}
                    data-testid="button-lock-front-close"
                  >
                    <Lock className="w-4 h-4 mr-1" /> Закрыть
                  </Button>
                </div>
              </div>
              <div className="flex items-center justify-between">
                <span className="font-medium">Задний замок</span>
                <div className="flex gap-2">
                  <Button 
                    size="sm"
                    onClick={() => testServoMutation.mutate({ servo: 'back', command: 'open' })}
                    disabled={testServoMutation.isPending}
                    data-testid="button-lock-back-open"
                  >
                    <Unlock className="w-4 h-4 mr-1" /> Открыть
                  </Button>
                  <Button 
                    size="sm"
                    variant="outline"
                    onClick={() => testServoMutation.mutate({ servo: 'back', command: 'close' })}
                    disabled={testServoMutation.isPending}
                    data-testid="button-lock-back-close"
                  >
                    <Lock className="w-4 h-4 mr-1" /> Закрыть
                  </Button>
                </div>
              </div>
            </div>
          </Card>

          <Card className="p-6">
            <h3 className="text-xl font-bold mb-4 flex items-center gap-2">
              <Settings className="w-5 h-5" />
              Шторки
            </h3>
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <span className="font-medium">Внутренняя</span>
                <div className="flex gap-2">
                  <Button 
                    size="sm"
                    onClick={() => testShutterMutation.mutate({ shutter: 'inner', command: 'open' })}
                    disabled={testShutterMutation.isPending}
                    data-testid="button-shutter-inner-open"
                  >
                    Открыть
                  </Button>
                  <Button 
                    size="sm"
                    variant="outline"
                    onClick={() => testShutterMutation.mutate({ shutter: 'inner', command: 'close' })}
                    disabled={testShutterMutation.isPending}
                    data-testid="button-shutter-inner-close"
                  >
                    Закрыть
                  </Button>
                </div>
              </div>
              <div className="flex items-center justify-between">
                <span className="font-medium">Внешняя</span>
                <div className="flex gap-2">
                  <Button 
                    size="sm"
                    onClick={() => testShutterMutation.mutate({ shutter: 'outer', command: 'open' })}
                    disabled={testShutterMutation.isPending}
                    data-testid="button-shutter-outer-open"
                  >
                    Открыть
                  </Button>
                  <Button 
                    size="sm"
                    variant="outline"
                    onClick={() => testShutterMutation.mutate({ shutter: 'outer', command: 'close' })}
                    disabled={testShutterMutation.isPending}
                    data-testid="button-shutter-outer-close"
                  >
                    Закрыть
                  </Button>
                </div>
              </div>
            </div>
          </Card>

          <Card className="p-6 col-span-2">
            <h3 className="text-xl font-bold mb-4 flex items-center gap-2">
              <Activity className="w-5 h-5" />
              Состояние датчиков
            </h3>
            <div className="grid grid-cols-6 gap-3">
              {diagnostics?.sensors && Object.entries(diagnostics.sensors).map(([key, value]) => (
                <div key={key} className="flex flex-col items-center p-3 bg-slate-50 rounded">
                  <div className={`w-4 h-4 rounded-full mb-2 ${value ? 'bg-green-500' : 'bg-slate-300'}`} />
                  <span className="text-xs text-slate-600">{key}</span>
                </div>
              ))}
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}
