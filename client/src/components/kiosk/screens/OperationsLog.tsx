import { useState, useCallback } from "react";
import { useQuery } from "@tanstack/react-query";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ScrollArea } from "@/components/ui/scroll-area";
import { History } from "lucide-react";
import type { Operation } from "@shared/schema";

export function OperationsLog() {
  const [logFilterType, setLogFilterType] = useState<string>('all');
  const [logFilterDate, setLogFilterDate] = useState<string>('all');
  const [logSearchText, setLogSearchText] = useState('');

  const { data: operations = [] } = useQuery<Operation[]>({ queryKey: ['/api/operations'] });

  const getFilteredOperations = useCallback(() => {
    let filtered = [...operations];
    if (logFilterType !== 'all') {
      filtered = filtered.filter((op) => op.operation === logFilterType);
    }
    if (logFilterDate === 'today') {
      const today = new Date();
      today.setHours(0, 0, 0, 0);
      filtered = filtered.filter((op) => op.timestamp && new Date(op.timestamp) >= today);
    } else if (logFilterDate === 'week') {
      const weekAgo = new Date();
      weekAgo.setDate(weekAgo.getDate() - 7);
      weekAgo.setHours(0, 0, 0, 0);
      filtered = filtered.filter((op) => op.timestamp && new Date(op.timestamp) >= weekAgo);
    }
    if (logSearchText.trim()) {
      const q = logSearchText.trim().toLowerCase();
      filtered = filtered.filter((op) => op.bookRfid?.toLowerCase().includes(q));
    }
    return filtered;
  }, [operations, logFilterType, logFilterDate, logSearchText]);

  const handleExportCsv = useCallback(() => {
    const rows = getFilteredOperations();
    const header = 'ID,Operation,Timestamp,BookRfid,UserRfid,Result\n';
    const csv = header + rows.map((op) =>
      [op.id, op.operation, op.timestamp || '', op.bookRfid || '', op.userRfid || '', op.result || '']
        .map((v) => `"${String(v).replace(/"/g, '""')}"`)
        .join(',')
    ).join('\n');
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `operations_${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  }, [getFilteredOperations]);

    const filtered = getFilteredOperations();
    return (
      <div className="min-h-screen bg-slate-100 pt-28 p-6" data-testid="screen-operations-log">
        <div className="max-w-4xl mx-auto">
          <h2 className="text-3xl font-bold text-slate-800 mb-6">Журнал операций</h2>

          {/* Filters */}
          <div className="flex flex-wrap items-end gap-4 mb-4">
            <div>
              <Label className="text-sm text-slate-500 mb-1 block">Тип</Label>
              <select
                className="border rounded px-3 py-2 text-sm bg-white"
                value={logFilterType}
                onChange={(e) => setLogFilterType(e.target.value)}
              >
                <option value="all">Все</option>
                <option value="ISSUE">ISSUE</option>
                <option value="RETURN">RETURN</option>
                <option value="LOAD">LOAD</option>
                <option value="EXTRACT">EXTRACT</option>
              </select>
            </div>
            <div>
              <Label className="text-sm text-slate-500 mb-1 block">Период</Label>
              <select
                className="border rounded px-3 py-2 text-sm bg-white"
                value={logFilterDate}
                onChange={(e) => setLogFilterDate(e.target.value)}
              >
                <option value="all">Все</option>
                <option value="today">Сегодня</option>
                <option value="week">Неделя</option>
              </select>
            </div>
            <div className="flex-1 min-w-[200px]">
              <Label className="text-sm text-slate-500 mb-1 block">Поиск по RFID</Label>
              <Input
                placeholder="RFID книги..."
                value={logSearchText}
                onChange={(e) => setLogSearchText(e.target.value)}
              />
            </div>
            <Button variant="outline" onClick={handleExportCsv} className="h-10">
              Экспорт CSV
            </Button>
          </div>

          {filtered.length === 0 ? (
            <Card className="p-10 text-center">
              <History className="w-16 h-16 text-slate-400 mx-auto mb-4" />
              <p className="text-xl text-slate-500">Нет операций</p>
            </Card>
          ) : (
            <ScrollArea className="h-[calc(100vh-280px)]">
              <div className="space-y-3">
                {filtered.map((op) => (
                  <Card key={op.id} className="p-4" data-testid={`card-operation-${op.id}`}>
                    <div className="flex items-center justify-between">
                      <div>
                        <div className="flex items-center gap-2">
                          <Badge variant={op.result === 'OK' ? 'default' : 'destructive'}>
                            {op.operation}
                          </Badge>
                          <span className="text-sm text-slate-500">
                            {op.timestamp ? new Date(op.timestamp).toLocaleString() : '-'}
                          </span>
                        </div>
                        {op.bookRfid && (
                          <p className="text-slate-600 mt-1">RFID: {op.bookRfid}</p>
                        )}
                      </div>
                      <div className={`text-sm ${op.result === 'OK' ? 'text-green-600' : 'text-red-600'}`}>
                        {op.result === 'OK' ? 'Успешно' : op.result}
                      </div>
                    </div>
                  </Card>
                ))}
              </div>
            </ScrollArea>
          )}
        </div>
      </div>
    );
}
