export const WHITEBOARD_TOOL_MODES = [
  { value: "brush", label: "画笔", icon: "brush" },
  { value: "erase", label: "橡皮", icon: "eraser" },
  { value: "layer", label: "图层", icon: "layers" },
  { value: "positive-point", label: "正点", icon: "plus" },
  { value: "negative-point", label: "负点", icon: "minus" },
];

export const INSPECTOR_TABS = [
  { value: "result", label: "结果" },
  { value: "project", label: "项目" },
  { value: "export", label: "导出" },
  { value: "benchmark", label: "实验" },
];

export const WORKSPACE_COPY = {
  appName: "科学图白板",
  leftRailTitle: "生成与输入",
  canvasTitle: "白板画布",
  inspectorTitle: "检查器",
};

export function whiteboardToolModeValues() {
  return WHITEBOARD_TOOL_MODES.map((mode) => mode.value);
}

export function inspectorTabLabels() {
  return INSPECTOR_TABS.map((tab) => tab.label);
}
