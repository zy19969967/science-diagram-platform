function HeaderBar({ status, sourceImage, latestResult }) {
  return (
    <header className="topbar">
      <div className="topbar-brand">
        <div>
          <p className="topbar-kicker">Scientific Diagram Editor</p>
          <h1>科学示意图智能编辑平台</h1>
        </div>
      </div>

      <div className="topbar-status">
        <span className="topbar-state">{status}</span>
        <span>{sourceImage ? "已载入底图" : "等待上传"}</span>
        <span>{latestResult ? `结果 ${latestResult.run_id}` : "未生成结果"}</span>
      </div>
    </header>
  );
}

export default HeaderBar;
