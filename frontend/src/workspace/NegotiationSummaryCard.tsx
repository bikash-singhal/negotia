import type { NegotiationSession } from "../api/negotiations";

interface NegotiationSummaryCardProps {
  negotiation: NegotiationSession;
  scenarioTitle: string;
  actionLabel: string;
  takeaway?: string | null;
  isTakeawayLoading?: boolean;
  takeawayError?: string;
  isOpening: boolean;
  onOpen: () => void;
}

export function NegotiationSummaryCard({
  negotiation,
  scenarioTitle,
  actionLabel,
  takeaway,
  isTakeawayLoading = false,
  takeawayError = "",
  isOpening,
  onOpen,
}: NegotiationSummaryCardProps) {
  return (
    <article className="negotiation-summary-card">
      <div className="summary-card-content">
        <div className="summary-card-heading">
          <h3>{scenarioTitle}</h3>
          <span
            className={`status-chip ${
              negotiation.status === "completed" ? "completed" : ""
            }`}
          >
            {negotiation.status}
          </span>
        </div>
        <p>Updated {formatDate(negotiation.updated_at)}</p>
        {negotiation.status === "completed" ? (
          <div className="negotiation-takeaway">
            <strong>Biggest takeaway</strong>
            {isTakeawayLoading ? (
              <p role="status">Loading review...</p>
            ) : takeawayError ? (
              <p className="compact-error" role="alert">
                {takeawayError}
              </p>
            ) : (
              <p>{takeaway ?? "Review this negotiation for your coaching insight."}</p>
            )}
          </div>
        ) : null}
      </div>
      <button
        className="secondary-button"
        type="button"
        disabled={isOpening || isTakeawayLoading}
        onClick={onOpen}
      >
        {isOpening ? "Opening..." : actionLabel}
      </button>
    </article>
  );
}

function formatDate(value: string): string {
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
  }).format(new Date(value));
}
