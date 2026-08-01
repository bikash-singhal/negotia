import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { toErrorMessage } from "../api/client";
import { getLatestMemory } from "../api/memory";
import {
  completeNegotiation,
  createNegotiation,
  getNegotiation,
  listNegotiations,
  streamOpponentResponse,
  type NegotiationCompletion,
  type NegotiationSession,
  type NegotiatorMemory,
  type OpponentResponseStreamEvent,
} from "../api/negotiations";
import {
  createScenario,
  getScenario,
  listScenarios,
  type Scenario,
  type ScenarioCreateRequest,
} from "../api/scenarios";
import { createTurn, listTurns, type NegotiationTurn } from "../api/turns";
import { CompletionResult } from "./CompletionResult";
import { Dashboard } from "./Dashboard";
import {
  getContinueNegotiations,
  getRecentCompletedNegotiations,
} from "./dashboardData";
import { NegotiationChat } from "./NegotiationChat";
import { ScenarioDetail } from "./ScenarioDetail";
import { ScenarioForm } from "./ScenarioForm";

interface WorkspaceProps {
  username: string;
  token: string;
  onLogout: () => void;
}

type WorkspaceView =
  | "dashboard"
  | "scenario-form"
  | "scenario-detail"
  | "negotiation-chat"
  | "results";

export function Workspace({ username, token, onLogout }: WorkspaceProps) {
  const [view, setView] = useState<WorkspaceView>("dashboard");
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [negotiations, setNegotiations] = useState<NegotiationSession[]>([]);
  const [selectedScenario, setSelectedScenario] = useState<Scenario | null>(null);
  const [activeSession, setActiveSession] =
    useState<NegotiationSession | null>(null);
  const [turns, setTurns] = useState<NegotiationTurn[]>([]);
  const [streamingOpponentText, setStreamingOpponentText] = useState<
    string | null
  >(null);
  const [completion, setCompletion] =
    useState<NegotiationCompletion | null>(null);
  const [latestMemory, setLatestMemory] =
    useState<NegotiatorMemory | null>(null);
  const [completionCache, setCompletionCache] = useState<
    Record<string, NegotiationCompletion>
  >({});
  const [takeawayLoadingIds, setTakeawayLoadingIds] = useState<Set<string>>(
    new Set(),
  );
  const [takeawayErrors, setTakeawayErrors] = useState<Record<string, string>>(
    {},
  );

  const [isLoadingScenarios, setIsLoadingScenarios] = useState(true);
  const [isLoadingNegotiations, setIsLoadingNegotiations] = useState(true);
  const [isLoadingMemory, setIsLoadingMemory] = useState(true);
  const [isLoadingTurns, setIsLoadingTurns] = useState(false);
  const [isCreatingScenario, setIsCreatingScenario] = useState(false);
  const [isStarting, setIsStarting] = useState(false);
  const [isSending, setIsSending] = useState(false);
  const [isOpponentThinking, setIsOpponentThinking] = useState(false);
  const [isCompleting, setIsCompleting] = useState(false);
  const [openingSessionId, setOpeningSessionId] = useState<string | null>(null);

  const [scenarioError, setScenarioError] = useState("");
  const [negotiationListError, setNegotiationListError] = useState("");
  const [memoryError, setMemoryError] = useState("");
  const [scenarioFormError, setScenarioFormError] = useState("");
  const [dashboardActionError, setDashboardActionError] = useState("");
  const [actionError, setActionError] = useState("");
  const opponentStreamControllerRef = useRef<AbortController | null>(null);

  const abortOpponentStream = useCallback(() => {
    opponentStreamControllerRef.current?.abort();
    opponentStreamControllerRef.current = null;
    setStreamingOpponentText(null);
    setIsOpponentThinking(false);
  }, []);

  const loadScenarios = useCallback(async () => {
    setIsLoadingScenarios(true);
    setScenarioError("");
    try {
      setScenarios(await listScenarios(token));
    } catch (error) {
      setScenarioError(toErrorMessage(error));
    } finally {
      setIsLoadingScenarios(false);
    }
  }, [token]);

  const loadNegotiationList = useCallback(async () => {
    setIsLoadingNegotiations(true);
    setNegotiationListError("");
    try {
      setNegotiations(await listNegotiations(token));
    } catch (error) {
      setNegotiationListError(toErrorMessage(error));
    } finally {
      setIsLoadingNegotiations(false);
    }
  }, [token]);

  const loadLatestMemory = useCallback(async () => {
    setIsLoadingMemory(true);
    setMemoryError("");
    try {
      setLatestMemory(await getLatestMemory(token));
    } catch (error) {
      setMemoryError(toErrorMessage(error));
    } finally {
      setIsLoadingMemory(false);
    }
  }, [token]);

  useEffect(() => {
    void loadScenarios();
    void loadNegotiationList();
    void loadLatestMemory();
  }, [loadLatestMemory, loadNegotiationList, loadScenarios]);

  useEffect(
    () => () => {
      opponentStreamControllerRef.current?.abort();
      opponentStreamControllerRef.current = null;
    },
    [],
  );

  const continueNegotiations = useMemo(
    () => getContinueNegotiations(negotiations),
    [negotiations],
  );
  const recentNegotiations = useMemo(
    () => getRecentCompletedNegotiations(negotiations),
    [negotiations],
  );

  useEffect(() => {
    if (view !== "dashboard") {
      return;
    }

    const missingResults = recentNegotiations.filter(
      (session) =>
        !completionCache[session.id] && !takeawayErrors[session.id],
    );
    if (missingResults.length === 0) {
      return;
    }

    let cancelled = false;
    setTakeawayLoadingIds(new Set(missingResults.map((session) => session.id)));
    void Promise.allSettled(
      missingResults.map(async (session) => ({
        sessionId: session.id,
        completion: await completeNegotiation(token, session.id),
      })),
    ).then((results) => {
      if (cancelled) {
        return;
      }

      const loaded: Record<string, NegotiationCompletion> = {};
      const errors: Record<string, string> = {};
      results.forEach((result, index) => {
        if (result.status === "fulfilled") {
          loaded[result.value.sessionId] = result.value.completion;
        } else {
          errors[missingResults[index].id] = toErrorMessage(result.reason);
        }
      });
      setCompletionCache((current) => ({ ...current, ...loaded }));
      setTakeawayErrors((current) => ({ ...current, ...errors }));
      setTakeawayLoadingIds(new Set());
    });

    return () => {
      cancelled = true;
    };
  }, [completionCache, recentNegotiations, takeawayErrors, token, view]);

  function handleNewScenario() {
    abortOpponentStream();
    setSelectedScenario(null);
    setActiveSession(null);
    setTurns([]);
    setCompletion(null);
    setScenarioFormError("");
    setActionError("");
    setDashboardActionError("");
    setView("scenario-form");
  }

  async function handleSelectScenario(scenario: Scenario) {
    abortOpponentStream();
    setSelectedScenario(scenario);
    setActiveSession(null);
    setTurns([]);
    setCompletion(null);
    setActionError("");
    setDashboardActionError("");
    setView("scenario-detail");

    try {
      setSelectedScenario(await getScenario(token, scenario.scenario_id));
    } catch (error) {
      setActionError(toErrorMessage(error));
    }
  }

  async function handleCreateScenario(
    request: ScenarioCreateRequest,
  ): Promise<boolean> {
    setIsCreatingScenario(true);
    setScenarioFormError("");
    try {
      const created = await createScenario(token, request);
      setScenarios((current) => [created, ...current]);
      setSelectedScenario(created);
      setView("scenario-detail");
      return true;
    } catch (error) {
      setScenarioFormError(toErrorMessage(error));
      return false;
    } finally {
      setIsCreatingScenario(false);
    }
  }

  async function handleStartNegotiation() {
    if (!selectedScenario) {
      return;
    }

    setIsStarting(true);
    setActionError("");
    try {
      const session = await createNegotiation(
        token,
        selectedScenario.scenario_id,
      );
      const persistedTurns = await listTurns(token, session.id);
      setActiveSession(session);
      setTurns(sortTurns(persistedTurns));
      setCompletion(null);
      setView("negotiation-chat");
      await loadNegotiationList();
    } catch (error) {
      setActionError(toErrorMessage(error));
    } finally {
      setIsStarting(false);
    }
  }

  async function handleContinueNegotiation(session: NegotiationSession) {
    abortOpponentStream();
    setOpeningSessionId(session.id);
    setDashboardActionError("");
    setActionError("");
    setCompletion(null);
    setIsLoadingTurns(true);
    try {
      const [persistedSession, persistedTurns, scenario] = await Promise.all([
        getNegotiation(token, session.id),
        listTurns(token, session.id),
        getScenario(token, session.scenario_id),
      ]);
      setActiveSession(persistedSession);
      setTurns(sortTurns(persistedTurns));
      setSelectedScenario(scenario);
      setView("negotiation-chat");
    } catch (error) {
      setDashboardActionError(toErrorMessage(error));
    } finally {
      setIsLoadingTurns(false);
      setOpeningSessionId(null);
    }
  }

  async function handleViewResults(session: NegotiationSession) {
    abortOpponentStream();
    setOpeningSessionId(session.id);
    setDashboardActionError("");
    setActionError("");
    setIsCompleting(true);
    try {
      const [persistedSession, scenario, result] = await Promise.all([
        getNegotiation(token, session.id),
        getScenario(token, session.scenario_id),
        completionCache[session.id] ?? completeNegotiation(token, session.id),
      ]);
      setActiveSession(persistedSession);
      setSelectedScenario(scenario);
      setCompletion(result);
      setCompletionCache((current) => ({ ...current, [session.id]: result }));
      if (result.memory) {
        setLatestMemory(result.memory);
      }
      setView("results");
    } catch (error) {
      setDashboardActionError(toErrorMessage(error));
    } finally {
      setIsCompleting(false);
      setOpeningSessionId(null);
    }
  }

  async function handleSend(content: string): Promise<boolean> {
    if (!activeSession) {
      return false;
    }

    setIsSending(true);
    setActionError("");
    let userTurnPersisted = false;
    try {
      const userTurn = await createTurn(token, {
        session_id: activeSession.id,
        speaker: "user",
        content,
      });
      userTurnPersisted = true;
      setTurns((current) => sortTurns([...current, userTurn]));

      setIsOpponentThinking(true);
      await receiveOpponentStream(activeSession.id);
      await refreshActiveConversation(activeSession.id);
    } catch (error) {
      if (isAbortError(error)) {
        return userTurnPersisted;
      }
      setActionError(toErrorMessage(error));
      if (userTurnPersisted) {
        await reloadTurnsSafely(activeSession.id);
      }
    } finally {
      setIsOpponentThinking(false);
      setIsSending(false);
    }
    return userTurnPersisted;
  }

  async function handleRetryOpponent() {
    if (!activeSession) {
      return;
    }

    setIsSending(true);
    setIsOpponentThinking(true);
    setActionError("");
    try {
      await receiveOpponentStream(activeSession.id);
      await refreshActiveConversation(activeSession.id);
    } catch (error) {
      if (isAbortError(error)) {
        return;
      }
      setActionError(toErrorMessage(error));
      await reloadTurnsSafely(activeSession.id);
    } finally {
      setIsOpponentThinking(false);
      setIsSending(false);
    }
  }

  async function handleComplete() {
    if (!activeSession) {
      return;
    }

    setIsCompleting(true);
    setActionError("");
    try {
      const result = await completeNegotiation(token, activeSession.id);
      setCompletion(result);
      setCompletionCache((current) => ({
        ...current,
        [activeSession.id]: result,
      }));
      if (result.memory) {
        setLatestMemory(result.memory);
      }
      setActiveSession((current) =>
        current
          ? {
              ...current,
              status: result.status,
              updated_at: result.completed_at,
            }
          : current,
      );
      setView("results");
      await loadNegotiationList();
    } catch (error) {
      setActionError(toErrorMessage(error));
    } finally {
      setIsCompleting(false);
    }
  }

  async function refreshActiveConversation(sessionId: string) {
    const [persistedSession, persistedTurns] = await Promise.all([
      getNegotiation(token, sessionId),
      listTurns(token, sessionId),
    ]);
    setActiveSession(persistedSession);
    setTurns(sortTurns(persistedTurns));
    await loadNegotiationList();
  }

  async function reloadTurnsSafely(sessionId: string) {
    try {
      setTurns(sortTurns(await listTurns(token, sessionId)));
    } catch {
      // Keep already-rendered persisted turns when the recovery read also fails.
    }
  }

  async function receiveOpponentStream(sessionId: string) {
    abortOpponentStream();
    const controller = new AbortController();
    opponentStreamControllerRef.current = controller;
    setStreamingOpponentText("");
    setIsOpponentThinking(true);

    try {
      await streamOpponentResponse(
        token,
        sessionId,
        handleOpponentStreamEvent,
        controller.signal,
      );
    } finally {
      if (opponentStreamControllerRef.current === controller) {
        opponentStreamControllerRef.current = null;
        setStreamingOpponentText(null);
      }
    }
  }

  function handleOpponentStreamEvent(event: OpponentResponseStreamEvent) {
    if (event.type === "started") {
      setStreamingOpponentText("");
    } else if (event.type === "delta") {
      setStreamingOpponentText((current) => (current ?? "") + event.text);
    } else if (event.type === "completed") {
      setTurns((current) => sortTurns([...current, event.turn]));
      setStreamingOpponentText(null);
      setIsOpponentThinking(false);
    }
  }

  function handleBackToDashboard() {
    abortOpponentStream();
    setView("dashboard");
    setSelectedScenario(null);
    setActiveSession(null);
    setTurns([]);
    setCompletion(null);
    setScenarioFormError("");
    setActionError("");
    setDashboardActionError("");
    void loadNegotiationList();
    void loadLatestMemory();
  }

  function handleLogout() {
    abortOpponentStream();
    onLogout();
  }

  const scenarioTitle = selectedScenario?.title ?? "Negotiation";
  const opponentRole = selectedScenario?.opponent_role;

  return (
    <main className="workspace-shell">
      <header className="workspace-header">
        <button
          className="brand-button"
          type="button"
          aria-label="Go to dashboard"
          onClick={handleBackToDashboard}
        >
          <span className="eyebrow">Negotiation practice</span>
          <strong>Negotia</strong>
        </button>
        <div className="account-actions">
          <span>
            Signed in as <strong>{username}</strong>
          </span>
          <button className="secondary-button" type="button" onClick={handleLogout}>
            Log out
          </button>
        </div>
      </header>

      <div className="workspace-layout">
        <div className="workspace-content">
          {view === "dashboard" ? (
            <Dashboard
              username={username}
              scenarios={scenarios}
              continueNegotiations={continueNegotiations}
              recentNegotiations={recentNegotiations}
              latestMemory={latestMemory}
              completionCache={completionCache}
              takeawayLoadingIds={takeawayLoadingIds}
              takeawayErrors={takeawayErrors}
              isLoadingScenarios={isLoadingScenarios}
              isLoadingNegotiations={isLoadingNegotiations}
              isLoadingMemory={isLoadingMemory}
              openingSessionId={openingSessionId}
              scenarioError={scenarioError}
              negotiationError={negotiationListError}
              memoryError={memoryError}
              actionError={dashboardActionError}
              onNewScenario={handleNewScenario}
              onSelectScenario={(scenario) => void handleSelectScenario(scenario)}
              onContinueNegotiation={(session) =>
                void handleContinueNegotiation(session)
              }
              onViewResults={(session) => void handleViewResults(session)}
              onRefreshScenarios={() => void loadScenarios()}
              onRefreshNegotiations={() => void loadNegotiationList()}
              onRefreshMemory={() => void loadLatestMemory()}
            />
          ) : null}

          {view === "scenario-form" ? (
            <ScenarioForm
              isSubmitting={isCreatingScenario}
              error={scenarioFormError}
              onSubmit={handleCreateScenario}
              onCancel={handleBackToDashboard}
            />
          ) : null}

          {view === "scenario-detail" && selectedScenario ? (
            <ScenarioDetail
              scenario={selectedScenario}
              isStarting={isStarting}
              error={actionError}
              onStart={() => void handleStartNegotiation()}
              onBack={handleBackToDashboard}
            />
          ) : null}

          {view === "negotiation-chat" && activeSession ? (
            <NegotiationChat
              session={activeSession}
              scenarioTitle={scenarioTitle}
              opponentRole={opponentRole}
              turns={turns}
              streamingOpponentText={streamingOpponentText}
              isLoadingTurns={isLoadingTurns}
              isSending={isSending}
              isOpponentThinking={isOpponentThinking}
              isCompleting={isCompleting}
              error={actionError}
              onSend={handleSend}
              onRetryOpponent={handleRetryOpponent}
              onComplete={handleComplete}
              onBack={handleBackToDashboard}
            />
          ) : null}

          {view === "results" && completion ? (
            <CompletionResult
              result={completion}
              scenarioTitle={scenarioTitle}
              onBack={handleBackToDashboard}
            />
          ) : null}
        </div>
      </div>
    </main>
  );
}

function sortTurns(turns: NegotiationTurn[]): NegotiationTurn[] {
  return [...turns].sort(
    (left, right) => left.turn_number - right.turn_number,
  );
}

function isAbortError(error: unknown): boolean {
  return error instanceof DOMException && error.name === "AbortError";
}
