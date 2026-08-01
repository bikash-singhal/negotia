import { apiRequest } from "./client";
import type { NegotiatorMemory } from "./negotiations";

export function getLatestMemory(
  token: string,
): Promise<NegotiatorMemory | null> {
  return apiRequest<NegotiatorMemory | null>("/memory/latest", { token });
}
