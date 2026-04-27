function compactText(value, fallback = "") {
  const trimmed = String(value ?? "").trim();
  return trimmed ? trimmed.slice(0, 160) : fallback;
}

function withoutDataUrls(value) {
  if (typeof value === "string") {
    return value.startsWith("data:") ? null : value;
  }
  if (Array.isArray(value)) {
    return value.map((item) => withoutDataUrls(item)).filter((item) => item !== null);
  }
  if (value && typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value)
        .map(([key, item]) => [key, withoutDataUrls(item)])
        .filter(([, item]) => item !== null),
    );
  }
  return value ?? null;
}

export function formatBenchmarkScore(value) {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return "n/a";
  }
  return `${Math.round(value * 1000) / 10}%`;
}

export function buildBenchmarkRecordPayload({
  latestResult,
  currentProject = null,
  selectedInitCandidateId = "",
  initGeneration = null,
  task = "",
  instruction = "",
  textValidationReport = null,
} = {}) {
  if (!latestResult?.run_id || !latestResult?.quality_report) {
    throw new Error("A latest result with a quality report is required before recording a benchmark.");
  }

  const prompt = latestResult.quality_report.prompt ?? {};
  const provider = compactText(initGeneration?.used_provider ?? initGeneration?.provider ?? prompt.planner_source, "unknown");
  const cleanQualityReport = withoutDataUrls(latestResult.quality_report);

  return {
    run_id: latestResult.run_id,
    project_id: currentProject?.project_id ?? null,
    version_id: currentProject?.latest_version_id ?? null,
    label: `Run ${latestResult.run_id}`,
    scenario: compactText(instruction, compactText(task, "manual-benchmark")),
    provider,
    model: compactText(latestResult.quality_report.quality_version, "phase4-v1"),
    task: task || prompt.task || null,
    seed: typeof prompt.seed === "number" ? prompt.seed : null,
    quality_report: cleanQualityReport,
    text_report: textValidationReport ? withoutDataUrls(textValidationReport) : null,
    tags: [task, provider].filter(Boolean),
    metadata: {
      instruction: compactText(instruction),
      selected_init_candidate_id: selectedInitCandidateId || null,
      init_provider: provider,
      latest_result_url: latestResult.artifacts?.result ?? null,
    },
  };
}

export function summarizeBenchmarkSummary(summary = null) {
  const metrics = summary?.average_metrics ?? {};
  return {
    totalRuns: summary?.total_runs ?? 0,
    localizationLabel: formatBenchmarkScore(metrics.edit_localization_score),
    preservationLabel: formatBenchmarkScore(metrics.preservation_score),
    textPassRateLabel: formatBenchmarkScore(summary?.text_pass_rate),
    providers: Array.isArray(summary?.by_provider) ? summary.by_provider : [],
    recentRuns: Array.isArray(summary?.recent_runs) ? summary.recent_runs : [],
    warnings: Array.isArray(summary?.warnings) ? summary.warnings : [],
  };
}
