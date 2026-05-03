const STATUS_LABELS = {
  queued: "排队中",
  planning: "规划中",
  generating: "生成中",
  completed: "已完成",
  failed: "失败",
  cancelled: "已取消",
};

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
  quality = "standard",
  numOutputs = 2,
}) {
  return {
    prompt: String(instruction ?? "").trim(),
    source_image: sourceImage || null,
    mask_image: maskPayload?.pixelCount > 0 ? maskPayload.dataUrl : null,
    options: {
      num_outputs: numOutputs,
      task_override: taskOverride || null,
      quality,
      seed,
      steps,
      guidance_scale: guidanceScale,
    },
  };
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
