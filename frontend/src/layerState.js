const BASE_LAYER_ID = "base-image";
const CLEAN_OVERRIDE_DEFAULTS = {
  visible: true,
  locked: false,
  opacity: 1,
};

const clamp = (value, min, max) => Math.min(max, Math.max(min, value));

function cleanOverridePatch(patch = {}) {
  const result = {};
  if (typeof patch.visible === "boolean" && patch.visible !== CLEAN_OVERRIDE_DEFAULTS.visible) {
    result.visible = patch.visible;
  }
  if (typeof patch.locked === "boolean" && patch.locked !== CLEAN_OVERRIDE_DEFAULTS.locked) {
    result.locked = patch.locked;
  }
  if (typeof patch.opacity === "number") {
    const opacity = clamp(patch.opacity, 0, 1);
    if (opacity !== CLEAN_OVERRIDE_DEFAULTS.opacity) {
      result.opacity = opacity;
    }
  }
  return result;
}

export function normalizeLayerOrder(layerOrder = [], layerIds = []) {
  const validIds = layerIds.filter(Boolean);
  if (!validIds.includes(BASE_LAYER_ID)) {
    return validIds;
  }
  const validSet = new Set(validIds);
  const ordered = [BASE_LAYER_ID];
  for (const layerId of layerOrder) {
    if (layerId !== BASE_LAYER_ID && validSet.has(layerId) && !ordered.includes(layerId)) {
      ordered.push(layerId);
    }
  }
  for (const layerId of validIds) {
    if (layerId !== BASE_LAYER_ID && !ordered.includes(layerId)) {
      ordered.push(layerId);
    }
  }
  return ordered;
}

export function sortLayersByOrder(layers = [], layerOrder = []) {
  const byId = new Map(layers.map((layer) => [layer.id, layer]));
  return normalizeLayerOrder(
    layerOrder,
    layers.map((layer) => layer.id),
  )
    .map((layerId) => byId.get(layerId))
    .filter(Boolean);
}

export function moveLayerInOrder(layerIds = [], layerId, direction) {
  const order = normalizeLayerOrder(layerIds, layerIds);
  const from = order.indexOf(layerId);
  if (from <= 0 || layerId === BASE_LAYER_ID) {
    return order;
  }
  const delta = direction === "up" ? 1 : direction === "down" ? -1 : 0;
  const to = from + delta;
  if (to <= 0 || to >= order.length) {
    return order;
  }
  const next = [...order];
  const [removed] = next.splice(from, 1);
  next.splice(to, 0, removed);
  return next;
}

export function patchLayerOverrides(layerOverrides = {}, layerId, patch = {}) {
  const current = layerOverrides[layerId] ?? {};
  const merged = cleanOverridePatch({ ...current, ...patch });
  const next = { ...layerOverrides };
  if (Object.keys(merged).length === 0) {
    delete next[layerId];
  } else {
    next[layerId] = merged;
  }
  return next;
}

export function applyLayerOverrides(layer, layerOverrides = {}) {
  const override = layerOverrides[layer.id] ?? {};
  return {
    ...layer,
    visible: typeof override.visible === "boolean" ? override.visible : layer.visible,
    locked: typeof override.locked === "boolean" ? override.locked : layer.locked,
    opacity: typeof override.opacity === "number" ? clamp(override.opacity, 0, 1) : layer.opacity,
  };
}

export function buildEditorLayers({
  sourceImage,
  hasMask = false,
  selectedAsset,
  assetPlacement,
  textLayers = [],
  pointPrompts = [],
  layerOrder = [],
  layerOverrides = {},
}) {
  if (!sourceImage) {
    return [];
  }

  const layers = [
    {
      id: BASE_LAYER_ID,
      type: "base-image",
      name: "Base image",
      visible: true,
      locked: true,
      opacity: 1,
      selectable: false,
      reorderable: false,
    },
  ];

  if (hasMask) {
    layers.push({
      id: "mask-current",
      type: "mask",
      name: "Current mask",
      visible: true,
      locked: false,
      opacity: 0.58,
      selectable: true,
      reorderable: true,
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
      selectable: true,
      reorderable: true,
    });
  }

  if ((pointPrompts ?? []).length > 0) {
    layers.push({
      id: "region-prompts",
      type: "region-prompt",
      name: "SAM point prompts",
      visible: true,
      locked: false,
      opacity: 1,
      selectable: false,
      reorderable: true,
    });
  }

  for (const [index, layer] of (textLayers ?? []).entries()) {
    layers.push({
      id: layer.id || `text-${index + 1}`,
      type: "text",
      name: layer.name || `Label ${index + 1}`,
      visible: layer.visible !== false,
      locked: Boolean(layer.locked),
      opacity: typeof layer.opacity === "number" ? clamp(layer.opacity, 0, 1) : 1,
      selectable: true,
      reorderable: true,
    });
  }

  return sortLayersByOrder(
    layers.map((layer) => applyLayerOverrides(layer, layerOverrides)),
    layerOrder,
  );
}
