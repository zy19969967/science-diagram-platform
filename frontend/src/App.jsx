import { useEffect, useMemo, useRef, useState } from "react";
import ControlPanel from "./components/ControlPanel";
import EditorStage from "./components/EditorStage";
import HeaderBar from "./components/HeaderBar";
import ResultPanel from "./components/ResultPanel";

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/$/, "");
const apiPath = (path) => (API_BASE_URL ? `${API_BASE_URL}${path}` : path);
const TASK_OPTIONS = [
  { value: "text-guided", label: "文本插入" },
  { value: "object-removal", label: "对象移除" },
  { value: "shape-guided", label: "形状引导" },
  { value: "image-outpainting", label: "图像扩展" },
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

function App() {
  const [assets, setAssets] = useState([]);
  const [sourceImage, setSourceImage] = useState("");
  const [instruction, setInstruction] = useState("");
  const [task, setTask] = useState("text-guided");
  const [brushSize, setBrushSize] = useState(24);
  const [drawMode, setDrawMode] = useState("brush");
  const [steps, setSteps] = useState(30);
  const [guidanceScale, setGuidanceScale] = useState(7.5);
  const [fittingDegree, setFittingDegree] = useState(0.85);
  const [seed, setSeed] = useState(2026);
  const [horizontalExpansionRatio, setHorizontalExpansionRatio] = useState(1.2);
  const [verticalExpansionRatio, setVerticalExpansionRatio] = useState(1.2);
  const [selectedAssetId, setSelectedAssetId] = useState("");
  const [assetPlacement, setAssetPlacement] = useState(null);
  const [plan, setPlan] = useState(null);
  const [latestResult, setLatestResult] = useState(null);
  const [history, setHistory] = useState([]);
  const [status, setStatus] = useState("等待上传图像与绘制选区");
  const [error, setError] = useState("");
  const [isGenerating, setIsGenerating] = useState(false);
  const [naturalSize, setNaturalSize] = useState({ width: 0, height: 0 });
  const [displayScale, setDisplayScale] = useState(1);

  const imageRef = useRef(null);
  const maskCanvasRef = useRef(null);
  const drawingRef = useRef(false);
  const lastPointRef = useRef(null);
  const dragActiveRef = useRef(false);

  const selectedAsset = useMemo(
    () => assets.find((item) => item.id === selectedAssetId) ?? null,
    [assets, selectedAssetId],
  );
  useEffect(() => {
    async function fetchAssets() {
      try {
        const response = await fetch(apiPath("/api/assets"));
        const data = await response.json();
        setAssets(data);
      } catch (fetchError) {
        setError(`素材库读取失败：${fetchError.message}`);
      }
    }

    fetchAssets();
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

  function syncCanvasToImage(width = naturalSize.width, height = naturalSize.height) {
    const image = imageRef.current;
    const canvas = maskCanvasRef.current;
    if (!image || !canvas || !width || !height) {
      return;
    }

    const snapshot = canvas.toDataURL("image/png");
    canvas.width = width;
    canvas.height = height;
    canvas.style.width = `${image.clientWidth}px`;
    canvas.style.height = `${image.clientHeight}px`;

    if (snapshot !== "data:," && snapshot.length > 10) {
      loadImage(snapshot).then((maskImage) => {
        const context = canvas.getContext("2d");
        context.drawImage(maskImage, 0, 0, width, height);
      });
    }
  }

  function clearMask() {
    const canvas = maskCanvasRef.current;
    if (!canvas) {
      return;
    }
    const context = canvas.getContext("2d");
    context.clearRect(0, 0, canvas.width, canvas.height);
    setStatus("已清空当前选区");
  }

  function clearCanvasWorkspace() {
    const canvas = maskCanvasRef.current;
    if (canvas) {
      const context = canvas.getContext("2d");
      context.clearRect(0, 0, canvas.width, canvas.height);
    }
    setSourceImage("");
    setSelectedAssetId("");
    setAssetPlacement(null);
    setPlan(null);
    setLatestResult(null);
    setHistory([]);
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
    const dataUrl = await readFileAsDataUrl(file);
    setSourceImage(dataUrl);
    setLatestResult(null);
    setPlan(null);
    setHistory([]);
    setDisplayScale(1);
    setStatus("图像已载入，可以开始涂抹 mask 或拖拽素材。");
    setError("");
    resetWorkspace();
  }

  function startDrawing(event) {
    if (!sourceImage || !maskCanvasRef.current) {
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
    mergedContext.drawImage(maskCanvas, 0, 0);

    if (selectedAsset && assetPlacement) {
      const assetImage = await loadImage(selectedAsset.image_url);
      const drawWidth = assetPlacement.width * naturalSize.width;
      const drawHeight = assetPlacement.height * naturalSize.height;
      const left = assetPlacement.x * naturalSize.width - drawWidth / 2;
      const top = assetPlacement.y * naturalSize.height - drawHeight / 2;

      const assetCanvas = document.createElement("canvas");
      assetCanvas.width = naturalSize.width;
      assetCanvas.height = naturalSize.height;
      const assetContext = assetCanvas.getContext("2d");
      assetContext.drawImage(assetImage, left, top, drawWidth, drawHeight);
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
      const response = await fetch(apiPath("/api/plan"), {
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

  async function generateResult() {
    if (!sourceImage) {
      setError("请先上传原始图像。");
      return;
    }

    setIsGenerating(true);
    setError("");
    setStatus("正在调用 PowerPaint 生成结果...");

    try {
      const maskPayload = await buildMaskPayload();
      if (maskPayload.pixelCount === 0) {
        throw new Error("当前没有有效的 mask 或素材位置，请先绘制或选择素材。");
      }

      const response = await fetch(apiPath("/api/generate"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          source_image: sourceImage,
          instruction,
          task,
          selected_asset_id: selectedAssetId || null,
          asset_placement: assetPlacement,
          mask_image: maskPayload.dataUrl,
          plan,
          steps,
          guidance_scale: guidanceScale,
          fitting_degree: fittingDegree,
          seed,
          horizontal_expansion_ratio: horizontalExpansionRatio,
          vertical_expansion_ratio: verticalExpansionRatio,
        }),
      });

      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail ?? "生成失败");
      }

      setPlan(data.plan);
      setLatestResult(data);
      setHistory((current) => [data, ...current]);
      setStatus(`生成完成：${data.evaluation.note}`);
    } catch (generationError) {
      setError(generationError.message);
      setStatus("生成失败，请调整选区或提示词后重试。");
    } finally {
      setIsGenerating(false);
    }
  }

  function continueFromHistory(item) {
    setSourceImage(item.result_image);
    setLatestResult(item);
    clearMask();
    setStatus(`已切换到历史结果 ${item.run_id}，可以继续多轮编辑。`);
  }

  function removeAsset() {
    setSelectedAssetId("");
    setAssetPlacement(null);
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
          task={task}
          taskOptions={TASK_OPTIONS}
          setTask={setTask}
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
          generateResult={generateResult}
          isGenerating={isGenerating}
          error={error}
          handleUpload={handleUpload}
        />

        <EditorStage
          sourceImage={sourceImage}
          naturalSize={naturalSize}
          imageRef={imageRef}
          maskCanvasRef={maskCanvasRef}
          syncCanvasToImage={syncCanvasToImage}
          startDrawing={startDrawing}
          drawOnCanvas={drawOnCanvas}
          stopDrawing={stopDrawing}
          selectedAsset={selectedAsset}
          assetPlacement={assetPlacement}
          dragActiveRef={dragActiveRef}
          clearMask={clearMask}
          clearCanvas={clearCanvasWorkspace}
          removeAsset={removeAsset}
          displayScale={displayScale}
          setDisplayScale={setDisplayScale}
        />

        <ResultPanel latestResult={latestResult} continueFromHistory={continueFromHistory} history={history} />
      </main>
    </div>
  );
}

export default App;
