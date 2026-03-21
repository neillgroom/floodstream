export type ClaimStatus = "pending_review" | "approved" | "uploaded" | "rejected";
export type ReportType = "prelim" | "final";

export interface Claim {
  id: string;
  fg_number: string;
  insured_name: string;
  policy_number: string;
  date_of_loss: string;
  carrier: string;
  report_type: ReportType;
  status: ClaimStatus;
  confidence: number;
  created_at: string;
  reviewed_by?: string;
  reviewed_at?: string;
  xml_data?: Record<string, string>;
  warnings?: string[];
}

// Prelim form fields matching the bot's 17 questions
export interface PrelimFormData {
  // From NOL (pre-filled)
  fg_number: string;
  insured_name: string;
  policy_number: string;
  date_of_loss: string;
  coverage_building: string;
  coverage_contents: string;
  carrier: string;

  // From inspection
  contact_date: string;
  inspection_date: string;
  water_height_external: string;
  water_height_internal: string;
  water_entered_date: string;
  water_receded_date: string;
  building_type: string;
  occupancy: string;
  number_of_floors: string;
  building_elevated: string;
  split_level: string;
  foundation_type: string;
  cause: string;
  reserves_building: string;
  reserves_content: string;
  advance_building: string;
  advance_contents: string;
}

export const BUILDING_TYPES = [
  "MAIN DWELLING",
  "CONDO UNIT",
  "COMMERCIAL BUILDING",
  "RCBAP",
  "OTHER RESIDENTIAL",
  "MANUFACTURED/MOBILE HOME",
];

export const OCCUPANCY_TYPES = [
  "OWNER-OCCUPIED (PRINCIPAL RESIDENCE)",
  "OWNER-OCCUPIED (SEASONAL RESIDENCE)",
  "TENANT-OCCUPIED",
  "RENTAL (NOT OWNER OCCUPIED)",
  "VACANT",
];

export const FOUNDATION_TYPES = [
  "Slab",
  "Crawlspace",
  "Basement",
  "Piles",
  "Piers",
  "Walls",
  "Elevated",
];

export const CAUSE_OPTIONS = [
  { value: "rainfall", label: "Accumulation of rainfall or snowmelt" },
  { value: "river", label: "Overflow of inland or tidal waters" },
  { value: "surge", label: "Unusual and rapid accumulation or runoff" },
  { value: "mudflow", label: "Mudflow" },
  { value: "erosion", label: "Collapse or subsidence of land" },
];
