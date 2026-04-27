const DEFAULT_TEXT_POSITIONS = [
  { x: 0.2, y: 0.22 },
  { x: 0.5, y: 0.22 },
  { x: 0.8, y: 0.22 },
  { x: 0.32, y: 0.68 },
  { x: 0.68, y: 0.68 },
  { x: 0.5, y: 0.84 },
];

const clamp = (value, min, max) => Math.min(max, Math.max(min, value));

function isDataUrl(value) {
  return typeof value === "string" && value.startsWith("data:");
}

function isCurrentResult({ latestResult, sourceImage }) {
  return Boolean(latestResult?.result_image && latestResult.result_image === sourceImage);
}

function inferSource({ latestResult, selectedInitCandidateId, sourceImage }) {
  if (isCurrentResult({ latestResult, sourceImage })) {
    return "history";
  }
  if (selectedInitCandidateId) {
    return "init-candidate";
  }
  return "upload";
}

function inferCanvasId({ latestResult, selectedInitCandidateId, naturalSize, sourceImage }) {
  if (isCurrentResult({ latestResult, sourceImage }) && latestResult?.canvas_state?.canvas_id) {
    return latestResult.canvas_state.canvas_id;
  }
  if (selectedInitCandidateId) {
    return `canvas-${selectedInitCandidateId}`;
  }
  if (isCurrentResult({ latestResult, sourceImage })) {
    return `canvas-${latestResult.run_id}`;
  }
  return `canvas-upload-${naturalSize.width}x${naturalSize.height}`;
}

function buildHistory({ source, selectedInitCandidateId, latestResult, sourceImage }) {
  const existing = latestResult?.canvas_state?.history;
  if (isCurrentResult({ latestResult, sourceImage }) && Array.isArray(existing) && existing.length > 0) {
    return [...existing];
  }
  if (source === "init-candidate" && selectedInitCandidateId) {
    return [selectedInitCandidateId];
  }
  return [];
}

function normalizeTextLayer(layer, index) {
  const position = DEFAULT_TEXT_POSITIONS[index % DEFAULT_TEXT_POSITIONS.length];
  const data = layer?.data ?? {};
  return {
    id: layer?.id || `text-${index + 1}`,
    type: "text",
    name: layer?.name || `Label ${index + 1}`,
    visible: layer?.visible !== false,
    locked: Boolean(layer?.locked),
    opacity: typeof layer?.opacity === "number" ? clamp(layer.opacity, 0, 1) : 1,
    data: {
      text: String(data.text ?? ""),
      x: typeof data.x === "number" ? clamp(data.x, 0, 1) : position.x,
      y: typeof data.y === "number" ? clamp(data.y, 0, 1) : position.y,
      font_size: typeof data.font_size === "number" ? data.font_size : 22,
      color: data.color || "#18324c",
      background: data.background || "rgba(255, 255, 255, 0.82)",
      align: data.align || "center",
    },
  };
}

export function createTextLayersFromLabels(labels = []) {
  return labels
    .map((label) => String(label ?? "").trim())
    .filter(Boolean)
    .slice(0, DEFAULT_TEXT_POSITIONS.length)
    .map((label, index) =>
      normalizeTextLayer(
        {
          id: `text-${index + 1}`,
          name: `Label ${index + 1}`,
          data: {
            text: label,
            ...DEFAULT_TEXT_POSITIONS[index],
          },
        },
        index,
      ),
    );
}

export function extractTextLayersFromCanvasState(canvasState) {
  if (!Array.isArray(canvasState?.layers)) {
    return [];
  }
  return canvasState.layers
    .filter((layer) => layer?.type === "text")
    .map((layer, index) => normalizeTextLayer(layer, index));
}

export function createCanvasStateSnapshot({
  sourceImage,
  naturalSize,
  selectedInitCandidateId,
  latestResult,
  maskPayload,
  selectedAsset,
  assetPlacement,
  textLayers,
  instruction,
  task,
  initPlan,
  seed,
  plan,
}) {
  const width = Number(naturalSize?.width) || 0;
  const height = Number(naturalSize?.height) || 0;
  if (!sourceImage || width <= 0 || height <= 0) {
    return null;
  }

  const source = inferSource({ latestResult, selectedInitCandidateId, sourceImage });
  const currentRunId = isCurrentResult({ latestResult, sourceImage }) ? latestResult.run_id : null;
  const layers = [
    {
      id: "base-image",
      type: "base-image",
      name: source === "upload" ? "Uploaded source" : "Canvas source",
      visible: true,
      locked: true,
      opacity: 1,
      data: {
        source,
        image_url: isDataUrl(sourceImage) ? null : sourceImage,
        embedded_source_image: isDataUrl(sourceImage),
        selected_init_candidate_id: selectedInitCandidateId || null,
        run_id: currentRunId,
      },
    },
  ];

  if (maskPayload?.pixelCount > 0) {
    layers.push({
      id: "mask-current",
      type: "mask",
      name: "Current mask",
      visible: true,
      locked: false,
      opacity: 0.58,
      data: {
        mask_image: isDataUrl(maskPayload.dataUrl) ? null : maskPayload.dataUrl,
        embedded_mask_image: isDataUrl(maskPayload.dataUrl),
        pixel_count: maskPayload.pixelCount,
      },
    });
  }

  if (selectedAsset && assetPlacement) {
    layers.push({
      id: `asset-${assetPlacement.asset_id}`,
      type: "asset",
      name: selectedAsset.name || assetPlacement.asset_id,
      visible: true,
      locked: false,
      opacity: 1,
      data: {
        ...assetPlacement,
        asset_name: selectedAsset.name,
        image_url: selectedAsset.image_url,
      },
    });
  }

  layers.push(...(textLayers ?? []).map((layer, index) => normalizeTextLayer(layer, index)));

  return {
    canvas_id: inferCanvasId({ latestResult, selectedInitCandidateId, naturalSize: { width, height }, sourceImage }),
    width,
    height,
    source,
    layers,
    history: buildHistory({ source, selectedInitCandidateId, latestResult, sourceImage }),
    metadata: {
      instruction,
      task,
      seed,
      selected_asset_id: assetPlacement?.asset_id ?? selectedAsset?.id ?? null,
      selected_init_candidate_id: selectedInitCandidateId || null,
      init_provider: initPlan?.provider ?? null,
      init_diagram_type: initPlan?.diagram_type ?? null,
      latest_run_id: currentRunId,
      plan_task: plan?.task ?? null,
    },
  };
}
