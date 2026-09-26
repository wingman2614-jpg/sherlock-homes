// Shapes produced by the Python pipeline (data/processed/*.json).
// Keep in sync with sherlock/build.py and sherlock/analytics.py.

export type Level = "HIGH" | "MEDIUM" | "LOW" | "INSUFFICIENT DATA";
export type ConfidenceLevel = "HIGH" | "MODERATE" | "LOW";

export interface Provenance {
  source: string;
  source_id: string;
  source_file: string;
  geography: string;
  period_start: string;
  period_end: string;
  time_resolution: string;
}

export interface Signal extends Provenance {
  indicator: string;
  label: string;
  short: string;
  category: string;
  unit: string;
  method: string;
  baseline_period: string;
  recent_period: string;
  baseline_value: number | null;
  recent_value: number | null;
  change_pct: number | null;
  city_baseline: number | null;
  city_recent: number | null;
  comparison_label?: string;
  city_change_pct: number | null;
  expected_recent: number | null;
  status: "scored" | "insufficient_data";
  residual?: number;
  z_score?: number;
  percentile?: number;
  direction?: "above_city_trend" | "below_city_trend" | "in_line";
  n_compared?: number;
  notes: string[];
  baseline_n?: number;
  recent_n?: number;
  largest_recent_permit_share?: number;
  largest_same_day_batch?: number;
}

export interface WhyNoticed {
  indicator: string;
  label: string;
  short: string;
  headline: string;
  change_pct: number | null;
  city_change_pct: number | null;
  baseline_value: number;
  recent_value: number;
  expected_recent: number | null;
  z_score: number;
  percentile: number | null;
  direction: string;
  source: string;
  geography: string;
  period: string;
}

export interface TimelinePoint {
  year: number;
  value: number | null;
  city_value: number | null;
  expected_from_2020_21_share: number | null;
  deviation: number | null;
  partial: string | null;
}

export interface Onset {
  indicator: string;
  label: string;
  short: string;
  year: number | null;
  direction: "up" | "down" | null;
  deviation?: number;
  statement: string;
  order?: number;
}

export interface WhatChangedFirst {
  ordered: Onset[];
  no_clear_change: Onset[];
  method: string;
  caution: string;
}

export interface SimilarFeature {
  indicator: string;
  label: string;
  direction?: string;
  z_self: number;
  z_other: number;
  text: string;
}

export interface SimilarCase {
  area_id: string;
  name: string;
  similarity: number;
  cosine: number;
  distance: number;
  features_compared: number;
  shared: SimilarFeature[];
  differences: SimilarFeature[];
}

export interface ConflictComparison {
  window: string;
  period_start: string;
  period_end: string;
  zillow_start: number;
  zillow_end: number;
  zillow_change_pct: number | null;
  redfin_start: number;
  redfin_end: number;
  redfin_change_pct: number | null;
  agreement: string;
}

export interface ConflictSource {
  label: string;
  source_id: string;
  file: string;
  geography?: string;
  baseline?: number | null;
  recent?: number | null;
  change_pct?: number | null;
}

export interface Conflict {
  id: string;
  scope: string;
  concept: string;
  geography?: string;
  status: "agree" | "magnitude" | "direction" | "unknown";
  summary?: string;
  sources?: ConflictSource[];
  comparisons?: ConflictComparison[];
  baseline_period?: string;
  recent_period?: string;
  evidence_agrees_on: string[];
  remains_uncertain: string[];
  possible_reasons: string[];
  reason_basis: string;
}

export interface ConfidenceFactor {
  severity: "major" | "moderate" | "minor";
  factor: string;
  detail: string;
}

export interface MetroSignal {
  indicator: string;
  label: string;
  short: string;
  category: string;
  window: string;
  transform: string;
  change: number;
  change_kind: string;
  peer_median: number | null;
  peer_n: number;
  z_score: number;
  percentile: number | null;
  large_metro_median: number | null;
  large_metro_n: number;
  z_score_large_metros: number;
  scored: boolean;
  source: string;
  source_file: string;
  geography: string;
  period_start: string;
  period_end: string;
  caveats: string[];
}

export interface VacancyContext {
  value: number | null;
  per_km2: number | null;
  z_vs_neighborhoods: number | null;
  city_per_km2: number | null;
  snapshot: string;
  source: string;
  source_file: string;
  geography: string;
  time_resolution: string;
  caveats: string[];
}

export interface CaseFile {
  id: string;
  case_number: number | null;
  case_label?: string | null;
  area_id: string;
  zip?: string;
  name: string;
  geography: string;
  geography_note: string;
  comparison_label?: string;
  timeline_expected_label?: string;
  anomaly_score: number | null;
  level: Level;
  max_abs_z: number | null;
  title: string;
  permit_last_date: string;
  why_noticed: WhyNoticed[];
  evidence: {
    signals: Signal[];
    context: {
      city_owned_vacant_lots?: VacancyContext;
      metro: { note: string; signals: MetroSignal[] };
      zip_market?: ZipMarketContext;
      neighborhoods?: { neighborhood: string; area_id: string; share_of_zip_land: number }[];
      acs?: AcsContext | null;
    };
  };
  timeline: Record<string, TimelinePoint[]>;
  what_changed_first: WhatChangedFirst;
  similar_cases: SimilarCase[];
  conflicting_evidence: {
    neighborhood: Conflict[];
    citywide_and_regional: Conflict[];
    national: Conflict[];
    note: string;
  };
  confidence: { level: ConfidenceLevel; factors: ConfidenceFactor[]; rule: string };
  finding: { text: string; generated_by: string; llm_status: string };
  limitations: string[];
  plain: PlainSummary;
}

export interface ZipSignalBrief {
  indicator: string;
  label: string;
  short: string;
  unit: string;
  status: string;
  change_pct: number | null;
  city_change_pct: number | null;
  z_score?: number | null;
  baseline_value: number | null;
  recent_value: number | null;
  baseline_period: string;
  recent_period: string;
  source: string;
}

export interface ZipMarketContext {
  note: string;
  plain: string | null;
  zips: {
    zip: string;
    name: string;
    case_id: string;
    level: Level;
    share_of_neighborhood_land: number;
    share_of_zip_land: number;
    signals: ZipSignalBrief[];
    price_conflict: Conflict | null;
  }[];
}

export interface AcsTract {
  geoid: string;
  share_of_neighborhood_land: number;
  median_gross_rent: number | null;
  median_household_income: number | null;
  vacancy_rate: number | null;
  renter_share: number | null;
}

export interface AcsContext {
  note: string;
  vintages: {
    year: number;
    period: string;
    tract_vintage: number;
    source: string;
    tracts: AcsTract[];
    typical_city_tract: Record<string, number | null>;
  }[];
}

export interface PlainSummary {
  level_label: string;
  headline: string;
  bullets: string[];
  timing: string | null;
  confidence: string;
  keep_in_mind: string[];
  similar: string[];
  similar_text: string | null;
  market?: string | null;
}

export interface CaseCard {
  id: string;
  case_number: number | null;
  case_label?: string | null;
  geography?: string;
  area_id: string;
  name: string;
  title: string;
  level: Level;
  anomaly_score: number | null;
  confidence: ConfidenceLevel;
  why_noticed: string[];
}

export interface Area {
  id: string;
  name: string;
  level: Level;
  anomaly_score: number | null;
  confidence: ConfidenceLevel;
  top_signal_headline: string | null;
  case_id: string | null;
}

export interface HomeSummary {
  areas_worth_investigating: number;
  areas_analysed: number;
  levels: Record<Level, number>;
  confidence: Record<ConfidenceLevel, number>;
  baseline_years: number[];
  recent_years: number[];
  permit_last_date: string;
  generated_at: string;
  city_trends: Record<string, { baseline: number; recent: number; change_pct: number | null }>;
  top_cases: CaseCard[];
  zip?: { areas: number; cases_worth_investigating: number; last_sale_date: string } | null;
  top_zip_cases?: CaseCard[];
}

export interface MetroCase {
  id: string;
  title: string;
  name: string;
  geography_note: string;
  signals: MetroSignal[];
  forecast: {
    base_date: string;
    horizons: Record<string, { pittsburgh_pct: number; us_pct: number }>;
    source: string;
    source_file: string;
    note: string;
  };
  anomaly: Record<string, { score: number | null; level: Level }>;
  limitations: string[];
}

export interface InvestigateResult {
  question: string;
  interpretation?: string;
  results: { area_id: string; name: string; case_id: string; score: number; level?: Level; evidence: string[] }[];
  total_matches?: number;
  notes?: string[];
  message?: string;
  method?: string;
  caution?: string;
  query?: { parser: string } | null;
}
