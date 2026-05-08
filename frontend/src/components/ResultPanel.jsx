import { candidateScoreSummary, summarizeInitGeneration } from "../initCandidates.js";
import { formatBenchmarkScore, summarizeBenchmarkSummary } from "../benchmarkState.js";
import { canCancelGenerationSnapshot, extractGenerationProviderMetadata } from "../smartGeneration.js";

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
  smartJobSnapshot,
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
  const activeJobSnapshot = smartJobSnapshot || jobSnapshot;
  const activeJobStatus = activeJobSnapshot?.status ?? "";
  const generationMetadata = extractGenerationProviderMetadata({ latestResult, smartJobSnapshot });
  const hasGenerationMetadata = Boolean(
    generationMetadata.provider || generationMetadata.pipeline || generationMetadata.model,
  );
  const canCancelJob = canCancelGenerationSnapshot(activeJobSnapshot);
  const exportWarnings = Array.from(new Set([...(textValidationReport?.warnings ?? []), ...(svgExport?.warnings ?? [])]));
  const initSummary = summarizeInitGeneration(initGeneration);
  const benchmarkDashboard = summarizeBenchmarkSummary(benchmarkSummary);
  const projectVersionCount = currentProject?.versions?.length ?? 0;

  return (
    <aside className="workbench-panel result-panel">
      <div className="panel-heading result-heading">
        <div>
          <p className="panel-eyebrow">输出</p>
          <h2>生成结果</h2>
        </div>
        <span className={latestResult ? "status-pill compact success-state" : "status-pill compact"}>{latestResult ? "结果已生成" : "等待结果"}</span>
      </div>

      <section className="surface-block emphasis-block preview-block">
        <div className="section-header compact-header">
          <div>
            <span className="section-label">预览</span>
            <strong>最新结果</strong>
          </div>
        </div>
        <div className="result-preview">
          {latestResult ? <img src={latestResult.result_image} alt="生成结果" /> : <div className="placeholder-card">生成结果会显示在这里</div>}
        </div>
        {latestResult && (
          <button type="button" className="secondary-button full-width" onClick={() => continueFromHistory(latestResult)}>
            继续编辑当前结果
          </button>
        )}
      </section>

      {initCandidates.length > 0 && (
        <section className="surface-block rail-block candidate-block">
          <div className="section-header compact-header">
            <div>
              <span className="section-label">初图</span>
              <strong>初图候选</strong>
            </div>
            {initPlan && <span className="section-meta">{initSummary.fallbackUsed ? "回退候选" : "候选已就绪"}</span>}
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
                    <strong>{score.rank ? `候选 #${score.rank}` : "候选图"}</strong>
                    <small>种子 {candidate.seed} | 评分 {score.scoreLabel}</small>
                    <small className="candidate-meta">标签覆盖 {score.labelCoverageLabel}</small>
                  </span>
                </button>
              );
            })}
          </div>
        </section>
      )}

      {activeJobSnapshot && (
        <section className="surface-block rail-block job-block">
          <div className="section-header compact-header">
            <div>
              <span className="section-label">任务</span>
              <strong>生成状态</strong>
            </div>
            <span className="section-meta">{activeJobStatus}</span>
          </div>
          <div className="job-progress">
            <div>
              <span>生成进度</span>
              <strong>{Math.round((activeJobSnapshot.progress ?? 0) * 100)}%</strong>
            </div>
            <progress value={activeJobSnapshot.progress ?? 0} max="1" />
            <p>{activeJobSnapshot.error || activeJobSnapshot.message}</p>
            {hasGenerationMetadata && (
              <p>
                Provider {generationMetadata.provider || "n/a"} | Pipeline {generationMetadata.pipeline || "n/a"} |
                Model {generationMetadata.model || "n/a"}
              </p>
            )}
            {(smartJobSnapshot?.metadata?.fallback_used || smartJobSnapshot?.metadata?.is_diagnostic_result) && (
              <p className="warning-text">当前结果是诊断占位，不代表正式模型生成效果。</p>
            )}
            {canCancelJob && (
              <button type="button" className="ghost-button full-width" onClick={cancelGenerateJob}>
                取消任务
              </button>
            )}
          </div>
        </section>
      )}

      {(textValidationReport || svgExport) && (
        <section className="surface-block rail-block export-block">
          <div className="section-header compact-header">
            <div>
              <span className="section-label">导出</span>
              <strong>文本与 SVG</strong>
            </div>
            {textValidationReport && <span className={`section-meta export-status ${textValidationReport.status}`}>{textValidationReport.status}</span>}
          </div>
          {textValidationReport && (
            <div className="export-summary">
              <div>
                <span>已匹配</span>
                <strong>{textValidationReport.matched_labels?.length ?? 0}</strong>
              </div>
              <div>
                <span>缺失</span>
                <strong>{textValidationReport.missing_labels?.length ?? 0}</strong>
              </div>
              <p>{(textValidationReport.matched_labels ?? []).join(", ") || "暂无匹配文本。"}</p>
              {(textValidationReport.missing_labels ?? []).length > 0 && (
                <p className="warning-text">缺失：{textValidationReport.missing_labels.join(", ")}</p>
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

      <details className="surface-block rail-block project-block">
        <summary className="details-summary">
          <span className="section-label">高级</span>
          <strong>项目版本</strong>
          <span className="section-meta">{currentProject ? `${projectVersionCount} 个版本` : "未保存"}</span>
        </summary>
        <div className="project-summary">
          <div>
            <span>当前状态</span>
            <strong>{currentProject ? "已保存项目" : "临时编辑"}</strong>
          </div>
          <div>
            <span>版本数量</span>
            <strong>{projectVersionCount}</strong>
          </div>
        </div>
        <div className="action-row split-actions">
          <button
            type="button"
            className="secondary-button full-width"
            onClick={saveCurrentProjectVersion}
            disabled={isSavingProject || !canSaveProject}
          >
            {isSavingProject ? "保存中..." : "保存版本"}
          </button>
          <button type="button" className="ghost-button full-width" onClick={refreshProjects} disabled={isLoadingProjects}>
            {isLoadingProjects ? "刷新中..." : "刷新"}
          </button>
        </div>
        <div className="project-list">
          {(projects ?? []).length === 0 && <div className="placeholder-card compact-placeholder">暂无保存项目。</div>}
          {(projects ?? []).map((project) => (
            <button key={project.project_id} type="button" className="project-card" onClick={() => loadProject(project)} title={project.project_id}>
              <span>
                <strong>{project.name}</strong>
                <small>点击载入项目</small>
              </span>
              <small>{project.versions?.length ?? 0} 版</small>
            </button>
          ))}
        </div>
      </details>

      <details className="surface-block rail-block result-details">
        <summary className="details-summary">
          <span className="section-label">实验</span>
          <strong>实验记录</strong>
          <span className="section-meta">{benchmarkDashboard.totalRuns} 次</span>
        </summary>
        <div className="benchmark-summary-grid">
          <div>
            <span>局部化</span>
            <strong>{benchmarkDashboard.localizationLabel}</strong>
          </div>
          <div>
            <span>保真</span>
            <strong>{benchmarkDashboard.preservationLabel}</strong>
          </div>
          <div>
            <span>文本通过</span>
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
            {isRecordingBenchmark ? "记录中..." : "记录本轮"}
          </button>
          <button type="button" className="ghost-button full-width" onClick={refreshBenchmarks} disabled={isLoadingBenchmarks}>
            {isLoadingBenchmarks ? "刷新中..." : "刷新"}
          </button>
        </div>
        {benchmarkDashboard.providers.length > 0 && (
          <div className="benchmark-provider-list">
            {benchmarkDashboard.providers.slice(0, 3).map((provider) => (
              <div key={provider.provider} className="benchmark-provider-row">
                <span>
                  <strong>{provider.provider}</strong>
                  <small>{provider.run_count} 次</small>
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
          {(benchmarkRuns ?? []).length === 0 && <div className="placeholder-card compact-placeholder">暂无实验记录。</div>}
        </div>
        {benchmarkDashboard.warnings.length > 0 && (
          <div className="warning-list">
            {benchmarkDashboard.warnings.slice(0, 2).map((warning) => (
              <p key={warning}>{warning}</p>
            ))}
          </div>
        )}
      </details>

      {latestResult?.evaluation && (
        <details className="surface-block rail-block result-details">
          <summary className="details-summary">
            <span className="section-label">指标</span>
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
                  <span>提示追踪</span>
                  <strong>{qualityPrompt.task ?? "n/a"}</strong>
                  <p>
                    {qualityPrompt.planner_source ?? "unknown"} | seed {qualityPrompt.seed ?? "n/a"}
                  </p>
                </div>
                {hasGenerationMetadata && (
                  <div className="metric-card">
                    <span>生成 Provider</span>
                    <strong>{generationMetadata.provider || "n/a"}</strong>
                    <p>
                      pipeline {generationMetadata.pipeline || "n/a"} | model {generationMetadata.model || "n/a"}
                    </p>
                  </div>
                )}
              </>
            )}
            <div className="metric-card">
              <span>评估说明</span>
              <strong>结果说明</strong>
              <p>{latestResult.evaluation.note}</p>
            </div>
          </section>
        </details>
      )}

      {canvasState && (
        <details className="surface-block rail-block result-details">
          <summary className="details-summary">
            <span className="section-label">诊断</span>
            <strong>画布状态</strong>
          </summary>
          <div className="canvas-state-grid">
            <div>
              <span>图层</span>
              <strong>{layerCount}</strong>
            </div>
            <div>
              <span>历史</span>
              <strong>{historyCount}</strong>
            </div>
            <div>
              <span>来源</span>
              <strong>{canvasState.source}</strong>
            </div>
            <div>
              <span>最近版本</span>
              <strong>{latestProjectVersionId}</strong>
            </div>
          </div>
        </details>
      )}

      <details className="surface-block rail-block result-details">
        <summary className="details-summary">
          <span className="section-label">历史</span>
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
