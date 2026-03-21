import type { Env, ConversationMessage } from "./types";

const CONVERSATION_TTL = 3600; // 1 hour

export async function loadConversation(
  env: Env,
  conversationId: string
): Promise<ConversationMessage[]> {
  const data = await env.ECHO_CONVERSATIONS.get(conversationId);
  if (!data) return [];
  try {
    return JSON.parse(data) as ConversationMessage[];
  } catch {
    return [];
  }
}

export async function saveConversation(
  env: Env,
  conversationId: string,
  messages: ConversationMessage[]
): Promise<void> {
  await env.ECHO_CONVERSATIONS.put(
    conversationId,
    JSON.stringify(messages),
    { expirationTtl: CONVERSATION_TTL }
  );
}
