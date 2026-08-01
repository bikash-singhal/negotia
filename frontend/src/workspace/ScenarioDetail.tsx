import type { Scenario } from "../api/scenarios";

interface ScenarioDetailProps {
  scenario: Scenario;
  isStarting: boolean;
  error: string;
  onStart: () => void;
  onBack: () => void;
}

export function ScenarioDetail({
  scenario,
  isStarting,
  error,
  onStart,
  onBack,
}: ScenarioDetailProps) {
  return (
    <section className="content-panel scenario-detail">
      <button className="back-button" type="button" onClick={onBack}>
        ← Back to Dashboard
      </button>
      <div className="panel-heading">
        <div>
          <p className="eyebrow">Practice scenario</p>
          <h2>{scenario.title}</h2>
        </div>
        <span className="status-chip">{scenario.difficulty}</span>
      </div>

      <p className="lead-copy">{scenario.description}</p>

      <p className="opponent-summary">
        <span>Opponent role</span>
        <strong>{scenario.opponent_role}</strong>
      </p>

      {error ? (
        <p className="form-message error-message" role="alert">
          {error}
        </p>
      ) : null}

      <button
        className="primary-button"
        type="button"
        onClick={onStart}
        disabled={isStarting}
      >
        {isStarting ? "Starting..." : "Start Negotiation"}
      </button>
    </section>
  );
}
