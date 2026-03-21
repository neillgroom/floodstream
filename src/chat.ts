import type { Env, ChatRequest, ErrorResponse } from "./types";
import { checkRateLimit } from "./rate-limit";
import { loadConversation, saveConversation } from "./conversation";
import { getSystemPrompt } from "./system-prompt";
import { callAnthropicStream, calculateCost } from "./anthropic";
import type { CallResult } from "./anthropic";
import { parseAnthropicLine, SourceTagStripper } from "./stream-parser";
import { parseSourceTag, detectTopics, logMessage, logKnowledgeGap } from "./analytics";

function errorResponse(
  status: number,
  error: ErrorResponse["error"],
  message: string
): Response {
  const body: ErrorResponse = { error, message };
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

export async function handleChat(
  request: Request,
  env: Env
): Promise<Response> {
  // ── Parse request ──────────────────────────────────────────────
  let body: ChatRequest;
  try {
    body = (await request.json()) as ChatRequest;
  } catch {
    return errorResponse(400, "invalid_request", "Invalid JSON body");
  }

  const { conversation_id, message, page_url, message_index } = body;

  if (!conversation_id || !message) {
    return errorResponse(
      400,
      "invalid_request",
      "Missing required fields: conversation_id, message"
    );
  }

  // ── Rate limiting ──────────────────────────────────────────────
  const ip =
    request.headers.get("CF-Connecting-IP") ||
    request.headers.get("X-Forwarded-For") ||
    "unknown";

  const rateCheck = await checkRateLimit(env, conversation_id, ip);
  if (!rateCheck.allowed) {
    return errorResponse(
      429,
      "rate_limited",
      "You've reached the conversation limit. Please try again later."
    );
  }

  // ── Load conversation history ──────────────────────────────────
  const history = await loadConversation(env, conversation_id);
  history.push({ role: "user", content: message });

  // ── Call Anthropic (streaming) ─────────────────────────────────
  const systemPrompt = getSystemPrompt();

  let streamResult;
  try {
    streamResult = await callAnthropicStream(
      env.ANTHROPIC_API_KEY,
      systemPrompt,
      history
    );
  } catch (err) {
    console.error("Anthropic API error:", err);
    return errorResponse(
      502,
      "api_error",
      "I'm having a technical issue right now. Please try again in a moment."
    );
  }

  // ── Transform Anthropic SSE → Widget SSE ───────────────────────
  const encoder = new TextEncoder();
  const decoder = new TextDecoder();

  let fullText = "";
  let inputTokens = 0;
  let outputTokens = 0;
  let cacheWriteTokens = 0;
  let cacheReadTokens = 0;
  let stopReason = "";

  const stripper = new SourceTagStripper();

  let resolveStreamDone: () => void;
  const streamDone = new Promise<void>((r) => {
    resolveStreamDone = r;
  });

  function enqueueText(
    controller: ReadableStreamDefaultController,
    text: string
  ) {
    controller.enqueue(
      encoder.encode(`data: ${JSON.stringify({ type: "delta", text })}\n\n`)
    );
  }

  const readable = new ReadableStream({
    async start(controller) {
      const reader = streamResult.body.getReader();
      let lineBuffer = "";

      try {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          lineBuffer += decoder.decode(value, { stream: true });

          const lines = lineBuffer.split("\n");
          lineBuffer = lines.pop() || "";

          for (const line of lines) {
            const trimmed = line.trim();
            if (!trimmed.startsWith("data: ")) continue;
            const data = trimmed.slice(6);
            if (data === "[DONE]") continue;

            const event = parseAnthropicLine(data);

            if (event.type === "text" && event.text) {
              fullText += event.text;
              const clean = stripper.feed(event.text);
              if (clean) enqueueText(controller, clean);
            } else if (event.type === "usage") {
              inputTokens = event.inputTokens || 0;
              cacheWriteTokens = event.cacheWriteTokens || 0;
              cacheReadTokens = event.cacheReadTokens || 0;
            } else if (event.type === "stop") {
              stopReason = event.stopReason || "";
              outputTokens = event.outputTokens || 0;
            }
          }
        }

        const flushed = stripper.flush();
        if (flushed) enqueueText(controller, flushed);

        const truncated = stopReason === "max_tokens";
        controller.enqueue(
          encoder.encode(
            `data: ${JSON.stringify({
              type: "done",
              conversation_id,
              message_index,
              truncated,
            })}\n\n`
          )
        );

        controller.close();
        resolveStreamDone();
      } catch (err) {
        console.error("Stream processing error:", err);
        try {
          controller.enqueue(
            encoder.encode(
              `data: ${JSON.stringify({
                type: "error",
                message: "Stream interrupted",
              })}\n\n`
            )
          );
        } catch {
          // Controller may already be closed
        }
        controller.close();
        resolveStreamDone();
      }
    },
  });

  // ── Background cleanup (KV save + analytics) ──────────────────
  const ctx = (request as any).ctx;
  if (ctx?.waitUntil) {
    const cleanupPromise = (async () => {
      await streamDone;

      const { sourceType, cleanResponse } = parseSourceTag(fullText);

      history.push({ role: "assistant", content: cleanResponse });
      await saveConversation(env, conversation_id, history);

      const result: CallResult = {
        text: cleanResponse,
        tokens_in: inputTokens,
        tokens_out: outputTokens,
        cache_write_tokens: cacheWriteTokens,
        cache_read_tokens: cacheReadTokens,
        truncated: stopReason === "max_tokens",
      };

      const cost = calculateCost(result);
      const topics = detectTopics(message + " " + cleanResponse);

      await logMessage(env, {
        conversation_id,
        message_index,
        timestamp: new Date().toISOString(),
        user_message: message,
        assistant_response: cleanResponse,
        source_type: sourceType,
        tokens_in: inputTokens,
        tokens_out: outputTokens,
        cost_usd: cost,
        page_url,
        topics,
      });

      if (sourceType === "GENERAL_KNOWLEDGE") {
        await Promise.all(
          topics.map((t) => logKnowledgeGap(env, t, message))
        );
      }
    })();

    ctx.waitUntil(cleanupPromise);
  }

  // ── Return SSE response ───────────────────────────────────────
  return new Response(readable, {
    status: 200,
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache",
      Connection: "keep-alive",
    },
  });
}
