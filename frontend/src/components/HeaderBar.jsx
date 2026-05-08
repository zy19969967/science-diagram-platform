import { CircleDot, Image, Sparkles } from "lucide-react";
import { WORKSPACE_COPY } from "../uiPresentation.js";

function HeaderBar({ status, sourceImage, latestResult }) {
  return (
    <header className="topbar whiteboard-topbar">
      <div className="topbar-brand">
        <span className="brand-mark" aria-hidden="true">SD</span>
        <h1>{WORKSPACE_COPY.appName}</h1>
      </div>

      <div className="topbar-status whiteboard-status-strip">
        <span className="topbar-state status-chip">
          <CircleDot size={14} aria-hidden="true" />
          {status}
        </span>
        <span className="status-chip">
          <Image size={14} aria-hidden="true" />
          {sourceImage ? "画布就绪" : "待导入"}
        </span>
        <span className="status-chip">
          <Sparkles size={14} aria-hidden="true" />
          {latestResult ? "有结果" : "待生成"}
        </span>
      </div>
    </header>
  );
}

export default HeaderBar;
