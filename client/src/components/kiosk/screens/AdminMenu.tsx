import { Card, CardContent } from "@/components/ui/card";
import { BookOpen, Shield, Settings, Cog, Target, GraduationCap, Sliders } from "lucide-react";

interface AdminMenuProps {
  onNavigate: (screen: string) => void;
  onOpenDashboard: () => void;
}

export function AdminMenu({ onNavigate, onOpenDashboard }: AdminMenuProps) {
  return (
    <div className="min-h-screen bg-slate-100 pt-28 p-6" data-testid="screen-admin-menu">
      <div className="max-w-5xl mx-auto">
        <h2 className="text-3xl font-bold text-slate-800 mb-6 text-center">Администрирование</h2>
        
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-5">
          <Card
            className="cursor-pointer hover:shadow-xl transition-all active:scale-[0.98] focus:outline-none focus:ring-2 focus:ring-slate-500"
            onClick={() => onOpenDashboard()}
            onKeyDown={(e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                onOpenDashboard();
              }
            }}
            role="button"
            tabIndex={0}
            aria-label="Открыть Dashboard"
            data-testid="card-admin-dashboard"
          >
            <CardContent className="p-7 flex flex-col items-center text-center">
              <Settings className="w-14 h-14 text-slate-600 mb-3" aria-hidden="true" />
              <h3 className="text-xl font-bold mb-1">Dashboard</h3>
              <p className="text-slate-500">Статистика и мониторинг</p>
            </CardContent>
          </Card>

          <Card
            className="cursor-pointer hover:shadow-xl transition-all active:scale-[0.98] focus:outline-none focus:ring-2 focus:ring-blue-500"
            onClick={() => onNavigate('librarian_menu')}
            onKeyDown={(e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                onNavigate('librarian_menu');
              }
            }}
            role="button"
            tabIndex={0}
            aria-label="Открыть функции библиотекаря"
            data-testid="card-librarian-functions"
          >
            <CardContent className="p-7 flex flex-col items-center text-center">
              <BookOpen className="w-14 h-14 text-blue-500 mb-3" aria-hidden="true" />
              <h3 className="text-xl font-bold mb-1">Функции библиотекаря</h3>
              <p className="text-slate-500">Загрузка, изъятие</p>
            </CardContent>
          </Card>

          <Card
            className="cursor-pointer hover:shadow-xl transition-all active:scale-[0.98] focus:outline-none focus:ring-2 focus:ring-purple-500"
            onClick={() => onNavigate('diagnostics')}
            onKeyDown={(e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                onNavigate('diagnostics');
              }
            }}
            role="button"
            tabIndex={0}
            aria-label="Открыть диагностику"
            data-testid="card-diagnostics"
          >
            <CardContent className="p-7 flex flex-col items-center text-center">
              <Shield className="w-14 h-14 text-purple-500 mb-3" aria-hidden="true" />
              <h3 className="text-xl font-bold mb-1">Диагностика</h3>
              <p className="text-slate-500">Проверка оборудования</p>
            </CardContent>
          </Card>

          <Card
            className="cursor-pointer hover:shadow-xl transition-all active:scale-[0.98] focus:outline-none focus:ring-2 focus:ring-orange-500"
            onClick={() => onNavigate('mechanics_test')}
            onKeyDown={(e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                onNavigate('mechanics_test');
              }
            }}
            role="button"
            tabIndex={0}
            aria-label="Открыть тест механики"
            data-testid="card-mechanics-test"
          >
            <CardContent className="p-7 flex flex-col items-center text-center">
              <Cog className="w-14 h-14 text-orange-500 mb-3" aria-hidden="true" />
              <h3 className="text-xl font-bold mb-1">Тест механики</h3>
              <p className="text-slate-500">Моторы, сервоприводы, шторки</p>
            </CardContent>
          </Card>

          <Card
            className="cursor-pointer hover:shadow-xl transition-all active:scale-[0.98] focus:outline-none focus:ring-2 focus:ring-green-500"
            onClick={() => onNavigate('calibration')}
            onKeyDown={(e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                onNavigate('calibration');
              }
            }}
            role="button"
            tabIndex={0}
            aria-label="Открыть калибровку"
            data-testid="card-calibration"
          >
            <CardContent className="p-7 flex flex-col items-center text-center">
              <Target className="w-14 h-14 text-green-500 mb-3" aria-hidden="true" />
              <h3 className="text-xl font-bold mb-1">Калибровка</h3>
              <p className="text-slate-500">Настройка позиций и скоростей</p>
            </CardContent>
          </Card>

          <Card
            className="cursor-pointer hover:shadow-xl transition-all active:scale-[0.98] focus:outline-none focus:ring-2 focus:ring-red-500"
            onClick={() => onNavigate('teach_mode')}
            onKeyDown={(e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                onNavigate('teach_mode');
              }
            }}
            role="button"
            tabIndex={0}
            aria-label="Открыть режим обучения"
            data-testid="card-teach-mode"
          >
            <CardContent className="p-7 flex flex-col items-center text-center">
              <GraduationCap className="w-14 h-14 text-red-500 mb-3" aria-hidden="true" />
              <h3 className="text-xl font-bold mb-1">Режим обучения</h3>
              <p className="text-slate-500">Запись последовательностей</p>
            </CardContent>
          </Card>

          <Card
            className="cursor-pointer hover:shadow-xl transition-all active:scale-[0.98] focus:outline-none focus:ring-2 focus:ring-cyan-500"
            onClick={() => onNavigate('settings')}
            onKeyDown={(e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                onNavigate('settings');
              }
            }}
            role="button"
            tabIndex={0}
            aria-label="Открыть настройки"
            data-testid="card-settings"
          >
            <CardContent className="p-7 flex flex-col items-center text-center">
              <Sliders className="w-14 h-14 text-cyan-500 mb-3" aria-hidden="true" />
              <h3 className="text-xl font-bold mb-1">Настройки</h3>
              <p className="text-slate-500">Таймауты, Telegram, ИРБИС</p>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
