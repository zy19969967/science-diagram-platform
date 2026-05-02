function HeaderBar({ status, sourceImage, latestResult }) {
  return (
    <header className="topbar">
      <div className="topbar-brand">
        <span className="brand-mark" aria-hidden="true">SD</span>
        <div>
          <p className="topbar-kicker">科研图像工作台</p>
          <h1>科学示意图智能编辑平台</h1>
          <p className="topbar-subtitle">从初图生成、局部标注到 SVG 导出的一体化编辑流程</p>
        </div>
      </div>

      <div className="topbar-status">
        <span className="topbar-state">{status}</span>
        <span>{sourceImage ? "底图已就绪" : "等待图像"}</span>
        <span>{latestResult ? "已有生成结果" : "等待生成"}</span>
      </div>
    </header>
  );
}

export default HeaderBar;
