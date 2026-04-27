import assert from "node:assert/strict";

import {
  buildBenchmarkRecordPayload,
  formatBenchmarkScore,
  summarizeBenchmarkSummary,
} from "../src/benchmarkState.js";

const latestResult = {
  run_id: "run_123",
  result_image: "data:image/png;base64,large-result",
  artifacts: {
    result: "http://localhost/artifacts/run_123/result.png",
    mask: "http://localhost/artifacts/run_123/mask.png",
  },
  quality_report: {
    run_id: "run_123",
    quality_version: "phase4-v1",
    prompt: {
      task: "shape-guided",
      seed: 2026,
      planner_source: "planner-service-or-fallback",
    },
    evaluation: {
      edit_localization_score: 0.876,
      preservation_score: 0.94,
      mask_coverage_ratio: 0.2,
    },
  },
};

const payload = buildBenchmarkRecordPayload({
  latestResult,
  currentProject: {
    project_id: "project_123",
    latest_version_id: "version_456",
  },
  selectedInitCandidateId: "init_1",
  initGeneration: {
    used_provider: "flux-remote",
    provider: "flux-remote",
  },
  task: "shape-guided",
  instruction: "Add enzyme arrow",
  textValidationReport: {
    status: "pass",
    matched_labels: ["enzyme"],
    missing_labels: [],
  },
});

assert.equal(payload.run_id, "run_123");
assert.equal(payload.project_id, "project_123");
assert.equal(payload.version_id, "version_456");
assert.equal(payload.provider, "flux-remote");
assert.equal(payload.task, "shape-guided");
assert.equal(payload.seed, 2026);
assert.equal(payload.quality_report.run_id, "run_123");
assert.equal(payload.text_report.status, "pass");
assert.equal(payload.metadata.selected_init_candidate_id, "init_1");
assert.equal(JSON.stringify(payload).includes("data:image/png"), false);

assert.throws(
  () => buildBenchmarkRecordPayload({ latestResult: { run_id: "run_missing" } }),
  /quality report/i,
);

assert.equal(formatBenchmarkScore(0.876), "87.6%");
assert.equal(formatBenchmarkScore(null), "n/a");

const emptySummary = summarizeBenchmarkSummary(null);
assert.equal(emptySummary.totalRuns, 0);
assert.equal(emptySummary.localizationLabel, "n/a");
assert.deepEqual(emptySummary.providers, []);

const populatedSummary = summarizeBenchmarkSummary({
  total_runs: 2,
  average_metrics: {
    edit_localization_score: 0.75,
    preservation_score: 0.95,
  },
  text_pass_rate: 0.5,
  by_provider: [
    {
      provider: "flux-remote",
      run_count: 2,
      average_metrics: {
        edit_localization_score: 0.75,
        preservation_score: 0.95,
      },
      text_pass_rate: 0.5,
    },
  ],
  recent_runs: [{ run_id: "run_123", provider: "flux-remote" }],
  warnings: [],
});

assert.equal(populatedSummary.totalRuns, 2);
assert.equal(populatedSummary.localizationLabel, "75%");
assert.equal(populatedSummary.preservationLabel, "95%");
assert.equal(populatedSummary.textPassRateLabel, "50%");
assert.equal(populatedSummary.providers[0].provider, "flux-remote");
assert.equal(populatedSummary.recentRuns[0].run_id, "run_123");
