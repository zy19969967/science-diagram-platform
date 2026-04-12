import { useEffect, useMemo, useRef, useState } from "react";

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
    context.strokeStyle = "rgba(255,255,255,1)";

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
      const response = await fetch(apiPath("/api/plan"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          instruction,
          preferred_task: task,
          selected_asset_id: selectedAssetId || null,
          canvas_hints: {
            has_mask: Boolean(sourceImage),
            has_asset: Boolean(assetPlacement),
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

  return (
    <div className="app-shell">
      <header className="hero">
        <div>
          <p className="eyebrow">Graduation Design Demo</p>
          <h1>科学示意图交互式生成平台</h1>
          <p className="hero-copy">
            基于技术报告中的“规划 + 分割 + 执行”链路，前端支持手绘选区与科学素材放置，后端由 FastAPI 网关统一调度 PowerPaint。
          </p>
        </div>
        <div className="hero-badges">
          <span>Qwen3.5-ready</span>
          <span>SAM-2-ready</span>
          <span>PowerPaint</span>
          <span>Docker Compose</span>
        </div>
      </header>

      <main className="workspace-grid">
        <section className="panel control-panel">
          <div className="panel-title-row">
            <h2>输入与任务</h2>
            <span className="status-pill">{status}</span>
          </div>

          <label className="upload-card">
            <span>上传原图</span>
            <small>支持科研示意图、实验装置图、流程图局部编辑</small>
            <input type="file" accept="image/*" onChange={handleUpload} />
          </label>

          <div className="field-group">
            <label>编辑指令</label>
            <textarea
              value={instruction}
              onChange={(event) => setInstruction(event.target.value)}
              rows={5}
              placeholder="例如：在右侧空白区域添加一个烧杯，并保持文字标签清晰。"
            />
          </div>

          <div className="field-group">
            <label>任务模式</label>
            <div className="segmented-grid">
              {TASK_OPTIONS.map((option) => (
                <button
                  key={option.value}
                  type="button"
                  className={task === option.value ? "segment active" : "segment"}
                  onClick={() => setTask(option.value)}
                >
                  {option.label}
                </button>
              ))}
            </div>
          </div>

          <div className="field-row">
            <div className="field-group compact">
              <label>笔刷大小</label>
              <input type="range" min="8" max="72" value={brushSize} onChange={(event) => setBrushSize(Number(event.target.value))} />
            </div>
            <div className="field-group compact">
              <label>绘制模式</label>
              <div className="segmented-grid two-up">
                <button type="button" className={drawMode === "brush" ? "segment active" : "segment"} onClick={() => setDrawMode("brush")}>画笔</button>
                <button type="button" className={drawMode === "erase" ? "segment active" : "segment"} onClick={() => setDrawMode("erase")}>橡皮</button>
              </div>
            </div>
          </div>

          <div className="field-row">
            <div className="field-group compact">
              <label>Steps</label>
              <input type="number" min="1" max="60" value={steps} onChange={(event) => setSteps(Number(event.target.value))} />
            </div>
            <div className="field-group compact">
              <label>Guidance</label>
              <input type="number" min="0.1" max="30" step="0.1" value={guidanceScale} onChange={(event) => setGuidanceScale(Number(event.target.value))} />
            </div>
          </div>

          <div className="field-row">
            <div className="field-group compact">
              <label>Fitting</label>
              <input type="number" min="0" max="1" step="0.05" value={fittingDegree} onChange={(event) => setFittingDegree(Number(event.target.value))} />
            </div>
            <div className="field-group compact">
              <label>Seed</label>
              <div className="seed-row">
                <input type="number" min="0" max="2147483647" value={seed} onChange={(event) => setSeed(Number(event.target.value))} />
                <button type="button" className="ghost-button" onClick={() => setSeed(Math.floor(Math.random() * 2147483647))}>随机</button>
              </div>
            </div>
          </div>

          {task === "image-outpainting" && (
            <div className="field-row">
              <div className="field-group compact">
                <label>横向扩展</label>
                <input type="number" min="1" max="4" step="0.1" value={horizontalExpansionRatio} onChange={(event) => setHorizontalExpansionRatio(Number(event.target.value))} />
              </div>
              <div className="field-group compact">
                <label>纵向扩展</label>
                <input type="number" min="1" max="4" step="0.1" value={verticalExpansionRatio} onChange={(event) => setVerticalExpansionRatio(Number(event.target.value))} />
              </div>
            </div>
          )}

          <div className="panel-subtitle-row">
            <h3>科学素材图库</h3>
            {selectedAsset && <span>{selectedAsset.name}</span>}
          </div>
          <div className="asset-grid">
            {assets.map((asset) => (
              <button
                key={asset.id}
                type="button"
                className={selectedAssetId === asset.id ? "asset-card active" : "asset-card"}
                onClick={() => chooseAsset(asset.id)}
              >
                <img src={asset.image_url} alt={asset.name} crossOrigin="anonymous" />
                <strong>{asset.name}</strong>
                <small>{asset.category}</small>
              </button>
            ))}
          </div>

          {assetPlacement && (
            <div className="field-group">
              <label>素材尺寸</label>
              <input
                type="range"
                min="0.12"
                max="0.45"
                step="0.01"
                value={assetPlacement.width}
                onChange={(event) => updateAssetScale(event.target.value)}
              />
            </div>
          )}

          <div className="action-row">
            <button type="button" className="secondary-button" onClick={analyzePlan}>解析任务</button>
            <button type="button" className="primary-button" onClick={generateResult} disabled={isGenerating}>
              {isGenerating ? "生成中..." : "调用 PowerPaint"}
            </button>
          </div>

          {error && <p className="error-text">{error}</p>}
        </section>

        <section className="panel editor-panel">
          <div className="panel-title-row">
            <h2>交互画布</h2>
            <div className="inline-actions">
              <button type="button" className="ghost-button" onClick={clearMask}>清空 Mask</button>
              <button type="button" className="ghost-button" onClick={() => setAssetPlacement(null)}>移除素材</button>
            </div>
          </div>

          <div className="canvas-stage">
            {sourceImage ? (
              <div className="canvas-stack">
                <img ref={imageRef} src={sourceImage} alt="source" onLoad={() => syncCanvasToImage()} />
                <canvas
                  ref={maskCanvasRef}
                  className="mask-canvas"
                  onPointerDown={startDrawing}
                  onPointerMove={drawOnCanvas}
                  onPointerUp={stopDrawing}
                  onPointerLeave={stopDrawing}
                />
                {selectedAsset && assetPlacement && (
                  <div
                    className="asset-overlay"
                    style={{
                      left: `${assetPlacement.x * 100}%`,
                      top: `${assetPlacement.y * 100}%`,
                      width: `${assetPlacement.width * 100}%`,
                      height: `${assetPlacement.height * 100}%`,
                    }}
                    onPointerDown={(event) => {
                      event.stopPropagation();
                      dragActiveRef.current = true;
                    }}
                  >
                    <img src={selectedAsset.image_url} alt={selectedAsset.name} crossOrigin="anonymous" draggable="false" />
                  </div>
                )}
              </div>
            ) : (
              <div className="empty-stage">
                <strong>等待图像</strong>
                <p>上传科研示意图后，可以在这里手绘 mask，或者放置烧杯、试管等素材来生成局部约束。</p>
              </div>
            )}
          </div>

          <div className="tip-grid">
            <article>
              <h4>手绘选区</h4>
              <p>适合删除错误箭头、局部补全背景、替换已有器材。</p>
            </article>
            <article>
              <h4>素材放置</h4>
              <p>适合先定位置，再交给 PowerPaint 做自然融合与边界修复。</p>
            </article>
            <article>
              <h4>多轮迭代</h4>
              <p>右侧历史结果可一键回灌，便于论文演示多轮编辑闭环。</p>
            </article>
          </div>
        </section>

        <section className="panel result-panel">
          <div className="panel-title-row">
            <h2>规划与结果</h2>
            {latestResult && <span className="status-pill">Run {latestResult.run_id}</span>}
          </div>

          <div className="result-preview">
            {latestResult ? <img src={latestResult.result_image} alt="result" /> : <div className="placeholder-card">生成结果会显示在这里</div>}
          </div>

          {latestResult?.evaluation && (
            <div className="metric-card">
              <div>
                <span>变化比例</span>
                <strong>{latestResult.evaluation.changed_ratio}</strong>
              </div>
              <div>
                <span>编辑外溢</span>
                <strong>{latestResult.evaluation.outside_mask_change_ratio}</strong>
              </div>
              <p>{latestResult.evaluation.note}</p>
            </div>
          )}

          <div className="action-row compact-row">
            {latestResult && (
              <button type="button" className="secondary-button" onClick={() => continueFromHistory(latestResult)}>
                继续编辑当前结果
              </button>
            )}
          </div>

          <div className="panel-subtitle-row">
            <h3>结构化计划</h3>
            <span>/api/plan</span>
          </div>
          <pre className="json-panel">{plan ? JSON.stringify(plan, null, 2) : "尚未生成任务计划。"}</pre>

          <div className="panel-subtitle-row">
            <h3>历史版本</h3>
            <span>{history.length} 项</span>
          </div>
          <div className="history-list">
            {history.length === 0 && <div className="placeholder-card">当前还没有历史结果。</div>}
            {history.map((item) => (
              <button key={item.run_id} type="button" className="history-card" onClick={() => continueFromHistory(item)}>
                <img src={item.result_image} alt={item.run_id} />
                <div>
                  <strong>{item.plan.task}</strong>
                  <small>{item.run_id}</small>
                </div>
              </button>
            ))}
          </div>
        </section>
      </main>
    </div>
  );
}

export default App;
