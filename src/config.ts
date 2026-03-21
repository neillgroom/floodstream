import type { AppConfig } from "./types";

export const CONFIG: AppConfig = {
  firm_name: "Fountain Group Adjusters",
  assistant_name: "Echo",
  branding: {
    primary_color: "#1a365d",
    accent_color: "#f7fafc",
    font: "Source Sans 3",
  },
  rate_limits: {
    messages_per_conversation: 20,
    conversations_per_ip_per_hour: 100, // High for testing; lower to 5 for production
  },
};
