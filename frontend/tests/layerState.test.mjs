import assert from "node:assert/strict";

import {
  buildEditorLayers,
  moveLayerInOrder,
  normalizeLayerOrder,
  patchLayerOverrides,
} from "../src/layerState.js";

const textLayers = [
  {
    id: "text-1",
    type: "text",
    name: "Label 1",
    visible: true,
    locked: false,
    opacity: 1,
    data: { text: "底物", x: 0.2, y: 0.22 },
  },
  {
    id: "text-2",
    type: "text",
    name: "Label 2",
    visible: true,
    locked: false,
    opacity: 1,
    data: { text: "酶", x: 0.5, y: 0.22 },
  },
];

const layers = buildEditorLayers({
  sourceImage: "data:image/png;base64,source",
  hasMask: true,
  selectedAsset: { id: "arrow", name: "Arrow" },
  assetPlacement: { asset_id: "arrow", x: 0.5, y: 0.5, width: 0.2, height: 0.1 },
  textLayers,
  pointPrompts: [{ id: "point-1", x: 0.5, y: 0.5, label: "positive" }],
  layerOrder: ["text-2", "asset-arrow", "missing-layer", "mask-current", "base-image"],
  layerOverrides: {
    "text-2": { visible: false, locked: true, opacity: 0.42 },
  },
});

assert.deepEqual(
  layers.map((layer) => layer.id),
  ["base-image", "text-2", "asset-arrow", "mask-current", "region-prompts", "text-1"],
);
assert.equal(layers[0].locked, true);
assert.equal(layers[0].reorderable, false);
assert.equal(layers[1].visible, false);
assert.equal(layers[1].locked, true);
assert.equal(layers[1].opacity, 0.42);

assert.deepEqual(
  normalizeLayerOrder(
    ["text-2", "asset-arrow", "missing-layer", "mask-current", "base-image"],
    ["base-image", "mask-current", "asset-arrow", "text-1", "text-2"],
  ),
  ["base-image", "text-2", "asset-arrow", "mask-current", "text-1"],
);

assert.deepEqual(
  moveLayerInOrder(["base-image", "mask-current", "asset-arrow", "text-1"], "asset-arrow", "up"),
  ["base-image", "mask-current", "text-1", "asset-arrow"],
);
assert.deepEqual(
  moveLayerInOrder(["base-image", "mask-current", "asset-arrow", "text-1"], "asset-arrow", "down"),
  ["base-image", "asset-arrow", "mask-current", "text-1"],
);
assert.deepEqual(
  moveLayerInOrder(["base-image", "mask-current", "asset-arrow", "text-1"], "base-image", "up"),
  ["base-image", "mask-current", "asset-arrow", "text-1"],
);

assert.deepEqual(patchLayerOverrides({}, "text-1", { visible: false }), {
  "text-1": { visible: false },
});
assert.deepEqual(
  patchLayerOverrides({ "text-1": { visible: false, locked: true } }, "text-1", { visible: true }),
  { "text-1": { locked: true } },
);
