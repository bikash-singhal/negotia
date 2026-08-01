import { apiRequest } from "./client";

export type ScenarioDifficulty = "beginner" | "intermediate" | "advanced";

export interface Scenario {
  scenario_id: string;
  title: string;
  description: string;
  industry: string;
  opponent_role: string;
  objective: string;
  difficulty: ScenarioDifficulty;
  constraints: string[];
  personality: string;
  negotiation_style: string;
  created_at: string;
  updated_at: string;
}

export interface ScenarioCreateRequest {
  title: string;
  description: string;
  difficulty: ScenarioDifficulty;
}

export function listScenarios(token: string): Promise<Scenario[]> {
  return apiRequest<Scenario[]>("/scenarios", { token });
}

export function getScenario(
  token: string,
  scenarioId: string,
): Promise<Scenario> {
  return apiRequest<Scenario>(`/scenarios/${scenarioId}`, { token });
}

export function createScenario(
  token: string,
  request: ScenarioCreateRequest,
): Promise<Scenario> {
  return apiRequest<Scenario>("/scenarios", {
    method: "POST",
    body: request,
    token,
  });
}
