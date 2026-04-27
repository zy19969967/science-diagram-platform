import assert from "node:assert/strict";

import {
  candidateScoreSummary,
  summarizeInitGeneration,
} from "../src/initCandidates.js";

const response = {
  provider: "flux-remote",
  requested_provider: "auto",
  used_provider: "flux-remote",
  fallback_used: false,
  warnings: [],
};

assert.deepEqual(summarizeInitGeneration(response), {
  provider: "flux-remote",
  requestedProvider: "auto",
  usedProvider: "flux-remote",
  fallbackUsed: false,
  warnings: [],
});

const localSummary = summarizeInitGeneration({
  provider: "flux-local",
  requested_provider: "auto",
  used_provider: "flux-local",
  fallback_used: false,
  warnings: [],
});
assert.equal(localSummary.usedProvider, "flux-local");

const fallbackSummary = summarizeInitGeneration({
  provider: "deterministic-fallback",
  requested_provider: "auto",
  used_provider: "deterministic-fallback",
  fallback_used: true,
  warnings: ["FLUX_INIT_URL is not configured"],
});
assert.equal(fallbackSummary.fallbackUsed, true);
assert.equal(fallbackSummary.warnings[0], "FLUX_INIT_URL is not configured");

const score = candidateScoreSummary({
  id: "remote-best",
  score: 0.9123,
  provider: "flux-remote",
  metadata: {
    rank: 1,
    label_coverage_score: 0.667,
    model_score: 0.84,
    provider_source: "flux-remote",
  },
});
assert.equal(score.rank, 1);
assert.equal(score.scoreLabel, "91.2%");
assert.equal(score.labelCoverageLabel, "66.7%");
assert.equal(score.providerSource, "flux-remote");
