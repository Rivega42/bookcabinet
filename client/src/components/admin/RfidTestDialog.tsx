import { useState, useRef, useEffect } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { MonitorDot, RefreshCw } from "lucide-react";

interface RfidTestDialogProps {
  readerId: string | null;
  onClose: () => void;
}

/** Консоль теста считывателя (SSE /api/rfid-test/{id}; пока только Express). */
export function RfidTestDialog({ readerId, onClose }: RfidTestDialogProps) {
  const [testLog, setTestLog] = useState<Array<{ type: string; message?: string; uid?: string; epc?: string; reader?: string }>>([]);
  const [testRunning, setTestRunning] = useState(false);
  const testLogRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!readerId) return;
    setTestLog([]);
    setTestRunning(true);
    const es = new EventSource(`/api/rfid-test/${readerId}`);
    es.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data);
        setTestLog(prev => [...prev.slice(-99), data]);
        if (data.type === 'done') { setTestRunning(false); es.close(); }
        setTimeout(() => testLogRef.current?.scrollTo(0, testLogRef.current.scrollHeight), 50);
      } catch {}
    };
    es.onerror = () => { setTestRunning(false); es.close(); };
    return () => { es.close(); setTestRunning(false); };
  }, [readerId]);

  return (
    <Dialog open={!!readerId} onOpenChange={(open) => { if (!open) onClose(); }}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <MonitorDot className="w-4 h-4" />
            Тест считывателя: {readerId?.toUpperCase()}
            {testRunning && <RefreshCw className="w-4 h-4 animate-spin text-blue-500" />}
          </DialogTitle>
        </DialogHeader>
        <div ref={testLogRef} className="bg-slate-900 rounded-md p-3 h-40 overflow-y-auto font-mono text-xs">
          {testLog.length === 0 && <span className="text-slate-500">Ожидание событий...</span>}
          {testLog.map((entry, i) => (
            <div key={i} className={
              entry.type === 'card' || entry.type === 'tag' ? 'text-green-400 font-bold' :
              entry.type === 'error' ? 'text-red-400' :
              entry.type === 'done' ? 'text-yellow-400' : 'text-slate-400'
            }>
              {entry.type === 'card' && `✅ КАРТА: ${entry.uid}  [${entry.reader}]`}
              {entry.type === 'tag' && `✅ МЕТКА: ${entry.epc}  [${entry.reader}]`}
              {entry.type === 'info' && `ℹ  ${entry.message}`}
              {entry.type === 'error' && `❌ ${entry.message}`}
              {entry.type === 'done' && `⏹  ${entry.message}`}
              {entry.type === 'raw' && entry.message}
            </div>
          ))}
        </div>
      </DialogContent>
    </Dialog>
  );
}
