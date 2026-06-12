import { useQuery } from "@tanstack/react-query";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Settings, CreditCard, Activity } from "lucide-react";

export function DiagnosticsScreen() {
  const { data: diagnostics } = useQuery<{ sensors: Record<string, boolean>; motors: string; rfid: Record<string, string> }>({
    queryKey: ['/api/diagnostics'],
  });

  return (
    <div className="min-h-screen bg-slate-100 pt-28 p-6" data-testid="screen-diagnostics">
      <div className="max-w-4xl mx-auto">
        <h2 className="text-3xl font-bold text-slate-800 mb-6">Диагностика оборудования</h2>
        
        <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
          <Card className="p-6">
            <h3 className="text-xl font-bold mb-4 flex items-center gap-2">
              <Activity className="w-5 h-5" />
              Датчики
            </h3>
            <div className="space-y-2">
              {diagnostics?.sensors && Object.entries(diagnostics.sensors).map(([key, value]) => (
                <div key={key} className="flex items-center justify-between py-2 border-b">
                  <span className="text-slate-600">{key}</span>
                  <Badge variant={value ? 'default' : 'secondary'}>
                    {value ? 'Активен' : 'Неактивен'}
                  </Badge>
                </div>
              ))}
              {!diagnostics && <p className="text-slate-400">Загрузка...</p>}
            </div>
          </Card>

          <Card className="p-6">
            <h3 className="text-xl font-bold mb-4 flex items-center gap-2">
              <Settings className="w-5 h-5" />
              Моторы
            </h3>
            <div className="flex items-center gap-3">
              <div className={`w-4 h-4 rounded-full ${diagnostics?.motors === 'ok' ? 'bg-green-500' : 'bg-red-500'}`} />
              <span className="text-lg">
                {diagnostics?.motors === 'ok' ? 'В норме' : diagnostics?.motors || 'Проверка...'}
              </span>
            </div>
          </Card>

          <Card className="p-6 col-span-2">
            <h3 className="text-xl font-bold mb-4 flex items-center gap-2">
              <CreditCard className="w-5 h-5" />
              RFID считыватели
            </h3>
            <div className="grid grid-cols-2 gap-4">
              {diagnostics?.rfid && Object.entries(diagnostics.rfid).map(([key, value]) => (
                <div key={key} className="flex items-center justify-between py-2 px-4 bg-slate-50 rounded">
                  <span className="text-slate-600">{key}</span>
                  <Badge variant={value === 'connected' ? 'default' : 'destructive'}>
                    {value === 'connected' ? 'Подключён' : value}
                  </Badge>
                </div>
              ))}
              {!diagnostics && <p className="text-slate-400">Загрузка...</p>}
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}
