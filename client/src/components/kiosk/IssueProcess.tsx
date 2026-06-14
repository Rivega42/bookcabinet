import { useState, useEffect, useRef, useCallback } from "react";
import { Card } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Badge } from "@/components/ui/badge";
import { BookOpen, CheckCircle2, Loader2, Clock, Package } from "lucide-react";
import type { Book } from "@shared/schema";
import { apiRequest } from "@/lib/queryClient";

interface IssueStep {
  id: number;
  label: string;
  description: string;
}

const ISSUE_STEPS: IssueStep[] = [
  { id: 1, label: "Подготовка", description: "Хоминг каретки" },
  { id: 2, label: "Перемещение", description: "Каретка перемещается к ячейке с книгой" },
  { id: 3, label: "Захват", description: "Открытие внутренней шторки" },
  { id: 4, label: "Извлечение", description: "Платформа выдвигается к полке" },
  { id: 5, label: "Транспортировка", description: "Перемещение к окну выдачи" },
  { id: 6, label: "Выдача", description: "Заберите книгу из окна" },
];

interface IssueProcessProps {
  book: Book | null;
  userRfid?: string;
  onComplete: () => void;
  onError: (message: string) => void;
  wsRef: React.RefObject<WebSocket | null>;
}

export function IssueProcess({ book, userRfid, onComplete, onError, wsRef }: IssueProcessProps) {
  const [currentStep, setCurrentStep] = useState(1);
  const [shutterTimer, setShutterTimer] = useState<number | null>(null);
  const [isStarted, setIsStarted] = useState(false);
  const [stepLabel, setStepLabel] = useState("");
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const startedRef = useRef(false);
  const onErrorRef = useRef(onError);
  onErrorRef.current = onError;

  // Сторож зависания: если WS-событие завершения потеряно (реконнект и т.п.) —
  // не висим на экране прогресса вечно. Снимается при unmount (успех/ошибка
  // меняют экран → размонтирование). 180 c с запасом перекрывают самый долгий цикл.
  useEffect(() => {
    const t = setTimeout(() => {
      onErrorRef.current('Операция не завершилась вовремя. Обратитесь к сотруднику.');
    }, 180000);
    return () => clearTimeout(t);
  }, []);

  // Map mechanical step numbers (1-14) to UI steps (1-6)
  const mapMechanicalStep = useCallback((mechStep: number, status: string): number => {
    if (mechStep <= 1) return 1;       // Homing
    if (mechStep <= 2) return 2;       // Move to cell
    if (mechStep <= 3) return 3;       // Open inner shutter
    if (mechStep <= 5) return 4;       // Tray back + close inner
    if (mechStep <= 8) return 5;       // Move to window + lock + tray front
    if (mechStep >= 9) return 6;       // Outer shutter open + wait + close + retract + home
    return 1;
  }, []);

  // Start the issue process when component mounts
  useEffect(() => {
    if (startedRef.current || !book) return;
    startedRef.current = true;
    setIsStarted(true);

    apiRequest('POST', '/api/book/issue', {
      bookRfid: book.rfid,
      userRfid: userRfid || book.reservedForRfid || book.issuedToRfid || '',
    }).then(async (response) => {
      const data = await response.json();
      if (!data.success) {
        onError(data.error || data.message || 'Issue sequence failed');
      }
      // Completion is handled by WebSocket operation_completed event
    }).catch((err) => {
      onError(err.message || 'Network error during issue');
    });
  }, [book, onError]);

  // Listen for WebSocket progress events
  useEffect(() => {
    const ws = wsRef.current;
    if (!ws) return;

    const handler = (event: MessageEvent) => {
      try {
        const msg = JSON.parse(event.data);

        // Progress events from the mechanical sequence
        if (msg.type === 'progress' && msg.data) {
          const data = msg.data;
          if (data.step && typeof data.step === 'number') {
            const uiStep = mapMechanicalStep(data.step, data.status || 'running');
            setCurrentStep(uiStep);
            if (data.label) {
              setStepLabel(data.label);
            }
            // When outer shutter opens (mechanical step 9), start the 30-sec timer
            if (data.step === 9 && data.status === 'done') {
              setCurrentStep(6);
              setShutterTimer(30);
            }
            // When wait step starts (mechanical step 10)
            if (data.step === 10 && data.status === 'running' && data.wait_seconds) {
              setShutterTimer(data.wait_seconds);
            }
          }
        }

        if (msg.type === 'shutter_state' && msg.data?.shutter === 'outer' && msg.data?.state === 'open') {
          setCurrentStep(6);
          setShutterTimer(30);
        }

        if (msg.type === 'book_presence' && msg.data?.present === false) {
          // Book was taken
          setShutterTimer(null);
        }

        if (msg.type === 'operation_completed' && msg.data?.operation === 'issue') {
          setCurrentStep(6);
          setShutterTimer(null);
          setTimeout(onComplete, 1500);
        }

        if (msg.type === 'operation_failed' || msg.type === 'error') {
          onError(msg.data?.message || 'Operation failed');
        }
      } catch {}
    };

    ws.addEventListener('message', handler);
    return () => ws.removeEventListener('message', handler);
  }, [wsRef, onComplete, onError, mapMechanicalStep]);

  // Timer countdown when shutter is open (step 6)
  useEffect(() => {
    if (shutterTimer === null || shutterTimer <= 0) {
      if (timerRef.current) clearInterval(timerRef.current);
      return;
    }

    timerRef.current = setInterval(() => {
      setShutterTimer(prev => {
        if (prev === null || prev <= 1) {
          if (timerRef.current) clearInterval(timerRef.current);
          return 0;
        }
        return prev - 1;
      });
    }, 1000);

    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [shutterTimer !== null]);

  const progressPercent = Math.round((currentStep / ISSUE_STEPS.length) * 100);

  return (
    <div className="min-h-screen bg-white pt-28 p-6" data-testid="screen-issue-process">
      <div className="max-w-2xl mx-auto">
        {/* Book info */}
        {book && (
          <Card className="p-5 mb-6">
            <div className="flex items-center gap-4">
              <BookOpen className="w-10 h-10 text-black" />
              <div>
                <h3 className="text-xl font-bold">{book.title}</h3>
                <p className="text-base text-black">{book.author}</p>
              </div>
            </div>
          </Card>
        )}

        {/* Step indicator */}
        <div className="mb-6">
          <div className="flex items-center justify-between mb-2">
            <span className="text-lg font-bold">
              Шаг {currentStep} / {ISSUE_STEPS.length}
            </span>
            <Badge variant="default">{progressPercent}%</Badge>
          </div>
          <Progress
            value={progressPercent}
            className="h-3 mb-2"
            role="progressbar"
            aria-valuenow={progressPercent}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-label="Прогресс выдачи книги"
          />
          <p className="text-base text-black font-medium" role="status" aria-live="polite">
            {ISSUE_STEPS[currentStep - 1]?.description || "Обработка..."}
          </p>
          {stepLabel && currentStep < 6 && (
            <p className="text-sm text-gray-500 mt-1">{stepLabel}</p>
          )}
        </div>

        {/* Steps list */}
        <div className="space-y-3 mb-6">
          {ISSUE_STEPS.map((step) => {
            const isCompleted = step.id < currentStep;
            const isCurrent = step.id === currentStep;
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

        {/* Timer when shutter is open */}
        {shutterTimer !== null && shutterTimer > 0 && currentStep === 6 && (
          <Card className="p-6 text-center border-2 border-black">
            <Package className="w-16 h-16 mx-auto mb-3 text-black" aria-hidden="true" />
            <h3 className="text-2xl font-bold mb-2">Заберите книгу!</h3>
            <div
              className="flex items-center justify-center gap-2 text-lg"
              role="timer"
              aria-live="polite"
              aria-label={`Осталось ${shutterTimer} секунд`}
            >
              <Clock className="w-5 h-5" aria-hidden="true" />
              <span className="font-bold text-2xl">{shutterTimer}</span>
              <span>сек.</span>
            </div>
          </Card>
        )}
      </div>
    </div>
  );
}
