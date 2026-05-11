import { createContext, useCallback, useContext, useMemo, useState } from "react";
import type { ReactNode } from "react";

export interface TranscriptEntry {
  question: string;
  text: string;
  table?: { headers: string[]; rows: string[][] } | null;
  summary?: string | null;
}

interface FlowState {
  selectedRings: string[];
  selectedRiskAccounts: string[];
  selectedCentralAccounts: string[];
  toggleRing: (ringId: string) => void;
  toggleRiskAccount: (accountId: string) => void;
  toggleCentralAccount: (accountId: string) => void;
  clearRings: () => void;
  clearSelections: () => void;
  selectedSignalIds: string[];
  conversationId: string | null;
  setConversationId: (id: string | null) => void;
  transcript: TranscriptEntry[];
  appendTranscript: (entry: TranscriptEntry) => void;
  resetTranscript: () => void;
}

const FlowContext = createContext<FlowState | null>(null);

export function FlowProvider({ children }: { children: ReactNode }) {
  const [selectedRings, setSelectedRings] = useState<string[]>([]);
  const [selectedRiskAccounts, setSelectedRiskAccounts] = useState<string[]>([]);
  const [selectedCentralAccounts, setSelectedCentralAccounts] = useState<string[]>([]);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [transcript, setTranscript] = useState<TranscriptEntry[]>([]);

  const toggleRing = useCallback((ringId: string) => {
    setSelectedRings((curr) =>
      curr.includes(ringId) ? curr.filter((r) => r !== ringId) : [...curr, ringId],
    );
  }, []);

  const toggleRiskAccount = useCallback((accountId: string) => {
    setSelectedRiskAccounts((curr) =>
      curr.includes(accountId)
        ? curr.filter((id) => id !== accountId)
        : [...curr, accountId],
    );
  }, []);

  const toggleCentralAccount = useCallback((accountId: string) => {
    setSelectedCentralAccounts((curr) =>
      curr.includes(accountId)
        ? curr.filter((id) => id !== accountId)
        : [...curr, accountId],
    );
  }, []);

  const clearRings = useCallback(() => setSelectedRings([]), []);

  const clearSelections = useCallback(() => {
    setSelectedRings([]);
    setSelectedRiskAccounts([]);
    setSelectedCentralAccounts([]);
  }, []);

  const appendTranscript = useCallback((entry: TranscriptEntry) => {
    setTranscript((curr) => [...curr, entry]);
  }, []);

  const resetTranscript = useCallback(() => setTranscript([]), []);

  const selectedSignalIds = useMemo(
    () => [
      ...selectedRings,
      ...selectedRiskAccounts,
      ...selectedCentralAccounts,
    ],
    [selectedRings, selectedRiskAccounts, selectedCentralAccounts],
  );

  const value = useMemo<FlowState>(
    () => ({
      selectedRings,
      selectedRiskAccounts,
      selectedCentralAccounts,
      toggleRing,
      toggleRiskAccount,
      toggleCentralAccount,
      clearRings,
      clearSelections,
      selectedSignalIds,
      conversationId,
      setConversationId,
      transcript,
      appendTranscript,
      resetTranscript,
    }),
    [
      selectedRings,
      selectedRiskAccounts,
      selectedCentralAccounts,
      selectedSignalIds,
      conversationId,
      transcript,
      toggleRing,
      toggleRiskAccount,
      toggleCentralAccount,
      clearRings,
      clearSelections,
      appendTranscript,
      resetTranscript,
    ],
  );

  return <FlowContext.Provider value={value}>{children}</FlowContext.Provider>;
}

export function useFlow(): FlowState {
  const ctx = useContext(FlowContext);
  if (!ctx) {
    throw new Error("useFlow must be used inside <FlowProvider>");
  }
  return ctx;
}
