import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

const styles = readFileSync(fileURLToPath(new URL("../src/styles.css", import.meta.url)), "utf8");
const appSource = readFileSync(fileURLToPath(new URL("../src/App.jsx", import.meta.url)), "utf8");

function blockFor(selector) {
  const escaped = selector.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const matches = Array.from(styles.matchAll(new RegExp(`${escaped}\\s*\\{([^}]*)\\}`, "gm")));
  assert.ok(matches.length > 0, `Expected CSS block for ${selector}`);
  return matches.at(-1)[1];
}

const canvasStack = blockFor(".canvas-stack");
assert.match(canvasStack, /max-width:\s*100%/, "editor canvas stack should not overflow the visible work area");

const resultPreviewImage = blockFor(".result-panel.whiteboard-inspector .result-preview img");
assert.match(resultPreviewImage, /object-fit:\s*contain/, "result preview should show the whole generated image");
assert.match(resultPreviewImage, /height:\s*auto/, "result preview images should keep their natural aspect ratio");
assert.match(resultPreviewImage, /max-height:\s*none/, "result preview should not clamp generated images to a cropped panel height");
assert.doesNotMatch(resultPreviewImage, /object-fit:\s*cover/, "result preview must not crop generated images");

const resultPreview = blockFor(".result-panel.whiteboard-inspector .result-preview");
assert.match(resultPreview, /aspect-ratio:\s*auto/, "result preview should not force generated images into a fixed frame");
assert.match(resultPreview, /overflow:\s*visible/, "result preview should not hide parts of generated images");

const historyImage = blockFor(".history-card img");
assert.match(historyImage, /object-fit:\s*contain/, "history result thumbnails should show the full generated image");

const applyGenerateResult = appSource.slice(
  appSource.indexOf("function applyGenerateResult"),
  appSource.indexOf("async function refreshProjects"),
);
assert.ok(applyGenerateResult.includes("setLatestResult(data);"));
assert.ok(!applyGenerateResult.includes("setSourceImage(data.result_image)"));
