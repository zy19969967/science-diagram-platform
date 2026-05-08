import {
  Bug,
  Brush,
  Download,
  Eraser,
  FileText,
  ImagePlus,
  Layers,
  MousePointer2,
  Play,
  RefreshCw,
  Shuffle,
  SlidersHorizontal,
  Sparkles,
  Upload,
  WandSparkles,
} from "lucide-react";
import { WORKSPACE_COPY } from "../uiPresentation.js";

function ControlPanel({
  status,
  instruction,
  setInstruction,
  taskOverride,
  smartTaskOptions,
  setTaskOverride,
  generationProvider,
  generationProviderOptions,
  setGenerationProvider,
  brushSize,
  setBrushSize,
  drawMode,
  setDrawMode,
  steps,
  setSteps,
  guidanceScale,
  setGuidanceScale,
  fittingDegree,
  setFittingDegree,
  seed,
  setSeed,
  horizontalExpansionRatio,
  setHorizontalExpansionRatio,
  verticalExpansionRatio,
  setVerticalExpansionRatio,
  assets,
  selectedAsset,
  selectedAssetId,
  chooseAsset,
  assetPlacement,
  updateAssetScale,
  analyzePlan,
  createInitialCanvas,
  runSmartGeneration,
  primaryActionLabel,
  generateResult,
  startGenerateJob,
  validateCanvasText,
  exportCanvasSvg,
  isInitializing,
  isGenerating,
  isJobGenerating,
  isValidatingText,
  isExportingSvg,
  error,
  handleUpload,
}) {
  const isBusy = isInitializing || isGenerating || isJobGenerating;

  return (
    <aside className="workbench-panel control-panel whiteboard-left-rail">
      <div className="panel-heading rail-heading">
        <div>
          <p className="panel-eyebrow">{WORKSPACE_COPY.leftRailTitle}</p>
          <h2>输入</h2>
        </div>
        <span className="status-pill compact soft-state">{status}</span>
      </div>

      <section className="surface-block rail-block primary-rail-block prompt-card">
        <div className="section-header compact-header">
          <div>
            <span className="section-label">Prompt</span>
            <strong>描述你要改什么</strong>
          </div>
          <WandSparkles size={16} aria-hidden="true" />
        </div>
        <textarea
          value={instruction}
          onChange={(event) => setInstruction(event.target.value)}
          rows={5}
          placeholder="例：把杯子换成白色花瓶，背景和光照保持不变。"
        />
        <label className="upload-card whiteboard-upload">
          <span>
            <Upload size={16} aria-hidden="true" />
            上传底图
          </span>
          <small>可选。上传后可涂抹局部区域再修改。</small>
          <input type="file" accept="image/*" onChange={handleUpload} />
        </label>
      </section>

      <section className="surface-block rail-block mask-tool-block">
        <div className="section-header compact-header">
          <div>
            <span className="section-label">Mask</span>
            <strong>圈出区域</strong>
          </div>
          <MousePointer2 size={16} aria-hidden="true" />
        </div>
        <div className="field-group">
          <label>工具</label>
          <div className="segmented-grid tool-mode-grid icon-segmented">
            <button type="button" className={drawMode === "brush" ? "segment active" : "segment"} onClick={() => setDrawMode("brush")}>
              <Brush size={14} aria-hidden="true" />
              画笔
            </button>
            <button type="button" className={drawMode === "erase" ? "segment active" : "segment"} onClick={() => setDrawMode("erase")}>
              <Eraser size={14} aria-hidden="true" />
              橡皮
            </button>
          </div>
        </div>
        <div className="field-group">
          <label>笔刷 {brushSize}px</label>
          <input type="range" min="8" max="72" value={brushSize} onChange={(event) => setBrushSize(Number(event.target.value))} />
        </div>
      </section>

      <section className="surface-block rail-block action-block generation-action-block">
        <button type="button" className="primary-button full-width icon-button-label" onClick={runSmartGeneration} disabled={isBusy}>
          <Sparkles size={16} aria-hidden="true" />
          {isBusy ? "生成中..." : primaryActionLabel}
        </button>
        {error && <p className="error-text">{error}</p>}
      </section>

      <details className="surface-block rail-block advanced-block whiteboard-advanced">
        <summary className="details-summary">
          <SlidersHorizontal size={16} aria-hidden="true" />
          <span className="section-label">高级</span>
          <strong>任务、素材、调试</strong>
        </summary>
        <div className="field-group compact">
          <label>任务</label>
          <div className="segmented-grid">
            {smartTaskOptions.map((option) => (
              <button
                key={option.value || "auto"}
                type="button"
                className={taskOverride === option.value ? "segment active" : "segment"}
                onClick={() => setTaskOverride(option.value)}
              >
                {option.label}
              </button>
            ))}
          </div>
        </div>
        <div className="field-group compact">
          <label>生成器</label>
          <div className="segmented-grid">
            {generationProviderOptions.map((option) => (
              <button
                key={option.value}
                type="button"
                className={generationProvider === option.value ? "segment active" : "segment"}
                onClick={() => setGenerationProvider(option.value)}
              >
                {option.label}
              </button>
            ))}
          </div>
        </div>
        <div className="field-group compact">
          <label>画布工具</label>
          <div className="segmented-grid tool-mode-grid icon-segmented">
            <button type="button" className={drawMode === "layer" ? "segment active" : "segment"} onClick={() => setDrawMode("layer")}>
              <Layers size={14} aria-hidden="true" />
              图层
            </button>
            <button type="button" className={drawMode === "positive-point" ? "segment active" : "segment"} onClick={() => setDrawMode("positive-point")}>
              +
              正点
            </button>
            <button type="button" className={drawMode === "negative-point" ? "segment active" : "segment"} onClick={() => setDrawMode("negative-point")}>
              -
              负点
            </button>
          </div>
        </div>

        <div className="section-header compact-header">
          <div>
            <span className="section-label">素材</span>
            <strong>科学素材</strong>
          </div>
          {selectedAsset && <span className="section-meta">{selectedAsset.name}</span>}
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
        <div className="advanced-grid">
          <div className="field-group compact">
            <label>步数</label>
            <input type="number" min="1" max="60" value={steps} onChange={(event) => setSteps(Number(event.target.value))} />
          </div>
          <div className="field-group compact">
            <label>引导</label>
            <input type="number" min="0.1" max="30" step="0.1" value={guidanceScale} onChange={(event) => setGuidanceScale(Number(event.target.value))} />
          </div>
          <div className="field-group compact">
            <label>贴合</label>
            <input type="number" min="0" max="1" step="0.05" value={fittingDegree} onChange={(event) => setFittingDegree(Number(event.target.value))} />
          </div>
          <div className="field-group compact">
            <label>种子</label>
            <div className="seed-row">
              <input type="number" min="0" max="2147483647" value={seed} onChange={(event) => setSeed(Number(event.target.value))} />
              <button type="button" className="ghost-button icon-button-label" onClick={() => setSeed(Math.floor(Math.random() * 2147483647))}>
                <Shuffle size={14} aria-hidden="true" />
                随机
              </button>
            </div>
          </div>
          {taskOverride === "outpainting" && (
            <>
              <div className="field-group compact">
                <label>横向扩展</label>
                <input
                  type="number"
                  min="1"
                  max="4"
                  step="0.1"
                  value={horizontalExpansionRatio}
                  onChange={(event) => setHorizontalExpansionRatio(Number(event.target.value))}
                />
              </div>
              <div className="field-group compact">
                <label>纵向扩展</label>
                <input
                  type="number"
                  min="1"
                  max="4"
                  step="0.1"
                  value={verticalExpansionRatio}
                  onChange={(event) => setVerticalExpansionRatio(Number(event.target.value))}
                />
              </div>
            </>
          )}
        </div>
        <div className="action-row action-stack inspector-actions">
          <button type="button" className="secondary-button icon-button-label" onClick={createInitialCanvas} disabled={isInitializing}>
            <ImagePlus size={14} aria-hidden="true" />
            {isInitializing ? "初图中..." : "无图初图"}
          </button>
          <button type="button" className="secondary-button icon-button-label" onClick={analyzePlan}>
            <Bug size={14} aria-hidden="true" />
            解析任务
          </button>
          <button type="button" className="secondary-button icon-button-label" onClick={validateCanvasText} disabled={isValidatingText}>
            <FileText size={14} aria-hidden="true" />
            {isValidatingText ? "校验中..." : "校验文本"}
          </button>
          <button type="button" className="secondary-button icon-button-label" onClick={exportCanvasSvg} disabled={isExportingSvg}>
            <Download size={14} aria-hidden="true" />
            {isExportingSvg ? "导出中..." : "导出 SVG"}
          </button>
          <button type="button" className="secondary-button icon-button-label" onClick={startGenerateJob} disabled={isJobGenerating || isGenerating}>
            <RefreshCw size={14} aria-hidden="true" />
            {isJobGenerating ? "任务中..." : "异步生成"}
          </button>
          <button type="button" className="primary-button icon-button-label" onClick={generateResult} disabled={isGenerating || isJobGenerating}>
            <Play size={14} aria-hidden="true" />
            {isGenerating ? "生成中..." : "局部生成"}
          </button>
        </div>
      </details>
    </aside>
  );
}

export default ControlPanel;
