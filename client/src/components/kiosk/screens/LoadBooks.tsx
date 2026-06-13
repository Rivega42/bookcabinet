import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Loader2, Plus } from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import { apiRequest, queryClient } from "@/lib/queryClient";

interface LoadBooksProps {
  onProgress: (message: string) => void;
  onSuccess: (message: string) => void;
  onError: (message: string) => void;
}

export function LoadBooks({ onProgress, onSuccess, onError }: LoadBooksProps) {
  const [newBookRfid, setNewBookRfid] = useState('');
  const [newBookTitle, setNewBookTitle] = useState('');
  const [newBookAuthor, setNewBookAuthor] = useState('');
  const { toast } = useToast();

  const loadBookMutation = useMutation({
    mutationFn: async ({ bookRfid, title, author }: { bookRfid: string; title: string; author?: string }) => {
      const response = await apiRequest('POST', '/api/load-book', { bookRfid, title, author });
      return response.json();
    },
    onSuccess: (data) => {
      if (data.success) {
        onSuccess('Книга загружена в ячейку');
        setNewBookRfid('');
        setNewBookTitle('');
        setNewBookAuthor('');
        queryClient.invalidateQueries({ queryKey: ['/api/books'] });
        queryClient.invalidateQueries({ queryKey: ['/api/cells'] });
      } else {
        onError(data.error || 'Ошибка загрузки книги');
      }
    },
    onError: (error: any) => {
      onError(error.message || 'Ошибка загрузки книги');
    },
  });

  const handleLoadBook = () => {
    if (!newBookRfid || !newBookTitle) {
      toast({ title: 'Ошибка', description: 'Заполните RFID и название книги', variant: 'destructive' });
      return;
    }
    onProgress(`Загрузка книги: ${newBookTitle}`);
    loadBookMutation.mutate({ bookRfid: newBookRfid, title: newBookTitle, author: newBookAuthor || undefined });
  };

  return (
    <div className="min-h-screen bg-slate-100 pt-28 p-6" data-testid="screen-load-books">
      <div className="max-w-2xl mx-auto">
        <h2 className="text-3xl font-bold text-slate-800 mb-6">Загрузка книги в шкаф</h2>
        
        <Card className="p-6">
          <div className="space-y-5">
            <div>
              <Label htmlFor="rfid" className="text-lg">RFID-метка книги *</Label>
              <Input 
                id="rfid"
                value={newBookRfid}
                onChange={(e) => setNewBookRfid(e.target.value)}
                placeholder="Сканируйте или введите RFID"
                className="h-14 text-lg mt-2"
                data-testid="input-book-rfid"
              />
            </div>
            
            <div>
              <Label htmlFor="title" className="text-lg">Название книги *</Label>
              <Input 
                id="title"
                value={newBookTitle}
                onChange={(e) => setNewBookTitle(e.target.value)}
                placeholder="Введите название"
                className="h-14 text-lg mt-2"
                data-testid="input-book-title"
              />
            </div>
            
            <div>
              <Label htmlFor="author" className="text-lg">Автор</Label>
              <Input 
                id="author"
                value={newBookAuthor}
                onChange={(e) => setNewBookAuthor(e.target.value)}
                placeholder="Введите автора (необязательно)"
                className="h-14 text-lg mt-2"
                data-testid="input-book-author"
              />
            </div>
            
            <Button 
              size="lg" 
              className="w-full h-16 text-xl"
              onClick={handleLoadBook}
              disabled={loadBookMutation.isPending || !newBookRfid || !newBookTitle}
              data-testid="button-load-book"
            >
              {loadBookMutation.isPending ? <Loader2 className="w-5 h-5 animate-spin mr-2" /> : <Plus className="w-5 h-5 mr-2" />}
              Загрузить книгу
            </Button>
          </div>
        </Card>
      </div>
    </div>
  );
}
