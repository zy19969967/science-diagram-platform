function EditorStage({
  sourceImage,
  naturalSize,
  imageRef,
  maskCanvasRef,
  syncCanvasToImage,
  startDrawing,
  drawOnCanvas,
  stopDrawing,
  selectedAsset,
  assetPlacement,
  textLayers,
  dragActiveRef,
  clearMask,
  clearCanvas,
  removeAsset,
  displayScale,
  setDisplayScale,
}) {
  const scaledWidth = naturalSize.width ? Math.max(280, Math.round(naturalSize.width * displayScale)) : null;

  return (
    <section className="editor-column">
      <div className="editor-stage-shell">
        <div className="canvas-toolbar">
          <div className="canvas-toolbar-title">
            <p className="panel-eyebrow">Canvas</p>
            <h2>交互画布</h2>
          </div>
          <label className="scale-control">
            <span>显示比例</span>
            <input
              type="range"
              min="0.5"
              max="1.8"
              step="0.05"
              value={displayScale}
              onChange={(event) => setDisplayScale(Number(event.target.value))}
            />
            <strong>{Math.round(displayScale * 100)}%</strong>
          </label>
          <div className="toolbar-actions">
            <button type="button" className="ghost-button" onClick={clearMask}>
              清空 Mask
            </button>
            <button type="button" className="ghost-button" onClick={clearCanvas}>
              清除画布
            </button>
            <button type="button" className="ghost-button" onClick={removeAsset}>
              移除素材
            </button>
          </div>
        </div>
        <div className="canvas-stage">
          {sourceImage ? (
            <div className="canvas-stack" style={scaledWidth ? { width: `${scaledWidth}px` } : undefined}>
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
              {(textLayers ?? [])
                .filter((layer) => layer.visible !== false)
                .map((layer) => {
                  const data = layer.data ?? {};
                  return (
                    <div
                      key={layer.id}
                      className="text-layer-overlay"
                      style={{
                        left: `${Number(data.x ?? 0.5) * 100}%`,
                        top: `${Number(data.y ?? 0.5) * 100}%`,
                        opacity: layer.opacity ?? 1,
                        color: data.color ?? "#18324c",
                        background: data.background ?? "rgba(255, 255, 255, 0.82)",
                        fontSize: `${Math.max(12, Number(data.font_size ?? 22) * displayScale)}px`,
                        textAlign: data.align ?? "center",
                      }}
                    >
                      {data.text}
                    </div>
                  );
                })}
            </div>
          ) : (
            <div className="empty-stage">
              <strong>等待图像输入</strong>
              <p>上传科研示意图后，即可开始局部标注、素材摆放与结果生成。</p>
            </div>
          )}
        </div>
      </div>
    </section>
  );
}

export default EditorStage;
