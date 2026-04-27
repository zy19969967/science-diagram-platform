function cleanLabel(value) {
  return String(value ?? "").trim().replace(/\s+/g, " ");
}

function uniqueLabels(labels = []) {
  const seen = new Set();
  const result = [];
  for (const label of labels.map(cleanLabel)) {
    const key = label.toLocaleLowerCase();
    if (!label || seen.has(key)) {
      continue;
    }
    seen.add(key);
    result.push(label);
  }
  return result;
}

export function deriveExpectedLabelsFromCanvasState(canvasState, { includeHiddenLayers = false } = {}) {
  if (!Array.isArray(canvasState?.layers)) {
    return [];
  }
  return uniqueLabels(
    canvasState.layers
      .filter((layer) => layer?.type === "text")
      .filter((layer) => includeHiddenLayers || layer.visible !== false)
      .map((layer) => layer?.data?.text),
  );
}

export function buildTextValidationPayload({
  canvasState,
  expectedLabels,
  ocrObservations = [],
  includeHiddenLayers = false,
}) {
  if (!canvasState) {
    throw new Error("A canvas_state is required for text validation.");
  }
  return {
    canvas_state: canvasState,
    expected_labels: uniqueLabels(
      Array.isArray(expectedLabels) && expectedLabels.length > 0
        ? expectedLabels
        : deriveExpectedLabelsFromCanvasState(canvasState, { includeHiddenLayers }),
    ),
    ocr_observations: Array.isArray(ocrObservations) ? ocrObservations : [],
    include_hidden_layers: includeHiddenLayers,
  };
}

export function buildCanvasExportPayload({
  canvasState,
  expectedLabels,
  ocrObservations = [],
  includeHiddenLayers = false,
  filename = "science-diagram.svg",
}) {
  return {
    ...buildTextValidationPayload({
      canvasState,
      expectedLabels,
      ocrObservations,
      includeHiddenLayers,
    }),
    filename: cleanLabel(filename) || "science-diagram.svg",
  };
}

export function buildSvgDownloadDescriptor(response) {
  const content = String(response?.svg ?? "");
  return {
    filename: cleanLabel(response?.filename) || "science-diagram.svg",
    mimeType: response?.mime_type || "image/svg+xml",
    content,
    size: content.length,
  };
}
