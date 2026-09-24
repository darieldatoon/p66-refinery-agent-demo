import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Button } from "@langchain/macaw-components/Button";
import { createClient, loadWorkspace } from "./api";
import { conditionLabel, errorText, previewWorkspace, rankedIssues, writeAssetUrl } from "./domain";
import type { Snapshot, Workspace } from "./types";
import { RefineryMap } from "./components/RefineryMap";
import { IssueDetail } from "./components/IssueDetail";
import { AgentPanel } from "./components/AgentPanel";

export default function App() {
  const [workspace, setWorkspace] = useState<Workspace | null>(null);
  const [apiKey, setApiKey] = useState("");
  const [keyInput, setKeyInput] = useState("");
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [selected, setSelected] = useState(
    () => new URLSearchParams(location.search).get("asset") || "P-101A",
  );
  const [unitFilter, setUnitFilter] = useState("all");
  const [reviewFilter, setReviewFilter] = useState("all");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [activeTab, setActiveTab] = useState("overview");
  const generation = useRef(0);
  const settingsDialog = useRef<HTMLDialogElement>(null);
  const client = useMemo(() => createClient(apiKey), [apiKey]);
  useEffect(() => {
    if (settingsOpen) settingsDialog.current?.showModal();
  }, [settingsOpen]);
  const closeSettings = () => {
    setSettingsOpen(false);
    setKeyInput("");
  };
  useEffect(() => {
    fetch(`${import.meta.env.BASE_URL}snapshot.json`)
      .then((response) => {
        if (!response.ok) throw new Error("Could not load the refinery snapshot.");
        return response.json() as Promise<Snapshot>;
      })
      .then((snapshot) => setWorkspace((previous) => previous ?? previewWorkspace(snapshot)))
      .catch((cause) => setError(errorText(cause)));
  }, []);
  const refresh = useCallback(() => {
    if (!apiKey) return;
    const request = ++generation.current;
    setLoading(true);
    loadWorkspace(client, selected)
      .then((result) => {
        if (request === generation.current) {
          setWorkspace(result);
          setError("");
        }
      })
      .catch((cause) => {
        if (request === generation.current) setError(errorText(cause));
      })
      .finally(() => {
        if (request === generation.current) setLoading(false);
      });
  }, [apiKey, client, selected]);
  useEffect(refresh, [refresh]);
  const selectAsset = (id: string) => {
    setSelected(id);
    writeAssetUrl(id);
  };
  const asset =
    workspace?.assets.find((asset) => asset.asset_id === selected) ?? workspace?.assets[0];
  useEffect(() => {
    if (workspace && asset && asset.asset_id !== selected) selectAsset(asset.asset_id);
  }, [workspace, asset, selected]);
  const issue = workspace?.issues.find((issue) => issue.asset_id === asset?.asset_id);
  const units = new Map(workspace?.assets.map((asset) => [asset.asset_id, asset.unit_id]));
  const issues = workspace ? rankedIssues(workspace.issues, unitFilter, units, reviewFilter) : [];
  const assessed = workspace?.issues.filter((issue) => issue.assessment).length ?? 0;
  const pending =
    workspace?.issues
      .flatMap((issue) => issue.proposals)
      .filter((proposal) => proposal.status === "pending_review").length ?? 0;
  return (
    <div className="app-shell">
      <nav className="nav-rail" aria-label="Workspace navigation">
        <div className="brand-mark">
          R<span>•</span>
        </div>
        <button
          aria-label="Refinery overview"
          aria-pressed={activeTab === "overview"}
          onClick={() => {
            setActiveTab("overview");
            document.getElementById("refinery-overview")?.scrollIntoView({ behavior: "smooth" });
          }}
        >
          ◫
        </button>
        <button
          aria-label="Issue investigations"
          aria-pressed={activeTab === "issues"}
          onClick={() => {
            setActiveTab("issues");
            document.getElementById("issue-queue")?.scrollIntoView({ behavior: "smooth" });
          }}
        >
          ☷
        </button>
        <div className="rail-bottom">
          <button aria-label="Connection settings" onClick={() => setSettingsOpen(true)}>
            ⚙
          </button>
          <span className="avatar">DD</span>
        </div>
      </nav>
      <main className="workspace-main">
        <header className="workspace-header">
          <div className="breadcrumb">
            Operations <span>/</span> Refinery reliability
          </div>
          <div className="header-actions">
            <span className="snapshot-badge">
              <i /> Fixed snapshot · Sep 23, 2026
            </span>
            <Button
              size="sm"
              variant="outlined"
              color="secondary"
              onClick={() => setSettingsOpen(true)}
            >
              {apiKey ? "Connection settings" : "Connect agent"}
            </Button>
          </div>
        </header>
        <div className="page-title">
          <div>
            <span className="eyebrow">RELIABILITY WORKSPACE</span>
            <h1>A clearer view of what needs attention.</h1>
            <p>Investigate the evidence. Make the call. Keep your refinery moving.</p>
          </div>
          <span className="demo-badge">SYNTHETIC DEMO</span>
        </div>
        {error && (
          <div className="error-banner" role="alert">
            <span>{error}</span>
            <Button size="sm" variant="plain" onClick={() => setSettingsOpen(true)}>
              Connection settings
            </Button>
          </div>
        )}
        <div className="metrics">
          <div>
            <span>Equipment in view</span>
            <strong>
              {workspace?.assets.length ?? "—"}
              <small>across 3 process units</small>
            </strong>
          </div>
          <div>
            <span>Signals to investigate</span>
            <strong>
              {workspace?.issues.length ?? "—"}
              <small>from the fixed snapshot</small>
            </strong>
          </div>
          <div>
            <span>Agent assessments</span>
            <strong>
              {assessed}
              <small>of {workspace?.issues.length ?? 4} signals</small>
            </strong>
          </div>
          <div className={pending ? "attention" : ""}>
            <span>Awaiting your review</span>
            <strong>
              {pending}
              <small>work proposals</small>
            </strong>
          </div>
        </div>
        {workspace && asset ? (
          <div className="workspace-layout">
            <div className="operations-column">
              <section className="overview-panel panel" id="refinery-overview">
                <div className="section-heading">
                  <div>
                    <h2>Refinery overview</h2>
                    <p>Select equipment to explore its condition and evidence.</p>
                  </div>
                  <span className="live-badge">
                    {!apiKey
                      ? "Snapshot preview"
                      : error
                        ? "Connection issue"
                        : loading
                          ? "Refreshing…"
                          : "Agent connected"}
                  </span>
                </div>
                <RefineryMap
                  workspace={workspace}
                  selected={asset.asset_id}
                  onSelect={selectAsset}
                />
              </section>
              <div className="investigation-layout">
                <section className="queue-panel panel" id="issue-queue">
                  <div className="section-heading">
                    <h2>
                      Issues <span className="count">{workspace.issues.length}</span>
                    </h2>
                    <span className="muted">By priority</span>
                  </div>
                  <div className="queue-filters">
                    <label>
                      <span className="sr-only">Process unit</span>
                      <select
                        aria-label="Process unit"
                        value={unitFilter}
                        onChange={(event) => setUnitFilter(event.target.value)}
                      >
                        <option value="all">All units</option>
                        {workspace.units.map((unit) => (
                          <option key={unit.unit_id} value={unit.unit_id}>
                            {unit.unit_id}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label>
                      <span className="sr-only">Review filter</span>
                      <select
                        aria-label="Review filter"
                        value={reviewFilter}
                        onChange={(event) => setReviewFilter(event.target.value)}
                      >
                        <option value="all">All signals</option>
                        <option value="assessed">Assessed</option>
                        <option value="pending">Awaiting review</option>
                      </select>
                    </label>
                  </div>
                  <div className="issue-list">
                    {issues.map((item) => (
                      <button
                        className={`issue-card ${issue?.issue_id === item.issue_id ? "active" : ""}`}
                        key={item.issue_id}
                        onClick={() => selectAsset(item.asset_id)}
                        aria-pressed={issue?.issue_id === item.issue_id}
                      >
                        <div>
                          <span
                            className={`priority ${item.assessment?.priority ?? item.priority}`}
                          >
                            {item.assessment?.priority ?? item.priority}
                          </span>
                          <code>{item.asset_id}</code>
                          <span className="issue-arrow">↗</span>
                        </div>
                        <h3>{item.title}</h3>
                        <p>
                          {conditionLabel(item)} · {item.evidence.length} evidence sources
                        </p>
                        <span className="issue-category">
                          {item.category.replaceAll("_", " ")}
                          {item.proposals.some(
                            (proposal) => proposal.status === "pending_review",
                          ) && " · Review needed"}
                        </span>
                      </button>
                    ))}
                    {!issues.length && (
                      <p className="empty-filter">No issues match these filters.</p>
                    )}
                  </div>
                  <div className="queue-note">
                    Priority is a recommendation. Review evidence before authorizing work.
                  </div>
                </section>
                <IssueDetail
                  key={asset.asset_id}
                  asset={asset}
                  issue={issue}
                  detail={
                    workspace.selected_asset?.asset.asset_id === asset.asset_id
                      ? workspace.selected_asset
                      : null
                  }
                  loading={loading}
                  connected={!!apiKey}
                />
              </div>
            </div>
            <AgentPanel
              key={`${asset.asset_id}:${!!apiKey}`}
              apiKey={apiKey}
              asset={asset}
              issue={issue}
              onRefresh={refresh}
              onConnect={() => setSettingsOpen(true)}
            />
          </div>
        ) : (
          <div className="loading-page">Loading the refinery snapshot…</div>
        )}
        <footer className="workspace-footer">
          Synthetic refinery data · 45-day evidence window ending September 23, 2026 at 12:00 UTC ·
          Decisions remain with the operator.
        </footer>
      </main>
      {settingsOpen && (
        <dialog
          ref={settingsDialog}
          className="dialog-backdrop"
          aria-labelledby="connection-title"
          onCancel={closeSettings}
          onClick={(event) => {
            if (event.target === event.currentTarget) closeSettings();
          }}
        >
          <section className="connection-dialog">
            <button className="dialog-close" aria-label="Close settings" onClick={closeSettings}>
              ×
            </button>
            <span className="eyebrow">AGENT CONNECTION</span>
            <h2 id="connection-title">Bring the agent into the workspace.</h2>
            <p>
              Use a LangSmith API key for the deployment’s workspace. The key stays in memory and is
              cleared when you reload.
            </p>
            <form
              onSubmit={(event) => {
                event.preventDefault();
                setApiKey(keyInput.trim());
                setKeyInput("");
                setSettingsOpen(false);
              }}
            >
              <label htmlFor="api-key">LangSmith API key</label>
              <input
                id="api-key"
                type="password"
                autoComplete="off"
                value={keyInput}
                onChange={(event) => setKeyInput(event.target.value)}
                required
                autoFocus
              />
              <Button type="submit" disabled={!keyInput.trim()}>
                Connect
              </Button>
            </form>
            {apiKey && (
              <Button
                variant="plain"
                color="secondary"
                onClick={() => {
                  setApiKey("");
                  setKeyInput("");
                  setSettingsOpen(false);
                  setError("");
                  setLoading(false);
                  generation.current++;
                }}
              >
                Disconnect agent
              </Button>
            )}
            <small>A shared workspace key gives access to shared demo investigations.</small>
          </section>
        </dialog>
      )}
    </div>
  );
}
