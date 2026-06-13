import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Loader2, Package, AlertTriangle, Search, Plus, History, BarChart3, Box } from "lucide-react";

interface LibrarianMenuProps {
  needsExtraction: number;
  extractAllPending: boolean;
  onNavigate: (screen: string) => void;
  onExtractAll: () => void;
  onInventory: () => void;
}

export function LibrarianMenu({ needsExtraction, extractAllPending, onNavigate, onExtractAll, onInventory }: LibrarianMenuProps) {
  return (
    <div className="min-h-screen bg-slate-100 pt-28 p-6" data-testid="screen-librarian-menu">
      <div className="max-w-5xl mx-auto">
        <h2 className="text-3xl font-bold text-slate-800 mb-6 text-center">Меню библиотекаря</h2>
        
        {needsExtraction > 0 && (
          <div className="mb-6 p-5 bg-yellow-100 border-2 border-yellow-400 rounded-xl flex items-center justify-between">
            <div className="flex items-center gap-3">
              <AlertTriangle className="w-7 h-7 text-yellow-600" />
              <span className="text-lg font-medium">
                {needsExtraction} книг требуют изъятия
              </span>
            </div>
            <Button 
              size="lg" 
              variant="default" 
              className="h-14 px-6 text-lg"
              onClick={() => onExtractAll()}
              disabled={extractAllPending}
              data-testid="button-extract-all"
            >
              {extractAllPending ? <Loader2 className="w-5 h-5 animate-spin mr-2" /> : null}
              Изъять все
            </Button>
          </div>
        )}
        
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-5">
          <Card
            className="cursor-pointer hover:shadow-xl transition-all active:scale-[0.98] focus:outline-none focus:ring-2 focus:ring-blue-500"
            onClick={() => onNavigate('load_books')}
            onKeyDown={(e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                onNavigate('load_books');
              }
            }}
            role="button"
            tabIndex={0}
            aria-label="Загрузить книги в шкаф"
            data-testid="card-load-books"
          >
            <CardContent className="p-7 flex flex-col items-center text-center">
              <Plus className="w-14 h-14 text-blue-500 mb-3" aria-hidden="true" />
              <h3 className="text-xl font-bold mb-1">Загрузить книги</h3>
              <p className="text-slate-500">Добавить в шкаф</p>
            </CardContent>
          </Card>

          <Card
            className="cursor-pointer hover:shadow-xl transition-all active:scale-[0.98] focus:outline-none focus:ring-2 focus:ring-orange-500"
            onClick={() => onNavigate('extract_books')}
            onKeyDown={(e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                onNavigate('extract_books');
              }
            }}
            role="button"
            tabIndex={0}
            aria-label="Изъять возвращённые книги"
            data-testid="card-unload-books"
          >
            <CardContent className="p-7 flex flex-col items-center text-center">
              <Package className="w-14 h-14 text-orange-500 mb-3" aria-hidden="true" />
              <h3 className="text-xl font-bold mb-1">Изъять книги</h3>
              <p className="text-slate-500">Забрать возвращённые</p>
            </CardContent>
          </Card>

          <Card
            className="cursor-pointer hover:shadow-xl transition-all active:scale-[0.98] focus:outline-none focus:ring-2 focus:ring-green-500"
            onClick={() => {
              onInventory();
            }}
            onKeyDown={(e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                onInventory();
              }
            }}
            role="button"
            tabIndex={0}
            aria-label="Запустить инвентаризацию"
            data-testid="card-inventory"
          >
            <CardContent className="p-7 flex flex-col items-center text-center">
              <Search className="w-14 h-14 text-green-500 mb-3" aria-hidden="true" />
              <h3 className="text-xl font-bold mb-1">Инвентаризация</h3>
              <p className="text-slate-500">Проверить содержимое</p>
            </CardContent>
          </Card>

          <Card
            className="cursor-pointer hover:shadow-xl transition-all active:scale-[0.98] focus:outline-none focus:ring-2 focus:ring-slate-500"
            onClick={() => onNavigate('operations_log')}
            onKeyDown={(e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                onNavigate('operations_log');
              }
            }}
            role="button"
            tabIndex={0}
            aria-label="Открыть журнал операций"
            data-testid="card-operations-log"
          >
            <CardContent className="p-7 flex flex-col items-center text-center">
              <History className="w-14 h-14 text-slate-600 mb-3" aria-hidden="true" />
              <h3 className="text-xl font-bold mb-1">Журнал операций</h3>
              <p className="text-slate-500">История выдач и возвратов</p>
            </CardContent>
          </Card>

          <Card
            className="cursor-pointer hover:shadow-xl transition-all active:scale-[0.98] focus:outline-none focus:ring-2 focus:ring-indigo-500"
            onClick={() => onNavigate('statistics')}
            onKeyDown={(e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                onNavigate('statistics');
              }
            }}
            role="button"
            tabIndex={0}
            aria-label="Открыть статистику"
            data-testid="card-statistics"
          >
            <CardContent className="p-7 flex flex-col items-center text-center">
              <BarChart3 className="w-14 h-14 text-indigo-500 mb-3" aria-hidden="true" />
              <h3 className="text-xl font-bold mb-1">Статистика</h3>
              <p className="text-slate-500">Аналитика и отчёты</p>
            </CardContent>
          </Card>

          <Card
            className="cursor-pointer hover:shadow-xl transition-all active:scale-[0.98] focus:outline-none focus:ring-2 focus:ring-cyan-500"
            onClick={() => onNavigate('cabinet_view')}
            onKeyDown={(e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                onNavigate('cabinet_view');
              }
            }}
            role="button"
            tabIndex={0}
            aria-label="Открыть 3D-модель шкафа"
            data-testid="card-cabinet-view"
          >
            <CardContent className="p-7 flex flex-col items-center text-center">
              <Box className="w-14 h-14 text-cyan-500 mb-3" aria-hidden="true" />
              <h3 className="text-xl font-bold mb-1">3D-модель шкафа</h3>
              <p className="text-slate-500">Визуализация RFID-меток</p>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
