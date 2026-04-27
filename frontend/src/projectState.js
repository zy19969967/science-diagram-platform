const DEFAULT_PROJECT_NAME = "Untitled science diagram";

function isDataUrl(value) {
  return typeof value === "string" && value.startsWith("data:");
}

function compactName(value) {
  const trimmed = String(value ?? "").trim();
  return trimmed ? trimmed.slice(0, 120) : DEFAULT_PROJECT_NAME;
}

function inferSource({ latestResult, selectedInitCandidateId }) {
  if (latestResult?.run_id) {
    return "generated";
  }
  if (selectedInitCandidateId) {
    return "init-candidate";
  }
  return "upload";
}

export function buildProjectCreatePayload({
  instruction,
  naturalSize,
  sourceImage,
  initPlan,
  selectedInitCandidateId,
  latestResult,
}) {
  return {
    name: compactName(instruction),
    source_image_metadata: {
      width: Number(naturalSize?.width) || null,
      height: Number(naturalSize?.height) || null,
      source: inferSource({ latestResult, selectedInitCandidateId }),
      embedded_source_image: isDataUrl(sourceImage),
      selected_init_candidate_id: selectedInitCandidateId || null,
      latest_run_id: latestResult?.run_id ?? null,
    },
    init_plan: initPlan ?? null,
    selected_candidate_id: selectedInitCandidateId || null,
  };
}

export function buildProjectVersionPayload({
  currentProject,
  canvasState,
  latestResult,
  selectedInitCandidateId,
  instruction,
  task,
}) {
  if (!canvasState) {
    throw new Error("A canvas state is required before saving a project version.");
  }

  const hasResult = Boolean(latestResult?.run_id);
  const kind = hasResult ? "generate-result" : selectedInitCandidateId ? "init-candidate" : "manual-snapshot";
  const runId = latestResult?.run_id ?? null;
  const resultArtifactUrl = latestResult?.artifacts?.result ?? null;

  return {
    kind,
    parent_version_id: currentProject?.latest_version_id ?? null,
    run_id: runId,
    label: hasResult ? `Run ${runId}` : selectedInitCandidateId ? `Initial ${selectedInitCandidateId}` : "Canvas snapshot",
    canvas_state: canvasState,
    quality_report: latestResult?.quality_report ?? null,
    artifacts: latestResult?.artifacts ?? {},
    result_image: resultArtifactUrl,
    metadata: {
      instruction: String(instruction ?? ""),
      task: task ?? null,
      selected_init_candidate_id: selectedInitCandidateId || null,
      canvas_id: canvasState.canvas_id ?? null,
    },
  };
}

export function latestProjectVersion(project) {
  if (!project?.versions?.length) {
    return null;
  }
  if (project.latest_version_id) {
    return project.versions.find((version) => version.version_id === project.latest_version_id) ?? project.versions.at(-1);
  }
  return project.versions.at(-1);
}

export function canSaveReloadableProjectVersion({ latestResult } = {}) {
  return Boolean(latestResult?.canvas_state && latestResult?.artifacts?.result);
}

export function shouldSaveReturnedCanvasState({ latestResult, sourceImage } = {}) {
  return Boolean(latestResult?.canvas_state && sourceImage !== latestResult.result_image);
}
