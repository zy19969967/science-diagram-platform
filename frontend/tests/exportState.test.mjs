import assert from "node:assert/strict";

import {
  buildCanvasExportPayload,
  buildSvgDownloadDescriptor,
  buildTextValidationPayload,
  deriveExpectedLabelsFromCanvasState,
} from "../src/exportState.js";

const canvasState = {
  canvas_id: "canvas-export-1",
  width: 800,
  height: 600,
  layers: [
    {
      id: "base-image",
      type: "base-image",
      name: "Generated result",
      data: { image_url: "http://example.test/result.png" },
    },
    {
      id: "text-1",
      type: "text",
      name: "Label 1",
      visible: true,
      data: { text: "底物", x: 0.2, y: 0.3 },
    },
    {
      id: "text-2",
      type: "text",
      name: "Label 2",
      visible: false,
      data: { text: "隐藏", x: 0.5, y: 0.5 },
    },
    {
      id: "text-3",
      type: "text",
      name: "Label 3",
      visible: true,
      data: { text: "酶", x: 0.6, y: 0.5 },
    },
  ],
};

assert.deepEqual(deriveExpectedLabelsFromCanvasState(canvasState), ["底物", "酶"]);

const validationPayload = buildTextValidationPayload({ canvasState });
assert.equal(validationPayload.canvas_state.canvas_id, "canvas-export-1");
assert.deepEqual(validationPayload.expected_labels, ["底物", "酶"]);
assert.deepEqual(validationPayload.ocr_observations, []);
assert.equal(validationPayload.include_hidden_layers, false);

const explicitPayload = buildCanvasExportPayload({
  canvasState,
  expectedLabels: ["底物", "产物"],
  filename: "enzyme.svg",
});
assert.equal(explicitPayload.filename, "enzyme.svg");
assert.deepEqual(explicitPayload.expected_labels, ["底物", "产物"]);

const descriptor = buildSvgDownloadDescriptor({
  svg: "<svg></svg>",
  filename: "enzyme.svg",
  mime_type: "image/svg+xml",
});
assert.equal(descriptor.filename, "enzyme.svg");
assert.equal(descriptor.mimeType, "image/svg+xml");
assert.equal(descriptor.content, "<svg></svg>");
assert.equal(descriptor.size, 11);
