function ControlPanel({
  status,
  instruction,
  setInstruction,
  task,
  taskOptions,
  setTask,
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
          <p className="panel-eyebrow">工作流</p>
          <h2>编辑控制台</h2>
        </div>
        <span className="status-pill compact soft-state">{status}</span>
      </div>

      <div className="workflow-strip" aria-label="主要流程">
        <span>1 输入</span>
        <span>2 标注</span>
        <span>3 生成</span>
      </div>

      <section className="surface-block rail-block primary-rail-block">
        <div className="section-header compact-header">
          <div>
            <span className="section-label">输入</span>
            <strong>上传与描述</strong>
          </div>
        </div>
        <label className="upload-card">
          <span>拖入或选择图片</span>
          <small>支持科研示意图、实验装置图、流程图等图像输入。</small>
          <input type="file" accept="image/*" onChange={handleUpload} />
        </label>
        <textarea
          value={instruction}
          onChange={(event) => setInstruction(event.target.value)}
          rows={5}
          placeholder="例如：在右侧空白区域加入烧杯与箭头标注，并保持图中文字清晰。"
        />
        <button type="button" className="secondary-button full-width" onClick={createInitialCanvas} disabled={isInitializing}>
          {isInitializing ? "生成初图中..." : "无图生成初图"}
        </button>
        <div className="segmented-grid">
          {taskOptions.map((option) => (
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
      </section>

      <section className="surface-block rail-block">
        <div className="section-header compact-header">
          <div>
            <span className="section-label">画布</span>
            <strong>标注与素材</strong>
          </div>
        </div>
        <div className="field-group">
          <label>绘制模式</label>
          <div className="segmented-grid tool-mode-grid">
            <button type="button" className={drawMode === "brush" ? "segment active" : "segment"} onClick={() => setDrawMode("brush")}>
              画笔
            </button>
            <button type="button" className={drawMode === "erase" ? "segment active" : "segment"} onClick={() => setDrawMode("erase")}>
              橡皮
            </button>
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
        <div className="field-group">
          <label>笔刷大小</label>
          <input type="range" min="8" max="72" value={brushSize} onChange={(event) => setBrushSize(Number(event.target.value))} />
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
      </section>

      <details className="surface-block rail-block advanced-block">
        <summary className="details-summary">
          <span className="section-label">参数</span>
          <strong>高级生成参数</strong>
        </summary>
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
          {task === "image-outpainting" && (
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
      </details>

      <section className="surface-block rail-block action-block">
        <div className="action-row action-stack">
          <button type="button" className="secondary-button" onClick={analyzePlan}>
            解析任务
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
        {error && <p className="error-text">{error}</p>}
      </section>
    </aside>
  );
}

export default ControlPanel;
