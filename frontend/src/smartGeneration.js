const STATUS_LABELS = {
  queued: "排队中",
  planning: "规划中",
  generating: "生成中",
  completed: "已完成",
  failed: "失败",
  cancelled: "已取消",
};

export const GENERATION_PROVIDER_OPTIONS = [
  { value: "qwen-image", label: "Qwen-Image" },
  { value: "powerpaint", label: "PowerPaint" },
];

export function normalizeGenerationProvider(provider) {
  const value = String(provider ?? "").trim().toLowerCase();
  return GENERATION_PROVIDER_OPTIONS.some((option) => option.value === value) ? value : "qwen-image";
}

export function primaryActionLabel({ sourceImage }) {
  return sourceImage ? "修改图片" : "生成图片";
}

export function buildSmartGenerationPayload({
  instruction,
  sourceImage,
  maskPayload,
  taskOverride,
  seed,
  steps,
  guidanceScale,
  generationProvider = "qwen-image",
  quality = "standard",
  numOutputs = 2,
}) {
  const normalizedProvider = normalizeGenerationProvider(generationProvider);
  return {
    prompt: String(instruction ?? "").trim(),
    source_image: sourceImage || null,
    mask_image: maskPayload?.pixelCount > 0 ? maskPayload.dataUrl : null,
    options: {
      num_outputs: numOutputs,
      task_override: taskOverride || null,
      quality,
      generation_provider: normalizedProvider,
      seed,
      steps,
      guidance_scale: guidanceScale,
    },
  };
}

function firstString(...values) {
  return values.find((value) => typeof value === "string" && value.trim())?.trim() ?? "";
}

export function extractGenerationProviderMetadata({ latestResult, smartJobSnapshot } = {}) {
  const parameters = latestResult?.quality_report?.prompt?.parameters ?? {};
  const metadata = smartJobSnapshot?.metadata ?? {};
  const provider = firstString(
    parameters.smart_generation_provider,
    parameters.smart_provider,
    parameters.generation_provider,
    parameters.provider,
    metadata.smart_generation_provider,
    metadata.smart_provider,
    metadata.generation_provider,
    metadata.provider,
  );
  const pipeline = firstString(
    parameters.smart_pipeline,
    parameters.smart_generation_pipeline,
    parameters.generation_pipeline,
    parameters.pipeline,
    metadata.smart_pipeline,
    metadata.smart_generation_pipeline,
    metadata.generation_pipeline,
    metadata.pipeline,
  );
  const model = firstString(
    parameters.smart_model,
    parameters.smart_model_name,
    parameters.model,
    parameters.model_name,
    metadata.smart_model,
    metadata.smart_model_name,
    metadata.model,
    metadata.model_name,
  );

  return { provider, pipeline, model };
}

export function canCancelGenerationSnapshot(snapshot) {
  if (!snapshot?.job_id) {
    return false;
  }
  const status = String(snapshot.status ?? "").toLowerCase();
  return !["completed", "failed", "cancelled", "done"].includes(status);
}

export function summarizeSmartGenerationStatus(snapshot) {
  const status = snapshot?.status || "queued";
  const prefix = STATUS_LABELS[status] || status;
  const hasDiagnosticResult = Boolean(
    snapshot?.metadata?.is_diagnostic_result ||
      snapshot?.metadata?.fallback_used ||
      (snapshot?.results ?? []).some((item) => item?.is_diagnostic_result),
  );
  const message = snapshot?.message || "";
  return {
    label: `${prefix}${hasDiagnosticResult ? "（诊断结果）" : ""}${message ? `：${message}` : ""}`,
    hasDiagnosticResult,
    isTerminal: ["completed", "failed", "cancelled"].includes(status),
    isFailed: status === "failed",
  };
}
