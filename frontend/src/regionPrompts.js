const VALID_LABELS = new Set(["positive", "negative"]);
const MAX_REGION_POINTS = 32;

const clamp = (value, min, max) => Math.min(max, Math.max(min, value));

function normalizePoint(point, index) {
  const label = VALID_LABELS.has(point?.label) ? point.label : "";
  if (!label) {
    return null;
  }
  return {
    id: point?.id || `point-${index + 1}`,
    x: clamp(Number(point?.x ?? 0), 0, 1),
    y: clamp(Number(point?.y ?? 0), 0, 1),
    label,
  };
}

export function normalizeRegionPoints(points = []) {
  return (points ?? [])
    .map((point, index) => normalizePoint(point, index))
    .filter(Boolean)
    .slice(0, MAX_REGION_POINTS);
}

export function addRegionPoint(points = [], point) {
  const normalized = normalizeRegionPoints(points);
  if (normalized.length >= MAX_REGION_POINTS) {
    return normalized;
  }
  const nextPoint = normalizePoint({ ...point, id: point?.id || `point-${normalized.length + 1}` }, normalized.length);
  return nextPoint ? [...normalized, nextPoint] : normalized;
}

export function removeRegionPoint(points = [], pointId) {
  return normalizeRegionPoints(points).filter((point) => point.id !== pointId);
}
