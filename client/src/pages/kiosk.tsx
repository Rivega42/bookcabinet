import { useState, useEffect, useCallback, useRef, lazy, Suspense } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { useLocation } from "wouter";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ScrollArea } from "@/components/ui/scroll-area";
import { useToast } from "@/hooks/use-toast";
import { apiRequest, queryClient } from "@/lib/queryClient";
import type { User, Book, Cell, SystemStatus, Operation, Statistics, CalibrationData, WebSocketMessage } from "@shared/schema";
import {
  BookOpen,
  Undo2,
  User as UserIcon,
  Shield,
  Settings,
  CreditCard,
  CheckCircle2,
  XCircle,
  Loader2,
  ArrowLeft,
  Library,
  Package,
  AlertTriangle,
  Search,
  Plus,
  History,
  BarChart3,
  Activity,
  Cog,
  Play,
  RotateCcw,
  Move,
  Lock,
  Unlock,
  Target,
  Home,
  ArrowUp,
  ArrowDown,
  ArrowRight,
  Box,
  GraduationCap,
  Sliders,
  Radio,
} from "lucide-react";
import { ReaderMenu, BookList, ReturnBook } from "@/components/kiosk/ReaderScreens";
import { ProgressScreen, SuccessScreen, ErrorScreen, MaintenanceScreen } from "@/components/kiosk/FeedbackScreens";
import { LibrarianMenu } from "@/components/kiosk/screens/LibrarianMenu";
import { AdminMenu } from "@/components/kiosk/screens/AdminMenu";
import { LoadBooks } from "@/components/kiosk/screens/LoadBooks";
import { ExtractBooks } from "@/components/kiosk/screens/ExtractBooks";
import { OperationsLog } from "@/components/kiosk/screens/OperationsLog";
import { StatisticsScreen } from "@/components/kiosk/screens/StatisticsScreen";
import { DiagnosticsScreen } from "@/components/kiosk/screens/DiagnosticsScreen";
import { MechanicsTest } from "@/components/kiosk/screens/MechanicsTest";
import { CalibrationScreen } from "@/components/kiosk/screens/CalibrationScreen";

// Lazy-load heavy/seldom-used screens to keep initial kiosk bundle small (RPi3 optimization).
const TeachMode = lazy(() => import("@/components/TeachMode"));
const SettingsPanel = lazy(() => import("@/components/SettingsPanel"));
const CabinetViewer = lazy(() =>
  import("@/components/CabinetViewer").then((m) => ({ default: m.CabinetViewer })),
);
const IssueProcess = lazy(() =>
  import("@/components/kiosk/IssueProcess").then((m) => ({ default: m.IssueProcess })),
);

const LazyFallback = () => (
  <div className="min-h-screen bg-white flex items-center justify-center">
    <Loader2 className="w-12 h-12 animate-spin" />
  </div>
);

type Screen =
  | 'welcome'
  | 'reader_menu'
  | 'librarian_menu'
  | 'admin_menu'
  | 'book_list'
  | 'return_book'
  | 'issue_process'
  | 'load_books'
  | 'extract_books'
  | 'inventory'
  | 'operations_log'
  | 'statistics'
  | 'diagnostics'
  | 'mechanics_test'
  | 'calibration'
  | 'cabinet_view'
  | 'settings'
  | 'teach_mode'
  | 'progress'
  | 'success'
  | 'error'
  | 'maintenance';

interface SessionData {
  user: User;
  reservedBooks: Book[];
  needsExtraction: number;
}

export default function KioskPage() {
  const [screen, setScreen] = useState<Screen>('welcome');
  const [session, setSession] = useState<SessionData | null>(null);
  const [progressMessage, setProgressMessage] = useState('');
  const [progressValue, setProgressValue] = useState(0);
  const [errorMessage, setErrorMessage] = useState('');
  const [successMessage, setSuccessMessage] = useState('');
  const [manualReturnRfid, setManualReturnRfid] = useState('');
  const [issuingBook, setIssuingBook] = useState<Book | null>(null);
  const [, setLocation] = useLocation();
  const { toast } = useToast();
  const wsRef = useRef<WebSocket | null>(null);

  // ─── Session timeout / auto-logout (60 s inactivity) ────────────
  const inactivityTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const warningTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  // Guard against duplicate card_read / authMutation races (WebSocket + button click).
  const authInProgressRef = useRef(false);

  const SESSION_TIMEOUT_MS = 60_000;
  const SESSION_WARNING_MS = 45_000;

  const clearInactivityTimers = useCallback(() => {
    if (inactivityTimerRef.current) { clearTimeout(inactivityTimerRef.current); inactivityTimerRef.current = null; }
    if (warningTimerRef.current) { clearTimeout(warningTimerRef.current); warningTimerRef.current = null; }
  }, []);

  // Guarantee timers are cleared on unmount (prevents memory leak if component unmounts mid-session).
  useEffect(() => {
    return () => {
      if (inactivityTimerRef.current) clearTimeout(inactivityTimerRef.current);
      if (warningTimerRef.current) clearTimeout(warningTimerRef.current);
    };
  }, []);

  const performAutoLogout = useCallback(async () => {
    clearInactivityTimers();
    // Emergency stop + close shutters for book safety
    try { await apiRequest('POST', '/api/emergency-stop', {}); } catch {}
    try { await apiRequest('POST', '/api/shutter/close-all', {}); } catch {}
    try { await apiRequest('POST', '/api/auth/logout', {}); } catch {}
    setSession(null);
    setScreen('welcome');
  }, [clearInactivityTimers]);

  const resetInactivityTimer = useCallback(() => {
    clearInactivityTimers();
    warningTimerRef.current = setTimeout(() => {
      toast({ title: 'Автоматический выход через 15 секунд', variant: 'destructive' });
    }, SESSION_WARNING_MS);
    inactivityTimerRef.current = setTimeout(() => {
      performAutoLogout();
    }, SESSION_TIMEOUT_MS);
  }, [clearInactivityTimers, performAutoLogout, toast]);

  useEffect(() => {
    const isActive = session !== null && screen !== 'welcome';
    if (!isActive) {
      clearInactivityTimers();
      return;
    }

    resetInactivityTimer();

    const events = ['click', 'touchstart', 'keydown'] as const;
    const handler = () => resetInactivityTimer();
    events.forEach((e) => window.addEventListener(e, handler, { passive: true }));

    return () => {
      clearInactivityTimers();
      events.forEach((e) => window.removeEventListener(e, handler));
    };
  }, [session, screen, resetInactivityTimer, clearInactivityTimers]);
  // ─── end session timeout ────────────────────────────────────────

  // WebSocket: автоматическая авторизация при обнаружении к��рты
  useEffect(() => {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws`;
    let reconnectTimer: ReturnType<typeof setTimeout>;

    function connect() {
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onmessage = async (event) => {
        try {
          const msg: WebSocketMessage = JSON.parse(event.data);
          if (msg.type === 'card_read' && screen === 'welcome' && !authInProgressRef.current) {
            const uid = (msg.data as any)?.uid;
            if (uid) {
              authInProgressRef.current = true;
              toast({ title: 'Карта обнаружена', description: `UID: ${uid}` });
              try {
                const response = await apiRequest('POST', '/api/auth/card', { rfid: uid });
                const result = await response.json();
                if (result.success) {
                  setSession({
                    user: result.user,
                    reservedBooks: result.reservedBooks || [],
                    needsExtraction: result.needsExtraction || 0,
                  });
                  const role = result.user.role;
                  setScreen(role === 'admin' ? 'admin_menu' : role === 'librarian' ? 'librarian_menu' : 'reader_menu');
                } else {
                  toast({ title: 'Ошибка', description: result.error || 'Карта не зарегистрирована', variant: 'destructive' });
                }
              } catch (err: any) {
                toast({ title: 'Ошибка', description: err.message, variant: 'destructive' });
              } finally {
                authInProgressRef.current = false;
              }
            }
          }
        } catch {}
      };

      ws.onclose = () => {
        reconnectTimer = setTimeout(connect, 3000);
      };
    }

    connect();
    return () => {
      clearTimeout(reconnectTimer);
      wsRef.current?.close();
    };
  }, [screen]);

  // RPi3 optimization: rely on WebSocket for live status; use long interval only as a fallback.
  const { data: systemStatus } = useQuery<SystemStatus>({
    queryKey: ['/api/status'],
    refetchInterval: 30000,
  });

  // Extraction list is refreshed via WebSocket invalidation (no polling).
  const { data: cellsNeedingExtraction = [] } = useQuery<Cell[]>({
    queryKey: ['/api/cells/extraction'],
    enabled: session?.user.role === 'librarian' || session?.user.role === 'admin',
  });

  const { data: cells = [] } = useQuery<Cell[]>({
    queryKey: ['/api/cells'],
    enabled: screen === 'extract_books' || screen === 'cabinet_view',
  });

  useEffect(() => {
    if (systemStatus?.maintenanceMode && screen !== 'maintenance' && session?.user.role !== 'admin') {
      setScreen('maintenance');
    }
  }, [systemStatus?.maintenanceMode, screen, session]);

  const authMutation = useMutation({
    mutationFn: async (rfid: string) => {
      authInProgressRef.current = true;
      const response = await apiRequest('POST', '/api/auth/card', { rfid });
      return response.json();
    },
    onSuccess: (data) => {
      if (data.success) {
        setSession({
          user: data.user,
          reservedBooks: data.reservedBooks || [],
          needsExtraction: data.needsExtraction || 0,
        });

        switch (data.user.role) {
          case 'admin':
            setScreen('admin_menu');
            break;
          case 'librarian':
            setScreen('librarian_menu');
            break;
          default:
            setScreen('reader_menu');
        }
      }
      authInProgressRef.current = false;
    },
    onError: (error: any) => {
      authInProgressRef.current = false;
      setErrorMessage(error.message || 'Ошибка авторизации');
      setScreen('error');
    },
  });

  const issueMutation = useMutation({
    mutationFn: async ({ bookRfid, userRfid }: { bookRfid: string; userRfid: string }) => {
      const response = await apiRequest('POST', '/api/issue', { bookRfid, userRfid });
      return response.json();
    },
    onSuccess: (data) => {
      if (data.success) {
        setSuccessMessage(`Книга "${data.book.title}" выдана`);
        setScreen('success');
        queryClient.invalidateQueries({ queryKey: ['/api/books'] });
        queryClient.invalidateQueries({ queryKey: ['/api/cells'] });
      }
    },
    onError: (error: any) => {
      setErrorMessage(error.message || 'Ошибка выдачи');
      setScreen('error');
    },
  });

  const extractAllMutation = useMutation({
    mutationFn: async () => {
      const response = await apiRequest('POST', '/api/extract-all', {});
      return response.json();
    },
    onSuccess: (data) => {
      setSuccessMessage(`Изъято ${data.extracted} книг`);
      setScreen('success');
      queryClient.invalidateQueries({ queryKey: ['/api/cells'] });
    },
    onError: (error: any) => {
      setErrorMessage(error.message || 'Ошибка изъятия');
      setScreen('error');
    },
  });

  const inventoryMutation = useMutation({
    mutationFn: async () => {
      const response = await apiRequest('POST', '/api/run-inventory', {});
      return response.json();
    },
    onSuccess: (data) => {
      setSuccessMessage(`Инвентаризация завершена: найдено ${data.found} книг, отсутствует ${data.missing}`);
      setScreen('success');
    },
    onError: (error: any) => {
      setErrorMessage(error.message || 'Ошибка инвентаризации');
      setScreen('error');
    },
  });

  const handleCardScan = useCallback((rfid: string) => {
    authMutation.mutate(rfid);
  }, [authMutation]);

  const handleLogout = () => {
    setSession(null);
    setScreen('welcome');
  };

  const handleBack = () => {
    if (!session) {
      setScreen('welcome');
      return;
    }
    switch (session.user.role) {
      case 'admin':
        setScreen('admin_menu');
        break;
      case 'librarian':
        setScreen('librarian_menu');
        break;
      default:
        setScreen('reader_menu');
    }
  };

  const handleIssueBook = (book: Book) => {
    if (!session) return;
    setIssuingBook(book);
    setScreen('issue_process');
    // IssueProcess component now triggers the API call itself on mount
  };

  const renderHeader = () => {
    if (screen === 'welcome' || screen === 'maintenance') return null;
    
    return (
      <div className="fixed top-0 left-0 right-0 h-20 bg-black text-white flex items-center justify-between px-6 z-50 border-b-4 border-black" data-testid="header">
        <div className="flex items-center gap-4">
          {!['reader_menu', 'librarian_menu', 'admin_menu'].includes(screen) && (
            <Button 
              variant="ghost" 
              size="lg"
              className="text-white hover:bg-slate-800 h-14 px-6 text-lg"
              onClick={handleBack}
              data-testid="button-back"
            >
              <ArrowLeft className="w-6 h-6 mr-2" />
              Назад
            </Button>
          )}
          <Library className="w-8 h-8" />
          <span className="text-xl font-bold">Библиотечный шкаф</span>
        </div>
        
        <div className="flex items-center gap-4">
          {session && (
            <div className="flex items-center gap-2">
              <UserIcon className="w-5 h-5" />
              <span className="text-lg">{session.user.name}</span>
              <Badge variant={
                session.user.role === 'admin' ? 'destructive' : 
                session.user.role === 'librarian' ? 'secondary' : 'default'
              }>
                {session.user.role === 'admin' ? 'Админ' : 
                 session.user.role === 'librarian' ? 'Библиотекарь' : 'Читатель'}
              </Badge>
            </div>
          )}
          
          <div className="flex items-center gap-2">
            <div className={`w-3 h-3 rounded-full ${
              systemStatus?.state === 'idle' ? 'bg-green-500' :
              systemStatus?.state === 'busy' ? 'bg-yellow-500' :
              systemStatus?.state === 'error' ? 'bg-red-500' : 'bg-gray-500'
            }`} />
            <span className="text-sm">
              {systemStatus?.state === 'idle' ? 'Готов' :
               systemStatus?.state === 'busy' ? 'Занят' : 'Ошибка'}
            </span>
          </div>
          
          {session && (
            <Button 
              variant="outline" 
              onClick={handleLogout}
              className="border-white text-white hover:bg-white hover:text-slate-900 h-12 px-6"
              data-testid="button-logout"
            >
              Выход
            </Button>
          )}
        </div>
      </div>
    );
  };

  const renderWelcome = () => (
    <div className="min-h-screen bg-white flex flex-col items-center justify-center text-black p-8" data-testid="screen-welcome">
      <Library className="w-28 h-28 mb-6 text-black" aria-hidden="true" />
      <h1 className="text-5xl font-black mb-3">Добро пожаловать!</h1>
      <p className="text-2xl text-black mb-12">Автоматический шкаф книговыдачи</p>

      <div className="border-4 border-black rounded-2xl p-10 flex flex-col items-center max-w-2xl w-full bg-white">
        <CreditCard className="w-20 h-20 mb-4 text-black animate-pulse" aria-hidden="true" />
        <p className="text-xl font-bold mb-2">Приложите карту читателя</p>
        <p className="text-base text-black mb-6">или выберите тестового пользователя</p>

        <div className="flex flex-wrap gap-3 justify-center">
          <Button
            size="lg"
            className="h-20 px-8 text-xl min-w-[200px]"
            onClick={() => handleCardScan('CARD001')}
            aria-label="Войти как тестовый читатель"
            data-testid="button-test-reader"
          >
            <UserIcon className="w-6 h-6 mr-2" aria-hidden="true" />
            Читатель
          </Button>
          <Button
            size="lg"
            variant="secondary"
            className="h-20 px-8 text-xl min-w-[200px]"
            onClick={() => handleCardScan('ADMIN01')}
            aria-label="Войти как тестовый библиотекарь"
            data-testid="button-test-librarian"
          >
            <BookOpen className="w-6 h-6 mr-2" aria-hidden="true" />
            Библиотекарь
          </Button>
          <Button
            size="lg"
            variant="outline"
            className="h-20 px-8 text-xl min-w-[200px] border-2 border-black text-black hover:bg-black hover:text-white"
            onClick={() => handleCardScan('ADMIN99')}
            aria-label="Войти как тестовый администратор"
            data-testid="button-test-admin"
          >
            <Shield className="w-6 h-6 mr-2" aria-hidden="true" />
            Администратор
          </Button>
        </div>
      </div>

      {authMutation.isPending && (
        <div className="mt-6 flex items-center gap-3" role="status" aria-live="polite">
          <Loader2 className="w-6 h-6 animate-spin" aria-hidden="true" />
          <span>Авторизация...</span>
        </div>
      )}
    </div>
  );

  const renderReaderMenu = () => (
    <div className="min-h-screen bg-slate-100 pt-28 p-6" data-testid="screen-reader-menu">
      <div className="max-w-4xl mx-auto">
        <h2 className="text-3xl font-bold text-slate-800 mb-6 text-center">Выберите действие</h2>
        
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
          <Card
            className="cursor-pointer hover:shadow-xl transition-all border-2 hover:border-blue-500 active:scale-[0.98] focus:outline-none focus:ring-2 focus:ring-blue-500"
            onClick={() => setScreen('book_list')}
            onKeyDown={(e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                setScreen('book_list');
              }
            }}
            role="button"
            tabIndex={0}
            aria-label="Забрать забронированные книги"
            data-testid="card-get-book"
          >
            <CardContent className="p-10 flex flex-col items-center text-center">
              <BookOpen className="w-20 h-20 text-blue-500 mb-4" aria-hidden="true" />
              <h3 className="text-2xl font-bold mb-2">Забрать книгу</h3>
              <p className="text-lg text-slate-500">
                {session?.reservedBooks.length
                  ? `${session.reservedBooks.length} забронировано`
                  : 'Нет бронирований'}
              </p>
              {session && session.reservedBooks.length > 0 && (
                <Badge className="mt-3 text-base px-4 py-1" variant="default">
                  {session.reservedBooks.length} книг
                </Badge>
              )}
            </CardContent>
          </Card>

          <Card
            className="cursor-pointer hover:shadow-xl transition-all border-2 hover:border-green-500 active:scale-[0.98] focus:outline-none focus:ring-2 focus:ring-green-500"
            onClick={() => setScreen('return_book')}
            onKeyDown={(e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                setScreen('return_book');
              }
            }}
            role="button"
            tabIndex={0}
            aria-label="Вернуть книгу"
            data-testid="card-return-book"
          >
            <CardContent className="p-10 flex flex-col items-center text-center">
              <Undo2 className="w-20 h-20 text-green-500 mb-4" aria-hidden="true" />
              <h3 className="text-2xl font-bold mb-2">Вернуть книгу</h3>
              <p className="text-lg text-slate-500">
                Положите книгу в окно приёма
              </p>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );

  const renderBookList = () => (
    <div className="min-h-screen bg-slate-100 pt-28 p-6" data-testid="screen-book-list">
      <div className="max-w-4xl mx-auto">
        <h2 className="text-3xl font-bold text-slate-800 mb-6">Ваши забронированные книги</h2>
        
        {session?.reservedBooks.length === 0 ? (
          <Card className="p-10 text-center">
            <BookOpen className="w-16 h-16 text-slate-300 mx-auto mb-4" />
            <p className="text-xl text-slate-500">Нет забронированных книг</p>
          </Card>
        ) : (
          <div className="space-y-4">
            {session?.reservedBooks.map((book) => (
              <Card key={book.id} className="p-5" data-testid={`card-book-${book.rfid}`}>
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="text-xl font-bold">{book.title}</h3>
                    <p className="text-base text-slate-500">{book.author}</p>
                  </div>
                  <Button 
                    size="lg" 
                    className="h-14 px-8 text-lg"
                    onClick={() => handleIssueBook(book)}
                    disabled={issueMutation.isPending}
                    data-testid={`button-issue-${book.rfid}`}
                  >
                    <BookOpen className="w-5 h-5 mr-2" />
                    Забрать
                  </Button>
                </div>
              </Card>
            ))}
          </div>
        )}
      </div>
    </div>
  );

  const renderReturnBook = () => (
    <div className="min-h-screen bg-slate-100 pt-28 p-6" data-testid="screen-return-book">
      <div className="max-w-3xl mx-auto text-center">
        <h2 className="text-3xl font-bold text-slate-800 mb-6">Возврат книги</h2>

        <Card className="p-10 mb-6">
          <Radio className="w-20 h-20 text-green-500 mx-auto mb-4 animate-pulse" />
          <p className="text-xl mb-3">Положите книгу в окно приёма</p>
          <p className="text-base text-slate-500 mb-6">
            Книга будет автоматически распознана по RFID-метке
          </p>

          <div className="flex items-center justify-center gap-3 text-green-600 mb-4">
            <span className="relative flex h-4 w-4">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-4 w-4 bg-green-500"></span>
            </span>
            <span className="text-lg font-medium">Ожидаю скан...</span>
          </div>
        </Card>

        <Card className="p-6">
          <p className="text-sm text-slate-500 mb-3">Ручной ввод RFID (если автоскан не сработал)</p>
          <div className="flex gap-3 justify-center">
            <Input
              placeholder="RFID метка книги"
              value={manualReturnRfid}
              onChange={(e) => setManualReturnRfid(e.target.value)}
              className="max-w-xs"
            />
            <Button
              onClick={() => {
                if (manualReturnRfid.trim()) {
                  apiRequest('POST', '/api/return', { bookRfid: manualReturnRfid.trim() })
                    .then(r => r.json())
                    .then(data => {
                      if (data.success) {
                        setSuccessMessage(`Книга "${data.book?.title || manualReturnRfid}" возвращена`);
                        setScreen('success');
                      } else {
                        toast({ title: 'Ошибка', description: data.error || 'Не удалось вернуть книгу', variant: 'destructive' });
                      }
                      setManualReturnRfid('');
                    })
                    .catch(err => toast({ title: 'Ошибка', description: err.message, variant: 'destructive' }));
                }
              }}
              disabled={!manualReturnRfid.trim()}
            >
              Вернуть
            </Button>
          </div>
        </Card>
      </div>
    </div>
  );

  const renderProgress = () => (
    <div className="min-h-screen bg-slate-100 pt-28 flex items-center justify-center" data-testid="screen-progress">
      <Card className="p-10 w-full max-w-xl text-center">
        <Loader2 className="w-20 h-20 text-blue-500 mx-auto mb-4 animate-spin" />
        <h2 className="text-2xl font-bold mb-3">{progressMessage}</h2>
        <Progress value={progressValue} className="h-3 mb-3" />
        <p className="text-slate-500">Пожалуйста, подождите...</p>
      </Card>
    </div>
  );

  const renderSuccess = () => (
    <div className="min-h-screen bg-green-50 pt-28 flex items-center justify-center" data-testid="screen-success">
      <Card className="p-10 w-full max-w-xl text-center border-green-500 border-2">
        <CheckCircle2 className="w-24 h-24 text-green-500 mx-auto mb-4" />
        <h2 className="text-3xl font-bold text-green-700 mb-3">Успешно!</h2>
        <p className="text-xl text-slate-600 mb-6">{successMessage}</p>
        <Button 
          size="lg" 
          className="h-14 px-10 text-lg"
          onClick={handleBack}
          data-testid="button-continue"
        >
          Продолжить
        </Button>
      </Card>
    </div>
  );

  const renderError = () => (
    <div className="min-h-screen bg-red-50 pt-28 flex items-center justify-center" data-testid="screen-error">
      <Card className="p-10 w-full max-w-xl text-center border-red-500 border-2">
        <XCircle className="w-24 h-24 text-red-500 mx-auto mb-4" />
        <h2 className="text-3xl font-bold text-red-700 mb-3">Ошибка</h2>
        <p className="text-xl text-slate-600 mb-6">{errorMessage}</p>
        <Button 
          size="lg" 
          variant="destructive"
          className="h-14 px-10 text-lg"
          onClick={handleBack}
          data-testid="button-back-error"
        >
          Назад
        </Button>
      </Card>
    </div>
  );

  const renderMaintenance = () => (
    <div className="min-h-screen bg-yellow-50 flex items-center justify-center" data-testid="screen-maintenance">
      <Card className="p-10 w-full max-w-xl text-center border-yellow-500 border-2">
        <AlertTriangle className="w-24 h-24 text-yellow-500 mx-auto mb-4" />
        <h2 className="text-3xl font-bold text-yellow-700 mb-3">Шкаф временно недоступен</h2>
        <p className="text-xl text-slate-600">Ведутся технические работы</p>
      </Card>
    </div>
  );

  const renderCabinetView = () => {
    const cabinetCells = cells.map(cell => ({
      id: cell.id,
      row: cell.row || 'A',
      x: cell.x,
      y: cell.y,
      status: cell.status as 'empty' | 'occupied' | 'reserved' | 'needs_extraction',
      bookRfid: cell.bookRfid || undefined,
      bookTitle: cell.bookTitle || undefined
    }));

    return (
      <div className="min-h-screen bg-slate-100 pt-28 p-6" data-testid="screen-cabinet-view">
        <div className="max-w-7xl mx-auto h-[calc(100vh-160px)]">
          <h2 className="text-3xl font-bold text-slate-800 mb-4">3D-модель шкафа</h2>
          <Suspense fallback={<LazyFallback />}>
            <CabinetViewer cells={cabinetCells} />
          </Suspense>
        </div>
      </div>
    );
  };

  return (
    <>
      {renderHeader()}
      {screen === 'welcome' && renderWelcome()}
      {screen === 'reader_menu' && (
        <ReaderMenu
          session={session}
          onGetBooks={() => setScreen('book_list')}
          onReturnBook={() => setScreen('return_book')}
        />
      )}
      {screen === 'librarian_menu' && (
        <LibrarianMenu
          needsExtraction={session?.needsExtraction ?? 0}
          extractAllPending={extractAllMutation.isPending}
          onNavigate={(s) => setScreen(s as Screen)}
          onExtractAll={() => {
            setProgressMessage('Изъятие всех книг...');
            setProgressValue(20);
            setScreen('progress');
            extractAllMutation.mutate();
          }}
          onInventory={() => {
            setProgressMessage('Инвентаризация...');
            setProgressValue(10);
            setScreen('progress');
            inventoryMutation.mutate();
          }}
        />
      )}
      {screen === 'admin_menu' && (
        <AdminMenu onNavigate={(s) => setScreen(s as Screen)} onOpenDashboard={() => setLocation('/admin')} />
      )}
      {screen === 'book_list' && (
        <BookList
          books={session?.reservedBooks || []}
          userRfid={session?.user.rfid || ''}
          onIssue={(bookRfid, _userRfid) => {
            const book = session?.reservedBooks.find(b => b.rfid === bookRfid);
            if (book) {
              setIssuingBook(book);
              setScreen('issue_process');
            }
          }}
          issuing={false}
        />
      )}
      {screen === 'issue_process' && (
        <Suspense fallback={<LazyFallback />}>
          <IssueProcess
            book={issuingBook}
            userRfid={session?.user.rfid}
            wsRef={wsRef}
            onComplete={() => {
              setSuccessMessage(`Книга "${issuingBook?.title || ''}" выдана`);
              setIssuingBook(null);
              setScreen('success');
            }}
            onError={(msg) => {
              setErrorMessage(msg);
              setIssuingBook(null);
              setScreen('error');
            }}
          />
        </Suspense>
      )}
      {screen === 'return_book' && (
        <ReturnBook
          isPending={false}
          wsRef={wsRef}
          onComplete={() => {
            setSuccessMessage('Книга успешно возвращена');
            setScreen('success');
          }}
          onError={(msg) => {
            setErrorMessage(msg);
            setScreen('error');
          }}
        />
      )}
      {screen === 'load_books' && (
        <LoadBooks
          onProgress={(m) => { setProgressMessage(m); setProgressValue(30); setScreen('progress'); }}
          onSuccess={(m) => { setSuccessMessage(m); setScreen('success'); }}
          onError={(m) => { setErrorMessage(m); setScreen('error'); }}
        />
      )}
      {screen === 'extract_books' && (
        <ExtractBooks
          extractAllPending={extractAllMutation.isPending}
          onExtractAll={() => {
            setProgressMessage('Изъятие всех книг...');
            setScreen('progress');
            extractAllMutation.mutate();
          }}
        />
      )}
      {screen === 'operations_log' && <OperationsLog />}
      {screen === 'statistics' && <StatisticsScreen />}
      {screen === 'diagnostics' && <DiagnosticsScreen />}
      {screen === 'mechanics_test' && <MechanicsTest />}
      {screen === 'calibration' && <CalibrationScreen />}
      {screen === 'cabinet_view' && renderCabinetView()}
      {screen === 'settings' && (
        <div className="min-h-screen bg-slate-100 pt-28 p-6">
          <div className="max-w-4xl mx-auto">
            <h2 className="text-3xl font-bold text-slate-800 mb-6">Настройки системы</h2>
            <Suspense fallback={<LazyFallback />}>
              <SettingsPanel />
            </Suspense>
          </div>
        </div>
      )}
      {screen === 'teach_mode' && (
        <div className="min-h-screen bg-slate-100 pt-28 p-6">
          <div className="max-w-5xl mx-auto">
            <h2 className="text-3xl font-bold text-slate-800 mb-6">Режим обучения</h2>
            <Suspense fallback={<LazyFallback />}>
              <TeachMode />
            </Suspense>
          </div>
        </div>
      )}
      {screen === 'progress' && <ProgressScreen message={progressMessage} value={progressValue} />}
      {screen === 'success' && <SuccessScreen message={successMessage} onContinue={() => {
        const role = session?.user.role;
        setScreen(role === 'admin' ? 'admin_menu' : role === 'librarian' ? 'librarian_menu' : 'reader_menu');
      }} />}
      {screen === 'error' && <ErrorScreen message={errorMessage} onBack={() => {
        const role = session?.user.role;
        setScreen(role === 'admin' ? 'admin_menu' : role === 'librarian' ? 'librarian_menu' : 'reader_menu');
      }} />}
      {screen === 'maintenance' && <MaintenanceScreen />}
    </>
  );
}
