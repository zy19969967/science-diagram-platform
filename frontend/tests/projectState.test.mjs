import assert from "node:assert/strict";

import {
  buildProjectCreatePayload,
  buildProjectVersionPayload,
  canSaveReloadableProjectVersion,
  shouldSaveReturnedCanvasState,
} from "../src/projectState.js";

const canvasState = {
  canvas_id: "canvas-init_1",
  width: 1024,
  height: 768,
  source: "generated",
  layers: [
    {
      id: "base-image",
      type: "base-image",
      name: "Canvas source",
      data: {
        source: "generated",
        image_url: "http://localhost/artifacts/run_123/result.png",
        embedded_source_image: false,
      },
    },
  ],
  history: ["init_1", "run_123"],
  metadata: {
    selected_init_candidate_id: "init_1",
    latest_run_id: "run_123",
  },
};

const createPayload = buildProjectCreatePayload({
  instruction: "Enzyme pathway",
  naturalSize: { width: 1024, height: 768 },
  sourceImage: "data:image/png;base64,source",
  initPlan: {
    provider: "deterministic-fallback",
    diagram_type: "enzyme_reaction_diagram",
  },
  selectedInitCandidateId: "init_1",
  latestResult: null,
});

assert.equal(createPayload.name, "Enzyme pathway");
assert.equal(createPayload.source_image_metadata.width, 1024);
assert.equal(createPayload.source_image_metadata.height, 768);
assert.equal(createPayload.source_image_metadata.source, "init-candidate");
assert.equal(createPayload.source_image_metadata.embedded_source_image, true);
assert.equal(createPayload.selected_candidate_id, "init_1");
assert.equal(createPayload.init_plan.provider, "deterministic-fallback");

const versionPayload = buildProjectVersionPayload({
  currentProject: {
    project_id: "project_1",
    latest_version_id: "version_parent",
  },
  canvasState,
  latestResult: {
    run_id: "run_123",
    result_image: "data:image/png;base64,large-result",
    artifacts: {
      result: "http://localhost/artifacts/run_123/result.png",
      mask: "http://localhost/artifacts/run_123/mask.png",
    },
    quality_report: {
      run_id: "run_123",
      quality_version: "phase4-v1",
    },
  },
  selectedInitCandidateId: "init_1",
  instruction: "Enzyme pathway",
  task: "shape-guided",
});

assert.equal(versionPayload.kind, "generate-result");
assert.equal(versionPayload.parent_version_id, "version_parent");
assert.equal(versionPayload.run_id, "run_123");
assert.equal(versionPayload.canvas_state.canvas_id, "canvas-init_1");
assert.equal(versionPayload.quality_report.run_id, "run_123");
assert.equal(versionPayload.artifacts.result, "http://localhost/artifacts/run_123/result.png");
assert.equal(versionPayload.result_image, "http://localhost/artifacts/run_123/result.png");
assert.equal(versionPayload.metadata.selected_init_candidate_id, "init_1");
assert.equal(versionPayload.metadata.task, "shape-guided");
assert.equal(JSON.stringify(versionPayload).includes("data:image/png"), false);

assert.equal(canSaveReloadableProjectVersion({ latestResult: null }), false);
assert.equal(canSaveReloadableProjectVersion({ latestResult: { canvas_state: canvasState } }), false);
assert.equal(
  canSaveReloadableProjectVersion({
    latestResult: {
      canvas_state: canvasState,
      artifacts: { result: "http://localhost/artifacts/run_123/result.png" },
    },
  }),
  true,
);

assert.equal(
  shouldSaveReturnedCanvasState({
    latestResult: {
      result_image: "data:image/png;base64,result",
      canvas_state: canvasState,
    },
    sourceImage: "data:image/png;base64,original",
  }),
  true,
);
assert.equal(
  shouldSaveReturnedCanvasState({
    latestResult: {
      result_image: "data:image/png;base64,result",
      canvas_state: canvasState,
    },
    sourceImage: "data:image/png;base64,result",
  }),
  false,
);
