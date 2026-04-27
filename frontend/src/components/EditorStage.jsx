import { useEffect, useMemo, useRef } from "react";
import { Canvas, FabricImage, Textbox } from "fabric";

const clamp = (value, min, max) => Math.min(max, Math.max(min, value));

function layerOverrideFor(layerOverrides, layerId) {
  return layerOverrides?.[layerId] ?? {};
}

function isLayerActive(layer, activeLayerId) {
  return layer.id === activeLayerId;
}

function LayerPanel({ layers, activeLayerId, setActiveLayerId, patchEditorLayer, moveEditorLayer }) {
  return (
    <div className="layer-panel">
      <div className="layer-panel-header">
        <span className="section-label">Layers</span>
        <strong>{layers.length}</strong>
      </div>
      <div className="layer-list">
        {[...layers].reverse().map((layer) => (
          <div key={layer.id} className={isLayerActive(layer, activeLayerId) ? "layer-row active" : "layer-row"}>
            <button type="button" className="layer-main" onClick={() => setActiveLayerId(layer.id)}>
              <strong>{layer.name}</strong>
              <small>{layer.type}</small>
            </button>
            <div className="layer-row-actions">
              <button
                type="button"
                className="icon-button"
                onClick={() => patchEditorLayer(layer.id, { visible: !layer.visible })}
                disabled={layer.id === "base-image"}
                title={layer.visible ? "Hide layer" : "Show layer"}
              >
                {layer.visible ? "On" : "Off"}
              </button>
              <button
                type="button"
                className="icon-button"
                onClick={() => patchEditorLayer(layer.id, { locked: !layer.locked })}
                disabled={layer.id === "base-image"}
                title={layer.locked ? "Unlock layer" : "Lock layer"}
              >
                {layer.locked ? "Lock" : "Free"}
              </button>
              <button
                type="button"
                className="icon-button"
                onClick={() => moveEditorLayer(layer.id, "up")}
                disabled={!layer.reorderable}
                title="Move layer up"
              >
                Up
              </button>
              <button
                type="button"
                className="icon-button"
                onClick={() => moveEditorLayer(layer.id, "down")}
                disabled={!layer.reorderable}
                title="Move layer down"
              >
                Down
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function FabricEditorCanvas({
  sourceImage,
  naturalSize,
  selectedAsset,
  assetPlacement,
  textLayers,
  editorLayers,
  activeLayerId,
  setActiveLayerId,
  updateTextLayerFromFabric,
  updateAssetPlacementFromFabric,
  layerOverrides,
  drawMode,
}) {
  const canvasElementRef = useRef(null);
  const fabricCanvasRef = useRef(null);
  const objectChangeRef = useRef(false);
  const latestRef = useRef({
    naturalSize,
    updateTextLayerFromFabric,
    updateAssetPlacementFromFabric,
  });

  const orderedLayerIds = useMemo(() => editorLayers.map((layer) => layer.id), [editorLayers]);
  const layersById = useMemo(() => new Map(editorLayers.map((layer) => [layer.id, layer])), [editorLayers]);
  const canEditLayers = drawMode === "layer";

  useEffect(() => {
    latestRef.current = {
      naturalSize,
      updateTextLayerFromFabric,
      updateAssetPlacementFromFabric,
    };
  }, [naturalSize, updateTextLayerFromFabric, updateAssetPlacementFromFabric]);

  useEffect(() => {
    if (!canvasElementRef.current) {
      return undefined;
    }

    const fabricCanvas = new Canvas(canvasElementRef.current, {
      backgroundColor: "transparent",
      preserveObjectStacking: true,
      selection: canEditLayers,
    });
    fabricCanvas.wrapperEl?.classList.add("fabric-canvas-wrapper");
    fabricCanvasRef.current = fabricCanvas;

    const updateActiveLayer = (event) => {
      const layerId = event.selected?.[0]?.layerId || event.target?.layerId || "";
      if (layerId) {
        setActiveLayerId(layerId);
      }
    };

    const updateObject = (event) => {
      const target = event.target;
      const latest = latestRef.current;
      const width = latest.naturalSize.width;
      const height = latest.naturalSize.height;
      if (!target?.layerId || objectChangeRef.current || !width || !height) {
        return;
      }
      objectChangeRef.current = true;
      if (target.layerId.startsWith("asset-")) {
        const scaledWidth = Math.max(1, target.getScaledWidth());
        const scaledHeight = Math.max(1, target.getScaledHeight());
        latest.updateAssetPlacementFromFabric({
          x: clamp((target.left ?? 0) / width, 0.02, 0.98),
          y: clamp((target.top ?? 0) / height, 0.02, 0.98),
          width: clamp(scaledWidth / width, 0.02, 1),
          height: clamp(scaledHeight / height, 0.02, 1),
          rotation: target.angle ?? 0,
        });
      }
      if (target.layerId.startsWith("text-")) {
        const fontSize = Number(target.fontSize ?? 22) * Number(target.scaleY || 1);
        target.set({ scaleX: 1, scaleY: 1 });
        latest.updateTextLayerFromFabric(target.layerId, {
          x: clamp((target.left ?? width / 2) / width, 0.02, 0.98),
          y: clamp((target.top ?? height / 2) / height, 0.02, 0.98),
          font_size: Math.round(clamp(fontSize, 10, 96)),
        });
      }
      window.requestAnimationFrame(() => {
        objectChangeRef.current = false;
      });
    };

    fabricCanvas.on("selection:created", updateActiveLayer);
    fabricCanvas.on("selection:updated", updateActiveLayer);
    fabricCanvas.on("object:modified", updateObject);

    return () => {
      fabricCanvas.dispose();
      fabricCanvasRef.current = null;
    };
  }, []);

  useEffect(() => {
    const fabricCanvas = fabricCanvasRef.current;
    if (!fabricCanvas) {
      return;
    }
    fabricCanvas.selection = canEditLayers;
    for (const object of fabricCanvas.getObjects()) {
      const layer = layersById.get(object.layerId);
      object.set({
        selectable: canEditLayers && layer?.selectable !== false && !layer?.locked,
        evented: canEditLayers && layer?.selectable !== false && !layer?.locked,
      });
    }
    fabricCanvas.requestRenderAll();
  }, [canEditLayers, layersById]);

  useEffect(() => {
    let cancelled = false;
    const fabricCanvas = fabricCanvasRef.current;
    if (!fabricCanvas || !sourceImage || !naturalSize.width || !naturalSize.height) {
      return undefined;
    }

    async function renderLayers() {
      const width = naturalSize.width;
      const height = naturalSize.height;
      fabricCanvas.setDimensions({ width, height });
      fabricCanvas.clear();

      const objectsByLayerId = new Map();
      const baseLayer = layersById.get("base-image");
      if (baseLayer?.visible !== false) {
        const baseImage = await FabricImage.fromURL(sourceImage, { crossOrigin: "anonymous" });
        if (cancelled) {
          return;
        }
        baseImage.set({
          layerId: "base-image",
          left: 0,
          top: 0,
          originX: "left",
          originY: "top",
          scaleX: width / Math.max(1, baseImage.width ?? width),
          scaleY: height / Math.max(1, baseImage.height ?? height),
          selectable: false,
          evented: false,
          opacity: baseLayer.opacity ?? 1,
        });
        objectsByLayerId.set("base-image", baseImage);
      }

      if (selectedAsset && assetPlacement) {
        const layerId = `asset-${assetPlacement.asset_id}`;
        const layer = layersById.get(layerId);
        if (layer?.visible !== false) {
          const assetImage = await FabricImage.fromURL(selectedAsset.image_url, { crossOrigin: "anonymous" });
          if (cancelled) {
            return;
          }
          const drawWidth = assetPlacement.width * width;
          const drawHeight = assetPlacement.height * height;
          assetImage.set({
            layerId,
            left: assetPlacement.x * width,
            top: assetPlacement.y * height,
            originX: "center",
            originY: "center",
            scaleX: drawWidth / Math.max(1, assetImage.width ?? drawWidth),
            scaleY: drawHeight / Math.max(1, assetImage.height ?? drawHeight),
            angle: assetPlacement.rotation ?? 0,
            opacity: layer.opacity ?? 1,
            selectable: canEditLayers && !layer.locked,
            evented: canEditLayers && !layer.locked,
            hasRotatingPoint: true,
          });
          objectsByLayerId.set(layerId, assetImage);
        }
      }

      for (const layer of textLayers ?? []) {
        const layerId = layer.id;
        const metadata = layersById.get(layerId);
        if (!metadata || metadata.visible === false) {
          continue;
        }
        const data = layer.data ?? {};
        const textObject = new Textbox(String(data.text ?? ""), {
          layerId,
          left: Number(data.x ?? 0.5) * width,
          top: Number(data.y ?? 0.5) * height,
          originX: "center",
          originY: "center",
          width: Math.max(120, width * 0.26),
          fontSize: Math.max(12, Number(data.font_size ?? 22)),
          fill: data.color ?? "#18324c",
          backgroundColor: data.background ?? "rgba(255, 255, 255, 0.82)",
          textAlign: data.align ?? "center",
          fontWeight: "700",
          opacity: metadata.opacity ?? 1,
          selectable: canEditLayers && !metadata.locked,
          evented: canEditLayers && !metadata.locked,
          editable: false,
          splitByGrapheme: true,
        });
        objectsByLayerId.set(layerId, textObject);
      }

      for (const layerId of orderedLayerIds) {
        const object = objectsByLayerId.get(layerId);
        if (object) {
          fabricCanvas.add(object);
        }
      }

      const activeObject = objectsByLayerId.get(activeLayerId);
      if (activeObject && activeObject.selectable) {
        fabricCanvas.setActiveObject(activeObject);
      }
      fabricCanvas.requestRenderAll();
    }

    renderLayers();
    return () => {
      cancelled = true;
    };
  }, [
    sourceImage,
    naturalSize,
    selectedAsset,
    assetPlacement,
    textLayers,
    orderedLayerIds,
    activeLayerId,
    layersById,
    canEditLayers,
    layerOverrides,
  ]);

  return <canvas ref={canvasElementRef} className="fabric-editor-canvas" />;
}

function EditorStage({
  sourceImage,
  naturalSize,
  imageRef,
  maskCanvasRef,
  syncCanvasToImage,
  drawMode,
  startDrawing,
  drawOnCanvas,
  stopDrawing,
  selectedAsset,
  assetPlacement,
  textLayers,
  editorLayers,
  activeLayerId,
  setActiveLayerId,
  patchEditorLayer,
  moveEditorLayer,
  updateTextLayerFromFabric,
  updateAssetPlacementFromFabric,
  layerOverrides,
  clearMask,
  clearCanvas,
  removeAsset,
  displayScale,
  setDisplayScale,
}) {
  const scaledWidth = naturalSize.width ? Math.max(280, Math.round(naturalSize.width * displayScale)) : null;
  const maskOverride = layerOverrideFor(layerOverrides, "mask-current");
  const canPaintMask = drawMode !== "layer" && !maskOverride.locked;

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
        <div className="canvas-stage-layout">
          <div className="canvas-stage">
            {sourceImage ? (
              <div className="canvas-stack" style={scaledWidth ? { width: `${scaledWidth}px` } : undefined}>
                <img
                  ref={imageRef}
                  className="stage-measure-image"
                  src={sourceImage}
                  alt="source"
                  onLoad={() => syncCanvasToImage()}
                />
                <FabricEditorCanvas
                  sourceImage={sourceImage}
                  naturalSize={naturalSize}
                  selectedAsset={selectedAsset}
                  assetPlacement={assetPlacement}
                  textLayers={textLayers}
                  editorLayers={editorLayers}
                  activeLayerId={activeLayerId}
                  setActiveLayerId={setActiveLayerId}
                  updateTextLayerFromFabric={updateTextLayerFromFabric}
                  updateAssetPlacementFromFabric={updateAssetPlacementFromFabric}
                  layerOverrides={layerOverrides}
                  drawMode={drawMode}
                />
                <canvas
                  ref={maskCanvasRef}
                  className="mask-canvas"
                  style={{
                    opacity: maskOverride.visible === false ? 0 : maskOverride.opacity ?? 1,
                    pointerEvents: canPaintMask ? "auto" : "none",
                  }}
                  onPointerDown={startDrawing}
                  onPointerMove={drawOnCanvas}
                  onPointerUp={stopDrawing}
                  onPointerLeave={stopDrawing}
                />
              </div>
            ) : (
              <div className="empty-stage">
                <strong>等待图像输入</strong>
                <p>上传科研示意图后，即可开始局部标注、素材摆放与结果生成。</p>
              </div>
            )}
          </div>
          {sourceImage && (
            <LayerPanel
              layers={editorLayers}
              activeLayerId={activeLayerId}
              setActiveLayerId={setActiveLayerId}
              patchEditorLayer={patchEditorLayer}
              moveEditorLayer={moveEditorLayer}
            />
          )}
        </div>
      </div>
    </section>
  );
}

export default EditorStage;
