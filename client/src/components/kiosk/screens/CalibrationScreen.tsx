import { useState } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Loader2, Package, Activity, Cog, Play, RotateCcw, Move, Lock, Target, Home, ArrowUp, Sliders } from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import { apiRequest, queryClient } from "@/lib/queryClient";
import type { CalibrationData } from "@shared/schema";

export function CalibrationScreen() {
  const { toast } = useToast();
  const { data: calibration, refetch: refetchCalibration } = useQuery<CalibrationData>({
    queryKey: ['/api/calibration'],
  });

  const [calibrationTestResults, setCalibrationTestResults] = useState<{
    test: string;
    status: 'pass' | 'fail' | 'running';
    message: string;
    duration?: number;
  }[]>([]);

  const testMotorMutation = useMutation({
    mutationFn: async (params: { command: string; axis?: string; steps?: number; speed?: number }) => {
      const response = await apiRequest('POST', '/api/test/motor', params);
      return response.json();
    },
    onSuccess: () => {
      toast({ title: 'Успех', description: 'Команда мотора выполнена' });
    },
    onError: (error: any) => {
      toast({ title: 'Ошибка', description: error.message, variant: 'destructive' });
    },
  });

  const saveCalibrationMutation = useMutation({
    mutationFn: async (data: Partial<CalibrationData>) => {
      const response = await apiRequest('POST', '/api/calibration', data);
      return response.json();
    },
    onSuccess: () => {
      toast({ title: 'Успех', description: 'Калибровка сохранена' });
      refetchCalibration();
    },
    onError: (error: any) => {
      toast({ title: 'Ошибка', description: error.message, variant: 'destructive' });
    },
  });

  const resetCalibrationMutation = useMutation({
    mutationFn: async () => {
      const response = await apiRequest('POST', '/api/calibration/reset', {});
      return response.json();
    },
    onSuccess: () => {
      toast({ title: 'Успех', description: 'Калибровка сброшена к значениям по умолчанию' });
      refetchCalibration();
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
    },
  });

  const runCalibrationSuiteMutation = useMutation({
    mutationFn: async () => {
      const response = await apiRequest('POST', '/api/calibration/test-suite', {});
      return response.json();
    },
    onSuccess: (data) => {
      setCalibrationTestResults(data.results || []);
      if (data.success) {
        toast({ title: 'Успех', description: `Все тесты пройдены: ${data.summary.passed}/${data.summary.total}` });
      } else {
        toast({ title: 'Внимание', description: `Пройдено ${data.summary.passed}/${data.summary.total} тестов`, variant: 'destructive' });
      }
    },
    onError: (error: any) => {
      toast({ title: 'Ошибка', description: error.message, variant: 'destructive' });
    },
  });

  const runSingleTestMutation = useMutation({
    mutationFn: async (testName: string) => {
      const response = await apiRequest('POST', `/api/calibration/test/${testName}`, {});
      return response.json();
    },
    onSuccess: (data) => {
      toast({ title: data.success ? 'Успех' : 'Ошибка', description: data.result?.message, variant: data.success ? 'default' : 'destructive' });
    },
    onError: (error: any) => {
      toast({ title: 'Ошибка', description: error.message, variant: 'destructive' });
    },
  });

  return (
    <div className="min-h-screen bg-slate-100 pt-28 p-6" data-testid="screen-calibration">
      <div className="max-w-5xl mx-auto">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-3xl font-bold text-slate-800">Калибровка</h2>
          <div className="flex gap-3">
            <Button
              variant="destructive"
              size="lg"
              className="h-14 px-8 text-lg font-bold bg-red-600 hover:bg-red-700"
              onClick={() => emergencyStopMutation.mutate()}
              aria-label="Экстренная остановка"
            >
              СТОП
            </Button>
            <Button
              variant="destructive"
              onClick={() => resetCalibrationMutation.mutate()}
              disabled={resetCalibrationMutation.isPending}
              data-testid="button-reset-calibration"
            >
              <RotateCcw className="w-4 h-4 mr-2" />
              Сброс к заводским
            </Button>
          </div>
        </div>
        
        <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
          <Card className="p-6">
            <h3 className="text-xl font-bold mb-4 flex items-center gap-2">
              <Cog className="w-5 h-5" />
              Скорости
            </h3>
            <div className="space-y-4">
              <div>
                <Label>Скорость XY (шаг/сек)</Label>
                <div className="flex gap-2 mt-1">
                  <Input 
                    type="number"
                    min={100}
                    max={3000}
                    value={calibration?.speeds?.xy || 3000}
                    className="h-12"
                    data-testid="input-speed-xy"
                    onChange={(e) => {
                      const val = Math.min(3000, Math.max(100, parseInt(e.target.value) || 800));
                      const update: Partial<CalibrationData> = { speeds: { ...calibration?.speeds, xy: val, tray: calibration?.speeds?.tray || 2000, acceleration: calibration?.speeds?.acceleration || 5000 } };
                      saveCalibrationMutation.mutate(update);
                    }}
                  />
                </div>
              </div>
              <div>
                <Label>Скорость лотка (шаг/сек)</Label>
                <div className="flex gap-2 mt-1">
                  <Input
                    type="number"
                    min={100}
                    max={3000}
                    value={calibration?.speeds?.tray || 2000}
                    className="h-12"
                    data-testid="input-speed-tray"
                    onChange={(e) => {
                      const val = Math.min(3000, Math.max(100, parseInt(e.target.value) || 800));
                      const update: Partial<CalibrationData> = { speeds: { ...calibration?.speeds, xy: calibration?.speeds?.xy || 3000, tray: val, acceleration: calibration?.speeds?.acceleration || 5000 } };
                      saveCalibrationMutation.mutate(update);
                    }}
                  />
                </div>
              </div>
              <div>
                <Label>Ускорение (шаг/сек²)</Label>
                <div className="flex gap-2 mt-1">
                  <Input 
                    type="number"
                    value={calibration?.speeds?.acceleration || 5000}
                    className="h-12"
                    data-testid="input-acceleration"
                    onChange={(e) => {
                      const update: Partial<CalibrationData> = { speeds: { ...calibration?.speeds, xy: calibration?.speeds?.xy || 3000, tray: calibration?.speeds?.tray || 2000, acceleration: parseInt(e.target.value) || 5000 } };
                      saveCalibrationMutation.mutate(update);
                    }}
                  />
                </div>
              </div>
            </div>
          </Card>

          <Card className="p-6">
            <h3 className="text-xl font-bold mb-4 flex items-center gap-2">
              <Sliders className="w-5 h-5" />
              Позиции стоек X (шаги)
            </h3>
            <div className="space-y-4">
              {[0, 1, 2].map((idx) => {
                const defaults = [100, 10220, 20370];
                const val = calibration?.positions?.x?.[idx] ?? defaults[idx];
                return (
                  <div key={idx} className="flex items-center gap-3">
                    <Label className="w-24 shrink-0">Стойка {idx + 1}</Label>
                    <Input
                      type="number"
                      value={val}
                      className="h-12"
                      data-testid={`input-rack-x-${idx}`}
                      onChange={(e) => {
                        const newX = [...(calibration?.positions?.x || defaults)];
                        newX[idx] = parseInt(e.target.value) || 0;
                        const update: Partial<CalibrationData> = {
                          positions: { ...calibration?.positions, x: newX, y: calibration?.positions?.y || [] }
                        };
                        saveCalibrationMutation.mutate(update);
                      }}
                    />
                    <Button
                      variant="outline"
                      className="h-12 shrink-0"
                      data-testid={`button-test-rack-x-${idx}`}
                      onClick={() => testMotorMutation.mutate({ command: 'move', axis: 'x', steps: val })}
                      disabled={testMotorMutation.isPending}
                    >
                      <Play className="w-4 h-4 mr-1" />
                      Тест
                    </Button>
                  </div>
                );
              })}
            </div>
          </Card>

          <Card className="p-6">
            <h3 className="text-xl font-bold mb-4 flex items-center gap-2">
              <Lock className="w-5 h-5" />
              Углы сервоприводов
            </h3>
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <Label>Замок 1 открыт (°)</Label>
                  <Input 
                    type="number"
                    value={calibration?.servos?.lock1_open || 90}
                    className="h-12 mt-1"
                    data-testid="input-servo-lock1-open"
                    onChange={(e) => {
                      const update: Partial<CalibrationData> = { servos: { lock1_open: parseInt(e.target.value) || 90, lock1_close: calibration?.servos?.lock1_close || 0, lock2_open: calibration?.servos?.lock2_open || 90, lock2_close: calibration?.servos?.lock2_close || 0 } };
                      saveCalibrationMutation.mutate(update);
                    }}
                  />
                </div>
                <div>
                  <Label>Замок 1 закрыт (°)</Label>
                  <Input 
                    type="number"
                    value={calibration?.servos?.lock1_close || 0}
                    className="h-12 mt-1"
                    data-testid="input-servo-lock1-close"
                    onChange={(e) => {
                      const update: Partial<CalibrationData> = { servos: { lock1_open: calibration?.servos?.lock1_open || 90, lock1_close: parseInt(e.target.value) || 0, lock2_open: calibration?.servos?.lock2_open || 90, lock2_close: calibration?.servos?.lock2_close || 0 } };
                      saveCalibrationMutation.mutate(update);
                    }}
                  />
                </div>
                <div>
                  <Label>Замок 2 открыт (°)</Label>
                  <Input 
                    type="number"
                    value={calibration?.servos?.lock2_open || 90}
                    className="h-12 mt-1"
                    data-testid="input-servo-lock2-open"
                    onChange={(e) => {
                      const update: Partial<CalibrationData> = { servos: { lock1_open: calibration?.servos?.lock1_open || 90, lock1_close: calibration?.servos?.lock1_close || 0, lock2_open: parseInt(e.target.value) || 90, lock2_close: calibration?.servos?.lock2_close || 0 } };
                      saveCalibrationMutation.mutate(update);
                    }}
                  />
                </div>
                <div>
                  <Label>Замок 2 закрыт (°)</Label>
                  <Input 
                    type="number"
                    value={calibration?.servos?.lock2_close || 0}
                    className="h-12 mt-1"
                    data-testid="input-servo-lock2-close"
                    onChange={(e) => {
                      const update: Partial<CalibrationData> = { servos: { lock1_open: calibration?.servos?.lock1_open || 90, lock1_close: calibration?.servos?.lock1_close || 0, lock2_open: calibration?.servos?.lock2_open || 90, lock2_close: parseInt(e.target.value) || 0 } };
                      saveCalibrationMutation.mutate(update);
                    }}
                  />
                </div>
              </div>
            </div>
          </Card>

          <Card className="p-6">
            <h3 className="text-xl font-bold mb-4 flex items-center gap-2">
              <Target className="w-5 h-5" />
              Позиция окна выдачи
            </h3>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label>X (шаги)</Label>
                <Input 
                  type="number"
                  value={calibration?.window?.x || 5000}
                  className="h-12 mt-1"
                  data-testid="input-window-x"
                  onChange={(e) => {
                    const update: Partial<CalibrationData> = { window: { x: parseInt(e.target.value) || 5000, y: calibration?.window?.y || 5000 } };
                    saveCalibrationMutation.mutate(update);
                  }}
                />
              </div>
              <div>
                <Label>Y (шаги)</Label>
                <Input 
                  type="number"
                  value={calibration?.window?.y || 5000}
                  className="h-12 mt-1"
                  data-testid="input-window-y"
                  onChange={(e) => {
                    const update: Partial<CalibrationData> = { window: { x: calibration?.window?.x || 5000, y: parseInt(e.target.value) || 5000 } };
                    saveCalibrationMutation.mutate(update);
                  }}
                />
              </div>
            </div>
          </Card>

          <Card className="p-6">
            <h3 className="text-xl font-bold mb-4 flex items-center gap-2">
              <Move className="w-5 h-5" />
              Кинематика CoreXY
            </h3>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label>X+ dir A</Label>
                <Input 
                  type="number"
                  value={calibration?.kinematics?.x_plus_dir_a || 1}
                  className="h-12 mt-1"
                  data-testid="input-kinematics-x-plus-dir-a"
                  onChange={(e) => {
                    const update: Partial<CalibrationData> = { kinematics: { x_plus_dir_a: parseInt(e.target.value) || 1, x_plus_dir_b: calibration?.kinematics?.x_plus_dir_b || -1, y_plus_dir_a: calibration?.kinematics?.y_plus_dir_a || 1, y_plus_dir_b: calibration?.kinematics?.y_plus_dir_b || 1 } };
                    saveCalibrationMutation.mutate(update);
                  }}
                />
              </div>
              <div>
                <Label>X+ dir B</Label>
                <Input 
                  type="number"
                  value={calibration?.kinematics?.x_plus_dir_b || -1}
                  className="h-12 mt-1"
                  data-testid="input-kinematics-x-plus-dir-b"
                  onChange={(e) => {
                    const update: Partial<CalibrationData> = { kinematics: { x_plus_dir_a: calibration?.kinematics?.x_plus_dir_a || 1, x_plus_dir_b: parseInt(e.target.value) || -1, y_plus_dir_a: calibration?.kinematics?.y_plus_dir_a || 1, y_plus_dir_b: calibration?.kinematics?.y_plus_dir_b || 1 } };
                    saveCalibrationMutation.mutate(update);
                  }}
                />
              </div>
              <div>
                <Label>Y+ dir A</Label>
                <Input 
                  type="number"
                  value={calibration?.kinematics?.y_plus_dir_a || 1}
                  className="h-12 mt-1"
                  data-testid="input-kinematics-y-plus-dir-a"
                  onChange={(e) => {
                    const update: Partial<CalibrationData> = { kinematics: { x_plus_dir_a: calibration?.kinematics?.x_plus_dir_a || 1, x_plus_dir_b: calibration?.kinematics?.x_plus_dir_b || -1, y_plus_dir_a: parseInt(e.target.value) || 1, y_plus_dir_b: calibration?.kinematics?.y_plus_dir_b || 1 } };
                    saveCalibrationMutation.mutate(update);
                  }}
                />
              </div>
              <div>
                <Label>Y+ dir B</Label>
                <Input 
                  type="number"
                  value={calibration?.kinematics?.y_plus_dir_b || 1}
                  className="h-12 mt-1"
                  data-testid="input-kinematics-y-plus-dir-b"
                  onChange={(e) => {
                    const update: Partial<CalibrationData> = { kinematics: { x_plus_dir_a: calibration?.kinematics?.x_plus_dir_a || 1, x_plus_dir_b: calibration?.kinematics?.x_plus_dir_b || -1, y_plus_dir_a: calibration?.kinematics?.y_plus_dir_a || 1, y_plus_dir_b: parseInt(e.target.value) || 1 } };
                    saveCalibrationMutation.mutate(update);
                  }}
                />
              </div>
            </div>
          </Card>

          <Card className="p-6 col-span-2">
            <h3 className="text-xl font-bold mb-4 flex items-center gap-2">
              <Play className="w-5 h-5" />
              Комплексные тесты калибровки
            </h3>
            
            <div className="flex gap-3 mb-4">
              <Button
                onClick={() => runCalibrationSuiteMutation.mutate()}
                disabled={runCalibrationSuiteMutation.isPending}
                className="h-12"
                data-testid="button-run-all-tests"
              >
                {runCalibrationSuiteMutation.isPending ? (
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                ) : (
                  <Play className="w-4 h-4 mr-2" />
                )}
                Запустить все тесты
              </Button>
            </div>

            <div className="grid grid-cols-3 gap-3 mb-4">
              <Button
                variant="outline"
                onClick={() => runSingleTestMutation.mutate('home')}
                disabled={runSingleTestMutation.isPending}
                className="h-12"
                data-testid="button-test-home"
              >
                <Home className="w-4 h-4 mr-2" />
                Homing
              </Button>
              <Button
                variant="outline"
                onClick={() => runSingleTestMutation.mutate('tray')}
                disabled={runSingleTestMutation.isPending}
                className="h-12"
                data-testid="button-test-tray"
              >
                <Package className="w-4 h-4 mr-2" />
                Лоток
              </Button>
              <Button
                variant="outline"
                onClick={() => runSingleTestMutation.mutate('servos')}
                disabled={runSingleTestMutation.isPending}
                className="h-12"
                data-testid="button-test-servos"
              >
                <Lock className="w-4 h-4 mr-2" />
                Сервоприводы
              </Button>
              <Button
                variant="outline"
                onClick={() => runSingleTestMutation.mutate('shutters')}
                disabled={runSingleTestMutation.isPending}
                className="h-12"
                data-testid="button-test-shutters"
              >
                <ArrowUp className="w-4 h-4 mr-2" />
                Шторки
              </Button>
              <Button
                variant="outline"
                onClick={() => runSingleTestMutation.mutate('sensors')}
                disabled={runSingleTestMutation.isPending}
                className="h-12"
                data-testid="button-test-sensors"
              >
                <Activity className="w-4 h-4 mr-2" />
                Датчики
              </Button>
              <Button
                variant="outline"
                onClick={() => runSingleTestMutation.mutate('move-cell')}
                disabled={runSingleTestMutation.isPending}
                className="h-12"
                data-testid="button-test-move"
              >
                <Move className="w-4 h-4 mr-2" />
                Перемещение
              </Button>
            </div>

            {calibrationTestResults.length > 0 && (
              <div className="border rounded-lg overflow-hidden">
                <div className="bg-slate-100 px-4 py-2 font-medium text-sm">
                  Результаты тестов
                </div>
                <div className="divide-y">
                  {calibrationTestResults.map((result, idx) => (
                    <div key={idx} className="flex items-center justify-between px-4 py-3">
                      <div className="flex items-center gap-3">
                        <div className={`w-3 h-3 rounded-full ${
                          result.status === 'pass' ? 'bg-green-500' : 
                          result.status === 'fail' ? 'bg-red-500' : 'bg-yellow-500'
                        }`} />
                        <span className="font-medium">{result.test}</span>
                      </div>
                      <div className="flex items-center gap-4">
                        <span className="text-sm text-slate-500">{result.message}</span>
                        {result.duration && (
                          <Badge variant="outline">{result.duration}ms</Badge>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </Card>
        </div>
      </div>
    </div>
  );
}
