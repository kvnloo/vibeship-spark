#!/usr/bin/env node
/**
 * Spark MCP Server
 *
 * Provides direct access to Spark's self-evolving intelligence capabilities.
 *
 * Tools:
 * - spark_status: Get system health and statistics
 * - spark_learnings: Query stored learnings from Mind
 * - spark_reflect: Trigger deep reflection and pattern analysis
 * - spark_process: Process pending events in queue
 * - spark_stats: Get learning statistics and tool effectiveness
 */

import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
  Tool,
} from "@modelcontextprotocol/sdk/types.js";
import { exec } from "child_process";
import { promisify } from "util";
import * as path from "path";
import * as fs from "fs";
import * as os from "os";

const execAsync = promisify(exec);

// Configuration
const SPARK_DIR = path.join(os.homedir(), "Desktop", "vibeship-spark");
const MIND_URL = "http://localhost:8080";
const QUEUE_DIR = path.join(os.homedir(), ".spark", "queue");

// Tool definitions
const TOOLS: Tool[] = [
  {
    name: "spark_status",
    description:
      "Get Spark system status including hook installation, Mind connection, and queue state. Use this to verify the system is healthy.",
    inputSchema: {
      type: "object",
      properties: {},
      required: [],
    },
  },
  {
    name: "spark_learnings",
    description:
      "Query learnings stored in Vibeship Mind. Returns patterns Spark has extracted from past actions.",
    inputSchema: {
      type: "object",
      properties: {
        query: {
          type: "string",
          description:
            "Search query for learnings (e.g., 'tool effectiveness', 'Bash', 'error avoidance')",
        },
        limit: {
          type: "number",
          description: "Maximum number of learnings to return (default: 10)",
        },
      },
      required: [],
    },
  },
  {
    name: "spark_reflect",
    description:
      "Trigger a deep reflection session. Analyzes all accumulated learnings, identifies meta-patterns, and stores insights.",
    inputSchema: {
      type: "object",
      properties: {},
      required: [],
    },
  },
  {
    name: "spark_process",
    description:
      "Process pending events in the queue. Extracts patterns and stores learnings in Mind.",
    inputSchema: {
      type: "object",
      properties: {},
      required: [],
    },
  },
  {
    name: "spark_stats",
    description:
      "Get learning statistics including tool effectiveness rankings, pattern counts, and improvement metrics.",
    inputSchema: {
      type: "object",
      properties: {},
      required: [],
    },
  },
  {
    name: "spark_clear_queue",
    description:
      "Clear the event queue. Use with caution - this removes unprocessed events.",
    inputSchema: {
      type: "object",
      properties: {
        confirm: {
          type: "boolean",
          description: "Must be true to confirm clearing the queue",
        },
      },
      required: ["confirm"],
    },
  },
];

// Helper functions
async function checkMindAvailable(): Promise<boolean> {
  try {
    const response = await fetch(`${MIND_URL}/health`);
    return response.ok;
  } catch {
    return false;
  }
}

async function getQueueSize(): Promise<number> {
  const queueFile = path.join(QUEUE_DIR, "events.jsonl");
  try {
    const content = fs.readFileSync(queueFile, "utf-8");
    return content.split("\n").filter((line) => line.trim()).length;
  } catch {
    return 0;
  }
}

async function runProcessor(mode: string): Promise<string> {
  const processorPath = path.join(SPARK_DIR, "processor.py");
  try {
    const { stdout, stderr } = await execAsync(
      `python "${processorPath}" --mode ${mode}`,
      { cwd: SPARK_DIR }
    );
    return stdout || stderr || "Completed";
  } catch (error: any) {
    return `Error: ${error.message}`;
  }
}

async function queryMind(query: string, limit: number = 10): Promise<any[]> {
  try {
    const response = await fetch(`${MIND_URL}/v1/memories/retrieve`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query, limit }),
    });
    if (response.ok) {
      const data = await response.json();
      return data.memories || [];
    }
    return [];
  } catch {
    return [];
  }
}

async function getMindStats(): Promise<any> {
  try {
    const response = await fetch(`${MIND_URL}/v1/stats`);
    if (response.ok) {
      return await response.json();
    }
    return {};
  } catch {
    return {};
  }
}

// Tool handlers
async function handleSparkStatus(): Promise<string> {
  const mindAvailable = await checkMindAvailable();
  const queueSize = await getQueueSize();

  // Check hook installation
  const userSettingsPath = path.join(os.homedir(), ".claude", "settings.json");
  let hooksInstalled = false;
  try {
    const settings = JSON.parse(fs.readFileSync(userSettingsPath, "utf-8"));
    hooksInstalled =
      settings.hooks &&
      Object.values(settings.hooks).some((hooks: any) =>
        hooks.some((h: any) => JSON.stringify(h).includes("vibeship-spark"))
      );
  } catch {}

  const status = {
    spark_installed: hooksInstalled,
    mind_available: mindAvailable,
    queue_pending: queueSize,
    spark_directory: SPARK_DIR,
    queue_directory: QUEUE_DIR,
  };

  let statusText = "## Spark Status\n\n";
  statusText += `- **Hooks Installed**: ${hooksInstalled ? "Yes" : "No"}\n`;
  statusText += `- **Mind Available**: ${mindAvailable ? "Yes" : "No"}\n`;
  statusText += `- **Queue Pending**: ${queueSize} events\n`;
  statusText += `- **Spark Directory**: ${SPARK_DIR}\n`;

  if (!hooksInstalled) {
    statusText += "\n### Action Needed\n";
    statusText += "Run `python setup.py install --scope user` to install Spark hooks.\n";
  }

  if (!mindAvailable) {
    statusText += "\n### Mind Not Running\n";
    statusText += "Start Mind with: `python src/mind/lite_tier.py`\n";
  }

  return statusText;
}

async function handleSparkLearnings(
  query?: string,
  limit: number = 10
): Promise<string> {
  const mindAvailable = await checkMindAvailable();
  if (!mindAvailable) {
    return "Mind is not available. Start Mind to query learnings.";
  }

  const searchQuery = query || "LEARNING";
  const memories = await queryMind(searchQuery, limit);

  if (memories.length === 0) {
    return `No learnings found for query: "${searchQuery}"`;
  }

  let result = `## Spark Learnings (${memories.length} found)\n\n`;
  for (const memory of memories) {
    result += `### ${memory.content_type || "learning"}\n`;
    result += `${memory.content}\n`;
    result += `- **Salience**: ${memory.effective_salience || memory.salience}\n`;
    result += `- **Created**: ${memory.created_at}\n\n`;
  }

  return result;
}

async function handleSparkReflect(): Promise<string> {
  const output = await runProcessor("reflect");
  return `## Reflection Complete\n\n${output}`;
}

async function handleSparkProcess(): Promise<string> {
  const output = await runProcessor("once");
  return `## Processing Complete\n\n${output}`;
}

async function handleSparkStats(): Promise<string> {
  const mindAvailable = await checkMindAvailable();
  const queueSize = await getQueueSize();

  // Get learning statistics
  const learnings = await queryMind("LEARNING", 100);
  const toolLearnings = learnings.filter((l) =>
    l.content.includes("TOOL_EFFECTIVENESS")
  );

  let result = "## Spark Statistics\n\n";
  result += `- **Total Learnings**: ${learnings.length}\n`;
  result += `- **Tool Effectiveness Learnings**: ${toolLearnings.length}\n`;
  result += `- **Queue Pending**: ${queueSize} events\n`;
  result += `- **Mind Available**: ${mindAvailable}\n\n`;

  if (toolLearnings.length > 0) {
    result += "### Tool Effectiveness\n\n";
    for (const learning of toolLearnings.slice(0, 5)) {
      // Extract key info from content
      const match = learning.content.match(
        /(\w+) has (\d+)% success rate.*\((\d+) samples\)/
      );
      if (match) {
        result += `- **${match[1]}**: ${match[2]}% success (${match[3]} samples)\n`;
      }
    }
  }

  return result;
}

async function handleSparkClearQueue(confirm: boolean): Promise<string> {
  if (!confirm) {
    return "Queue clear cancelled. Set confirm=true to proceed.";
  }

  const queueFile = path.join(QUEUE_DIR, "events.jsonl");
  try {
    fs.writeFileSync(queueFile, "");
    return "Queue cleared successfully.";
  } catch (error: any) {
    return `Error clearing queue: ${error.message}`;
  }
}

// Main server
async function main() {
  const server = new Server(
    {
      name: "spark-mcp",
      version: "0.1.0",
    },
    {
      capabilities: {
        tools: {},
      },
    }
  );

  // List tools
  server.setRequestHandler(ListToolsRequestSchema, async () => {
    return { tools: TOOLS };
  });

  // Handle tool calls
  server.setRequestHandler(CallToolRequestSchema, async (request) => {
    const { name, arguments: args } = request.params;

    try {
      let result: string;

      switch (name) {
        case "spark_status":
          result = await handleSparkStatus();
          break;
        case "spark_learnings":
          result = await handleSparkLearnings(
            args?.query as string,
            (args?.limit as number) || 10
          );
          break;
        case "spark_reflect":
          result = await handleSparkReflect();
          break;
        case "spark_process":
          result = await handleSparkProcess();
          break;
        case "spark_stats":
          result = await handleSparkStats();
          break;
        case "spark_clear_queue":
          result = await handleSparkClearQueue(args?.confirm as boolean);
          break;
        default:
          result = `Unknown tool: ${name}`;
      }

      return {
        content: [{ type: "text", text: result }],
      };
    } catch (error: any) {
      return {
        content: [{ type: "text", text: `Error: ${error.message}` }],
        isError: true,
      };
    }
  });

  // Start server
  const transport = new StdioServerTransport();
  await server.connect(transport);
  console.error("Spark MCP server running");
}

main().catch(console.error);
