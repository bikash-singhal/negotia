import type { Scenario } from "../api/scenarios";

interface ScenarioListProps {
  scenarios: Scenario[];
  selectedScenarioId: string | null;
  isLoading: boolean;
  error: string;
  onSelect: (scenario: Scenario) => void;
  onCreate: () => void;
  onRefresh: () => void;
}

export function ScenarioList({
  scenarios,
  selectedScenarioId,
  isLoading,
  error,
  onSelect,
  onCreate,
  onRefresh,
}: ScenarioListProps) {
  return (
    <section className="sidebar-section" aria-labelledby="scenarios-title">
      <div className="section-heading-row">
        <h2 id="scenarios-title">Scenarios</h2>
        <button className="text-button" type="button" onClick={onCreate}>
          + New
        </button>
      </div>

      {isLoading ? (
        <p className="muted-copy" role="status">
          Loading scenarios...
        </p>
      ) : null}

      {error ? (
        <div className="compact-error" role="alert">
          <span>{error}</span>
          <button className="text-button" type="button" onClick={onRefresh}>
            Retry
          </button>
        </div>
      ) : null}

      {!isLoading && !error && scenarios.length === 0 ? (
        <div className="empty-sidebar-state">
          <p>No scenarios yet.</p>
          <button className="text-button" type="button" onClick={onCreate}>
            Create your first scenario
          </button>
        </div>
      ) : null}

      <div className="sidebar-list">
        {scenarios.map((scenario) => (
          <button
            className={
              selectedScenarioId === scenario.scenario_id
                ? "sidebar-list-item selected"
                : "sidebar-list-item"
            }
            type="button"
            key={scenario.scenario_id}
            onClick={() => onSelect(scenario)}
          >
            <strong>{scenario.title}</strong>
            <span>{scenario.industry}</span>
            <span>
              {scenario.difficulty} · {scenario.opponent_role}
            </span>
          </button>
        ))}
      </div>
    </section>
  );
}
