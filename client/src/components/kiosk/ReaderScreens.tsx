import { useState, useEffect, useRef } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Progress } from "@/components/ui/progress";
import { BookOpen, Undo2, CreditCard, Loader2, Radio, Clock, CheckCircle2 } from "lucide-react";
import type { User, Book } from "@shared/schema";
import type { SessionData } from "./types";

interface ReaderMenuProps {
  session: SessionData | null;
  onGetBooks: () => void;
  onReturnBook: () => void;
}

export function ReaderMenu({ session, onGetBooks, onReturnBook }: ReaderMenuProps) {
  return (
    <div className="min-h-screen bg-slate-100 pt-28 p-6" data-testid="screen-reader-menu">
      <div className="max-w-3xl mx-auto">
        <h2 className="text-3xl font-bold text-slate-800 mb-2 text-center">
          Здравствуйте, {session?.user.name}!
        </h2>
        {(session?.reservedBooks?.length ?? 0) > 0 && (
          <p className="text-center text-slate-500 mb-6">
            У вас {session?.reservedBooks.length} забронированных книг
          </p>
        )}

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
          <Card
            className="cursor-pointer hover:shadow-xl transition-all active:scale-[0.98] focus:outline-none focus:ring-2 focus:ring-blue-500"
            onClick={onGetBooks}
            onKeyDown={(e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                onGetBooks();
              }
            }}
            role="button"
            tabIndex={0}
            aria-label="Получить забронированные книги"
            data-testid="card-get-book"
          >
            <CardContent className="p-8 sm:p-10 flex flex-col items-center text-center">
              <BookOpen className="w-16 h-16 sm:w-20 sm:h-20 text-blue-500 mb-4" aria-hidden="true" />
              <h3 className="text-2xl font-bold mb-2">Получить книгу</h3>
              <p className="text-slate-500">Забронированные книги</p>
              {(session?.reservedBooks?.length ?? 0) > 0 && (
                <Badge className="mt-3 text-lg px-4 py-1">{session?.reservedBooks.length}</Badge>
              )}
            </CardContent>
          </Card>

          <Card
            className="cursor-pointer hover:shadow-xl transition-all active:scale-[0.98] focus:outline-none focus:ring-2 focus:ring-green-500"
            onClick={onReturnBook}
            onKeyDown={(e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                onReturnBook();
              }
            }}
            role="button"
            tabIndex={0}
            aria-label="Вернуть книгу"
            data-testid="card-return-book"
          >
            <CardContent className="p-8 sm:p-10 flex flex-col items-center text-center">
              <Undo2 className="w-16 h-16 sm:w-20 sm:h-20 text-green-500 mb-4" aria-hidden="true" />
              <h3 className="text-2xl font-bold mb-2">Вернуть книгу</h3>
              <p className="text-slate-500">Поднесите книгу к считывателю</p>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}

interface BookListProps {
  books: Book[];
  onIssue: (bookRfid: string, userRfid: string) => void;
  userRfid: string;
  issuing: boolean;
}

export function BookList({ books, onIssue, userRfid, issuing }: BookListProps) {
  return (
    <div className="min-h-screen bg-slate-100 pt-28 p-6" data-testid="screen-book-list">
      <div className="max-w-4xl mx-auto">
        <h2 className="text-3xl font-bold text-slate-800 mb-6">Ваши забронированные книги</h2>

        {books.length === 0 ? (
          <Card className="p-10 text-center">
            <BookOpen className="w-16 h-16 text-slate-300 mx-auto mb-4" aria-hidden="true" />
            <p className="text-xl text-slate-500">Нет забронированных книг</p>
          </Card>
        ) : (
          <div className="space-y-4" role="list">
            {books.map((book) => (
              <Card
                key={book.id}
                className="p-5 focus:outline-none focus:ring-2 focus:ring-blue-500"
                role="listitem"
                aria-label={`Книга: ${book.title}, автор ${book.author}`}
                data-testid={`card-book-${book.rfid}`}
              >
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="text-xl font-bold">{book.title}</h3>
                    <p className="text-base text-slate-500">{book.author}</p>
                  </div>
                  <Button
                    size="lg"
                    className="h-14 px-8 text-lg"
                    onClick={() => onIssue(book.rfid, userRfid)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault();
                        onIssue(book.rfid, userRfid);
                      }
                    }}
                    disabled={issuing}
                    aria-label={`Получить книгу ${book.title}`}
                    data-testid={`button-issue-${book.rfid}`}
                  >
                    {issuing ? <Loader2 className="w-5 h-5 animate-spin mr-2" aria-hidden="true" /> : null}
                    Получить
                  </Button>
                </div>
              </Card>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

interface ReturnStep {
  id: number;
  label: string;
  description: string;
}

// Реальный процесс возврата: книгу УЖЕ положили в окно (RRU распознал) → шкаф
// её укладывает в ячейку (give_shelf). Бэкенд шлёт чистую шкалу 1..4 (_KioskProgress).
const RETURN_STEPS: ReturnStep[] = [
  { id: 1, label: "Приём", description: "Книга распознана, шторки закрываются" },
  { id: 2, label: "Перемещение", description: "Каретка везёт книгу к ячейке" },
  { id: 3, label: "Размещение", description: "Книга укладывается в ячейку" },
  { id: 4, label: "Завершение", description: "Возврат каретки в исходное положение" },
];

interface ReturnBookProps {
  isPending: boolean;
  onManualReturn?: (rfid: string) => void;
  onComplete?: () => void;
  onError?: (message: string) => void;
  wsRef?: React.RefObject<WebSocket | null>;
}

export function ReturnBook({ isPending, onManualReturn, onComplete, onError, wsRef }: ReturnBookProps) {
  const [manualRfid, setManualRfid] = useState('');
  const [timer, setTimer] = useState(60);
  const [detectedBook, setDetectedBook] = useState<{ rfid: string; title?: string } | null>(null);
  const [returnStep, setReturnStep] = useState(0);
  const [stepLabel, setStepLabel] = useState('');
  const [sequenceStarted, setSequenceStarted] = useState(false);
  const [returnPending, setReturnPending] = useState(false);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const returnStartedRef = useRef(false);

  // Бэкенд (_KioskProgress, return-ветка) уже шлёт чистую шкалу 1..4 —
  // ровно под RETURN_STEPS. Здесь только зажимаем в диапазон.
  const mapMechanicalStep = (mechStep: number): number => {
    return Math.min(RETURN_STEPS.length, Math.max(1, mechStep));
  };

  // Start the return sequence when a book RFID is detected
  const startReturnSequence = (bookRfid: string) => {
    if (returnStartedRef.current) return;
    returnStartedRef.current = true;
    setSequenceStarted(true);
    setReturnPending(true);
    setReturnStep(1);

    fetch('/api/book/return', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ bookRfid }),
    })
      .then(async (response) => {
        const data = await response.json();
        if (!data.success && onError) {
          onError(data.error || data.message || 'Return sequence failed');
        }
        setReturnPending(false);
      })
      .catch((err) => {
        setReturnPending(false);
        if (onError) {
          onError(err.message || 'Network error during return');
        }
      });
  };

  // 60-second countdown timer for waiting for book scan
  useEffect(() => {
    if (sequenceStarted) return; // Don't run scan timer once sequence started
    setTimer(60);
    timerRef.current = setInterval(() => {
      setTimer(prev => {
        if (prev <= 1) {
          if (timerRef.current) clearInterval(timerRef.current);
          return 0;
        }
        return prev - 1;
      });
    }, 1000);

    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [sequenceStarted]);

  // Listen for WebSocket events
  useEffect(() => {
    const currentWs = wsRef?.current;
    if (!currentWs) return;

    const handler = (event: MessageEvent) => {
      try {
        const msg = JSON.parse(event.data);

        // Book RFID detected via reader
        if ((msg.type === 'book_read' || msg.type === 'book_detected') && !sequenceStarted) {
          const rfid = msg.data?.rfid;
          if (rfid) {
            setDetectedBook({ rfid, title: msg.data?.title });
            // Auto-start the return sequence
            startReturnSequence(rfid);
          }
        }

        // Progress events from the mechanical sequence
        if (msg.type === 'progress' && msg.data) {
          const data = msg.data;
          if (data.step && typeof data.step === 'number') {
            const uiStep = mapMechanicalStep(data.step);
            setReturnStep(uiStep);
            if (data.label) {
              setStepLabel(data.label);
            }
          }
        }

        if (msg.type === 'operation_completed' && msg.data?.operation === 'return') {
          setReturnStep(RETURN_STEPS.length);
          if (onComplete) {
            setTimeout(onComplete, 1500);
          }
        }

        if (msg.type === 'operation_failed' && msg.data?.operation === 'return') {
          if (onError) {
            onError(msg.data?.message || 'Return operation failed');
          }
        }
      } catch {}
    };

    currentWs.addEventListener('message', handler);
    return () => currentWs.removeEventListener('message', handler);
  }, [wsRef, sequenceStarted, onComplete, onError]);

  // Calculate progress
  const progressPercent = returnStep > 0 ? Math.round((returnStep / RETURN_STEPS.length) * 100) : 0;

  return (
    <div className="min-h-screen bg-white pt-28 p-6" data-testid="screen-return-book">
      <div className="max-w-3xl mx-auto text-center">
        <h2 className="text-3xl font-bold text-black mb-6">Возврат книги</h2>

        {/* Before sequence starts: scan waiting */}
        {!sequenceStarted && (
          <Card className="p-10 mb-6">
            <Radio className="w-20 h-20 text-black mx-auto mb-4 animate-pulse" />
            <p className="text-xl mb-3">Положите книгу в окно приёма</p>
            <p className="text-base text-black mb-4">
              Книга будет автоматически распознана по RFID-метке
            </p>

            {/* Timer */}
            <div className="flex items-center justify-center gap-2 mb-4">
              <Clock className="w-5 h-5 text-black" />
              <span className={`text-2xl font-bold ${timer <= 10 ? 'text-red-600' : 'text-black'}`}>
                {timer}
              </span>
              <span className="text-black">сек.</span>
            </div>

            <div className="flex items-center justify-center gap-3 text-black mb-4">
              <span className="relative flex h-4 w-4">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-black opacity-30"></span>
                <span className="relative inline-flex rounded-full h-4 w-4 bg-black"></span>
              </span>
              <span className="text-lg font-medium">Ожидаю скан...</span>
            </div>

            {isPending && (
              <div className="flex items-center justify-center gap-3 text-black">
                <Loader2 className="w-6 h-6 animate-spin" />
                <span>Обработка...</span>
              </div>
            )}
          </Card>
        )}

        {/* After sequence starts: progress steps */}
        {sequenceStarted && (
          <>
            {/* Detected book info */}
            {detectedBook && (
              <Card className="p-5 mb-6">
                <div className="flex items-center justify-center gap-3">
                  <CheckCircle2 className="w-6 h-6 text-black" />
                  <div>
                    <span className="font-bold">Книга обнаружена</span>
                    {detectedBook.title && (
                      <span className="ml-2 text-black">{detectedBook.title}</span>
                    )}
                    <p className="text-sm text-gray-500">RFID: {detectedBook.rfid}</p>
                  </div>
                </div>
              </Card>
            )}

            {/* Step indicator */}
            <div className="mb-6 text-left">
              <div className="flex items-center justify-between mb-2">
                <span className="text-lg font-bold">
                  Шаг {returnStep} / {RETURN_STEPS.length}
                </span>
                <Badge variant="default">{progressPercent}%</Badge>
              </div>
              <Progress value={progressPercent} className="h-3 mb-2" />
              <p className="text-base text-black font-medium">
                {RETURN_STEPS[returnStep - 1]?.description || "Обработка..."}
              </p>
              {stepLabel && (
                <p className="text-sm text-gray-500 mt-1">{stepLabel}</p>
              )}
            </div>

            {/* Steps list */}
            <div className="space-y-3 mb-6 text-left">
              {RETURN_STEPS.map((step) => {
                const isCompleted = step.id < returnStep;
                const isCurrent = step.id === returnStep;
                return (
                  <div
                    key={step.id}
                    className={`flex items-center gap-3 p-3 rounded-xl border-2 ${
                      isCompleted
                        ? "border-black bg-white"
                        : isCurrent
                        ? "border-black bg-white"
                        : "border-gray-300 bg-white opacity-50"
                    }`}
                  >
                    <div className="w-8 h-8 flex items-center justify-center">
                      {isCompleted ? (
                        <CheckCircle2 className="w-6 h-6 text-black" />
                      ) : isCurrent ? (
                        <Loader2 className="w-6 h-6 text-black animate-spin" />
                      ) : (
                        <span className="w-6 h-6 rounded-full border-2 border-gray-400 flex items-center justify-center text-sm text-gray-400">
                          {step.id}
                        </span>
                      )}
                    </div>
                    <div>
                      <span className={`font-bold ${isCompleted || isCurrent ? "text-black" : "text-gray-400"}`}>
                        {step.label}
                      </span>
                      {isCurrent && (
                        <p className="text-sm text-black">{step.description}</p>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </>
        )}

        {/* Manual RFID input */}
        <Card className="p-6">
          <p className="text-sm text-black mb-3">Ручной ввод RFID (если автоскан не сработал)</p>
          <div className="flex gap-3 justify-center">
            <Input
              placeholder="RFID метка книги"
              value={manualRfid}
              onChange={(e) => setManualRfid(e.target.value)}
              className="max-w-xs"
              disabled={sequenceStarted}
            />
            <Button
              onClick={() => {
                if (manualRfid.trim()) {
                  setDetectedBook({ rfid: manualRfid.trim() });
                  startReturnSequence(manualRfid.trim());
                  if (onManualReturn) {
                    onManualReturn(manualRfid.trim());
                  }
                  setManualRfid('');
                }
              }}
              disabled={!manualRfid.trim() || isPending || sequenceStarted}
            >
              Вернуть
            </Button>
          </div>
        </Card>
      </div>
    </div>
  );
}
