import assert from "node:assert/strict";
import {
  INSPECTOR_TABS,
  WHITEBOARD_TOOL_MODES,
  WORKSPACE_COPY,
  inspectorTabLabels,
  whiteboardToolModeValues,
} from "../src/uiPresentation.js";

assert.deepEqual(whiteboardToolModeValues(), [
  "brush",
  "erase",
  "layer",
  "positive-point",
  "negative-point",
]);

assert.deepEqual(inspectorTabLabels(), ["结果", "项目", "导出", "实验"]);

assert.equal(WORKSPACE_COPY.appName, "科学图白板");
assert.equal(WORKSPACE_COPY.leftRailTitle, "生成与输入");
assert.equal(WORKSPACE_COPY.canvasTitle, "白板画布");
assert.equal(WORKSPACE_COPY.inspectorTitle, "检查器");

assert.equal(WHITEBOARD_TOOL_MODES[0].label, "画笔");
assert.equal(WHITEBOARD_TOOL_MODES[1].label, "橡皮");
assert.equal(INSPECTOR_TABS[0].value, "result");
