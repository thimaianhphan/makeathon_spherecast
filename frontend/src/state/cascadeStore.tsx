import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import type { CascadeProgress, CascadeReport, LiveMessage } from "@/data/types";
import { subscribeToStream } from "@/api/client";

type ControlsState = {
  productId: string;
  quantity: number;
  budgetEur: number;
  desiredDeliveryDate: string;
};

type CascadeState = {
  progress: CascadeProgress;
  report: CascadeReport | null;
  messages: LiveMessage[];
  connected: boolean;
  controls: ControlsState;
  setProgress: (progress: CascadeProgress) => void;
  setReport: (report: CascadeReport | null) => void;
  setControls: (updates: Partial<ControlsState>) => void;
  appendMessage: (msg: LiveMessage) => void;
  clearMessages: () => void;
  connectStream: () => void;
  disconnectStream: () => void;
};

const STORAGE_KEY = "supply-chainer:cascade-state";
const MAX_MESSAGES = 120;

const CascadeContext = createContext<CascadeState | null>(null);

function readStorage(): Partial<CascadeState> | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

function writeStorage(state: {
  progress: CascadeProgress;
  report: CascadeReport | null;
  messages: LiveMessage[];
  controls: ControlsState;
}) {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({
        progress: state.progress,
        report: state.report,
        messages: state.messages,
        controls: state.controls,
      }),
    );
  } catch {
    // ignore write errors
  }
}

export function CascadeProvider({ children }: { children: React.ReactNode }) {
  const [progress, setProgress] = useState<CascadeProgress>({ running: false, progress: 0 });
  const [report, setReport] = useState<CascadeReport | null>(null);
  const [messages, setMessages] = useState<LiveMessage[]>([]);
  const [connected, setConnected] = useState(false);
  const [controls, setControlsState] = useState<ControlsState>({
    productId: "",
    quantity: 1,
    budgetEur: 330000,
    desiredDeliveryDate: new Date(Date.now() + 21 * 24 * 60 * 60 * 1000)
      .toISOString()
      .slice(0, 10),
  });

  const esRef = useRef<EventSource | null>(null);

  const setControls = useCallback((updates: Partial<ControlsState>) => {
    setControlsState((prev) => ({ ...prev, ...updates }));
  }, []);

  const appendMessage = useCallback((msg: LiveMessage) => {
    setMessages((prev) => {
      const next = [...prev, msg];
      return next.length > MAX_MESSAGES ? next.slice(-MAX_MESSAGES) : next;
    });
  }, []);

  const clearMessages = useCallback(() => setMessages([]), []);

  const connectStream = useCallback(() => {
    if (esRef.current) {
      esRef.current.close();
    }
    const es = subscribeToStream(
      (msg) => {
        appendMessage(msg);
        setConnected(true);
      },
      () => setConnected(false),
    );
    es.onopen = () => setConnected(true);
    esRef.current = es;
  }, [appendMessage]);

  const disconnectStream = useCallback(() => {
    esRef.current?.close();
    esRef.current = null;
    setConnected(false);
  }, []);

  useEffect(() => {
    const stored = readStorage();
    if (stored?.progress) setProgress(stored.progress as CascadeProgress);
    if (stored?.report) setReport(stored.report as CascadeReport);
    if (stored?.messages) setMessages(stored.messages as LiveMessage[]);
    if (stored?.controls) setControlsState(stored.controls as ControlsState);
  }, []);

  useEffect(() => {
    writeStorage({ progress, report, messages, controls });
  }, [progress, report, messages, controls]);

  useEffect(() => {
    const onStorage = (event: StorageEvent) => {
      if (event.key !== STORAGE_KEY || !event.newValue) return;
      try {
        const next = JSON.parse(event.newValue);
        if (next.progress) setProgress(next.progress);
        if (next.report !== undefined) setReport(next.report);
        if (next.messages) setMessages(next.messages);
        if (next.controls) setControlsState(next.controls);
      } catch {
        // ignore parse errors
      }
    };
    window.addEventListener("storage", onStorage);
    return () => window.removeEventListener("storage", onStorage);
  }, []);

  useEffect(() => {
    if (progress.running && !connected) {
      connectStream();
    }
  }, [progress.running, connected, connectStream]);

  useEffect(() => {
    return () => esRef.current?.close();
  }, []);

  const value = useMemo(
    () => ({
      progress,
      report,
      messages,
      connected,
      controls,
      setProgress,
      setReport,
      setControls,
      appendMessage,
      clearMessages,
      connectStream,
      disconnectStream,
    }),
    [progress, report, messages, connected, controls, setProgress, setReport, setControls, appendMessage, clearMessages, connectStream, disconnectStream],
  );

  return <CascadeContext.Provider value={value}>{children}</CascadeContext.Provider>;
}

export function useCascadeStore(): CascadeState {
  const ctx = useContext(CascadeContext);
  if (!ctx) {
    throw new Error("useCascadeStore must be used within CascadeProvider");
  }
  return ctx;
}
