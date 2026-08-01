import type {
  NegotiationCompletion,
  NegotiationTactic,
} from "../api/negotiations";
import { getBiggestTakeaway } from "./dashboardData";

interface CompletionResultProps {
  result: NegotiationCompletion;
  scenarioTitle: string;
  onBack: () => void;
}

export function CompletionResult({
  result,
  scenarioTitle,
  onBack,
}: CompletionResultProps) {
  const { debrief, strategy, memory } = result;

  return (
    <section className="completion-result" aria-labelledby="results-title">
      <header className="results-header">
        <div>
          <button className="back-button" type="button" onClick={onBack}>
            ← Back to Dashboard
          </button>
          <p className="eyebrow">Negotiation completed</p>
          <h2 id="results-title">{scenarioTitle}: Your results</h2>
        </div>
        <span className="status-chip completed">Completed</span>
      </header>

      <article className="takeaway-card">
        <p className="eyebrow">Biggest takeaway</p>
        <p>{getBiggestTakeaway(result)}</p>
      </article>

      <article className="result-card">
        <h3>Debrief</h3>
        <p className="assessment-copy">{debrief.overall_assessment}</p>
        <div className="result-grid">
          <ResultList title="Strengths you repeated" items={debrief.repeated_strengths} />
          <ResultList
            title="Patterns to improve"
            items={debrief.repeated_weaknesses}
          />
          <ResultList
            title="Missed opportunities"
            items={debrief.key_missed_opportunities}
          />
          <ResultList title="Risks to watch" items={debrief.recurring_risks} />
        </div>
      </article>

      <article className="result-card">
        <h3>Strategy</h3>
        <dl className="summary-list">
          <div>
            <dt>Primary objective</dt>
            <dd>{strategy.primary_objective}</dd>
          </div>
          <div>
            <dt>Expected outcome</dt>
            <dd>{strategy.expected_outcome}</dd>
          </div>
        </dl>

        <div className="tactic-list">
          {strategy.prioritized_tactics.map((tactic) => (
            <TacticCard key={`${tactic.priority}-${tactic.title}`} tactic={tactic} />
          ))}
        </div>

        <div className="result-grid">
          <ResultList title="Skills to build" items={strategy.long_term_skills} />
          <ResultList
            title="Preparation checklist"
            items={strategy.preparation_checklist}
          />
          <ResultList title="Avoid next time" items={strategy.avoid_next_time} />
        </div>
      </article>

      <article className="result-card">
        <h3>Negotiation Profile</h3>
        {memory ? (
          <>
            <dl className="summary-list">
              <div>
                <dt>Progress</dt>
                <dd>{memory.progress_summary}</dd>
              </div>
              <div>
                <dt>Highest priority skill</dt>
                <dd>{memory.highest_priority_skill}</dd>
              </div>
              <div>
                <dt>Next practice drill</dt>
                <dd>{memory.next_session_drill}</dd>
              </div>
            </dl>
            <div className="result-grid">
              <ResultList
                title="Stable strengths"
                items={memory.stable_strengths}
              />
              <ResultList
                title="Stable weaknesses"
                items={memory.stable_weaknesses}
              />
              <ResultList
                title="Improving skills"
                items={memory.improving_skills}
              />
              <ResultList
                title="Persistent risks"
                items={memory.persistent_risks}
              />
            </div>
          </>
        ) : (
          <p className="memory-empty">
            Complete more negotiations to unlock cross-session coaching guidance.
          </p>
        )}
      </article>
    </section>
  );
}

function TacticCard({ tactic }: { tactic: NegotiationTactic }) {
  return (
    <section className="tactic-card">
      <div className="tactic-heading">
        <span className="priority-badge" aria-label={`Priority ${tactic.priority}`}>
          {tactic.priority}
        </span>
        <h4>{tactic.title}</h4>
      </div>
      <p>{tactic.rationale}</p>
      <ResultList title="Actions" items={tactic.actions} />
      <ResultList title="Try saying" items={tactic.example_language} />
      <p>
        <strong>Success looks like:</strong> {tactic.success_indicator}
      </p>
    </section>
  );
}

function ResultList({ title, items }: { title: string; items: string[] }) {
  return (
    <section className="result-list-section">
      <h4>{title}</h4>
      {items.length > 0 ? (
        <ul className="compact-list">
          {items.map((item, index) => (
            <li key={`${index}-${item}`}>{item}</li>
          ))}
        </ul>
      ) : (
        <p className="muted-copy">None identified.</p>
      )}
    </section>
  );
}
