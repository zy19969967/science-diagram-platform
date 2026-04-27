import assert from "node:assert/strict";

import {
  addRegionPoint,
  normalizeRegionPoints,
  removeRegionPoint,
} from "../src/regionPrompts.js";

const points = normalizeRegionPoints([
  { id: "keep", x: 1.2, y: -0.2, label: "positive" },
  { x: 0.25, y: 0.75, label: "negative" },
  { x: 0.5, y: 0.5, label: "ignored" },
]);

assert.equal(points.length, 2);
assert.deepEqual(points[0], { id: "keep", x: 1, y: 0, label: "positive" });
assert.equal(points[1].label, "negative");
assert.equal(points[1].id, "point-2");

const appended = addRegionPoint(points, { x: 0.3333, y: 0.6666, label: "positive" });
assert.equal(appended.length, 3);
assert.equal(appended[2].x, 0.3333);
assert.equal(appended[2].y, 0.6666);
assert.equal(appended[2].label, "positive");
assert.equal(appended[2].id, "point-3");

const removed = removeRegionPoint(appended, "keep");
assert.equal(removed.length, 2);
assert.equal(removed.some((point) => point.id === "keep"), false);
