export type AcceleratorSlug = "yc" | "ef" | "spc" | "a16z_speedrun";

export interface Accelerator {
  id: number;
  slug: AcceleratorSlug;
  name: string;
  website: string | null;
  hq_location: string | null;
  founded_year: number | null;
  investment_amount_usd: number | null;
  investment_equity_pct: number | null;
  investment_terms_note: string | null;
  program_duration_weeks: number | null;
  batch_cadence: string | null;
  focus_areas: string | null;
  description: string | null;
  notable_alumni: string | null;
  total_companies_funded: number | null;
  company_count: number;
  active_count: number;
  acquired_count: number;
  public_count: number;
  dead_count: number;
}

export interface Totals {
  n_companies: number;
  n_active: number;
  n_acquired: number;
  n_public: number;
  n_dead: number;
  n_founders: number;
  n_batches: number;
}

export interface IndustryCount {
  industry: string;
  n: number;
}

export interface IndustryYear {
  industry: string;
  founded_year: number;
  n: number;
}

export interface BatchTrendRow {
  slug: AcceleratorSlug;
  founded_year: number;
  n: number;
}

export interface FundingCoverage {
  slug: AcceleratorSlug;
  n_matched: number;
  n_total: number;
  sum_usd: number;
  avg_usd: number;
}

export interface SampleInfo {
  n_companies: number;
  n_companies_total: number;
}

export interface Summary {
  generated_at: string;
  sample?: SampleInfo;
  totals: Totals;
  accelerators: Accelerator[];
  industries: IndustryCount[];
  industry_year: IndustryYear[];
  batch_trend: BatchTrendRow[];
  funding_coverage?: FundingCoverage[];
}

export interface Founder {
  name: string;
  role: string | null;
  linkedin: string | null;
}

export interface Company {
  id: number;
  accelerator: AcceleratorSlug;
  slug: string;
  name: string;
  one_liner: string | null;
  website: string | null;
  linkedin_url: string | null;
  twitter_url: string | null;
  source_url: string | null;
  status: "Active" | "Dead" | "Acquired" | "Public" | "Unknown";
  status_source: string | null;
  status_confidence: number | null;
  industry_primary: string | null;
  industry: string;
  stage: string | null;
  funding_tier: string | null;
  is_top_company: number | null;
  is_b2b: number | null;
  is_hiring: number | null;
  all_locations: string | null;
  country: string | null;
  team_size_current: number | null;
  total_funding_usd: number | null;
  total_funding_source: string | null;
  total_funding_confidence: number | null;
  last_round_type: string | null;
  traction_arr_usd: number | null;
  traction_mrr_usd: number | null;
  traction_users: number | null;
  traction_customers: number | null;
  traction_gmv_usd: number | null;
  traction_growth_rate: number | null;
  traction_source: string | null;
  traction_confidence: number | null;
  traction_snippet: string | null;
  founded_year: number | null;
  batch_slug: string | null;
  batch_name: string | null;
  batch_year: number | null;
  batch_season: string | null;
  founders: Founder[];
  founder_count: number;
  has_serial_founder: boolean;
}

export interface Batch {
  id: number;
  accelerator: AcceleratorSlug;
  slug: string;
  name: string;
  year: number | null;
  season: string | null;
  notes: string | null;
  industries_csv: string | null;
  company_count: number;
  active_count: number;
  acquired_count: number;
  public_count: number;
  dead_count: number;
}

export interface SerialFounder {
  key: string;
  display_name: string;
  aliases: string[];
  company_count: number;
  accelerator_count: number;
  accelerators: AcceleratorSlug[];
  companies: Array<{
    name: string;
    slug: string;
    accelerator: AcceleratorSlug;
    role: string | null;
    linkedin: string | null;
    status: string;
  }>;
}

export interface Insight {
  id: number;
  kind: string;
  subject_type: string | null;
  subject_id: string | null;
  title: string | null;
  content: string;
  model: string;
  created_at: string;
}

export interface BudgetByPurpose {
  purpose: string;
  calls: number;
  spent_usd: number;
  prompt_tokens: number;
  completion_tokens: number;
}

export interface Budget {
  cap_usd: number;
  spent_usd: number;
  remaining_usd: number;
  calls: number;
  prompt_tokens: number;
  completion_tokens: number;
  by_purpose: BudgetByPurpose[];
}

export interface CoverageRow {
  field: string;
  accelerator: AcceleratorSlug;
  total: number;
  have: number;
  pct: number;
}

export const ACCELERATOR_LABELS: Record<AcceleratorSlug, string> = {
  yc: "Y Combinator",
  ef: "Entrepreneur First",
  spc: "South Park Commons",
  a16z_speedrun: "a16z Speedrun",
};

export const ACCELERATOR_COLORS: Record<AcceleratorSlug, string> = {
  yc: "#cc785c",
  ef: "#5c7a8a",
  spc: "#7a6b5c",
  a16z_speedrun: "#8a5c6b",
};

export const STATUS_COLORS: Record<string, string> = {
  Active: "#3f6b4a",
  Acquired: "#a96f1d",
  Public: "#2b5f8a",
  Dead: "#8a3a2a",
  Unknown: "#807e78",
};
