function ResultPanel({ latestResult, continueFromHistory, history }) {
  return (
    <aside className="workbench-panel result-panel">
      <div className="panel-heading">
        <div>
          <p className="panel-eyebrow">Result</p>
          <h2>结果预览</h2>
        </div>
        {latestResult && <span className="status-pill compact">Run {latestResult.run_id}</span>}
      </div>

      <section className="surface-block emphasis-block preview-block">
        <div className="section-header compact-header">
          <div>
            <span className="section-label">Preview</span>
            <strong>最新结果</strong>
          </div>
        </div>
        <div className="result-preview">
          {latestResult ? <img src={latestResult.result_image} alt="result" /> : <div className="placeholder-card">生成结果会显示在这里</div>}
        </div>
      </section>

      <section className="surface-block rail-block">
        <div className="action-row">
          {latestResult && (
            <button type="button" className="secondary-button full-width" onClick={() => continueFromHistory(latestResult)}>
              继续编辑当前结果
            </button>
          )}
        </div>
      </section>

      {latestResult?.evaluation && (
        <details className="surface-block rail-block result-details">
          <summary className="details-summary">
            <span className="section-label">Metrics</span>
            <strong>结果指标</strong>
          </summary>
          <section className="metrics-grid single-column">
            <div className="metric-card">
              <span>变化比例</span>
              <strong>{latestResult.evaluation.changed_ratio}</strong>
              <p>衡量本轮编辑对整体图像的影响程度。</p>
            </div>
            <div className="metric-card">
              <span>编辑外溢</span>
              <strong>{latestResult.evaluation.outside_mask_change_ratio}</strong>
              <p>数值越低，代表修改越集中在目标区域。</p>
            </div>
            <div className="metric-card">
              <span>评估说明</span>
              <strong>Result Note</strong>
              <p>{latestResult.evaluation.note}</p>
            </div>
          </section>
        </details>
      )}

      <details className="surface-block rail-block result-details">
        <summary className="details-summary">
          <span className="section-label">History</span>
          <strong>历史版本</strong>
        </summary>
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
      </details>
    </aside>
  );
}

export default ResultPanel;
