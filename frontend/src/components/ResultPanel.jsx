const formatRatio = (value) => {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return "n/a";
  }
  return `${Math.round(value * 1000) / 10}%`;
};

function ResultPanel({
  latestResult,
  continueFromHistory,
  history,
  initPlan,
  initCandidates,
  selectedInitCandidateId,
  chooseInitCandidate,
  jobSnapshot,
  canvasState,
}) {
  const layerCount = canvasState?.layers?.length ?? 0;
  const historyCount = canvasState?.history?.length ?? 0;
  const qualityReport = latestResult?.quality_report ?? null;
  const qualityMask = qualityReport?.mask ?? {};
  const qualityEvaluation = qualityReport?.evaluation ?? {};
  const qualityPrompt = qualityReport?.prompt ?? {};

  return (
    <aside className="workbench-panel result-panel">
      <div className="panel-heading">
        <div>
          <p className="panel-eyebrow">Result</p>
          <h2>结果预览</h2>
        </div>
        {latestResult && <span className="status-pill compact">Run {latestResult.run_id}</span>}
      </div>

      {initCandidates.length > 0 && (
        <section className="surface-block rail-block candidate-block">
          <div className="section-header compact-header">
            <div>
              <span className="section-label">Initial</span>
              <strong>初图候选</strong>
            </div>
            {initPlan && <span className="section-meta">{initPlan.provider}</span>}
          </div>
          <div className="candidate-list">
            {initCandidates.map((candidate) => (
              <button
                key={candidate.id}
                type="button"
                className={selectedInitCandidateId === candidate.id ? "candidate-card active" : "candidate-card"}
                onClick={() => chooseInitCandidate(candidate)}
              >
                <img src={candidate.image} alt={candidate.id} />
                <span>
                  <strong>{candidate.id}</strong>
                  <small>seed {candidate.seed} | score {candidate.score}</small>
                </span>
              </button>
            ))}
          </div>
        </section>
      )}

      {jobSnapshot && (
        <section className="surface-block rail-block job-block">
          <div className="section-header compact-header">
            <div>
              <span className="section-label">Job</span>
              <strong>异步任务</strong>
            </div>
            <span className="section-meta">{jobSnapshot.status}</span>
          </div>
          <div className="job-progress">
            <div>
              <span>{jobSnapshot.job_id}</span>
              <strong>{Math.round(jobSnapshot.progress * 100)}%</strong>
            </div>
            <progress value={jobSnapshot.progress} max="1" />
            <p>{jobSnapshot.error || jobSnapshot.message}</p>
          </div>
        </section>
      )}

      {canvasState && (
        <section className="surface-block rail-block canvas-state-block">
          <div className="section-header compact-header">
            <div>
              <span className="section-label">State</span>
              <strong>画布状态</strong>
            </div>
            <span className="section-meta">{canvasState.source}</span>
          </div>
          <div className="canvas-state-grid">
            <div>
              <span>Layers</span>
              <strong>{layerCount}</strong>
            </div>
            <div>
              <span>History</span>
              <strong>{historyCount}</strong>
            </div>
          </div>
        </section>
      )}

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
            {qualityReport && (
              <>
                <div className="metric-card">
                  <span>Mask 覆盖</span>
                  <strong>{formatRatio(qualityMask.coverage_ratio)}</strong>
                  <p>{qualityMask.bounding_box ? `bbox ${qualityMask.bounding_box.join(", ")}` : "未检测到有效边界框。"}</p>
                </div>
                <div className="metric-card">
                  <span>Mask 内变化</span>
                  <strong>{formatRatio(qualityEvaluation.inside_mask_change_ratio)}</strong>
                  <p>衡量目标选区内部是否发生了足够的编辑变化。</p>
                </div>
                <div className="metric-card">
                  <span>局部化得分</span>
                  <strong>{formatRatio(qualityEvaluation.edit_localization_score)}</strong>
                  <p>变化像素落在 mask 内的比例。</p>
                </div>
                <div className="metric-card">
                  <span>保真得分</span>
                  <strong>{formatRatio(qualityEvaluation.preservation_score)}</strong>
                  <p>非编辑区域保持程度，越高越稳定。</p>
                </div>
                <div className="metric-card">
                  <span>Prompt Trace</span>
                  <strong>{qualityPrompt.task ?? "n/a"}</strong>
                  <p>
                    {qualityPrompt.planner_source ?? "unknown"} | seed {qualityPrompt.seed ?? "n/a"}
                  </p>
                </div>
              </>
            )}
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
