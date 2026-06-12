import { useQuery } from "@tanstack/react-query";
import { Card } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { BookOpen, Undo2, Package, AlertTriangle } from "lucide-react";
import type { Statistics } from "@shared/schema";

export function StatisticsScreen() {
  const { data: statistics } = useQuery<Statistics>({ queryKey: ['/api/statistics'] });

  return (
    <div className="min-h-screen bg-slate-100 pt-28 p-6" data-testid="screen-statistics">
      <div className="max-w-4xl mx-auto">
        <h2 className="text-3xl font-bold text-slate-800 mb-6">Статистика</h2>
        
        <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
          <Card className="p-6">
            <div className="flex items-center gap-4">
              <BookOpen className="w-12 h-12 text-blue-500" />
              <div>
                <p className="text-sm text-slate-500">Выдано сегодня</p>
                <p className="text-3xl font-bold">{statistics?.issuesToday || 0}</p>
                <p className="text-sm text-slate-400">Всего: {statistics?.issuesTotal || 0}</p>
              </div>
            </div>
          </Card>

          <Card className="p-6">
            <div className="flex items-center gap-4">
              <Undo2 className="w-12 h-12 text-green-500" />
              <div>
                <p className="text-sm text-slate-500">Возвращено сегодня</p>
                <p className="text-3xl font-bold">{statistics?.returnsToday || 0}</p>
                <p className="text-sm text-slate-400">Всего: {statistics?.returnsTotal || 0}</p>
              </div>
            </div>
          </Card>

          <Card className="p-6">
            <div className="flex items-center gap-4">
              <Package className="w-12 h-12 text-slate-500" />
              <div>
                <p className="text-sm text-slate-500">Заполненность шкафа</p>
                <p className="text-3xl font-bold">{statistics?.occupiedCells || 0}/{statistics?.totalCells || 0}</p>
                <Progress 
                  value={statistics?.totalCells ? (statistics.occupiedCells / statistics.totalCells) * 100 : 0} 
                  className="h-2 mt-2 w-32" 
                />
              </div>
            </div>
          </Card>

          <Card className="p-6">
            <div className="flex items-center gap-4">
              <AlertTriangle className="w-12 h-12 text-orange-500" />
              <div>
                <p className="text-sm text-slate-500">Требуют изъятия</p>
                <p className="text-3xl font-bold text-orange-500">{statistics?.booksNeedExtraction || 0}</p>
              </div>
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}
