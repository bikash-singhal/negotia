import {
  useEffect,
  useRef,
  useState,
  type FormEvent,
  type KeyboardEvent,
  type UIEvent,
} from "react";

import type { NegotiationSession } from "../api/negotiations";
import type { NegotiationTurn } from "../api/turns";

interface NegotiationChatProps {
  session: NegotiationSession;
  scenarioTitle: string;
  opponentRole?: string;
  turns: NegotiationTurn[];
  streamingOpponentText: string | null;
  isLoadingTurns: boolean;
  isSending: boolean;
  isOpponentThinking: boolean;
  isCompleting: boolean;
  error: string;
  onSend: (content: string) => Promise<boolean>;
  onRetryOpponent: () => Promise<void>;
  onComplete: () => Promise<void>;
  onBack: () => void;
}

export function NegotiationChat({
  session,
  scenarioTitle,
  opponentRole,
  turns,
  streamingOpponentText,
  isLoadingTurns,
  isSending,
  isOpponentThinking,
  isCompleting,
  error,
  onSend,
  onRetryOpponent,
  onComplete,
  onBack,
}: NegotiationChatProps) {
  const [content, setContent] = useState("");
  const isSubmittingRef = useRef(false);
  const messageListRef = useRef<HTMLDivElement>(null);
  const shouldAutoScrollRef = useRef(true);
  const isCompleted = session.status === "completed";
  const latestTurn = turns.at(-1);
  const isWaitingForOpponent =
    !isCompleted && latestTurn?.speaker === "user";
  const mayRetryOpponent = isWaitingForOpponent && !isSending;
  const typingRole = opponentRole?.trim() || "Opponent";

  useEffect(() => {
    const messageList = messageListRef.current;
    if (!messageList || !shouldAutoScrollRef.current) {
      return;
    }

    const animationFrame = requestAnimationFrame(() => {
      messageList.scrollTo({
        top: messageList.scrollHeight,
        behavior: "auto",
      });
    });

    return () => cancelAnimationFrame(animationFrame);
  }, [isOpponentThinking, streamingOpponentText, turns]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const normalizedContent = content.trim();
    if (
      !normalizedContent ||
      isSubmittingRef.current ||
      isSending ||
      isCompleted ||
      isCompleting ||
      isWaitingForOpponent
    ) {
      return;
    }

    isSubmittingRef.current = true;
    try {
      const persisted = await onSend(normalizedContent);
      if (persisted) {
        setContent("");
      }
    } finally {
      isSubmittingRef.current = false;
    }
  }

  function handleMessageKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (
      event.key !== "Enter" ||
      event.shiftKey ||
      !content.trim() ||
      isSubmittingRef.current ||
      isSending ||
      isCompleted ||
      isCompleting ||
      isWaitingForOpponent
    ) {
      return;
    }

    event.preventDefault();
    event.currentTarget.form?.requestSubmit();
  }

  function handleMessageListScroll(event: UIEvent<HTMLDivElement>) {
    const messageList = event.currentTarget;
    const distanceFromBottom =
      messageList.scrollHeight - messageList.scrollTop - messageList.clientHeight;
    shouldAutoScrollRef.current = distanceFromBottom < 140;
  }

  return (
    <section className="chat-panel" aria-labelledby="chat-title">
      <header className="chat-header">
        <div>
          <button className="back-button" type="button" onClick={onBack}>
            ← Back to Dashboard
          </button>
          <p className="eyebrow">Negotiation</p>
          <h2 id="chat-title">{scenarioTitle}</h2>
        </div>
        <span className={`status-chip ${isCompleted ? "completed" : ""}`}>
          {session.status}
        </span>
      </header>

      <div
        className="message-list"
        aria-live="polite"
        ref={messageListRef}
        onScroll={handleMessageListScroll}
      >
        {isLoadingTurns ? (
          <p className="muted-copy" role="status">
            Loading conversation...
          </p>
        ) : null}
        {!isLoadingTurns && turns.length === 0 ? (
          <div className="conversation-empty">
            <strong>Ready when you are.</strong>
            <span>Send the first message to begin the negotiation.</span>
          </div>
        ) : null}
        {turns.map((turn) => (
          <article
            className={`message-bubble ${turn.speaker}`}
            key={turn.id}
          >
            <div className="message-meta">
              <strong>{turn.speaker === "user" ? "You" : "Opponent"}</strong>
              <span>Turn {turn.turn_number}</span>
            </div>
            <p>{turn.content}</p>
          </article>
        ))}
        {streamingOpponentText !== null ? (
          <article className="message-bubble opponent streaming">
            <div className="message-meta">
              <strong>{typingRole}</strong>
              <span>Streaming</span>
            </div>
            <p>{streamingOpponentText || "\u00a0"}</p>
          </article>
        ) : null}
        {isOpponentThinking ? (
          <div className="thinking-state" role="status">
            {typingRole} is typing...
          </div>
        ) : null}
      </div>

      {error ? (
        <div className="chat-error" role="alert">
          <span>
            {mayRetryOpponent ? (
              <strong>Opponent response interrupted. </strong>
            ) : null}
            {error}
          </span>
          {mayRetryOpponent ? (
            <button
              className="text-button"
              type="button"
              onClick={() => void onRetryOpponent()}
            >
              Retry opponent response
            </button>
          ) : null}
        </div>
      ) : null}

      {!error && mayRetryOpponent ? (
        <div className="chat-recovery" role="status">
          <span>Your last message is saved and still needs an opponent response.</span>
          <button
            className="text-button"
            type="button"
            onClick={() => void onRetryOpponent()}
          >
            Generate opponent response
          </button>
        </div>
      ) : null}

      {!isCompleted ? (
        <form className="message-composer" onSubmit={handleSubmit}>
          <label className="sr-only" htmlFor="negotiation-message">
            Your message
          </label>
          <textarea
            id="negotiation-message"
            rows={3}
            value={content}
            onChange={(event) => setContent(event.target.value)}
            onKeyDown={handleMessageKeyDown}
            placeholder="State your position..."
            disabled={isSending || isCompleting || isWaitingForOpponent}
          />
          <div className="composer-actions">
            <button
              className="secondary-button danger-button"
              type="button"
              disabled={isSending || isCompleting}
              onClick={() => void onComplete()}
            >
              {isCompleting ? "Completing..." : "Complete negotiation"}
            </button>
            <button
              className="primary-button"
              type="submit"
              disabled={
                !content.trim() ||
                isSending ||
                isCompleting ||
                isWaitingForOpponent
              }
            >
              {isSending ? "Sending..." : "Send"}
            </button>
          </div>
        </form>
      ) : null}

    </section>
  );
}
