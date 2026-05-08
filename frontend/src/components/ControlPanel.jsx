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
  return (
    <aside className="workbench-panel control-panel">
      <div className="panel-heading">
        <div>
          <p className="panel-eyebrow">生成</p>
          <h2>一键生成与修改</h2>
        </div>
        <span className="status-pill compact soft-state">{status}</span>
      </div>

      <div className="workflow-strip" aria-label="主要流程">
        <span>1 描述需求</span>
        <span>2 可选上传</span>
        <span>3 点击生成</span>
      </div>

      <section className="surface-block rail-block primary-rail-block">
        <div className="section-header compact-header">
          <div>
            <span className="section-label">需求</span>
            <strong>你想生成或修改什么？</strong>
          </div>
        </div>
        <textarea
          value={instruction}
          onChange={(event) => setInstruction(event.target.value)}
          rows={5}
          placeholder="例如：把杯子换成白色花瓶，并保持背景和光照不变。"
        />
        <label className="upload-card">
          <span>可选：上传一张图片</span>
          <small>不上传图片时会进入文生图；上传后可涂抹局部区域再修改。</small>
          <input type="file" accept="image/*" onChange={handleUpload} />
        </label>
      </section>

      <section className="surface-block rail-block">
        <div className="section-header compact-header">
          <div>
            <span className="section-label">选区</span>
            <strong>可选：涂抹要修改的区域</strong>
          </div>
        </div>
        <div className="field-group">
          <label>画笔工具</label>
          <div className="segmented-grid tool-mode-grid">
            <button type="button" className={drawMode === "brush" ? "segment active" : "segment"} onClick={() => setDrawMode("brush")}>
              画笔
            </button>
            <button type="button" className={drawMode === "erase" ? "segment active" : "segment"} onClick={() => setDrawMode("erase")}>
              橡皮
            </button>
          </div>
        </div>
        <div className="field-group">
          <label>笔刷大小</label>
          <input type="range" min="8" max="72" value={brushSize} onChange={(event) => setBrushSize(Number(event.target.value))} />
        </div>
      </section>

      <section className="surface-block rail-block action-block">
        <button type="button" className="primary-button full-width" onClick={runSmartGeneration} disabled={isInitializing || isGenerating || isJobGenerating}>
          {isInitializing || isGenerating || isJobGenerating ? "生成中..." : primaryActionLabel}
        </button>
        {error && <p className="error-text">{error}</p>}
      </section>

      <details className="surface-block rail-block advanced-block">
        <summary className="details-summary">
          <span className="section-label">高级</span>
          <strong>任务覆盖、素材和调试</strong>
        </summary>
        <div className="field-group compact">
          <label>任务判断</label>
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
          <label>生成 Provider</label>
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
          <label>高级画布工具</label>
          <div className="segmented-grid tool-mode-grid">
            <button type="button" className={drawMode === "layer" ? "segment active" : "segment"} onClick={() => setDrawMode("layer")}>
              图层
            </button>
            <button type="button" className={drawMode === "positive-point" ? "segment active" : "segment"} onClick={() => setDrawMode("positive-point")}>
              正点
            </button>
            <button type="button" className={drawMode === "negative-point" ? "segment active" : "segment"} onClick={() => setDrawMode("negative-point")}>
              负点
            </button>
          </div>
        </div>
        <div className="section-header compact-header">
          <div>
            <span className="section-label">素材</span>
            <strong>科学素材库</strong>
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
            <label>迭代步数</label>
            <input type="number" min="1" max="60" value={steps} onChange={(event) => setSteps(Number(event.target.value))} />
          </div>
          <div className="field-group compact">
            <label>引导强度</label>
            <input type="number" min="0.1" max="30" step="0.1" value={guidanceScale} onChange={(event) => setGuidanceScale(Number(event.target.value))} />
          </div>
          <div className="field-group compact">
            <label>贴合程度</label>
            <input type="number" min="0" max="1" step="0.05" value={fittingDegree} onChange={(event) => setFittingDegree(Number(event.target.value))} />
          </div>
          <div className="field-group compact">
            <label>随机种子</label>
            <div className="seed-row">
              <input type="number" min="0" max="2147483647" value={seed} onChange={(event) => setSeed(Number(event.target.value))} />
              <button type="button" className="ghost-button" onClick={() => setSeed(Math.floor(Math.random() * 2147483647))}>
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
        <div className="action-row action-stack">
          <button type="button" className="secondary-button" onClick={createInitialCanvas} disabled={isInitializing}>
            {isInitializing ? "生成初图中..." : "旧入口：无图初图"}
          </button>
          <button type="button" className="secondary-button" onClick={analyzePlan}>
            调试：解析任务
          </button>
          <button type="button" className="secondary-button" onClick={validateCanvasText} disabled={isValidatingText}>
            {isValidatingText ? "校验中..." : "校验文本"}
          </button>
          <button type="button" className="secondary-button" onClick={exportCanvasSvg} disabled={isExportingSvg}>
            {isExportingSvg ? "导出中..." : "导出 SVG"}
          </button>
          <button type="button" className="secondary-button" onClick={startGenerateJob} disabled={isJobGenerating || isGenerating}>
            {isJobGenerating ? "异步任务中..." : "异步生成"}
          </button>
          <button type="button" className="primary-button" onClick={generateResult} disabled={isGenerating || isJobGenerating}>
            {isGenerating ? "生成中..." : "局部生成"}
          </button>
        </div>
      </details>
    </aside>
  );
}

export default ControlPanel;
