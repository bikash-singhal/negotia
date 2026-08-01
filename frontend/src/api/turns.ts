import { apiRequest } from "./client";

export type NegotiationTurnSpeaker = "user" | "opponent";

export interface NegotiationTurn {
  id: string;
  session_id: string;
  speaker: NegotiationTurnSpeaker;
  content: string;
  turn_number: number;
  created_at: string;
}

export interface NegotiationTurnCreateRequest {
  session_id: string;
  speaker: NegotiationTurnSpeaker;
  content: string;
}

export function createTurn(
  token: string,
  request: NegotiationTurnCreateRequest,
): Promise<NegotiationTurn> {
  return apiRequest<NegotiationTurn>("/turns", {
    method: "POST",
    body: request,
    token,
  });
}

export function listTurns(
  token: string,
  sessionId: string,
): Promise<NegotiationTurn[]> {
  return apiRequest<NegotiationTurn[]>(
    `/negotiations/${sessionId}/turns`,
    { token },
  );
}
