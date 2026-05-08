import assert from "node:assert/strict";
import {
  buildSmartGenerationPayload,
  canCancelGenerationSnapshot,
  extractGenerationProviderMetadata,
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
    generation_provider: "qwen-image",
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

const powerPaintPayload = buildSmartGenerationPayload({
  instruction: "replace the cup",
  sourceImage: "data:image/png;base64,source",
  maskPayload: { dataUrl: "data:image/png;base64,mask", pixelCount: 42 },
  taskOverride: "local_inpaint",
  generationProvider: "powerpaint",
  seed: 11,
  steps: 20,
  guidanceScale: 5,
});
assert.equal(powerPaintPayload.options.generation_provider, "powerpaint");

const qualityMetadata = extractGenerationProviderMetadata({
  latestResult: {
    quality_report: {
      prompt: {
        parameters: {
          smart_generation_provider: "powerpaint",
          smart_pipeline: "local_inpaint",
          smart_model: "PowerPaint-v2",
          provider: "fallback-provider",
          pipeline: "fallback-pipeline",
          model: "fallback-model",
        },
      },
    },
  },
  smartJobSnapshot: {
    metadata: {
      generation_provider: "qwen-image",
      pipeline: "text_to_image",
      model: "Qwen-Image",
    },
  },
});
assert.deepEqual(qualityMetadata, {
  provider: "powerpaint",
  pipeline: "local_inpaint",
  model: "PowerPaint-v2",
});

const snapshotMetadata = extractGenerationProviderMetadata({
  latestResult: null,
  smartJobSnapshot: {
    metadata: {
      provider: "qwen-image",
      generation_pipeline: "text_to_image",
      model_name: "Qwen-Image",
    },
  },
});
assert.deepEqual(snapshotMetadata, {
  provider: "qwen-image",
  pipeline: "text_to_image",
  model: "Qwen-Image",
});

assert.equal(canCancelGenerationSnapshot({ job_id: "smart-1", status: "queued" }), true);
assert.equal(canCancelGenerationSnapshot({ job_id: "smart-2", status: "generating" }), true);
assert.equal(canCancelGenerationSnapshot({ job_id: "smart-3", status: "completed" }), false);
assert.equal(canCancelGenerationSnapshot({ job_id: "legacy-1", status: "DONE" }), false);
assert.equal(canCancelGenerationSnapshot({ status: "queued" }), false);

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
