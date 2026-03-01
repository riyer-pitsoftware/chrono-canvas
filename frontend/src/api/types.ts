export interface Figure {
  id: string;
  name: string;
  birth_year: number | null;
  death_year: number | null;
  period_id: string | null;
  nationality: string | null;
  occupation: string | null;
  description: string | null;
  physical_description: string | null;
  clothing_notes: string | null;
  metadata_json: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
}

export interface FigureListResponse {
  items: Figure[];
  total: number;
  offset: number;
  limit: number;
}

export interface StoryboardPanel {
  scene_index: number;
  description: string;
  characters: string[];
  mood: string;
  setting: string;
  image_prompt: string;
  image_path: string;
  status: string;
}

export interface StoryboardData {
  characters: Array<Record<string, unknown>>;
  scenes: Array<Record<string, unknown>>;
  panels: StoryboardPanel[];
  total_scenes: number;
  completed_scenes: number;
}

export interface GenerationRequest {
  id: string;
  figure_id: string | null;
  input_text: string;
  run_type: string;
  status: string;
  current_agent: string | null;
  extracted_data: Record<string, unknown> | null;
  research_data: Record<string, unknown> | null;
  generated_prompt: string | null;
  error_message: string | null;
  agent_trace: Array<Record<string, unknown>> | null;
  llm_calls: LLMCallDetail[] | null;
  llm_costs: Record<string, unknown> | null;
  storyboard_data: StoryboardData | null;
  created_at: string;
  updated_at: string;
}

export interface GenerationListResponse {
  items: GenerationRequest[];
  total: number;
}

export interface GeneratedImage {
  id: string;
  request_id: string;
  figure_id: string | null;
  file_path: string;
  thumbnail_path: string | null;
  prompt_used: string | null;
  provider: string;
  width: number;
  height: number;
  validation_score: number | null;
  created_at: string;
}

export interface Agent {
  name: string;
  description: string;
  status: string;
}

export interface AgentListResponse {
  agents: Agent[];
}

export interface LLMAvailability {
  providers: Record<string, boolean>;
}

export interface CostSummary {
  total_cost: number;
  total_tokens: number;
  by_provider: Record<string, number>;
  num_calls: number;
}

export interface ValidationResult {
  id: string;
  request_id: string;
  category: string;
  rule_name: string;
  passed: boolean;
  score: number;
  details: string | null;
  suggestions: string[] | null;
  created_at: string;
}

export interface ValidationSummary {
  request_id: string;
  overall_score: number;
  passed: boolean;
  results: ValidationResult[];
}

export interface LLMCallDetail {
  agent: string;
  timestamp: number;
  system_prompt: string | null;
  user_prompt: string | null;
  raw_response: string | null;
  parsed_output: unknown;
  provider: string | null;
  model: string | null;
  input_tokens: number;
  output_tokens: number;
  cost: number;
  duration_ms: number;
}

export interface ValidationCategoryDetail {
  category: string;
  rule_name: string;
  passed: boolean;
  score: number;
  details: string | null;
  reasoning: string | null;
}

export interface FaceUploadResponse {
  face_id: string;
  file_path: string;
}

export interface StateSnapshot {
  agent: string;
  snapshot: Record<string, unknown>;
}

export interface TimelineFigureListResponse {
  items: Figure[];
  total: number;
  year_min: number;
  year_max: number;
}

// ── Validation Admin ──────────────────────────────────────────────────────

export interface ValidationRule {
  id: string;
  category: string;
  display_name: string;
  weight: number;
  description: string | null;
  enabled: boolean;
  created_at: string;
  updated_at: string;
}

export interface ValidationRulesConfig {
  rules: ValidationRule[];
  pass_threshold: number;
}

export interface ValidationQueueCategory {
  category: string;
  rule_name: string;
  score: number;
  passed: boolean;
  details: string | null;
}

export interface ValidationQueueItem {
  request_id: string;
  input_text: string;
  figure_name: string | null;
  overall_score: number;
  categories: ValidationQueueCategory[];
  image_url: string | null;
  human_review_status: string | null;
  created_at: string;
}

export interface ValidationQueueResponse {
  items: ValidationQueueItem[];
  total: number;
}

export interface AuditDetail {
  id: string;
  input_text: string;
  status: string;
  current_agent: string | null;
  figure_name: string | null;
  created_at: string;
  updated_at: string;
  extracted_data: Record<string, unknown> | null;
  research_data: Record<string, unknown> | null;
  generated_prompt: string | null;
  error_message: string | null;
  total_cost: number;
  total_duration_ms: number;
  llm_calls: LLMCallDetail[];
  validation_score: number | null;
  validation_passed: boolean | null;
  validation_reasoning: string | null;
  validation_categories: ValidationCategoryDetail[];
  images: GeneratedImage[];
  state_snapshots: StateSnapshot[];
  agent_trace: Array<Record<string, unknown>>;
}

// ── Audit Feedback ────────────────────────────────────────────────────────

export interface AuditFeedback {
  id: string;
  request_id: string;
  step_name: string;
  comment: string;
  author: string;
  created_at: string;
}

export interface AuditFeedbackListResponse {
  items: AuditFeedback[];
}

// ── Eval Viewer ──────────────────────────────────────────────────────────

export interface EvalRunSummary {
  run_id: string;
  case_id: string;
  condition: string;
  success: boolean;
  image_url: string | null;
  title: string;
  has_rating: boolean;
  rejected: boolean;
}

export interface EvalRunDetail extends EvalRunSummary {
  manifest: Record<string, unknown>;
  rating: Record<string, unknown> | null;
  output_text: string | null;
}

export interface EvalCase {
  case_id: string;
  title: string;
  subject_type: string;
  region: string;
  time_period_label: string;
  runs: EvalRunSummary[];
}

export interface DimensionAggregate {
  condition: string;
  dimension: string;
  mean: number;
  median: number;
  n: number;
}

export interface DashboardData {
  conditions: Record<string, unknown>[];
  dimension_scores: DimensionAggregate[];
  failure_tags: { tag: string; count: number; category: string }[];
  total_runs: number;
  total_rated: number;
}

// ── Memory Cache ──────────────────────────────────────────────────────────

export interface CacheEntry {
  id: string;
  figure_name: string;
  time_period: string;
  region: string;
  hit_count: number;
  cost_saved_usd: number;
  original_cost_usd: number;
}

export interface CacheStats {
  total_entries: number;
  total_hits: number;
  estimated_cost_saved_usd: number;
}

export interface CacheListResponse {
  entries: CacheEntry[];
  stats: CacheStats;
}
