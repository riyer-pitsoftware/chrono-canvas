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

export interface GenerationRequest {
  id: string;
  figure_id: string | null;
  input_text: string;
  status: string;
  current_agent: string | null;
  extracted_data: Record<string, unknown> | null;
  research_data: Record<string, unknown> | null;
  generated_prompt: string | null;
  error_message: string | null;
  agent_trace: Array<Record<string, unknown>> | null;
  llm_calls: LLMCallDetail[] | null;
  llm_costs: Record<string, unknown> | null;
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
}
