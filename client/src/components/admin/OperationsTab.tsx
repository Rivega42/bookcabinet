import { useQuery } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import type { Operation } from "@shared/schema";

export function OperationsTab() {
  const { data: operations = [] } = useQuery<Operation[]>({ queryKey: ['/api/operations'] });

  return (
    <Card>
      <CardHeader>
        <CardTitle>История операций</CardTitle>
      </CardHeader>
      <CardContent>
        <ScrollArea className="h-96">
          <table className="w-full">
            <thead>
              <tr className="border-b">
                <th className="text-left py-2">Время</th>
                <th className="text-left py-2">Операция</th>
                <th className="text-left py-2">Ячейка</th>
                <th className="text-left py-2">Книга</th>
                <th className="text-left py-2">Результат</th>
              </tr>
            </thead>
            <tbody>
              {operations.map((op) => (
                <tr key={op.id} className="border-b" data-testid={`row-operation-${op.id}`}>
                  <td className="py-2 text-sm">
                    {op.timestamp ? new Date(op.timestamp).toLocaleString() : '-'}
                  </td>
                  <td className="py-2">
                    <Badge>{op.operation}</Badge>
                  </td>
                  <td className="py-2">
                    {op.cellRow ? `${op.cellRow} X${op.cellX} Y${op.cellY}` : '-'}
                  </td>
                  <td className="py-2 font-mono text-sm">{op.bookRfid || '-'}</td>
                  <td className="py-2">
                    <Badge variant={op.result === 'OK' ? 'default' : 'destructive'}>
                      {op.result}
                    </Badge>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </ScrollArea>
      </CardContent>
    </Card>
  );
}
