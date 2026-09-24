import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Badge } from "@langchain/macaw-components/Badge";
import { Banner } from "@langchain/macaw-components/Banner";
import { Button } from "@langchain/macaw-components/Button";
import { Dialog, DialogContent } from "@langchain/macaw-components/Dialog";
import { GroupedTabs } from "@langchain/macaw-components/GroupedTabs";
import { IconButton } from "@langchain/macaw-components/IconButton";
import { Input } from "@langchain/macaw-components/Input";
import { Text } from "@langchain/macaw-components/Text";
import { cn } from "@langchain/macaw-components/utils/cn";
import { useColorScheme } from "@langchain/macaw-components/hooks/useColorScheme";
import { AsteriskIcon } from "@phosphor-icons/react/dist/ssr/Asterisk";
import { MoonIcon } from "@phosphor-icons/react/dist/ssr/Moon";
import { SunIcon } from "@phosphor-icons/react/dist/ssr/Sun";
import { createClient, loadWorkspace } from "./api";
import {
  errorText,
  pendingProposal,
  previewWorkspace,
  writeAssetUrl,
  type ReviewFilter,
} from "./domain";
import type { AssetDetail as Detail, Snapshot, Workspace } from "./types";
import { AgentPanel, type AgentAction, type AgentRequest } from "./components/AgentPanel";
import { AssetDetail } from "./components/AssetDetail";
import { EquipmentMap } from "./components/EquipmentMap";
import { IssueQueue } from "./components/IssueQueue";

type Browse = "issues" | "equipment";

export default function App() {
  const [workspace, setWorkspace] = useState<Workspace | null>(null);
  const [evidence, setEvidence] = useState<Record<string, Detail>>({});
  const [apiKey, setApiKey] = useState("");
  const [keyInput, setKeyInput] = useState("");
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [selected, setSelected] = useState(
    () => new URLSearchParams(location.search).get("asset") || "P-101A",
  );
  const [browse, setBrowse] = useState<Browse>("issues");
  const [unitFilter, setUnitFilter] = useState("all");
  const [reviewFilter, setReviewFilter] = useState<ReviewFilter>("all");
  const [visited, setVisited] = useState<string[]>([]);
  const [request, setRequest] = useState<AgentRequest | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const generation = useRef(0);
  const { isDarkMode, setMode } = useColorScheme();
  const client = useMemo(() => createClient(apiKey), [apiKey]);
  useEffect(() => {
    fetch(`${import.meta.env.BASE_URL}snapshot.json`)
      .then((response) => {
        if (!response.ok) throw new Error("Could not load the refinery snapshot.");
        return response.json() as Promise<Snapshot>;
      })
      .then((snapshot) => {
        setEvidence(snapshot.evidence);
        setWorkspace((previous) => previous ?? previewWorkspace(snapshot));
      })
      .catch((cause) => setError(errorText(cause)));
  }, []);
  const refresh = useCallback(() => {
    if (!apiKey) return;
    const current = ++generation.current;
    setLoading(true);
    loadWorkspace(client)
      .then((result) => {
        if (current === generation.current) {
          setWorkspace(result);
          setError("");
        }
      })
      .catch((cause) => {
        if (current === generation.current) setError(errorText(cause));
      })
      .finally(() => {
        if (current === generation.current) setLoading(false);
      });
  }, [apiKey, client]);
  useEffect(refresh, [refresh]);
  const asset =
    workspace?.assets.find((item) => item.asset_id === selected) ?? workspace?.assets[0];
  useEffect(() => {
    if (!asset) return;
    if (asset.asset_id !== selected) setSelected(asset.asset_id);
    setVisited((previous) =>
      previous.includes(asset.asset_id) ? previous : [...previous, asset.asset_id],
    );
  }, [asset, selected]);
  const selectAsset = (id: string) => {
    setSelected(id);
    writeAssetUrl(id);
  };
  const requestAgent = (action: AgentAction) => {
    if (!apiKey || !asset) {
      setSettingsOpen(true);
      return;
    }
    setRequest({ assetId: asset.asset_id, action, nonce: Date.now() });
  };
  const closeSettings = () => {
    setSettingsOpen(false);
    setKeyInput("");
  };
  const disconnect = () => {
    setApiKey("");
    setVisited(asset ? [asset.asset_id] : []);
    setError("");
    setLoading(false);
    generation.current++;
    closeSettings();
  };
  const issues = workspace?.issues ?? [];
  const assessed = issues.filter((item) => item.assessment).length;
  const awaiting = issues.filter((item) => pendingProposal(item)).length;
  const issueFor = (assetId: string) => issues.find((item) => item.asset_id === assetId);
  return (
    <div className="flex min-h-screen flex-col bg-surface-level-1 text-primary lg:h-screen">
      <header className="flex flex-wrap items-center gap-space-3 border-b border-muted px-space-5 py-space-3">
        <span className="flex size-8 items-center justify-center rounded-md bg-brand text-brand-on-fill">
          <AsteriskIcon aria-hidden size={18} weight="bold" />
        </span>
        <div className="flex flex-col">
          <Text variant="md" weight="semibold" as="h1">
            Refinery Reliability
          </Text>
          <Text variant="xs" color="tertiary" as="span">
            Synthetic data · snapshot Sep 23, 2026 12:00 UTC
          </Text>
        </div>
        <div className="ml-auto flex flex-wrap items-center gap-space-3">
          <Text variant="xs" color="secondary" as="span" aria-live="polite">
            {apiKey
              ? loading
                ? "Refreshing…"
                : `${assessed} of ${issues.length} assessed · ${awaiting} awaiting review`
              : "Preview · connect to investigate"}
          </Text>
          <IconButton
            icon={isDarkMode ? SunIcon : MoonIcon}
            label={isDarkMode ? "Use light theme" : "Use dark theme"}
            variant="plain"
            color="secondary"
            onClick={() => setMode(isDarkMode ? "light" : "dark")}
          />
          <Button
            size="sm"
            variant={apiKey ? "outlined" : "normal"}
            color={apiKey ? "secondary" : "primary"}
            onClick={() => setSettingsOpen(true)}
          >
            {apiKey ? "Agent connected" : "Connect agent"}
          </Button>
        </div>
      </header>
      {error && (
        <div className="px-space-5 pt-space-3">
          <Banner
            intent="error"
            action={
              <Button
                size="sm"
                variant="outlined"
                color="secondary"
                onClick={() => setSettingsOpen(true)}
              >
                Connection settings
              </Button>
            }
          >
            {error}
          </Banner>
        </div>
      )}
      {workspace && asset ? (
        <main className="grid min-h-0 flex-1 gap-space-4 p-space-4 lg:grid-cols-[18rem_minmax(0,1fr)_24rem] xl:grid-cols-[20rem_minmax(0,1fr)_26rem]">
          <nav aria-label="Browse" className="flex min-h-0 flex-col gap-space-3">
            <GroupedTabs<Browse>
              value={browse}
              onChange={setBrowse}
              options={[
                {
                  value: "issues",
                  display: "Issues",
                  rightDecorator: (
                    <Badge size="xs" color="secondary">
                      {String(issues.length)}
                    </Badge>
                  ),
                },
                {
                  value: "equipment",
                  display: "Equipment",
                  rightDecorator: (
                    <Badge size="xs" color="secondary">
                      {String(workspace.assets.length)}
                    </Badge>
                  ),
                },
              ]}
            />
            <div className="min-h-0 flex-1 overflow-y-auto pr-space-1">
              {browse === "issues" ? (
                <IssueQueue
                  workspace={workspace}
                  selected={asset.asset_id}
                  unit={unitFilter}
                  review={reviewFilter}
                  onUnitChange={setUnitFilter}
                  onReviewChange={setReviewFilter}
                  onSelect={selectAsset}
                />
              ) : (
                <EquipmentMap
                  workspace={workspace}
                  selected={asset.asset_id}
                  onSelect={selectAsset}
                />
              )}
            </div>
          </nav>
          <AssetDetail
            key={asset.asset_id}
            asset={asset}
            issue={issueFor(asset.asset_id)}
            detail={evidence[asset.asset_id]}
            connected={!!apiKey}
            onInvestigate={() => requestAgent("investigate")}
          />
          <div className="min-h-[36rem] lg:min-h-0">
            {apiKey ? (
              visited.map((assetId) => {
                const item = workspace.assets.find((candidate) => candidate.asset_id === assetId);
                return item ? (
                  <div
                    key={`${assetId}:${apiKey}`}
                    className={cn("h-full", assetId !== asset.asset_id && "hidden")}
                  >
                    <AgentPanel
                      apiKey={apiKey}
                      asset={item}
                      issue={issueFor(assetId)}
                      request={request}
                      onRequestHandled={() => setRequest(null)}
                      onRefresh={refresh}
                      onConnect={() => setSettingsOpen(true)}
                    />
                  </div>
                ) : null;
              })
            ) : (
              <AgentPanel
                apiKey=""
                asset={asset}
                issue={issueFor(asset.asset_id)}
                onRefresh={refresh}
                onConnect={() => setSettingsOpen(true)}
              />
            )}
          </div>
        </main>
      ) : (
        <div className="flex flex-1 items-center justify-center">
          <Text color="tertiary">Loading the refinery snapshot…</Text>
        </div>
      )}
      <Dialog
        open={settingsOpen}
        onOpenChange={(open) => (open ? setSettingsOpen(true) : closeSettings())}
      >
        <DialogContent
          title="Connect the agent"
          description="Use a LangSmith API key for the deployment's workspace. The key stays in memory and is cleared on reload."
        >
          <form
            className="flex flex-col gap-space-4"
            onSubmit={(event) => {
              event.preventDefault();
              setApiKey(keyInput.trim());
              closeSettings();
            }}
          >
            <Input
              id="api-key"
              size="md"
              type="password"
              label="LangSmith API key"
              autoComplete="off"
              value={keyInput}
              onChange={setKeyInput}
              required
              autoFocus
            />
            <Text variant="xs" color="tertiary">
              A shared workspace key can see every presenter's investigations.
            </Text>
            <div className="flex justify-end gap-space-2">
              {apiKey && (
                <Button
                  type="button"
                  size="sm"
                  variant="outlined"
                  color="secondary"
                  onClick={disconnect}
                >
                  Disconnect
                </Button>
              )}
              <Button type="submit" size="sm" disabled={!keyInput.trim()}>
                Connect
              </Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
