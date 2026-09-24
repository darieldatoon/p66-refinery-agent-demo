import { Client } from "@langchain/langgraph-sdk";
import type { AgentState, Workspace } from "./types";

export const ASSISTANT = "refinery-reliability-agent";
export const API_URL =
  import.meta.env.VITE_MDA_API_URL ||
  "https://refinery-reliability-agent-2ff25319fc775250b7402d9fae3a6b66.us.langgraph.app";

export function createClient(apiKey: string): Client {
  return new Client({ apiUrl: API_URL, apiKey });
}

export async function loadWorkspace(client: Client): Promise<Workspace> {
  const result = (await client.runs.wait(null, ASSISTANT, {
    input: {},
    context: { operation: "workspace" },
    metadata: { source: "refinery-workspace", operation: "workspace" },
  })) as AgentState & { __error__?: { message?: string } };
  if (result.__error__ || !result.workspace?.issues)
    throw new Error(
      result.__error__?.message || "The agent did not return the refinery workspace.",
    );
  return result.workspace;
}
