import { useQuery } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import type { Cell } from "@shared/schema";

export function CabinetMapTab() {
  const { data: cells = [] } = useQuery<Cell[]>({ queryKey: ['/api/cells'] });

  const frontCells = cells.filter(c => c.row === 'FRONT');
  const backCells = cells.filter(c => c.row === 'BACK');

  const getCellColor = (cell: Cell | undefined) => {
    if (!cell) return 'bg-slate-100';
    switch (cell.status) {
      case 'blocked': return 'bg-slate-300';
      case 'occupied': return 'bg-blue-500';
      case 'reserved': return 'bg-green-500';
      case 'empty': return 'bg-white border-2 border-slate-200';
      default: return 'bg-slate-100';
    }
  };

  const renderRow = (rowCells: Cell[], rowName: string) => (
    <div>
      <h3 className="font-bold mb-2">{rowName}</h3>
      <div className="grid grid-cols-21 gap-1">
        {[0, 1, 2].map(x => (
          <div key={x} className="contents">
            {Array.from({ length: 21 }, (_, y) => {
              const cell = rowCells.find(c => c.x === x && c.y === y);
              return (
                <div
                  key={`${x}-${y}`}
                  className={`w-6 h-6 rounded text-xs flex items-center justify-center ${getCellColor(cell)}`}
                  title={cell ? `${cell.row} X${cell.x} Y${cell.y}: ${cell.status}${cell.bookTitle ? ` - ${cell.bookTitle}` : ''}` : ''}
                  data-testid={`cell-${rowName}-${x}-${y}`}
                >
                  {cell?.needsExtraction && '!'}
                </div>
              );
            })}
          </div>
        ))}
      </div>
    </div>
  );

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>Карта шкафа</CardTitle>
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="flex gap-4 text-sm">
            <div className="flex items-center gap-2">
              <div className="w-4 h-4 bg-white border-2 border-slate-200 rounded" />
              <span>Свободна</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-4 h-4 bg-blue-500 rounded" />
              <span>Занята</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-4 h-4 bg-green-500 rounded" />
              <span>Забронирована</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-4 h-4 bg-slate-300 rounded" />
              <span>Заблокирована</span>
            </div>
          </div>

          {renderRow(frontCells, 'FRONT')}
          <Separator />
          {renderRow(backCells, 'BACK')}
        </CardContent>
      </Card>
    </div>
  );
}
