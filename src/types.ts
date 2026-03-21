// ─── Environment Bindings ────────────────────────────────────────
export interface Env {
  ECHO_CONVERSATIONS: KVNamespace;
  ECHO_RATE_LIMITS: KVNamespace;
  ECHO_ANALYTICS: KVNamespace;
  ANTHROPIC_API_KEY: string;
  ANALYTICS_API_KEY?: string;
  ENVIRONMENT: string;
  DISABLE_RATE_LIMIT?: string;
}

// ─── Chat Request / Response ─────────────────────────────────────
export interface ChatRequest {
  conversation_id: string;
  message: string;
  page_url?: string;
  message_index: number;
}

export interface ChatResponse {
  reply: string;
  conversation_id: string;
  message_index: number;
  truncated?: boolean;
}

export interface ErrorResponse {
  error: "rate_limited" | "api_error" | "invalid_request";
  message: string;
}

// ─── Conversation State ──────────────────────────────────────────
export interface ConversationMessage {
  role: "user" | "assistant";
  content: string;
}

// ─── Analytics ───────────────────────────────────────────────────
export type SourceType =
  | "KB_PRIMARY"
  | "KB_SUPPLEMENTED"
  | "GENERAL_KNOWLEDGE"
  | "ESCALATED"
  | "OUT_OF_SCOPE";

export interface MessageLog {
  conversation_id: string;
  message_index: number;
  timestamp: string;
  user_message: string;
  assistant_response: string;
  source_type: SourceType;
  tokens_in: number;
  tokens_out: number;
  cost_usd: number;
  page_url?: string;
  topics?: string[];
}

// ─── Config ─────────────────────────────────────────────────────
export interface AppConfig {
  firm_name: string;
  assistant_name: string;
  branding: {
    primary_color: string;
    accent_color: string;
    font: string;
  };
  rate_limits: {
    messages_per_conversation: number;
    conversations_per_ip_per_hour: number;
  };
}
