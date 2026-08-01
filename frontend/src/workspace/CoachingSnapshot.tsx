import type { NegotiatorMemory } from "../api/negotiations";
import { getCoachingSnapshot } from "./dashboardData";

interface CoachingSnapshotProps {
  memory: NegotiatorMemory | null;
  isLoading: boolean;
  error: string;
  onRefresh: () => void;
}

export function CoachingSnapshot({
  memory,
  isLoading,
  error,
  onRefresh,
}: CoachingSnapshotProps) {
  return (
    <section
      className="dashboard-section coaching-snapshot"
      aria-labelledby="coaching-snapshot-title"
    >
      <div className="dashboard-section-heading">
        <div>
          <h2 id="coaching-snapshot-title">Your Coaching Snapshot</h2>
          <p>A compact view of what to work on in your next practice session.</p>
        </div>
        <button className="text-button" type="button" onClick={onRefresh}>
          Refresh
        </button>
      </div>

      {isLoading ? (
        <p className="dashboard-empty" role="status">
          Loading your coaching snapshot...
        </p>
      ) : error ? (
        <p className="compact-error" role="alert">
          {error}
        </p>
      ) : memory ? (
        <SnapshotContent memory={memory} />
      ) : (
        <p className="dashboard-empty">
          Your coaching snapshot will appear after you complete more practice
          sessions.
        </p>
      )}
    </section>
  );
}

function SnapshotContent({ memory }: { memory: NegotiatorMemory }) {
  const snapshot = getCoachingSnapshot(memory);

  return (
    <div className="snapshot-content">
      <div className="snapshot-highlight progress-highlight">
        <span>Progress</span>
        <strong>{snapshot.progressSummary}</strong>
      </div>
      <div className="snapshot-highlight">
        <span>Highest Priority Skill</span>
        <strong>{snapshot.highestPrioritySkill}</strong>
      </div>
      <div className="snapshot-highlight drill-highlight">
        <span>Next Practice Drill</span>
        <strong>{snapshot.nextSessionDrill}</strong>
      </div>
      <div className="snapshot-list-grid">
        <SnapshotList title="Stable Strengths" items={snapshot.stableStrengths} />
        <SnapshotList title="Skills to Improve" items={snapshot.stableWeaknesses} />
        {snapshot.improvingSkills.length > 0 ? (
          <SnapshotList title="Improving Skills" items={snapshot.improvingSkills} />
        ) : null}
        {snapshot.persistentRisks.length > 0 ? (
          <SnapshotList title="Persistent Risks" items={snapshot.persistentRisks} />
        ) : null}
      </div>
    </div>
  );
}

function SnapshotList({ title, items }: { title: string; items: string[] }) {
  return (
    <section className="snapshot-list">
      <h3>{title}</h3>
      {items.length > 0 ? (
        <ul className="compact-list">
          {items.map((item, index) => (
            <li key={`${index}-${item}`}>{item}</li>
          ))}
        </ul>
      ) : (
        <p className="muted-copy">None identified yet.</p>
      )}
    </section>
  );
}
