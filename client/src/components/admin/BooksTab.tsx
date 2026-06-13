import { useQuery } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import type { Book } from "@shared/schema";

export function BooksTab() {
  const { data: books = [] } = useQuery<Book[]>({ queryKey: ['/api/books'] });

  return (
    <Card>
      <CardHeader>
        <CardTitle>Книги в системе</CardTitle>
      </CardHeader>
      <CardContent>
        <ScrollArea className="h-96">
          <table className="w-full">
            <thead>
              <tr className="border-b">
                <th className="text-left py-2">RFID</th>
                <th className="text-left py-2">Название</th>
                <th className="text-left py-2">Автор</th>
                <th className="text-left py-2">Статус</th>
                <th className="text-left py-2">Ячейка</th>
              </tr>
            </thead>
            <tbody>
              {books.map((book) => (
                <tr key={book.id} className="border-b" data-testid={`row-book-${book.rfid}`}>
                  <td className="py-2 font-mono text-sm">{book.rfid}</td>
                  <td className="py-2">{book.title}</td>
                  <td className="py-2 text-slate-500">{book.author}</td>
                  <td className="py-2">
                    <Badge variant={
                      book.status === 'issued' ? 'destructive' :
                      book.status === 'reserved' ? 'default' : 'secondary'
                    }>
                      {book.status}
                    </Badge>
                  </td>
                  <td className="py-2">{book.cellId !== null ? `#${book.cellId}` : '-'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </ScrollArea>
      </CardContent>
    </Card>
  );
}
