import type { ConversationMessage } from "./types";

const ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages";
const MODEL = "claude-haiku-4-5-20251001";

interface AnthropicResponse {
  content: Array<{ type: string; text: string }>;
  stop_reason: string;
  usage: {
    input_tokens: number;
    output_tokens: number;
    cache_creation_input_tokens?: number;
    cache_read_input_tokens?: number;
  };
}

export interface CallResult {
  text: string;
  tokens_in: number;
  tokens_out: number;
  cache_write_tokens: number;
  cache_read_tokens: number;
  truncated: boolean;
}

export async function callAnthropicStream(
  apiKey: string,
  systemPrompt: string,
  messages: ConversationMessage[]
): Promise<{ body: ReadableStream<Uint8Array> }> {
  const body = {
    model: MODEL,
    max_tokens: 2048,
    temperature: 0,
    stream: true,
    system: [
      {
        type: "text",
        text: systemPrompt,
        cache_control: { type: "ephemeral" },
      },
    ],
    messages: messages.map((m) => ({
      role: m.role,
      content: m.content,
    })),
  };

  const response = await fetch(ANTHROPIC_API_URL, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "x-api-key": apiKey,
      "anthropic-version": "2023-06-01",
      "anthropic-beta": "prompt-caching-2024-07-31",
    },
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    const errText = await response.text();
    throw new Error(`Anthropic API error ${response.status}: ${errText}`);
  }

  if (!response.body) {
    throw new Error("Anthropic returned no body for streaming request");
  }

  return { body: response.body };
}

// Cost calculation based on Haiku 4.5 pricing
export function calculateCost(result: CallResult): number {
  const inputCost = (result.tokens_in / 1_000_000) * 1.0;
  const outputCost = (result.tokens_out / 1_000_000) * 5.0;
  const cacheWriteCost = (result.cache_write_tokens / 1_000_000) * 1.25;
  const cacheReadCost = (result.cache_read_tokens / 1_000_000) * 0.1;
  return inputCost + outputCost + cacheWriteCost + cacheReadCost;
}
