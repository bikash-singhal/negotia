import assert from "node:assert/strict";
import test from "node:test";

import {
  getBiggestTakeaway,
  getCoachingSnapshot,
  getContinueNegotiations,
  getRecentCompletedNegotiations,
} from "../src/workspace/dashboardData.ts";

function negotiation(id, status, updatedAt) {
  return {
    id,
    scenario_id: `scenario-${id}`,
    status,
    created_at: updatedAt,
    updated_at: updatedAt,
  };
}

test("selects the three most recent incomplete negotiations", () => {
  const negotiations = [
    negotiation("old", "active", "2026-01-01T00:00:00Z"),
    negotiation("completed", "completed", "2026-06-01T00:00:00Z"),
    negotiation("newest", "created", "2026-05-01T00:00:00Z"),
    negotiation("middle", "active", "2026-04-01T00:00:00Z"),
    negotiation("third", "created", "2026-03-01T00:00:00Z"),
  ];

  assert.deepEqual(
    getContinueNegotiations(negotiations).map(({ id }) => id),
    ["newest", "middle", "third"],
  );
});

test("selects at most five recent completed negotiations", () => {
  const negotiations = Array.from({ length: 7 }, (_, index) =>
    negotiation(
      String(index),
      "completed",
      `2026-01-${String(index + 1).padStart(2, "0")}T00:00:00Z`,
    ),
  );

  assert.deepEqual(
    getRecentCompletedNegotiations(negotiations).map(({ id }) => id),
    ["6", "5", "4", "3", "2"],
  );
});

test("uses the requested biggest-takeaway fallback order", () => {
  const completion = {
    debrief: {
      key_missed_opportunities: ["Ask a diagnostic question first."],
      repeated_weaknesses: ["Avoid conceding too quickly."],
      overall_assessment: "A clear and professional conversation.",
    },
  };

  assert.equal(
    getBiggestTakeaway(completion),
    "Ask a diagnostic question first.",
  );
  completion.debrief.key_missed_opportunities = [];
  assert.equal(
    getBiggestTakeaway(completion),
    "Avoid conceding too quickly.",
  );
  completion.debrief.repeated_weaknesses = [];
  assert.equal(
    getBiggestTakeaway(completion),
    "A clear and professional conversation.",
  );
});

test("projects the compact coaching snapshot without internal confidence", () => {
  const memory = {
    stable_strengths: ["Clear opening positions"],
    stable_weaknesses: ["Makes unconditional concessions"],
    improving_skills: ["Diagnostic questioning"],
    persistent_risks: ["Unilateral concessions"],
    highest_priority_skill: "Make concessions conditional",
    next_session_drill: "Prepare three conditional trades.",
    progress_summary: "Questions are improving; concession discipline needs work.",
    sessions_analyzed: 3,
    confidence: "medium",
  };

  const snapshot = getCoachingSnapshot(memory);
  assert.deepEqual(snapshot, {
    progressSummary:
      "Questions are improving; concession discipline needs work.",
    highestPrioritySkill: "Make concessions conditional",
    nextSessionDrill: "Prepare three conditional trades.",
    stableStrengths: ["Clear opening positions"],
    stableWeaknesses: ["Makes unconditional concessions"],
    improvingSkills: ["Diagnostic questioning"],
    persistentRisks: ["Unilateral concessions"],
  });
  assert.equal(Object.hasOwn(snapshot, "confidence"), false);
});
