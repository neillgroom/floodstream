import type { Env, SourceType, MessageLog } from "./types";

// ─── Source Tag Parsing ──────────────────────────────────────────
export function parseSourceTag(text: string): {
  sourceType: SourceType;
  cleanResponse: string;
} {
  const match = text.match(/^\[SOURCE:\s*([\w_]+)\]\s*/);
  if (match) {
    const tag = match[1] as SourceType;
    const valid: SourceType[] = [
      "KB_PRIMARY",
      "KB_SUPPLEMENTED",
      "GENERAL_KNOWLEDGE",
      "ESCALATED",
      "OUT_OF_SCOPE",
    ];
    return {
      sourceType: valid.includes(tag) ? tag : "KB_PRIMARY",
      cleanResponse: text.slice(match[0].length),
    };
  }
  return { sourceType: "KB_PRIMARY", cleanResponse: text };
}

// ─── Topic Detection ──────────────────────────────────────────────
const TOPIC_PATTERNS: [RegExp, string][] = [
  [/coverag|covered|excluded|exclusion/i, "coverage"],
  [/estimat|line.?item|lump.?sum|bunch/i, "estimates"],
  [/pric|database|xactimate|deviation/i, "pricing"],
  [/document|receipt|invoice|proof.?of.?loss|POL/i, "documentation"],
  [/basement|below.?BFE|enclosure/i, "basement-coverage"],
  [/advance|partial.?payment/i, "advance-payments"],
  [/ICC|increased.?cost/i, "icc"],
  [/dry.?out|drying|dehumidif|air.?mover/i, "drying"],
  [/manufactured|mobile.?home/i, "manufactured-homes"],
  [/content|personal.?property/i, "contents"],
  [/depreciat|ACV|replacement.?cost|RCV/i, "loss-settlement"],
  [/RCBAP|condo|condominium/i, "rcbap"],
  [/subrogat/i, "subrogation"],
  [/cause.?of.?loss|proximate.?cause|flood.?definition/i, "cause-of-loss"],
  [/supplement|RAP|reopen/i, "supplements"],
  [/photo|waterline/i, "photos"],
  [/deductib|coinsurance/i, "deductibles"],
];

export function detectTopics(text: string): string[] {
  return TOPIC_PATTERNS.filter(([re]) => re.test(text)).map(([, topic]) => topic);
}

// ─── Message Logging ──────────────────────────────────────────────
export async function logMessage(env: Env, log: MessageLog): Promise<void> {
  const key = `analytics:msg:${log.conversation_id}:${log.message_index}`;
  await env.ECHO_ANALYTICS.put(key, JSON.stringify(log), {
    expirationTtl: 90 * 86400, // 90 days
  });
}

// ─── Knowledge Gap Logging ────────────────────────────────────────
export async function logKnowledgeGap(
  env: Env,
  topic: string,
  userMessage: string
): Promise<void> {
  const key = `analytics:gap:${topic}:${Date.now()}`;
  await env.ECHO_ANALYTICS.put(
    key,
    JSON.stringify({ topic, sample: userMessage.slice(0, 200), count: 1 }),
    { expirationTtl: 90 * 86400 }
  );
}
