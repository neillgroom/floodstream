// ─── Anthropic SSE Event Parser ──────────────────────────────────
// Anthropic streams events like:
//   event: content_block_delta
//   data: {"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":"Hello"}}
//
//   event: message_start
//   data: {"type":"message_start","message":{"usage":{"input_tokens":100,...}}}
//
//   event: message_delta
//   data: {"type":"message_delta","delta":{"stop_reason":"end_turn"},"usage":{"output_tokens":42}}

export interface ParsedAnthropicEvent {
  type: "text" | "usage" | "stop" | "ignored";
  text?: string;
  inputTokens?: number;
  outputTokens?: number;
  cacheWriteTokens?: number;
  cacheReadTokens?: number;
  stopReason?: string;
}

export function parseAnthropicLine(data: string): ParsedAnthropicEvent {
  try {
    const parsed = JSON.parse(data);

    if (
      parsed.type === "content_block_delta" &&
      parsed.delta?.type === "text_delta"
    ) {
      return { type: "text", text: parsed.delta.text };
    }

    if (parsed.type === "message_start" && parsed.message?.usage) {
      const u = parsed.message.usage;
      return {
        type: "usage",
        inputTokens: u.input_tokens,
        cacheWriteTokens: u.cache_creation_input_tokens,
        cacheReadTokens: u.cache_read_input_tokens,
      };
    }

    if (parsed.type === "message_delta") {
      return {
        type: "stop",
        stopReason: parsed.delta?.stop_reason,
        outputTokens: parsed.usage?.output_tokens,
      };
    }

    return { type: "ignored" };
  } catch {
    return { type: "ignored" };
  }
}

// ─── Source Tag Stripper ────────────────────────────────────────
// Buffers initial text from the stream to detect and strip [SOURCE: XX] tags.
// After the tag is handled (or determined absent), passes text through directly.

export class SourceTagStripper {
  private buffer = "";
  private stripped = false;
  private trimNextLeadingSpace = false;
  private readonly regex = /^\[SOURCE:\s*[\w_]+\]\s*/;
  private readonly threshold: number;

  constructor(threshold = 40) {
    this.threshold = threshold;
  }

  /** Feed text into the stripper. Returns clean text to forward, or null if still buffering. */
  feed(text: string): string | null {
    if (this.stripped) {
      // If the tag was just stripped and the remainder was empty,
      // the space between tag and content may arrive in this chunk.
      if (this.trimNextLeadingSpace) {
        this.trimNextLeadingSpace = false;
        text = text.replace(/^\s+/, "");
        return text || null;
      }
      return text;
    }

    this.buffer += text;

    // If buffer doesn't start with '[', there's no source tag — flush immediately
    if (this.buffer.length > 0 && this.buffer[0] !== "[") {
      this.stripped = true;
      return this.buffer;
    }

    // Check if we can see the completed tag
    const match = this.buffer.match(this.regex);
    if (match) {
      this.stripped = true;
      const remainder = this.buffer.slice(match[0].length);
      if (remainder) return remainder;
      // Tag matched but no content yet — the space may arrive next chunk
      this.trimNextLeadingSpace = true;
      return null;
    }

    // Hit threshold without finding tag — flush everything
    if (this.buffer.length >= this.threshold) {
      this.stripped = true;
      return this.buffer;
    }

    // Still buffering — waiting for more text
    return null;
  }

  /** Flush any remaining buffer (call when stream ends). */
  flush(): string | null {
    if (!this.stripped && this.buffer) {
      this.stripped = true;
      const match = this.buffer.match(this.regex);
      if (match) {
        const remainder = this.buffer.slice(match[0].length);
        return remainder || null;
      }
      return this.buffer;
    }
    return null;
  }

  /** Whether the source tag has been handled (stripped or determined absent). */
  get isDone(): boolean {
    return this.stripped;
  }
}
