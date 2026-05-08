import { useEffect, useMemo, useRef, useState } from "react";
import ControlPanel from "./components/ControlPanel";
import EditorStage from "./components/EditorStage";
import HeaderBar from "./components/HeaderBar";
import ResultPanel from "./components/ResultPanel";
import {
  createCanvasStateSnapshot,
  extractPointPromptsFromCanvasState,
  createTextLayersFromLabels,
  extractTextLayersFromCanvasState,
} from "./canvasState.js";
import {
  buildEditorLayers,
  moveLayerInOrder,
  normalizeLayerOrder,
  patchLayerOverrides,
} from "./layerState.js";
import { addRegionPoint, normalizeRegionPoints, removeRegionPoint } from "./regionPrompts.js";
import {
  buildCanvasExportPayload,
  buildSvgDownloadDescriptor,
  buildTextValidationPayload,
} from "./exportState.js";
import {
  buildProjectCreatePayload,
  buildProjectVersionPayload,
  canSaveReloadableProjectVersion,
  latestProjectVersion,
} from "./projectState.js";
import { buildBenchmarkRecordPayload } from "./benchmarkState.js";
import { apiFetch } from "./apiClient.js";
import {
  buildSmartGenerationPayload,
  GENERATION_PROVIDER_OPTIONS,
  primaryActionLabel,
  summarizeSmartGenerationStatus,
} from "./smartGeneration.js";

const TASK_OPTIONS = [
  { value: "text-guided", label: "文本插入" },
  { value: "object-removal", label: "对象移除" },
  { value: "shape-guided", label: "形状引导" },
  { value: "image-outpainting", label: "图像扩展" },
];

const SMART_TASK_OPTIONS = [
  { value: "", label: "自动判断" },
  { value: "text_to_image", label: "文生图" },
  { value: "image_variation", label: "整体改图" },
  { value: "local_inpaint", label: "局部修改" },
  { value: "outpainting", label: "扩图" },
  { value: "svg_or_structure_generation", label: "结构化图" },
];

const clamp = (value, min, max) => Math.min(max, Math.max(min, value));

function loadImage(source) {
  return new Promise((resolve, reject) => {
    const image = new Image();
    image.crossOrigin = "anonymous";
    image.onload = () => resolve(image);
    image.onerror = reject;
    image.src = source;
  });
}

function readFileAsDataUrl(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
}

function readBlobAsDataUrl(blob) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = reject;
    reader.readAsDataURL(blob);
  });
}

async function readImageSourceAsDataUrl(source) {
  if (!source || source.startsWith("data:")) {
    return source || "";
  }
  const response = await fetch(source);
  if (!response.ok) {
    throw new Error("Unable to load saved project image artifact.");
  }
  return readBlobAsDataUrl(await response.blob());
}

function App() {
  const [assets, setAssets] = useState([]);
  const [sourceImage, setSourceImage] = useState("");
  const [instruction, setInstruction] = useState("");
  const [task, setTask] = useState("text-guided");
  const [taskOverride, setTaskOverride] = useState("");
  const [generationProvider, setGenerationProvider] = useState("qwen-image");
  const [brushSize, setBrushSize] = useState(24);
  const [drawMode, setDrawMode] = useState("brush");
  const [steps, setSteps] = useState(25);
  const [guidanceScale, setGuidanceScale] = useState(5.0);
  const [fittingDegree, setFittingDegree] = useState(0.9);
  const [seed, setSeed] = useState(() => Math.floor(Math.random() * 2147483647));
  const [horizontalExpansionRatio, setHorizontalExpansionRatio] = useState(1.2);
  const [verticalExpansionRatio, setVerticalExpansionRatio] = useState(1.2);
  const [selectedAssetId, setSelectedAssetId] = useState("");
  const [assetPlacement, setAssetPlacement] = useState(null);
  const [plan, setPlan] = useState(null);
  const [initPlan, setInitPlan] = useState(null);
  const [initGeneration, setInitGeneration] = useState(null);
  const [initCandidates, setInitCandidates] = useState([]);
  const [selectedInitCandidateId, setSelectedInitCandidateId] = useState("");
  const [textLayers, setTextLayers] = useState([]);
  const [pointPrompts, setPointPrompts] = useState([]);
  const [layerOrder, setLayerOrder] = useState([]);
  const [layerOverrides, setLayerOverrides] = useState({});
  const [activeLayerId, setActiveLayerId] = useState("");
  const [latestResult, setLatestResult] = useState(null);
  const [history, setHistory] = useState([]);
  const [projects, setProjects] = useState([]);
  const [currentProject, setCurrentProject] = useState(null);
  const [benchmarkRuns, setBenchmarkRuns] = useState([]);
  const [benchmarkSummary, setBenchmarkSummary] = useState(null);
  const [status, setStatus] = useState("等待上传图像与绘制选区");
  const [error, setError] = useState("");
  const [isInitializing, setIsInitializing] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const [isJobGenerating, setIsJobGenerating] = useState(false);
  const [isSavingProject, setIsSavingProject] = useState(false);
  const [isLoadingProjects, setIsLoadingProjects] = useState(false);
  const [isLoadingBenchmarks, setIsLoadingBenchmarks] = useState(false);
  const [isRecordingBenchmark, setIsRecordingBenchmark] = useState(false);
  const [jobSnapshot, setJobSnapshot] = useState(null);
  const [smartJobSnapshot, setSmartJobSnapshot] = useState(null);
  const [textValidationReport, setTextValidationReport] = useState(null);
  const [svgExport, setSvgExport] = useState(null);
  const [isValidatingText, setIsValidatingText] = useState(false);
  const [isExportingSvg, setIsExportingSvg] = useState(false);
  const [naturalSize, setNaturalSize] = useState({ width: 0, height: 0 });
  const [displayScale, setDisplayScale] = useState(1);

  const imageRef = useRef(null);
  const maskCanvasRef = useRef(null);
  const drawingRef = useRef(false);
  const lastPointRef = useRef(null);
  const dragActiveRef = useRef(false);
  const jobTokenRef = useRef(0);
  const maskSyncTokenRef = useRef(0);

  const selectedAsset = useMemo(
    () => assets.find((item) => item.id === selectedAssetId) ?? null,
    [assets, selectedAssetId],
  );
  const editorLayers = useMemo(
    () =>
      buildEditorLayers({
        sourceImage,
        hasMask: Boolean(sourceImage),
        selectedAsset,
        assetPlacement,
        textLayers,
        pointPrompts,
        layerOrder,
        layerOverrides,
      }),
    [sourceImage, selectedAsset, assetPlacement, textLayers, pointPrompts, layerOrder, layerOverrides],
  );
  const editorLayerIds = useMemo(() => editorLayers.map((layer) => layer.id), [editorLayers]);

  useEffect(() => {
    async function fetchAssets() {
      try {
        const response = await apiFetch("/api/assets");
        const data = await response.json();
        setAssets(data);
      } catch {
        setAssets([]);
        setStatus("素材库暂不可用，可继续编辑。");
      }
    }

    fetchAssets();
  }, []);

  useEffect(() => {
    refreshProjects();
  }, []);

  useEffect(() => {
    refreshBenchmarks();
  }, []);

  useEffect(() => {
    if (!sourceImage) {
      setNaturalSize({ width: 0, height: 0 });
      return;
    }

    loadImage(sourceImage)
      .then((image) => {
        setNaturalSize({ width: image.naturalWidth, height: image.naturalHeight });
        window.requestAnimationFrame(() => syncCanvasToImage(image.naturalWidth, image.naturalHeight));
      })
      .catch(() => setError("无法读取当前图像，请重新上传。"));
  }, [sourceImage]);

  useEffect(() => {
    const handleMove = (event) => {
      if (!dragActiveRef.current || !imageRef.current || !assetPlacement) {
        return;
      }
      const rect = imageRef.current.getBoundingClientRect();
      const x = clamp((event.clientX - rect.left) / rect.width, 0.05, 0.95);
      const y = clamp((event.clientY - rect.top) / rect.height, 0.05, 0.95);
      setAssetPlacement((current) => (current ? { ...current, x, y } : current));
    };

    const handleUp = () => {
      dragActiveRef.current = false;
    };

    const handleResize = () => syncCanvasToImage(naturalSize.width, naturalSize.height);

    window.addEventListener("pointermove", handleMove);
    window.addEventListener("pointerup", handleUp);
    window.addEventListener("resize", handleResize);
    return () => {
      window.removeEventListener("pointermove", handleMove);
      window.removeEventListener("pointerup", handleUp);
      window.removeEventListener("resize", handleResize);
    };
  }, [assetPlacement, naturalSize]);

  useEffect(() => {
    if (!sourceImage) {
      return;
    }
    window.requestAnimationFrame(() => syncCanvasToImage(naturalSize.width, naturalSize.height));
  }, [displayScale, naturalSize, sourceImage]);

  useEffect(() => {
    setLayerOrder((current) => normalizeLayerOrder(current, editorLayerIds));
    setLayerOverrides((current) =>
      Object.fromEntries(Object.entries(current).filter(([layerId]) => editorLayerIds.includes(layerId))),
    );
    setActiveLayerId((current) => {
      if (!editorLayerIds.length) {
        return "";
      }
      return editorLayerIds.includes(current) ? current : editorLayerIds[0];
    });
  }, [editorLayerIds.join("|")]);

  useEffect(() => {
    setTextValidationReport(null);
    setSvgExport(null);
  }, [sourceImage, selectedInitCandidateId, latestResult?.run_id, textLayers, assetPlacement, layerOrder, layerOverrides]);

  function syncCanvasToImage(width = naturalSize.width, height = naturalSize.height) {
    const image = imageRef.current;
    const canvas = maskCanvasRef.current;
    if (!image || !canvas || !width || !height) {
      return;
    }

    const token = maskSyncTokenRef.current + 1;
    maskSyncTokenRef.current = token;
    const snapshot = canvas.toDataURL("image/png");
    canvas.width = width;
    canvas.height = height;
    canvas.style.width = `${image.clientWidth}px`;
    canvas.style.height = `${image.clientHeight}px`;

    if (snapshot !== "data:," && snapshot.length > 10) {
      loadImage(snapshot).then((maskImage) => {
        if (maskSyncTokenRef.current !== token) {
          return;
        }
        const context = canvas.getContext("2d");
        context.drawImage(maskImage, 0, 0, width, height);
      });
    }
  }

  function invalidateJobPolling() {
    jobTokenRef.current += 1;
    setIsJobGenerating(false);
    setSmartJobSnapshot(null);
  }

  function resetLayerEditorState() {
    setLayerOrder([]);
    setLayerOverrides({});
    setActiveLayerId("");
  }

  function restoreLayerEditorState(canvasState) {
    const layers = Array.isArray(canvasState?.layers) ? canvasState.layers : [];
    setLayerOrder(layers.map((layer) => layer.id).filter(Boolean));
    setLayerOverrides(
      layers.reduce((overrides, layer) => {
        if (!layer?.id || layer.id === "base-image") {
          return overrides;
        }
        const patch = {};
        if (layer.visible === false) {
          patch.visible = false;
        }
        if (layer.locked) {
          patch.locked = true;
        }
        if (typeof layer.opacity === "number" && layer.opacity !== 1) {
          patch.opacity = layer.opacity;
        }
        if (Object.keys(patch).length > 0) {
          overrides[layer.id] = patch;
        }
        return overrides;
      }, {}),
    );
  }

  function restoreRegionPrompts(canvasState) {
    setPointPrompts(normalizeRegionPoints(extractPointPromptsFromCanvasState(canvasState)));
  }

  function patchEditorLayer(layerId, patch) {
    setLayerOverrides((current) => patchLayerOverrides(current, layerId, patch));
    if (layerId.startsWith("text-")) {
      setTextLayers((current) =>
        current.map((layer) =>
          layer.id === layerId
            ? {
                ...layer,
                visible: typeof patch.visible === "boolean" ? patch.visible : layer.visible,
                locked: typeof patch.locked === "boolean" ? patch.locked : layer.locked,
                opacity: typeof patch.opacity === "number" ? patch.opacity : layer.opacity,
              }
            : layer,
        ),
      );
    }
  }

  function moveEditorLayer(layerId, direction) {
    setLayerOrder((current) => moveLayerInOrder(normalizeLayerOrder(current, editorLayerIds), layerId, direction));
  }

  function updateTextLayerFromFabric(layerId, patch) {
    setTextLayers((current) =>
      current.map((layer) =>
        layer.id === layerId
          ? {
              ...layer,
              data: {
                ...layer.data,
                ...patch,
              },
            }
          : layer,
      ),
    );
  }

  function updateAssetPlacementFromFabric(patch) {
    setAssetPlacement((current) => (current ? { ...current, ...patch } : current));
  }

  function addPointPromptFromCanvas(event, label) {
    if (!imageRef.current) {
      return;
    }
    const rect = imageRef.current.getBoundingClientRect();
    setPointPrompts((current) =>
      addRegionPoint(current, {
        x: (event.clientX - rect.left) / rect.width,
        y: (event.clientY - rect.top) / rect.height,
        label,
      }),
    );
    setStatus(label === "positive" ? "已添加 SAM 正点提示" : "已添加 SAM 负点提示");
  }

  function removePointPrompt(pointId) {
    setPointPrompts((current) => removeRegionPoint(current, pointId));
    setStatus("已移除 SAM 点提示");
  }

  function clearMask() {
    maskSyncTokenRef.current += 1;
    const canvas = maskCanvasRef.current;
    if (!canvas) {
      return;
    }
    const context = canvas.getContext("2d");
    context.clearRect(0, 0, canvas.width, canvas.height);
    setStatus("已清空当前选区");
  }

  function clearCanvasWorkspace() {
    invalidateJobPolling();
    const canvas = maskCanvasRef.current;
    if (canvas) {
      const context = canvas.getContext("2d");
      context.clearRect(0, 0, canvas.width, canvas.height);
    }
    setSourceImage("");
    setSelectedAssetId("");
    setAssetPlacement(null);
    setPlan(null);
    setInitPlan(null);
    setInitGeneration(null);
    setInitCandidates([]);
    setSelectedInitCandidateId("");
    setTextLayers([]);
    setPointPrompts([]);
    resetLayerEditorState();
    setJobSnapshot(null);
    setSmartJobSnapshot(null);
    setTextValidationReport(null);
    setSvgExport(null);
    setLatestResult(null);
    setHistory([]);
    setCurrentProject(null);
    setNaturalSize({ width: 0, height: 0 });
    setDisplayScale(1);
    dragActiveRef.current = false;
    setStatus("已清除当前画布");
    setError("");
  }

  function resetWorkspace() {
    setSelectedAssetId("");
    setAssetPlacement(null);
    clearMask();
  }

  async function handleUpload(event) {
    const file = event.target.files?.[0];
    if (!file) {
      return;
    }
    invalidateJobPolling();
    const dataUrl = await readFileAsDataUrl(file);
    setSourceImage(dataUrl);
    setLatestResult(null);
    setPlan(null);
    setInitPlan(null);
    setInitGeneration(null);
    setInitCandidates([]);
    setSelectedInitCandidateId("");
    setTextLayers([]);
    setPointPrompts([]);
    resetLayerEditorState();
    setJobSnapshot(null);
    setSmartJobSnapshot(null);
    setTextValidationReport(null);
    setSvgExport(null);
    setHistory([]);
    setCurrentProject(null);
    setDisplayScale(1);
    setStatus("图像已载入，可以开始涂抹 mask 或拖拽素材。");
    setError("");
    resetWorkspace();
  }

  async function readJsonResponse(response, fallbackMessage) {
    const contentType = response.headers.get("content-type") ?? "";
    if (contentType.includes("application/json")) {
      const body = await response.json();
      if (!response.ok) {
        throw new Error(body.detail ?? fallbackMessage);
      }
      return body;
    }
    const body = await response.text();
    if (!response.ok) {
      throw new Error(body || fallbackMessage);
    }
    return body;
  }

  function startDrawing(event) {
    if (!sourceImage || drawMode === "layer" || !maskCanvasRef.current) {
      return;
    }
    if (drawMode === "positive-point" || drawMode === "negative-point") {
      if (layerOverrides["region-prompts"]?.locked) {
        return;
      }
      addPointPromptFromCanvas(event, drawMode === "positive-point" ? "positive" : "negative");
      return;
    }
    if (layerOverrides["mask-current"]?.locked) {
      return;
    }

    drawingRef.current = true;
    drawOnCanvas(event);
  }

  function drawOnCanvas(event) {
    if (!drawingRef.current || !maskCanvasRef.current || !imageRef.current) {
      return;
    }

    const canvas = maskCanvasRef.current;
    const image = imageRef.current;
    const context = canvas.getContext("2d");
    const rect = image.getBoundingClientRect();
    const scaleX = canvas.width / rect.width;
    const scaleY = canvas.height / rect.height;
    const x = (event.clientX - rect.left) * scaleX;
    const y = (event.clientY - rect.top) * scaleY;

    context.lineJoin = "round";
    context.lineCap = "round";
    context.lineWidth = brushSize * scaleX;
    context.globalCompositeOperation = drawMode === "erase" ? "destination-out" : "source-over";
    context.strokeStyle = "rgba(128,128,128,0.58)";

    if (!lastPointRef.current) {
      context.beginPath();
      context.moveTo(x, y);
      context.lineTo(x, y);
      context.stroke();
    } else {
      context.beginPath();
      context.moveTo(lastPointRef.current.x, lastPointRef.current.y);
      context.lineTo(x, y);
      context.stroke();
    }

    lastPointRef.current = { x, y };
  }

  function stopDrawing() {
    drawingRef.current = false;
    lastPointRef.current = null;
  }

  function chooseAsset(assetId) {
    const asset = assets.find((item) => item.id === assetId);
    setSelectedAssetId(assetId);
    setAssetPlacement({
      asset_id: assetId,
      x: 0.5,
      y: 0.52,
      width: assetId === "arrow" ? 0.28 : 0.22,
      height: assetId === "arrow" ? 0.12 : 0.22,
      rotation: 0,
    });
    if (task === "text-guided") {
      setTask("shape-guided");
    }
    setStatus(`已选中素材：${asset?.name ?? assetId}`);
  }

  function updateAssetScale(value) {
    setAssetPlacement((current) => {
      if (!current) {
        return current;
      }
      const ratio = Number(value);
      return {
        ...current,
        width: ratio,
        height: current.asset_id === "arrow" ? ratio * 0.45 : ratio,
      };
    });
  }

  async function buildMaskPayload() {
    const maskCanvas = maskCanvasRef.current;
    if (!maskCanvas || !naturalSize.width || !naturalSize.height) {
      return { dataUrl: "", pixelCount: 0 };
    }

    const mergedCanvas = document.createElement("canvas");
    mergedCanvas.width = naturalSize.width;
    mergedCanvas.height = naturalSize.height;
    const mergedContext = mergedCanvas.getContext("2d");
    if (layerOverrides["mask-current"]?.visible !== false) {
      mergedContext.drawImage(maskCanvas, 0, 0);
    }

    const assetLayerId = assetPlacement ? `asset-${assetPlacement.asset_id}` : "";
    if (selectedAsset && assetPlacement && layerOverrides[assetLayerId]?.visible !== false) {
      const assetImage = await loadImage(selectedAsset.image_url);
      const drawWidth = assetPlacement.width * naturalSize.width;
      const drawHeight = assetPlacement.height * naturalSize.height;
      const left = assetPlacement.x * naturalSize.width - drawWidth / 2;
      const top = assetPlacement.y * naturalSize.height - drawHeight / 2;

      const assetCanvas = document.createElement("canvas");
      assetCanvas.width = naturalSize.width;
      assetCanvas.height = naturalSize.height;
      const assetContext = assetCanvas.getContext("2d");
      assetContext.save();
      assetContext.translate(assetPlacement.x * naturalSize.width, assetPlacement.y * naturalSize.height);
      assetContext.rotate(((assetPlacement.rotation ?? 0) * Math.PI) / 180);
      assetContext.drawImage(assetImage, -drawWidth / 2, -drawHeight / 2, drawWidth, drawHeight);
      assetContext.restore();
      const imageData = assetContext.getImageData(0, 0, assetCanvas.width, assetCanvas.height);
      const pixels = imageData.data;
      for (let index = 0; index < pixels.length; index += 4) {
        if (pixels[index + 3] > 0) {
          pixels[index] = 255;
          pixels[index + 1] = 255;
          pixels[index + 2] = 255;
          pixels[index + 3] = 255;
        }
      }
      assetContext.putImageData(imageData, 0, 0);
      mergedContext.drawImage(assetCanvas, 0, 0);
    }

    const pixels = mergedContext.getImageData(0, 0, mergedCanvas.width, mergedCanvas.height).data;
    let pixelCount = 0;
    for (let index = 3; index < pixels.length; index += 4) {
      if (pixels[index] > 0) {
        pixelCount += 1;
      }
    }

    return {
      dataUrl: mergedCanvas.toDataURL("image/png"),
      pixelCount,
    };
  }

  async function analyzePlan() {
    setError("");
    try {
      const maskPayload = sourceImage ? await buildMaskPayload() : { dataUrl: "", pixelCount: 0 };
      const response = await apiFetch("/api/plan", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          source_image: sourceImage || null,
          instruction,
          preferred_task: task,
          selected_asset_id: selectedAssetId || null,
          canvas_hints: {
            has_mask: maskPayload.pixelCount > 0,
            has_asset: Boolean(assetPlacement),
            has_point_prompts: pointPrompts.length > 0,
            has_source_image: Boolean(sourceImage),
            image_width: naturalSize.width || null,
            image_height: naturalSize.height || null,
          },
        }),
      });

      if (!response.ok) {
        const body = await response.json();
        throw new Error(body.detail ?? "任务解析失败");
      }

      const data = await response.json();
      setPlan(data);
      setStatus(`规划完成：${data.reasoning}`);
    } catch (planError) {
      setError(planError.message);
      setStatus("任务解析失败，请检查网关与规划服务。");
    }
  }

  async function createInitialCanvas() {
    const prompt = instruction.trim();
    if (!prompt) {
      setError("请输入无图生成的科学示意图需求。");
      return;
    }

    invalidateJobPolling();
    setIsInitializing(true);
    setError("");
    setStatus("正在规划无图初始画布...");

    try {
      const planResponse = await apiFetch("/api/init-plan", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          instruction: prompt,
          width: 1024,
          height: 768,
          style: "clean scientific illustration, flat vector-like",
          candidate_count: 3,
          seed,
        }),
      });
      const scenePlan = await readJsonResponse(planResponse, "初图规划失败");

      const generateResponse = await apiFetch("/api/init-generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          scene_plan: scenePlan,
          seed,
        }),
      });
      const data = await readJsonResponse(generateResponse, "初图候选生成失败");

      setInitPlan(data.scene_plan);
      setInitGeneration(data);
      setInitCandidates(data.candidates);
      setSelectedInitCandidateId("");
      setTextLayers([]);
      setLatestResult(null);
      setHistory([]);
      setCurrentProject(null);
      setStatus(`已生成 ${data.candidates.length} 张初图候选，可选择一张进入编辑闭环。`);
    } catch (initError) {
      setError(initError.message);
      setStatus("无图初图生成失败，请检查网关服务。");
    } finally {
      setIsInitializing(false);
    }
  }

  async function buildGenerateRequestPayload() {
    if (!sourceImage) {
      throw new Error("请先上传原始图像或选择一张初图候选。");
    }

    const maskPayload = await buildMaskPayload();
    const assetLayerId = assetPlacement ? `asset-${assetPlacement.asset_id}` : "";
    const hasVisibleAssetPlacement = Boolean(
      selectedAsset && assetPlacement && layerOverrides[assetLayerId]?.visible !== false,
    );
    if (maskPayload.pixelCount === 0 && !hasVisibleAssetPlacement && pointPrompts.length === 0) {
      throw new Error("当前没有有效的 mask、素材位置或 SAM 点提示，请先绘制、选择素材或添加点提示。");
    }

    const canvasState = createCanvasStateSnapshot({
      sourceImage,
      naturalSize,
      selectedInitCandidateId,
      latestResult,
      maskPayload,
      selectedAsset,
      assetPlacement,
      textLayers,
      pointPrompts,
      instruction,
      task,
      initPlan,
      seed,
      plan,
      layerOrder,
      layerOverrides,
    });

    return {
      source_image: sourceImage,
      instruction,
      task,
      selected_asset_id: selectedAssetId || null,
      asset_placement: assetPlacement,
      mask_image: maskPayload.pixelCount > 0 ? maskPayload.dataUrl : null,
      point_prompts: pointPrompts,
      plan,
      steps,
      guidance_scale: guidanceScale,
      generation_provider: generationProvider,
      fitting_degree: fittingDegree,
      seed,
      horizontal_expansion_ratio: horizontalExpansionRatio,
      vertical_expansion_ratio: verticalExpansionRatio,
      canvas_state: canvasState,
    };
  }

  function applyGenerateResult(data, statusPrefix = "生成完成") {
    setPlan(data.plan);
    setLatestResult(data);
    if (data.result_image) {
      setSourceImage(data.result_image);
      setSelectedInitCandidateId("");
    }
    if (data.canvas_state) {
      setTextLayers(extractTextLayersFromCanvasState(data.canvas_state));
      restoreLayerEditorState(data.canvas_state);
    }
    setPointPrompts([]);
    setSelectedAssetId("");
    setAssetPlacement(null);
    clearMask();
    setHistory((current) => [data, ...current]);
    setStatus(`${statusPrefix}：${data.evaluation.note}`);
  }

  async function refreshProjects() {
    setIsLoadingProjects(true);
    try {
      const response = await apiFetch("/api/projects");
      const data = await readJsonResponse(response, "Project list loading failed");
      setProjects(data);
      return data;
    } catch (projectError) {
      setError(projectError.message);
      return [];
    } finally {
      setIsLoadingProjects(false);
    }
  }

  async function refreshBenchmarks() {
    setIsLoadingBenchmarks(true);
    try {
      const [summaryResponse, runsResponse] = await Promise.all([
        apiFetch("/api/benchmarks/summary"),
        apiFetch("/api/benchmarks/runs"),
      ]);
      const summary = await readJsonResponse(summaryResponse, "Benchmark summary loading failed");
      const runs = await readJsonResponse(runsResponse, "Benchmark runs loading failed");
      setBenchmarkSummary(summary);
      setBenchmarkRuns(runs);
      return { summary, runs };
    } catch (benchmarkError) {
      setError(benchmarkError.message);
      return { summary: null, runs: [] };
    } finally {
      setIsLoadingBenchmarks(false);
    }
  }

  async function recordBenchmarkRun() {
    setIsRecordingBenchmark(true);
    setError("");
    try {
      const payload = buildBenchmarkRecordPayload({
        latestResult,
        currentProject,
        selectedInitCandidateId,
        initGeneration,
        task,
        instruction,
        textValidationReport,
      });
      const response = await apiFetch("/api/benchmarks/runs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const recorded = await readJsonResponse(response, "Benchmark recording failed");
      await refreshBenchmarks();
      setStatus(`Benchmark recorded: ${recorded.benchmark_id}`);
    } catch (benchmarkError) {
      setError(benchmarkError.message);
      setStatus("Benchmark recording failed.");
    } finally {
      setIsRecordingBenchmark(false);
    }
  }

  async function buildCurrentProjectCanvasState() {
    if (!sourceImage) {
      return null;
    }
    const maskPayload = await buildMaskPayload();
    return createCanvasStateSnapshot({
      sourceImage,
      naturalSize,
      selectedInitCandidateId,
      latestResult,
      maskPayload,
      selectedAsset,
      assetPlacement,
      textLayers,
      pointPrompts,
      instruction,
      task,
      initPlan,
      seed,
      plan,
      layerOrder,
      layerOverrides,
    });
  }

  function mergeProjectIntoList(project) {
    setProjects((current) => {
      const withoutProject = current.filter((item) => item.project_id !== project.project_id);
      return [project, ...withoutProject];
    });
  }

  async function saveCurrentProjectVersion() {
    setIsSavingProject(true);
    setError("");
    try {
      const canvasState = await buildCurrentProjectCanvasState();
      if (!canvasState) {
        throw new Error("No canvas state is available to save.");
      }

      let project = currentProject;
      if (!project) {
        const createResponse = await apiFetch("/api/projects", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(
            buildProjectCreatePayload({
              instruction,
              naturalSize,
              sourceImage,
              initPlan,
              selectedInitCandidateId,
              latestResult,
            }),
          ),
        });
        project = await readJsonResponse(createResponse, "Project creation failed");
      }

      const versionResponse = await apiFetch(`/api/projects/${project.project_id}/versions`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(
          buildProjectVersionPayload({
            currentProject: project,
            canvasState,
            latestResult,
            selectedInitCandidateId,
            instruction,
            task,
          }),
        ),
      });
      const updatedProject = await readJsonResponse(versionResponse, "Project version saving failed");
      setCurrentProject(updatedProject);
      mergeProjectIntoList(updatedProject);
      setStatus(`Project saved: ${updatedProject.project_id}`);
    } catch (projectError) {
      setError(projectError.message);
      setStatus("Project save failed.");
    } finally {
      setIsSavingProject(false);
    }
  }

  function resultFromProjectVersion(version) {
    if (!version) {
      return null;
    }
    const resultImage = version.result_image || version.artifacts?.result || "";
    if (!resultImage) {
      return null;
    }
    return {
      run_id: version.run_id || version.version_id,
      plan: {
        task: version.metadata?.task || "text-guided",
        task_prompt: "",
        negative_prompt: "",
        reasoning: "Loaded from saved project version",
      },
      result_image: resultImage,
      evaluation: version.quality_report?.evaluation ?? {
        changed_ratio: 0,
        outside_mask_change_ratio: 0,
        note: "Loaded from saved project version",
      },
      artifacts: version.artifacts ?? {},
      canvas_state: version.canvas_state ?? null,
      quality_report: version.quality_report ?? null,
    };
  }

  async function loadProject(project) {
    invalidateJobPolling();
    setError("");
    try {
      const response = await apiFetch(`/api/projects/${project.project_id}`);
      const loadedProject = await readJsonResponse(response, "Project loading failed");
      const latestVersion = latestProjectVersion(loadedProject);
      const loadedResult = resultFromProjectVersion(latestVersion);
      const versionResults = [...(loadedProject.versions ?? [])]
        .reverse()
        .map((version) => resultFromProjectVersion(version))
        .filter(Boolean);
      const editableResult = loadedResult
        ? { ...loadedResult, result_image: await readImageSourceAsDataUrl(loadedResult.result_image) }
        : null;

      setCurrentProject(loadedProject);
      mergeProjectIntoList(loadedProject);
      setLatestResult(editableResult);
      setHistory(versionResults);
      setTextLayers(extractTextLayersFromCanvasState(latestVersion?.canvas_state));
      restoreRegionPrompts(latestVersion?.canvas_state);
      restoreLayerEditorState(latestVersion?.canvas_state);
      setInstruction(latestVersion?.metadata?.instruction || loadedProject.name || "");
      setTask(latestVersion?.metadata?.task || "text-guided");
      setInitPlan(loadedProject.init_plan ?? null);
      setInitGeneration(null);
      setInitCandidates([]);
      setSelectedInitCandidateId(
        latestVersion?.metadata?.selected_init_candidate_id || loadedProject.selected_candidate_id || "",
      );
      setSelectedAssetId("");
      setAssetPlacement(null);
      setPlan(null);
      setJobSnapshot(null);
      clearMask();
      dragActiveRef.current = false;
      setSourceImage(editableResult?.result_image || "");
      if (latestVersion?.canvas_state) {
        setNaturalSize({ width: latestVersion.canvas_state.width, height: latestVersion.canvas_state.height });
      }
      setStatus(`Project loaded: ${loadedProject.project_id}`);
    } catch (projectError) {
      setError(projectError.message);
      setStatus("Project load failed.");
    }
  }

  async function generateResult() {
    invalidateJobPolling();
    setIsGenerating(true);
    setError("");
    setStatus("正在调用 PowerPaint 生成结果...");

    try {
      const requestPayload = await buildGenerateRequestPayload();
      const response = await apiFetch("/api/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(requestPayload),
      });

      const data = await readJsonResponse(response, "生成失败");

      applyGenerateResult(data);
    } catch (generationError) {
      setError(generationError.message);
      setStatus("生成失败，请调整选区或提示词后重试。");
    } finally {
      setIsGenerating(false);
    }
  }

  async function pollSmartJobUntilComplete(jobId, token) {
    for (let attempt = 0; attempt < 240; attempt += 1) {
      await new Promise((resolve) => {
        window.setTimeout(resolve, 1500);
      });
      if (jobTokenRef.current !== token) {
        return null;
      }
      const response = await apiFetch(`/api/generation/jobs/${jobId}`);
      const snapshot = await readJsonResponse(response, "任务状态读取失败");
      if (jobTokenRef.current !== token) {
        return null;
      }
      setSmartJobSnapshot(snapshot);
      setStatus(summarizeSmartGenerationStatus(snapshot).label);

      if (["completed", "failed", "cancelled"].includes(snapshot.status)) {
        return snapshot;
      }
    }
    throw new Error("生成任务超时，请稍后刷新任务状态。");
  }

  function applySmartGenerationSnapshot(snapshot) {
    const summary = summarizeSmartGenerationStatus(snapshot);
    setSmartJobSnapshot(snapshot);
    setStatus(summary.label);
    if (summary.isFailed) {
      setError(snapshot.message || snapshot.error || "生成失败");
      return;
    }
    if (snapshot.generate_response) {
      applyGenerateResult(snapshot.generate_response, summary.hasDiagnosticResult ? "诊断结果" : "生成完成");
      return;
    }
    const firstResult = snapshot.results?.[0];
    if (firstResult?.image_url) {
      setSourceImage(firstResult.image_url);
      setLatestResult(null);
      setInitCandidates([]);
      setSelectedInitCandidateId("");
      setHistory([]);
      setStatus(summary.label);
      if (summary.hasDiagnosticResult) {
        setError("当前结果是诊断占位，不代表正式模型生成效果。");
      }
    }
  }

  async function runSmartGeneration() {
    const prompt = instruction.trim();
    if (!prompt) {
      setError("请输入你想生成或修改的内容。");
      return;
    }

    const token = jobTokenRef.current + 1;
    jobTokenRef.current = token;
    setIsJobGenerating(true);
    setError("");
    setSmartJobSnapshot(null);
    setStatus(sourceImage ? "正在提交图片修改任务..." : "正在提交文生图任务...");

    try {
      const maskPayload = sourceImage ? await buildMaskPayload() : { dataUrl: "", pixelCount: 0 };
      const requestPayload = buildSmartGenerationPayload({
        instruction: prompt,
        sourceImage,
        maskPayload,
        taskOverride,
        generationProvider,
        seed,
        steps,
        guidanceScale,
      });
      const response = await apiFetch("/api/generation/jobs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(requestPayload),
      });
      const created = await readJsonResponse(response, "生成任务创建失败");
      if (jobTokenRef.current !== token) {
        return;
      }
      setSmartJobSnapshot(created);
      setStatus(summarizeSmartGenerationStatus(created).label);

      const finalSnapshot = ["queued", "planning", "generating"].includes(created.status)
        ? await pollSmartJobUntilComplete(created.job_id, token)
        : created;
      if (!finalSnapshot || jobTokenRef.current !== token) {
        return;
      }
      applySmartGenerationSnapshot(finalSnapshot);
    } catch (smartError) {
      setError(smartError.message);
      setStatus("生成失败，请调整输入后重试。");
    } finally {
      if (jobTokenRef.current === token) {
        setIsJobGenerating(false);
      }
    }
  }

  async function validateCanvasText() {
    setIsValidatingText(true);
    setError("");
    setStatus("正在校验画布文本层...");
    try {
      const canvasState = await buildCurrentProjectCanvasState();
      if (!canvasState) {
        throw new Error("当前没有可校验的画布状态。");
      }
      const response = await apiFetch("/api/canvas/validate-text", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(buildTextValidationPayload({ canvasState })),
      });
      const report = await readJsonResponse(response, "文本校验失败");
      setTextValidationReport(report);
      setStatus(`文本校验完成：${report.status}`);
    } catch (validationError) {
      setError(validationError.message);
      setStatus("文本校验失败。");
    } finally {
      setIsValidatingText(false);
    }
  }

  function downloadSvgExport(exportResponse = svgExport) {
    if (!exportResponse?.svg) {
      return;
    }
    const descriptor = buildSvgDownloadDescriptor(exportResponse);
    const blob = new Blob([descriptor.content], { type: descriptor.mimeType });
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = descriptor.filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.URL.revokeObjectURL(url);
  }

  async function exportCanvasSvg() {
    setIsExportingSvg(true);
    setError("");
    setStatus("正在导出 SVG...");
    try {
      const canvasState = await buildCurrentProjectCanvasState();
      if (!canvasState) {
        throw new Error("当前没有可导出的画布状态。");
      }
      const response = await apiFetch("/api/canvas/export-svg", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(
          buildCanvasExportPayload({
            canvasState,
            filename: `${canvasState.canvas_id || "science-diagram"}.svg`,
          }),
        ),
      });
      const exportResponse = await readJsonResponse(response, "SVG 导出失败");
      setSvgExport(exportResponse);
      setTextValidationReport(exportResponse.text_report ?? null);
      downloadSvgExport(exportResponse);
      setStatus(`SVG 导出完成：${exportResponse.filename}`);
    } catch (exportError) {
      setError(exportError.message);
      setStatus("SVG 导出失败。");
    } finally {
      setIsExportingSvg(false);
    }
  }

  async function pollJobUntilComplete(jobId, token) {
    for (let attempt = 0; attempt < 240; attempt += 1) {
      await new Promise((resolve) => {
        window.setTimeout(resolve, 1500);
      });
      if (jobTokenRef.current !== token) {
        return null;
      }
      const response = await apiFetch(`/api/jobs/${jobId}`);
      const snapshot = await readJsonResponse(response, "任务状态读取失败");
      if (jobTokenRef.current !== token) {
        return null;
      }
      setJobSnapshot(snapshot);
      setStatus(`${snapshot.status}：${snapshot.message}`);

      if (snapshot.status === "DONE") {
        if (!snapshot.result) {
          throw new Error("任务已完成，但没有返回生成结果。");
        }
        return snapshot;
      }
      if (snapshot.status === "CANCELLED") {
        return snapshot;
      }
      if (snapshot.status === "FAILED") {
        throw new Error(snapshot.error || snapshot.message || "异步生成失败");
      }
    }
    throw new Error("异步生成超时，请稍后刷新任务状态。");
  }

  async function startGenerateJob() {
    const token = jobTokenRef.current + 1;
    jobTokenRef.current = token;
    setIsJobGenerating(true);
    setError("");
    setJobSnapshot(null);
    setStatus("正在提交异步生成任务...");

    try {
      const requestPayload = await buildGenerateRequestPayload();
      const response = await apiFetch("/api/jobs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          kind: "generate",
          generate_request: requestPayload,
        }),
      });
      const created = await readJsonResponse(response, "任务创建失败");
      if (jobTokenRef.current !== token) {
        return;
      }
      setJobSnapshot(created);
      setStatus(`任务已创建：${created.job_id}`);

      const completed = await pollJobUntilComplete(created.job_id, token);
      if (!completed) {
        return;
      }
      if (completed.status === "CANCELLED") {
        setStatus("Async generation job cancelled.");
        return;
      }
      applyGenerateResult(completed.result, "异步生成完成");
    } catch (jobError) {
      setError(jobError.message);
      setStatus("异步生成失败，请查看任务状态或调整输入后重试。");
    } finally {
      if (jobTokenRef.current === token) {
        setIsJobGenerating(false);
      }
    }
  }

  async function cancelGenerateJob() {
    const activeSmartJob = smartJobSnapshot?.job_id ? smartJobSnapshot : null;
    const activeLegacyJob = jobSnapshot?.job_id ? jobSnapshot : null;
    if (!activeSmartJob && !activeLegacyJob) {
      return;
    }
    const isSmartJob = Boolean(activeSmartJob);
    const jobId = isSmartJob ? activeSmartJob.job_id : activeLegacyJob.job_id;
    invalidateJobPolling();
    setIsJobGenerating(false);
    setError("");
    try {
      const response = await apiFetch(isSmartJob ? `/api/generation/jobs/${jobId}/cancel` : `/api/jobs/${jobId}/cancel`, {
        method: "POST",
      });
      const snapshot = await readJsonResponse(response, "任务取消失败");
      if (isSmartJob) {
        setSmartJobSnapshot(snapshot);
      } else {
        setJobSnapshot(snapshot);
      }
      setStatus(`任务已取消：${snapshot.job_id}`);
    } catch (cancelError) {
      setIsJobGenerating(false);
      setError(cancelError.message);
      setStatus("任务取消失败。");
    }
  }

  async function continueFromHistory(item) {
    invalidateJobPolling();
    setError("");
    try {
      const editableImage = await readImageSourceAsDataUrl(item.result_image);
      const editableItem = { ...item, result_image: editableImage };
      setSourceImage(editableImage);
      setLatestResult(editableItem);
      setTextLayers(extractTextLayersFromCanvasState(item.canvas_state));
      setPointPrompts([]);
      restoreLayerEditorState(item.canvas_state);
      clearMask();
      setStatus(`已切换到历史结果 ${item.run_id}，可以继续多轮编辑。`);
    } catch (historyError) {
      setError(historyError.message);
      setStatus("History result loading failed.");
    }
  }

  function chooseInitCandidate(candidate) {
    invalidateJobPolling();
    const canvas = maskCanvasRef.current;
    if (canvas) {
      const context = canvas.getContext("2d");
      context.clearRect(0, 0, canvas.width, canvas.height);
    }
    setSourceImage(candidate.image);
    setLatestResult(null);
    setPlan(null);
    setHistory([]);
    setJobSnapshot(null);
    setCurrentProject(null);
    setSelectedInitCandidateId(candidate.id);
    setTextLayers(createTextLayersFromLabels(initPlan?.labels ?? candidate.metadata?.labels ?? []));
    setPointPrompts([]);
    resetLayerEditorState();
    setSelectedAssetId("");
    setAssetPlacement(null);
    setDisplayScale(1);
    setStatus(`已选择初图候选 ${candidate.id}，现在可以涂抹 mask 或拖拽素材继续编辑。`);
    setError("");
  }

  function removeAsset() {
    const layerId = assetPlacement ? `asset-${assetPlacement.asset_id}` : "";
    setSelectedAssetId("");
    setAssetPlacement(null);
    if (layerId) {
      setLayerOverrides((current) => {
        const next = { ...current };
        delete next[layerId];
        return next;
      });
      setLayerOrder((current) => current.filter((item) => item !== layerId));
    }
    dragActiveRef.current = false;
    setStatus("已移除当前素材");
  }

  return (
    <div className="app-shell">
      <div className="app-backdrop" />
      <HeaderBar status={status} sourceImage={sourceImage} latestResult={latestResult} />

      <main className="workspace-grid">
        <ControlPanel
          status={status}
          instruction={instruction}
          setInstruction={setInstruction}
          taskOverride={taskOverride}
          smartTaskOptions={SMART_TASK_OPTIONS}
          setTaskOverride={setTaskOverride}
          generationProvider={generationProvider}
          generationProviderOptions={GENERATION_PROVIDER_OPTIONS}
          setGenerationProvider={setGenerationProvider}
          brushSize={brushSize}
          setBrushSize={setBrushSize}
          drawMode={drawMode}
          setDrawMode={setDrawMode}
          steps={steps}
          setSteps={setSteps}
          guidanceScale={guidanceScale}
          setGuidanceScale={setGuidanceScale}
          fittingDegree={fittingDegree}
          setFittingDegree={setFittingDegree}
          seed={seed}
          setSeed={setSeed}
          horizontalExpansionRatio={horizontalExpansionRatio}
          setHorizontalExpansionRatio={setHorizontalExpansionRatio}
          verticalExpansionRatio={verticalExpansionRatio}
          setVerticalExpansionRatio={setVerticalExpansionRatio}
          assets={assets}
          selectedAsset={selectedAsset}
          selectedAssetId={selectedAssetId}
          chooseAsset={chooseAsset}
          assetPlacement={assetPlacement}
          updateAssetScale={updateAssetScale}
          analyzePlan={analyzePlan}
          createInitialCanvas={createInitialCanvas}
          runSmartGeneration={runSmartGeneration}
          primaryActionLabel={primaryActionLabel({ sourceImage })}
          generateResult={generateResult}
          startGenerateJob={startGenerateJob}
          validateCanvasText={validateCanvasText}
          exportCanvasSvg={exportCanvasSvg}
          isInitializing={isInitializing}
          isGenerating={isGenerating}
          isJobGenerating={isJobGenerating}
          isValidatingText={isValidatingText}
          isExportingSvg={isExportingSvg}
          error={error}
          handleUpload={handleUpload}
        />

        <EditorStage
          sourceImage={sourceImage}
          naturalSize={naturalSize}
          imageRef={imageRef}
          maskCanvasRef={maskCanvasRef}
          syncCanvasToImage={syncCanvasToImage}
          drawMode={drawMode}
          startDrawing={startDrawing}
          drawOnCanvas={drawOnCanvas}
          stopDrawing={stopDrawing}
          selectedAsset={selectedAsset}
          assetPlacement={assetPlacement}
          textLayers={textLayers}
          pointPrompts={pointPrompts}
          removePointPrompt={removePointPrompt}
          editorLayers={editorLayers}
          activeLayerId={activeLayerId}
          setActiveLayerId={setActiveLayerId}
          patchEditorLayer={patchEditorLayer}
          moveEditorLayer={moveEditorLayer}
          updateTextLayerFromFabric={updateTextLayerFromFabric}
          updateAssetPlacementFromFabric={updateAssetPlacementFromFabric}
          layerOverrides={layerOverrides}
          dragActiveRef={dragActiveRef}
          clearMask={clearMask}
          clearCanvas={clearCanvasWorkspace}
          removeAsset={removeAsset}
          displayScale={displayScale}
          setDisplayScale={setDisplayScale}
        />

        <ResultPanel
          latestResult={latestResult}
          continueFromHistory={continueFromHistory}
          history={history}
          initPlan={initPlan}
          initGeneration={initGeneration}
          initCandidates={initCandidates}
          selectedInitCandidateId={selectedInitCandidateId}
          chooseInitCandidate={chooseInitCandidate}
          jobSnapshot={jobSnapshot}
          smartJobSnapshot={smartJobSnapshot}
          cancelGenerateJob={cancelGenerateJob}
          canvasState={latestResult?.canvas_state ?? jobSnapshot?.result?.canvas_state ?? null}
          projects={projects}
          currentProject={currentProject}
          saveCurrentProjectVersion={saveCurrentProjectVersion}
          loadProject={loadProject}
          refreshProjects={refreshProjects}
          isSavingProject={isSavingProject}
          isLoadingProjects={isLoadingProjects}
          canSaveProject={canSaveReloadableProjectVersion({ latestResult })}
          textValidationReport={textValidationReport}
          svgExport={svgExport}
          downloadSvgExport={downloadSvgExport}
          benchmarkSummary={benchmarkSummary}
          benchmarkRuns={benchmarkRuns}
          recordBenchmarkRun={recordBenchmarkRun}
          refreshBenchmarks={refreshBenchmarks}
          isRecordingBenchmark={isRecordingBenchmark}
          isLoadingBenchmarks={isLoadingBenchmarks}
          canRecordBenchmark={Boolean(latestResult?.quality_report)}
        />
      </main>
    </div>
  );
}

export default App;
