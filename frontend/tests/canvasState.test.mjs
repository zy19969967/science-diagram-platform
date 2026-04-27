import assert from "node:assert/strict";

import {
  createCanvasStateSnapshot,
  createTextLayersFromLabels,
  extractTextLayersFromCanvasState,
} from "../src/canvasState.js";

const textLayers = createTextLayersFromLabels(["底物", "酶", "产物"]);

assert.equal(textLayers.length, 3);
assert.equal(textLayers[0].type, "text");
assert.equal(textLayers[0].data.text, "底物");
assert.equal(textLayers[0].visible, true);

const snapshot = createCanvasStateSnapshot({
  sourceImage: "data:image/png;base64,source",
  naturalSize: { width: 1024, height: 768 },
  selectedInitCandidateId: "init_1",
  latestResult: null,
  maskPayload: {
    dataUrl: "data:image/png;base64,mask",
    pixelCount: 42,
  },
  selectedAsset: {
    id: "arrow",
    name: "Arrow",
    image_url: "/assets/arrow.svg",
  },
  assetPlacement: {
    asset_id: "arrow",
    x: 0.5,
    y: 0.52,
    width: 0.28,
    height: 0.12,
    rotation: 0,
  },
  textLayers,
  instruction: "画一个酶促反应示意图",
  task: "shape-guided",
  initPlan: {
    provider: "deterministic-fallback",
    diagram_type: "enzyme_reaction_diagram",
  },
  seed: 2026,
  plan: null,
  layerOrder: ["text-2", "asset-arrow", "mask-current", "text-1"],
  layerOverrides: {
    "text-2": { visible: false, locked: true, opacity: 0.45 },
    "asset-arrow": { locked: true },
  },
});

assert.equal(snapshot.source, "init-candidate");
assert.equal(snapshot.canvas_id, "canvas-init_1");
assert.equal(snapshot.width, 1024);
assert.equal(snapshot.height, 768);
assert.equal(snapshot.layers.length, 6);
assert.equal(snapshot.layers[0].type, "base-image");
assert.equal(snapshot.layers[1].id, "text-2");
assert.equal(snapshot.layers[1].visible, false);
assert.equal(snapshot.layers[1].locked, true);
assert.equal(snapshot.layers[1].opacity, 0.45);
assert.equal(snapshot.layers[2].id, "asset-arrow");
assert.equal(snapshot.layers[2].locked, true);
assert.equal(snapshot.layers[3].id, "mask-current");
assert.equal(snapshot.layers[3].data.mask_image, null);
assert.equal(snapshot.layers[3].data.embedded_mask_image, true);
assert.deepEqual(snapshot.history, ["init_1"]);
assert.equal(snapshot.metadata.selected_init_candidate_id, "init_1");
assert.equal(snapshot.metadata.init_provider, "deterministic-fallback");

const restored = extractTextLayersFromCanvasState(snapshot);
assert.equal(restored.length, 3);
assert.equal(restored[2].data.text, "产物");

const alternateFromSameBase = createCanvasStateSnapshot({
  sourceImage: "data:image/png;base64,source",
  naturalSize: { width: 1024, height: 768 },
  selectedInitCandidateId: "init_1",
  latestResult: {
    run_id: "run_old",
    result_image: "data:image/png;base64,previous-result",
    canvas_state: {
      canvas_id: "canvas-init_1",
      history: ["init_1", "run_old"],
      layers: [],
    },
  },
  maskPayload: {
    dataUrl: "data:image/png;base64,mask",
    pixelCount: 42,
  },
  selectedAsset: null,
  assetPlacement: null,
  textLayers,
  instruction: "画一个酶促反应示意图",
  task: "shape-guided",
  initPlan: {
    provider: "deterministic-fallback",
    diagram_type: "enzyme_reaction_diagram",
  },
  seed: 2026,
  plan: null,
});

assert.deepEqual(alternateFromSameBase.history, ["init_1"]);
assert.equal(alternateFromSameBase.layers[0].data.run_id, null);
assert.equal(alternateFromSameBase.metadata.latest_run_id, null);
