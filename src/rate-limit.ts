import type { Env, AppConfig } from "./types";
import { CONFIG } from "./config";

interface RateLimitResult {
  allowed: boolean;
  reason?: string;
}

export async function checkRateLimit(
  env: Env,
  conversationId: string,
  ip: string
): Promise<RateLimitResult> {
  if (env.DISABLE_RATE_LIMIT) {
    return { allowed: true };
  }

  const { rate_limits } = CONFIG;

  // Check per-conversation message count
  const msgKey = `msg_count:${conversationId}`;
  const msgCountStr = await env.ECHO_RATE_LIMITS.get(msgKey);
  const msgCount = msgCountStr ? parseInt(msgCountStr, 10) : 0;

  if (msgCount >= rate_limits.messages_per_conversation) {
    return { allowed: false, reason: "conversation_limit" };
  }

  // Check per-IP conversation limit (only on first message)
  if (msgCount === 0) {
    const hourBucket = Math.floor(Date.now() / 3600000);
    const ipKey = `ip_convos:${ip}:${hourBucket}`;
    const ipCountStr = await env.ECHO_RATE_LIMITS.get(ipKey);
    const ipCount = ipCountStr ? parseInt(ipCountStr, 10) : 0;

    if (ipCount >= rate_limits.conversations_per_ip_per_hour) {
      return { allowed: false, reason: "ip_limit" };
    }

    await env.ECHO_RATE_LIMITS.put(ipKey, String(ipCount + 1), {
      expirationTtl: 3600,
    });
  }

  // Increment message count
  await env.ECHO_RATE_LIMITS.put(msgKey, String(msgCount + 1), {
    expirationTtl: 3600,
  });

  return { allowed: true };
}
