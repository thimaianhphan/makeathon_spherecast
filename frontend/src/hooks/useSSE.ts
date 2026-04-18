import { useCascadeStore } from "@/state/cascadeStore";

export function useSSE() {
  const {
    messages,
    connected,
    connectStream,
    disconnectStream,
    clearMessages,
  } = useCascadeStore();

  return {
    messages,
    connected,
    connect: connectStream,
    disconnect: disconnectStream,
    clear: clearMessages,
  };
}
