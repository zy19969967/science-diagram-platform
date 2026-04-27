function formatScore(value) {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return "n/a";
  }
  return `${Math.round(value * 1000) / 10}%`;
}

export function summarizeInitGeneration(response = null) {
  return {
    provider: response?.provider ?? "unknown",
    requestedProvider: response?.requested_provider ?? "auto",
    usedProvider: response?.used_provider ?? response?.provider ?? "unknown",
    fallbackUsed: Boolean(response?.fallback_used),
    warnings: Array.isArray(response?.warnings) ? response.warnings : [],
  };
}

export function candidateScoreSummary(candidate = {}) {
  const metadata = candidate.metadata ?? {};
  return {
    rank: metadata.rank ?? null,
    scoreLabel: formatScore(candidate.score),
    labelCoverageLabel: formatScore(metadata.label_coverage_score),
    modelScoreLabel: formatScore(metadata.model_score),
    providerSource: metadata.provider_source ?? candidate.provider ?? "unknown",
  };
}
