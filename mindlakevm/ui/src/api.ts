const BASE = '/api'

async function post<T>(path: string, body: unknown): Promise<T> {
  const r = await fetch(BASE + path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  const data = await r.json()
  if (!r.ok) throw new Error(data.detail ?? 'Request failed')
  return data as T
}

async function get<T>(path: string): Promise<T> {
  const r = await fetch(BASE + path)
  const data = await r.json()
  if (!r.ok) throw new Error(data.detail ?? 'Request failed')
  return data as T
}

// ── Types ────────────────────────────────────────────────────────────────────

export interface RCore { domain: string; object_type: string; semantic_space: string }
export interface NCore { structure: string; schema: unknown; constraints: string[]; references: { path: string; scope: string; required: boolean }[] }
export interface ECore { format: string; target_entropy: string; hard_constraints: string[]; soft_constraints: string[]; meta_ignorance: string[] }
export interface PathStep { id: string; name: string; description: string; decision_points: { condition: string; if_true: string; if_false?: string }[]; requires_evidence: boolean }
export interface TCore { path: PathStep[]; cot_steps: string[] }
export interface SemanticKernelIR { kernel_id: string; version: string; compiled_at: string; r: RCore; n: NCore; e: ECore; t: TCore }
export interface SkillFile { path: string; type: string; token_estimate?: number }
export interface SkillPackage { skill_id: string; skill_name: string; description: string; files_tree: SkillFile[]; compiled_at: string }
export interface CompileResponse { kernel_id: string; cache_hit: boolean; ir: SemanticKernelIR; artifacts: SkillPackage }

export interface Violation { constraint: string; reason: string; severity: string }
export interface TraceStep { step_id: string; status: 'pending' | 'running' | 'completed' | 'skipped' | 'blocked'; decision_taken?: string }
export interface EvidenceItem { source_path: string; excerpt?: string; relevance?: string }
export interface ValidationResult { passed: boolean; schema_valid?: boolean; evidence_sufficient?: boolean; stop_condition_met?: boolean; warnings: string[] }
export interface TokenUsage { input_tokens: number; output_tokens: number; total_tokens: number }
export interface RunResponse { output_text: string; blocked: boolean; violations: Violation[]; trace: TraceStep[]; evidence: EvidenceItem[]; validation: ValidationResult; usage?: TokenUsage }

export interface BenchRow { baseline: string; success_rate: number; token_cost: TokenUsage; citation_rate: number; guardrail_block_rate: number; false_positive_rate: number }
export interface BenchSummary { token_savings_pct: number; success_rate_delta: number; guardrail_accuracy: number; highlight: string }
export interface BenchResponse { scenario_id: string; results_table: BenchRow[]; report_summary: BenchSummary }

export interface SkillSummary { skill_id: string; skill_name: string; domain: string; object_type: string; compiled_at: string }
export interface SkillFileContent { skill_id: string; path: string; content: string }

// ── API calls ─────────────────────────────────────────────────────────────────

export const compileDoc = (body: { task_description: string; document_content: string; strategy: string; enable_probe: boolean }) =>
  post<CompileResponse>('/compile', body)

export const listSkills = () => get<{ skills: SkillSummary[] }>('/skills')

export const getSkillFile = (skill_id: string, path: string) =>
  get<SkillFileContent>(`/skills/${skill_id}/file?path=${encodeURIComponent(path)}`)

export const runSkill = (skill_id: string, user_input: string) =>
  post<RunResponse>('/run', { skill_id, user_input })

export const runBench = (scenario_id: string, baselines: string[]) =>
  post<BenchResponse>('/bench', { scenario_id, baselines })
