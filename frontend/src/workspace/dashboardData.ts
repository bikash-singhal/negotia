import type {
  NegotiationCompletion,
  NegotiationSession,
  NegotiatorMemory,
} from "../api/negotiations";

export function getContinueNegotiations(
  negotiations: NegotiationSession[],
): NegotiationSession[] {
  return sortByUpdatedAt(
    negotiations.filter(
      (negotiation) =>
        negotiation.status === "created" || negotiation.status === "active",
    ),
  ).slice(0, 3);
}

export function getRecentCompletedNegotiations(
  negotiations: NegotiationSession[],
): NegotiationSession[] {
  return sortByUpdatedAt(
    negotiations.filter(
      (negotiation) => negotiation.status === "completed",
    ),
  ).slice(0, 5);
}

export function getBiggestTakeaway(
  completion: NegotiationCompletion,
): string {
  return (
    completion.debrief.key_missed_opportunities[0] ??
    completion.debrief.repeated_weaknesses[0] ??
    completion.debrief.overall_assessment
  );
}

export interface CoachingSnapshotData {
  progressSummary: string;
  highestPrioritySkill: string;
  nextSessionDrill: string;
  stableStrengths: string[];
  stableWeaknesses: string[];
  improvingSkills: string[];
  persistentRisks: string[];
}

export function getCoachingSnapshot(
  memory: NegotiatorMemory,
): CoachingSnapshotData {
  return {
    progressSummary: memory.progress_summary,
    highestPrioritySkill: memory.highest_priority_skill,
    nextSessionDrill: memory.next_session_drill,
    stableStrengths: [...memory.stable_strengths],
    stableWeaknesses: [...memory.stable_weaknesses],
    improvingSkills: [...memory.improving_skills],
    persistentRisks: [...memory.persistent_risks],
  };
}

function sortByUpdatedAt(
  negotiations: NegotiationSession[],
): NegotiationSession[] {
  return [...negotiations].sort(
    (left, right) => Date.parse(right.updated_at) - Date.parse(left.updated_at),
  );
}
