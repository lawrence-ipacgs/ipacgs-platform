// Thin client over the real FastAPI backend — no mocking, every call here
// hits services/api's actual routes. `X-Dev-User` is the local-dev-only
// auth bypass core/security.py's get_current_user carries (never reachable
// outside ENVIRONMENT=local) — see that module's own docstring.

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(
  path: string,
  actor: string,
  init?: RequestInit
): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      "X-Dev-User": actor,
      ...(init?.headers ?? {}),
    },
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail ?? JSON.stringify(body);
    } catch {
      // ignore — use statusText
    }
    throw new ApiError(res.status, detail);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

function get<T>(path: string, actor: string): Promise<T> {
  return request<T>(path, actor);
}
function post<T>(path: string, actor: string, body?: unknown): Promise<T> {
  return request<T>(path, actor, {
    method: "POST",
    body: body ? JSON.stringify(body) : undefined,
  });
}

// ---- Types (mirrors api/schemas/*.py — kept minimal, only what the UI uses) ----

export interface Organisation {
  id: string;
  legal_name: string;
}

export interface Stage {
  id: string;
  code: string;
  name: string;
  description: string | null;
  sequence: number;
  is_active: boolean;
}

export interface Project {
  id: string;
  organisation_id: string;
  name: string;
  current_stage_id: string;
  status: string;
}

export interface ProjectSummary {
  id: string;
  name: string;
  organisation_id: string;
  current_stage_code: string | null;
  current_stage_name: string | null;
  status: string;
  rag_status: string;
  blocking_gate_code: string | null;
  assigned_to: string | null;
  stage_due_date: string | null;
}

export interface ChecklistItem {
  item_id: string;
  sequence: number;
  criterion: string;
  response_value: "yes" | "no" | "not_applicable" | null;
  comment: string | null;
  answered_by: string | null;
  answered_at: string | null;
}

export interface StageDecisionOut {
  id: string;
  outcome: string;
  conditions: string | null;
  decided_by: string;
  decided_at: string;
}

export interface OpbohAssessment {
  id: string;
  organisation_id: string;
  framework_version_id: string;
  status: string;
  prepared_by: string;
  assessed_by: string | null;
  reviewed_by: string | null;
  approved_by: string | null;
  assurance_score: number | null;
  has_critical_failure: boolean;
  decision_summary: string | null;
}

export interface QuestionOut {
  id: string;
  domain_id: string;
  control_objective: string;
  question_text: string;
  sequence: number;
  is_critical_control: boolean;
  pass_threshold: number;
  evidence_type_hint: string | null;
}

export interface DomainWithQuestions {
  id: string;
  code: string;
  name: string;
  sequence: number;
  weight: number;
  min_score_threshold: number;
  questions: QuestionOut[];
}

export interface ResponseOut {
  id: string;
  assessment_id: string;
  question_id: string;
  response_value: string | null;
  score: number | null;
  evidence_sufficiency_factor: number | null;
  notes: string | null;
}

export interface DomainResultOut {
  domain_id: string;
  name: string;
  score: number;
  meets_threshold: boolean;
  critical_failures: { question_id: string; control_objective: string; reason: string }[];
  unanswered_count: number;
}

export interface ScoreOut {
  overall_score: number;
  evidence_sufficiency_factor: number;
  assurance_score: number;
  rag: string;
  is_clean: boolean;
  has_critical_failure: boolean;
  domain_results: DomainResultOut[];
}

export interface BaselineOpinionOut {
  rag: string;
  headline: string;
  narrative: string;
  recommendation: string;
}

export interface FindingOut {
  id: string;
  severity: string;
  description: string;
  status: string;
  owner: string | null;
  due_date: string | null;
}

export interface BillOfHealthReportOut {
  assessment_id: string;
  organisation_id: string;
  status: string;
  prepared_by: string;
  assessed_by: string | null;
  reviewed_by: string | null;
  approved_by: string | null;
  decision_summary: string | null;
  score: ScoreOut;
  opinion: BaselineOpinionOut;
  open_findings: FindingOut[];
}

// ---- Calls ----

export const api = {
  listOrganisations: (actor: string) => get<Organisation[]>("/organisations", actor),
  createOrganisation: (actor: string, legal_name: string) =>
    post<Organisation>("/organisations", actor, { legal_name }),
  listProjects: (actor: string) => get<ProjectSummary[]>("/projects", actor),
  createProject: (actor: string, organisationId: string, name: string) =>
    post<Project>("/projects", actor, { organisation_id: organisationId, name }),
  listStages: (actor: string) => get<Stage[]>("/stages", actor),
  getProject: (actor: string, id: string) => get<Project>(`/projects/${id}`, actor),
  getProjectRag: (actor: string, id: string) => get<{ status: string }>(`/projects/${id}/rag`, actor),
  getStageChecklist: (actor: string, projectId: string) =>
    get<ChecklistItem[]>(`/projects/${projectId}/stage-checklist`, actor),
  respondToChecklistItem: (
    actor: string,
    projectId: string,
    itemId: string,
    body: { response_value: string; comment?: string }
  ) => post(`/projects/${projectId}/stage-checklist/${itemId}/respond`, actor, body),
  recordStageDecision: (
    actor: string,
    projectId: string,
    body: { outcome: string; conditions?: string }
  ) => post<StageDecisionOut>(`/projects/${projectId}/stage-decision`, actor, body),
  advanceStage: (actor: string, projectId: string, notes?: string) =>
    post(`/projects/${projectId}/advance-stage`, actor, { notes }),

  createAssessment: (actor: string, organisationId: string) =>
    post<OpbohAssessment>("/opboh/assessments", actor, { organisation_id: organisationId }),
  getAssessment: (actor: string, id: string) =>
    get<OpbohAssessment>(`/opboh/assessments/${id}`, actor),
  getCatalogue: (actor: string, frameworkVersionId: string) =>
    get<DomainWithQuestions[]>(`/opboh/framework-versions/${frameworkVersionId}/catalogue`, actor),
  upsertResponse: (
    actor: string,
    assessmentId: string,
    body: {
      question_id: string;
      response_value: string;
      score: number;
      evidence_sufficiency_factor?: number;
    }
  ) => post<ResponseOut>(`/opboh/assessments/${assessmentId}/responses`, actor, body),
  submitAssessment: (actor: string, id: string) =>
    post<OpbohAssessment>(`/opboh/assessments/${id}/submit`, actor),
  beginAssessment: (actor: string, id: string) =>
    post<OpbohAssessment>(`/opboh/assessments/${id}/begin-assessment`, actor),
  independentlyReview: (actor: string, id: string) =>
    post<OpbohAssessment>(`/opboh/assessments/${id}/independently-review`, actor),
  decide: (actor: string, id: string, decision: string, decision_summary?: string) =>
    post<OpbohAssessment>(`/opboh/assessments/${id}/decide`, actor, {
      decision,
      decision_summary,
    }),
  reopen: (actor: string, id: string, reason: string) =>
    post<OpbohAssessment>(`/opboh/assessments/${id}/reopen`, actor, { reason }),
  getScore: (actor: string, id: string) => get<ScoreOut>(`/opboh/assessments/${id}/score`, actor),
  getBillOfHealth: (actor: string, id: string) =>
    get<BillOfHealthReportOut>(`/opboh/assessments/${id}/bill-of-health`, actor),
};

export { API_URL };
