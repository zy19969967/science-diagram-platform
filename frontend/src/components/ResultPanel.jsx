import { candidateScoreSummary, summarizeInitGeneration } from "../initCandidates.js";
import { formatBenchmarkScore, summarizeBenchmarkSummary } from "../benchmarkState.js";

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
  initGeneration,
  initCandidates,
  selectedInitCandidateId,
  chooseInitCandidate,
  jobSnapshot,
  cancelGenerateJob,
  canvasState,
  projects,
  currentProject,
  saveCurrentProjectVersion,
  loadProject,
  refreshProjects,
  isSavingProject,
  isLoadingProjects,
  canSaveProject,
  textValidationReport,
  svgExport,
  downloadSvgExport,
  benchmarkSummary,
  benchmarkRuns,
  recordBenchmarkRun,
  refreshBenchmarks,
  isRecordingBenchmark,
  isLoadingBenchmarks,
  canRecordBenchmark,
}) {
  const layerCount = canvasState?.layers?.length ?? 0;
  const historyCount = canvasState?.history?.length ?? 0;
  const qualityReport = latestResult?.quality_report ?? null;
  const qualityMask = qualityReport?.mask ?? {};
  const qualityEvaluation = qualityReport?.evaluation ?? {};
  const qualityPrompt = qualityReport?.prompt ?? {};
  const latestProjectVersionId = currentProject?.latest_version_id ?? "none";
  const canCancelJob = jobSnapshot && !["DONE", "FAILED", "CANCELLED"].includes(jobSnapshot.status);
  const exportWarnings = Array.from(new Set([...(textValidationReport?.warnings ?? []), ...(svgExport?.warnings ?? [])]));
  const initSummary = summarizeInitGeneration(initGeneration);
  const benchmarkDashboard = summarizeBenchmarkSummary(benchmarkSummary);

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
            {initPlan && <span className="section-meta">{initSummary.usedProvider}</span>}
          </div>
          <div className={initSummary.fallbackUsed ? "candidate-provider-summary fallback" : "candidate-provider-summary"}>
            <span>Requested {initSummary.requestedProvider}</span>
            <strong>{initSummary.fallbackUsed ? "Fallback active" : initSummary.provider}</strong>
          </div>
          {initSummary.warnings.length > 0 && (
            <div className="candidate-warning-list">
              {initSummary.warnings.slice(0, 2).map((warning) => (
                <p key={warning}>{warning}</p>
              ))}
            </div>
          )}
          <div className="candidate-list">
            {initCandidates.map((candidate) => {
              const score = candidateScoreSummary(candidate);
              return (
                <button
                  key={candidate.id}
                  type="button"
                  className={selectedInitCandidateId === candidate.id ? "candidate-card active" : "candidate-card"}
                  onClick={() => chooseInitCandidate(candidate)}
                >
                  <img src={candidate.image} alt={candidate.id} />
                  <span>
                    <strong>{score.rank ? `#${score.rank} ${candidate.id}` : candidate.id}</strong>
                    <small>seed {candidate.seed} | score {score.scoreLabel}</small>
                    <small className="candidate-meta">
                      {score.providerSource} | labels {score.labelCoverageLabel}
                    </small>
                  </span>
                </button>
              );
            })}
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
            <p>
              Attempt {jobSnapshot.attempt ?? 1}/{jobSnapshot.max_attempts ?? 1}
              {jobSnapshot.failure_stage ? ` | failed at ${jobSnapshot.failure_stage}` : ""}
            </p>
            {canCancelJob && (
              <button type="button" className="ghost-button full-width" onClick={cancelGenerateJob}>
                Cancel job
              </button>
            )}
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

      {(textValidationReport || svgExport) && (
        <section className="surface-block rail-block export-block">
          <div className="section-header compact-header">
            <div>
              <span className="section-label">Export</span>
              <strong>文本与 SVG</strong>
            </div>
            {textValidationReport && <span className={`section-meta export-status ${textValidationReport.status}`}>{textValidationReport.status}</span>}
          </div>
          {textValidationReport && (
            <div className="export-summary">
              <div>
                <span>Matched</span>
                <strong>{textValidationReport.matched_labels?.length ?? 0}</strong>
              </div>
              <div>
                <span>Missing</span>
                <strong>{textValidationReport.missing_labels?.length ?? 0}</strong>
              </div>
              <p>{(textValidationReport.matched_labels ?? []).join(", ") || "No matched labels yet."}</p>
              {(textValidationReport.missing_labels ?? []).length > 0 && (
                <p className="warning-text">Missing: {textValidationReport.missing_labels.join(", ")}</p>
              )}
            </div>
          )}
          {svgExport && (
            <button type="button" className="secondary-button full-width" onClick={() => downloadSvgExport(svgExport)}>
              下载 {svgExport.filename}
            </button>
          )}
          {exportWarnings.length > 0 && (
            <div className="warning-list">
              {exportWarnings.slice(0, 3).map((warning) => (
                <p key={warning}>{warning}</p>
              ))}
            </div>
          )}
        </section>
      )}

      <section className="surface-block rail-block project-block">
        <div className="section-header compact-header">
          <div>
            <span className="section-label">Project</span>
            <strong>Saved versions</strong>
          </div>
          {currentProject && <span className="section-meta">{currentProject.project_id}</span>}
        </div>
        <div className="project-summary">
          <div>
            <span>Latest</span>
            <strong>{latestProjectVersionId}</strong>
          </div>
          <div>
            <span>Versions</span>
            <strong>{currentProject?.versions?.length ?? 0}</strong>
          </div>
        </div>
        <div className="action-row split-actions">
          <button
            type="button"
            className="secondary-button full-width"
            onClick={saveCurrentProjectVersion}
            disabled={isSavingProject || !canSaveProject}
          >
            {isSavingProject ? "Saving..." : "Save version"}
          </button>
          <button type="button" className="ghost-button full-width" onClick={refreshProjects} disabled={isLoadingProjects}>
            {isLoadingProjects ? "Loading..." : "Refresh"}
          </button>
        </div>
        <div className="project-list">
          {(projects ?? []).length === 0 && <div className="placeholder-card compact-placeholder">No saved projects yet.</div>}
          {(projects ?? []).map((project) => (
            <button key={project.project_id} type="button" className="project-card" onClick={() => loadProject(project)}>
              <span>
                <strong>{project.name}</strong>
                <small>{project.project_id}</small>
              </span>
              <small>{project.versions?.length ?? 0} versions</small>
            </button>
          ))}
        </div>
      </section>

      <section className="surface-block rail-block benchmark-block">
        <div className="section-header compact-header">
          <div>
            <span className="section-label">Benchmark</span>
            <strong>Experiment ledger</strong>
          </div>
          <span className="section-meta">{benchmarkDashboard.totalRuns} runs</span>
        </div>
        <div className="benchmark-summary-grid">
          <div>
            <span>Localization</span>
            <strong>{benchmarkDashboard.localizationLabel}</strong>
          </div>
          <div>
            <span>Preservation</span>
            <strong>{benchmarkDashboard.preservationLabel}</strong>
          </div>
          <div>
            <span>Text pass</span>
            <strong>{benchmarkDashboard.textPassRateLabel}</strong>
          </div>
        </div>
        <div className="action-row split-actions">
          <button
            type="button"
            className="secondary-button full-width"
            onClick={recordBenchmarkRun}
            disabled={isRecordingBenchmark || !canRecordBenchmark}
          >
            {isRecordingBenchmark ? "Recording..." : "Record run"}
          </button>
          <button type="button" className="ghost-button full-width" onClick={refreshBenchmarks} disabled={isLoadingBenchmarks}>
            {isLoadingBenchmarks ? "Loading..." : "Refresh"}
          </button>
        </div>
        {benchmarkDashboard.providers.length > 0 && (
          <div className="benchmark-provider-list">
            {benchmarkDashboard.providers.slice(0, 3).map((provider) => (
              <div key={provider.provider} className="benchmark-provider-row">
                <span>
                  <strong>{provider.provider}</strong>
                  <small>{provider.run_count} runs</small>
                </span>
                <small>
                  loc {formatBenchmarkScore(provider.average_metrics?.edit_localization_score)} | keep{" "}
                  {formatBenchmarkScore(provider.average_metrics?.preservation_score)}
                </small>
              </div>
            ))}
          </div>
        )}
        <div className="benchmark-run-list">
          {(benchmarkRuns ?? []).slice(0, 3).map((run) => (
            <div key={run.benchmark_id} className="benchmark-run-row">
              <span>
                <strong>{run.run_id}</strong>
                <small>{run.provider}</small>
              </span>
              <small>{formatBenchmarkScore(run.quality_report?.evaluation?.edit_localization_score)}</small>
            </div>
          ))}
          {(benchmarkRuns ?? []).length === 0 && <div className="placeholder-card compact-placeholder">No benchmark runs yet.</div>}
        </div>
        {benchmarkDashboard.warnings.length > 0 && (
          <div className="warning-list">
            {benchmarkDashboard.warnings.slice(0, 2).map((warning) => (
              <p key={warning}>{warning}</p>
            ))}
          </div>
        )}
      </section>

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
