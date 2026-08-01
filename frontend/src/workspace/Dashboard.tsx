import type {
  NegotiationCompletion,
  NegotiationSession,
  NegotiatorMemory,
} from "../api/negotiations";
import type { Scenario } from "../api/scenarios";
import { CoachingSnapshot } from "./CoachingSnapshot";
import { getBiggestTakeaway } from "./dashboardData";
import { NegotiationSummaryCard } from "./NegotiationSummaryCard";

interface DashboardProps {
  username: string;
  scenarios: Scenario[];
  continueNegotiations: NegotiationSession[];
  recentNegotiations: NegotiationSession[];
  latestMemory: NegotiatorMemory | null;
  completionCache: Record<string, NegotiationCompletion>;
  takeawayLoadingIds: ReadonlySet<string>;
  takeawayErrors: Record<string, string>;
  isLoadingScenarios: boolean;
  isLoadingNegotiations: boolean;
  isLoadingMemory: boolean;
  openingSessionId: string | null;
  scenarioError: string;
  negotiationError: string;
  memoryError: string;
  actionError: string;
  onNewScenario: () => void;
  onSelectScenario: (scenario: Scenario) => void;
  onContinueNegotiation: (session: NegotiationSession) => void;
  onViewResults: (session: NegotiationSession) => void;
  onRefreshScenarios: () => void;
  onRefreshNegotiations: () => void;
  onRefreshMemory: () => void;
}

export function Dashboard({
  username,
  scenarios,
  continueNegotiations,
  recentNegotiations,
  latestMemory,
  completionCache,
  takeawayLoadingIds,
  takeawayErrors,
  isLoadingScenarios,
  isLoadingNegotiations,
  isLoadingMemory,
  openingSessionId,
  scenarioError,
  negotiationError,
  memoryError,
  actionError,
  onNewScenario,
  onSelectScenario,
  onContinueNegotiation,
  onViewResults,
  onRefreshScenarios,
  onRefreshNegotiations,
  onRefreshMemory,
}: DashboardProps) {
  const scenarioTitles = new Map(
    scenarios.map((scenario) => [scenario.scenario_id, scenario.title]),
  );

  return (
    <div className="dashboard">
      <section className="dashboard-hero">
        <div>
          <p className="eyebrow">Your practice dashboard</p>
          <h2>Welcome back, {username}</h2>
          <p>Continue building confidence one focused negotiation at a time.</p>
        </div>
        <button className="primary-button" type="button" onClick={onNewScenario}>
          New Practice Scenario
        </button>
      </section>

      {actionError ? (
        <p className="form-message error-message dashboard-action-error" role="alert">
          {actionError}
        </p>
      ) : null}

      <div className="dashboard-primary-grid">
        <DashboardSection
          title="Continue Practice"
          description="Resume your most recently active negotiations."
          isLoading={isLoadingNegotiations}
          error={negotiationError}
          emptyMessage="No active negotiations."
          isEmpty={continueNegotiations.length === 0}
          onRefresh={onRefreshNegotiations}
        >
          <div className="negotiation-card-list">
            {continueNegotiations.map((session) => (
              <NegotiationSummaryCard
                key={session.id}
                negotiation={session}
                scenarioTitle={scenarioTitles.get(session.scenario_id) ?? "Practice scenario"}
                actionLabel="Continue"
                isOpening={openingSessionId === session.id}
                onOpen={() => onContinueNegotiation(session)}
              />
            ))}
          </div>
        </DashboardSection>

        <CoachingSnapshot
          memory={latestMemory}
          isLoading={isLoadingMemory}
          error={memoryError}
          onRefresh={onRefreshMemory}
        />
      </div>

      <DashboardSection
        title="Recent Negotiations"
        description="Review results from your latest completed practice sessions."
        isLoading={isLoadingNegotiations}
        error={negotiationError}
        emptyMessage="Complete your first negotiation to see it here."
        isEmpty={recentNegotiations.length === 0}
        onRefresh={onRefreshNegotiations}
      >
        <div className="negotiation-card-list completed-list">
          {recentNegotiations.map((session) => (
            <NegotiationSummaryCard
              key={session.id}
              negotiation={session}
              scenarioTitle={scenarioTitles.get(session.scenario_id) ?? "Practice scenario"}
              actionLabel="View Full Review"
              takeaway={
                completionCache[session.id]
                  ? getBiggestTakeaway(completionCache[session.id])
                  : null
              }
              isTakeawayLoading={takeawayLoadingIds.has(session.id)}
              takeawayError={takeawayErrors[session.id] ?? ""}
              isOpening={openingSessionId === session.id}
              onOpen={() => onViewResults(session)}
            />
          ))}
        </div>
      </DashboardSection>

      <DashboardSection
        title="Practice Scenarios"
        description="Choose a saved scenario or create a new one."
        isLoading={isLoadingScenarios}
        error={scenarioError}
        emptyMessage="No scenarios yet. Create your first practice scenario."
        isEmpty={scenarios.length === 0}
        onRefresh={onRefreshScenarios}
      >
        <div className="scenario-card-grid">
          {scenarios.map((scenario) => (
            <button
              className="scenario-summary-card"
              type="button"
              key={scenario.scenario_id}
              onClick={() => onSelectScenario(scenario)}
            >
              <span className="status-chip">{scenario.difficulty}</span>
              <strong>{scenario.title}</strong>
              <span>{scenario.opponent_role}</span>
            </button>
          ))}
        </div>
      </DashboardSection>
    </div>
  );
}

interface DashboardSectionProps {
  title: string;
  description: string;
  isLoading: boolean;
  error: string;
  emptyMessage: string;
  isEmpty: boolean;
  onRefresh: () => void;
  children: React.ReactNode;
}

function DashboardSection({
  title,
  description,
  isLoading,
  error,
  emptyMessage,
  isEmpty,
  onRefresh,
  children,
}: DashboardSectionProps) {
  const headingId = `dashboard-${title.toLowerCase().replaceAll(" ", "-")}`;

  return (
    <section className="dashboard-section" aria-labelledby={headingId}>
      <div className="dashboard-section-heading">
        <div>
          <h2 id={headingId}>{title}</h2>
          <p>{description}</p>
        </div>
        <button className="text-button" type="button" onClick={onRefresh}>
          Refresh
        </button>
      </div>
      {isLoading ? (
        <p className="dashboard-empty" role="status">
          Loading...
        </p>
      ) : error ? (
        <p className="compact-error" role="alert">
          {error}
        </p>
      ) : isEmpty ? (
        <p className="dashboard-empty">{emptyMessage}</p>
      ) : (
        children
      )}
    </section>
  );
}
