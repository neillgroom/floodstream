// System prompt + knowledge bases loaded as static strings.
// Imported at build time by wrangler's module bundling.

import SYSTEM_PROMPT_TEXT from "../system-prompt/echo_system_prompt.txt";
import DWELLING_FORM from "../knowledge-base/distilled/dwelling-form.md.txt";
import GENERAL_PROPERTY_FORM from "../knowledge-base/distilled/general-property-form.md.txt";
import RCBAP_FORM from "../knowledge-base/distilled/rcbap-form.md.txt";
import CLAIMS_MANUAL from "../knowledge-base/distilled/claims-manual.md.txt";
import FEMA_COMMENTARY from "../knowledge-base/distilled/fema-commentary.md.txt";
import FG_GUIDELINES from "../knowledge-base/distilled/fg-guidelines.md.txt";

export function getSystemPrompt(): string {
  return [
    SYSTEM_PROMPT_TEXT,
    "\n\n---\n\n## SFIP — DWELLING FORM (Policy Tier 1)\n\n",
    DWELLING_FORM,
    "\n\n---\n\n## SFIP — GENERAL PROPERTY FORM (Policy Tier 1)\n\n",
    GENERAL_PROPERTY_FORM,
    "\n\n---\n\n## SFIP — RCBAP FORM (Policy Tier 1)\n\n",
    RCBAP_FORM,
    "\n\n---\n\n## NFIP CLAIMS MANUAL 2025 (Tier 2)\n\n",
    CLAIMS_MANUAL,
    "\n\n---\n\n## FEMA COMMENTARY (Tier 3)\n\n",
    FEMA_COMMENTARY,
    "\n\n---\n\n## FOUNTAIN GROUP GUIDELINES (Tier 3 — cite only when no higher authority)\n\n",
    FG_GUIDELINES,
  ].join("");
}
