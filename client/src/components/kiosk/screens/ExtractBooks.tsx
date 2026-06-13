import { useQuery, useMutation } from "@tanstack/react-query";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { CheckCircle2 } from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import { apiRequest, queryClient } from "@/lib/queryClient";
import type { Cell } from "@shared/schema";

interface ExtractBooksProps {
  extractAllPending: boolean;
  onExtractAll: () => void;
}

export function ExtractBooks({ extractAllPending, onExtractAll }: ExtractBooksProps) {
  const { toast } = useToast();
  const { data: cellsData = [] } = useQuery<Cell[]>({ queryKey: ['/api/cells'] });

  const extractMutation = useMutation({
    mutationFn: async (cellId: number) => {
      const response = await apiRequest('POST', '/api/extract', { cellId });
      return response.json();
    },
    onSuccess: (data) => {
      if (data.success) {
        toast({ title: 'Успешно', description: `Книга "${data.book?.title}" изъята` });
        queryClient.invalidateQueries({ queryKey: ['/api/cells'] });
        queryClient.invalidateQueries({ queryKey: ['/api/cells/extraction'] });
      }
    },
    onError: (error: any) => {
      toast({ title: 'Ошибка', description: error.message, variant: 'destructive' });
    },
  });

    const extractionCells = cellsData.filter(c => c.needsExtraction);

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
                          onClick={() => extractMutation.mutate(cell.id)}
                          disabled={extractMutation.isPending}
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
