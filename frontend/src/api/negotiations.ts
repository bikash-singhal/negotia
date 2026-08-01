import { ApiError, apiRequest, apiStreamRequest } from "./client";
import { readNdjsonStream } from "./ndjson";
import type { NegotiationTurn } from "./turns";

export type NegotiationStatus =
  | "created"
  | "active"
  | "completed"
  | "abandoned";

export interface NegotiationSession {
  id: string;
  scenario_id: string;
  status: NegotiationStatus;
  created_at: string;
  updated_at: string;
}

export interface NegotiationDebrief {
  repeated_strengths: string[];
  repeated_weaknesses: string[];
  key_missed_opportunities: string[];
  recurring_risks: string[];
  overall_assessment: string;
  confidence: string;
}

export interface NegotiationTactic {
  priority: number;
  title: string;
  rationale: string;
  actions: string[];
  example_language: string[];
  success_indicator: string;
}

export interface NegotiationStrategy {
  primary_objective: string;
  expected_outcome: string;
  prioritized_tactics: NegotiationTactic[];
  long_term_skills: string[];
  preparation_checklist: string[];
  avoid_next_time: string[];
  confidence: string;
}

export interface NegotiatorMemory {
  stable_strengths: string[];
  stable_weaknesses: string[];
  improving_skills: string[];
  persistent_risks: string[];
  highest_priority_skill: string;
  next_session_drill: string;
  progress_summary: string;
  sessions_analyzed: number;
  confidence: string;
}

export interface NegotiationCompletion {
  session_id: string;
  status: NegotiationStatus;
  completed_at: string;
  debrief: NegotiationDebrief;
  observation_count: number;
  debrief_id: string;
  debrief_created_at: string;
  strategy: NegotiationStrategy;
  strategy_id: string;
  strategy_created_at: string;
  memory: NegotiatorMemory | null;
  memory_id: string | null;
  memory_created_at: string | null;
}

export function listNegotiations(token: string): Promise<NegotiationSession[]> {
  return apiRequest<NegotiationSession[]>("/negotiations", { token });
}

export function getNegotiation(
  token: string,
  sessionId: string,
): Promise<NegotiationSession> {
  return apiRequest<NegotiationSession>(`/negotiations/${sessionId}`, {
    token,
  });
}

export function createNegotiation(
  token: string,
  scenarioId: string,
): Promise<NegotiationSession> {
  return apiRequest<NegotiationSession>("/negotiations", {
    method: "POST",
    body: { scenario_id: scenarioId },
    token,
  });
}

export function generateOpponentResponse(
  token: string,
  sessionId: string,
): Promise<NegotiationTurn> {
  return apiRequest<NegotiationTurn>(
    `/negotiations/${sessionId}/opponent-response`,
    { method: "POST", token },
  );
}

export type OpponentResponseStreamEvent =
  | { type: "started" }
  | { type: "delta"; text: string }
  | { type: "completed"; turn: NegotiationTurn }
  | { type: "error"; code: string; message: string };

export async function streamOpponentResponse(
  token: string,
  sessionId: string,
  onEvent: (event: OpponentResponseStreamEvent) => void,
  signal: AbortSignal,
): Promise<void> {
  const response = await apiStreamRequest(
    `/negotiations/${sessionId}/opponent-response/stream`,
    {
      accept: "application/x-ndjson",
      method: "POST",
      token,
      signal,
    },
  );
  let terminalEventReceived = false;

  await readNdjsonStream<unknown>(response, (value) => {
    const event = parseOpponentResponseStreamEvent(value);
    if (event.type === "completed") {
      terminalEventReceived = true;
    }
    if (event.type === "error") {
      terminalEventReceived = true;
      throw new ApiError(502, event.message, event.code);
    }
    onEvent(event);
  });

  if (!terminalEventReceived) {
    throw new Error("The opponent response stream ended before completion.");
  }
}

function parseOpponentResponseStreamEvent(
  value: unknown,
): OpponentResponseStreamEvent {
  if (!isRecord(value) || typeof value.type !== "string") {
    throw new Error("The opponent response stream returned an invalid event.");
  }
  if (value.type === "started") {
    return { type: "started" };
  }
  if (value.type === "delta" && typeof value.text === "string") {
    return { type: "delta", text: value.text };
  }
  if (value.type === "completed" && isNegotiationTurn(value.turn)) {
    return { type: "completed", turn: value.turn };
  }
  if (
    value.type === "error" &&
    typeof value.code === "string" &&
    typeof value.message === "string"
  ) {
    return { type: "error", code: value.code, message: value.message };
  }
  throw new Error("The opponent response stream returned an invalid event.");
}

function isNegotiationTurn(value: unknown): value is NegotiationTurn {
  return (
    isRecord(value) &&
    typeof value.id === "string" &&
    typeof value.session_id === "string" &&
    (value.speaker === "user" || value.speaker === "opponent") &&
    typeof value.content === "string" &&
    typeof value.turn_number === "number" &&
    typeof value.created_at === "string"
  );
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

export function completeNegotiation(
  token: string,
  sessionId: string,
): Promise<NegotiationCompletion> {
  return apiRequest<NegotiationCompletion>(
    `/negotiations/${sessionId}/complete`,
    { method: "POST", token },
  );
}
