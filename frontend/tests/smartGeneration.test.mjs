import assert from "node:assert/strict";
import {
  buildSmartGenerationPayload,
  primaryActionLabel,
  summarizeSmartGenerationStatus,
} from "../src/smartGeneration.js";

assert.equal(primaryActionLabel({ sourceImage: "" }), "生成图片");
assert.equal(primaryActionLabel({ sourceImage: "data:image/png;base64,source" }), "修改图片");

const textToImagePayload = buildSmartGenerationPayload({
  instruction: "画一个细胞结构图",
  sourceImage: "",
  maskPayload: { dataUrl: "", pixelCount: 0 },
  taskOverride: "",
  seed: 2026,
  steps: 30,
  guidanceScale: 7.5,
});
assert.deepEqual(textToImagePayload, {
  prompt: "画一个细胞结构图",
  source_image: null,
  mask_image: null,
  options: {
    num_outputs: 2,
    task_override: null,
    quality: "standard",
    seed: 2026,
    steps: 30,
    guidance_scale: 7.5,
  },
});

const localPayload = buildSmartGenerationPayload({
  instruction: "把杯子换成花瓶",
  sourceImage: "data:image/png;base64,source",
  maskPayload: { dataUrl: "data:image/png;base64,mask", pixelCount: 42 },
  taskOverride: "local_inpaint",
  seed: 7,
  steps: 25,
  guidanceScale: 6,
});
assert.equal(localPayload.options.task_override, "local_inpaint");
assert.equal(localPayload.mask_image, "data:image/png;base64,mask");

const diagnostic = summarizeSmartGenerationStatus({
  status: "completed",
  task_type: "text_to_image",
  results: [{ is_diagnostic_result: true }],
  message: "diagnostic fallback",
});
assert.equal(diagnostic.hasDiagnosticResult, true);
assert.match(diagnostic.label, /诊断/);

const queued = summarizeSmartGenerationStatus({
  status: "queued",
  task_type: "local_inpaint",
  message: "任务已创建",
});
assert.equal(queued.label, "排队中：任务已创建");
