import { useQuery } from "@tanstack/react-query";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { CheckCircle2 } from "lucide-react";
import type { Cell } from "@shared/schema";

interface ExtractBooksProps {
  extractAllPending: boolean;
  onExtract: (cellId: number) => void;
  onExtractAll: () => void;
}

export function ExtractBooks({ extractAllPending, onExtract, onExtractAll }: ExtractBooksProps) {
  // Эндпоинт уже отдаёт ТОЛЬКО ячейки, требующие изъятия (awaiting_extraction),
  // camelize на бэке → bookTitle/needsExtraction корректны. Локальный фильтр не нужен.
  const { data: extractionCells = [] } = useQuery<Cell[]>({ queryKey: ['/api/cells/extraction'] });

    return (
      <div className="min-h-screen bg-slate-100 pt-28 p-6" data-testid="screen-extract-books">
        <div className="max-w-4xl mx-auto">
          <h2 className="text-3xl font-bold text-slate-800 mb-6">Изъятие книг</h2>
          
          {extractionCells.length === 0 ? (
            <Card className="p-10 text-center">
              <CheckCircle2 className="w-16 h-16 text-green-500 mx-auto mb-4" />
              <p className="text-xl text-slate-500">Нет книг для изъятия</p>
            </Card>
          ) : (
            <>
              <div className="mb-4 flex justify-between items-center">
                <span className="text-lg">{extractionCells.length} книг для изъятия</span>
                <Button
                  onClick={() => onExtractAll()}
                  disabled={extractAllPending}
                  data-testid="button-extract-all-page"
                >
                  Изъять все
                </Button>
              </div>
              
              <ScrollArea className="h-96">
                <div className="space-y-3">
                  {extractionCells.map((cell) => (
                    <Card key={cell.id} className="p-4" data-testid={`card-cell-${cell.id}`}>
                      <div className="flex items-center justify-between">
                        <div>
                          <h3 className="text-lg font-bold">{cell.bookTitle}</h3>
                          <p className="text-sm text-slate-500">
                            Ячейка: {cell.row} X{cell.x} Y{cell.y}
                          </p>
                        </div>
                        <Button
                          onClick={() => onExtract(cell.id)}
                          disabled={extractAllPending}
                          data-testid={`button-extract-${cell.id}`}
                        >
                          Изъять
                        </Button>
                      </div>
                    </Card>
                  ))}
                </div>
              </ScrollArea>
            </>
          )}
        </div>
      </div>
    );
}
