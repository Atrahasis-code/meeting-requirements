export interface Project {
  id: string;
  name: string;
  description: string;
  context: string;
  glossary: Record<string, string>;
  created_at: string;
  updated_at: string;
}
export interface Job {
  id: string;
  meeting_id: string;
  kind: string;
  status: string;
  stage: string;
  progress: number | null;
  error: string | null;
  blocked_reason: string | null;
  cancel_requested: boolean;
  created_at: string;
}
export interface Meeting {
  id: string;
  project_id: string;
  title: string;
  date: string;
  profile: string;
  language: string | null;
  status: string;
  transcript_revision: number;
  active_analysis_id: string | null;
  jobs: Job[];
  media: {
    original_name: string;
    size: number;
    duration: number;
    mime_type: string;
  } | null;
}
export interface Segment {
  id: string;
  start: number;
  end: number;
  original_text: string;
  revised_text: string | null;
  reviewed: boolean;
  discarded: boolean;
  doubtful: boolean;
  detection: Record<string, unknown>;
}
export interface Transcript {
  revision: number;
  complete: boolean;
  segments: Segment[];
}
export interface Evidence {
  id: string;
  segment_id: string;
  quote: string;
  start: number;
  end: number;
}
export interface Requirement {
  id: string;
  project_id: string;
  analysis_id: string;
  code: string;
  kind: string;
  title: string;
  description: string;
  actor: string;
  module: string;
  priority: string;
  status: string;
  interpretation: string;
  observations: string;
  evidence: Evidence[];
  original: { description: string };
  questions: string[];
  dependencies: string[];
  meeting_id?: string;
  revisions?: {
    id: string;
    created_at: string;
    before: Record<string, unknown>;
    after: Record<string, unknown>;
  }[];
}
export interface Note {
  text: string;
  evidence: { segment_id: string; quote: string }[];
}
export interface Result {
  summary: Record<string, string | string[]>;
  stories: { code: string; text: string; requirements: string[] }[];
  criteria: {
    code: string;
    story_code: string;
    given: string;
    when: string;
    then: string;
    requirements: string[];
  }[];
  business_rules: Note[];
  questions: Note[];
  processes: Note[];
  conceptual_model: Note[];
  backlog: {
    code: string;
    module: string;
    story_code: string;
    priority: string;
    status: string;
    dependencies: string[];
    requirements: string[];
  }[];
}
export interface Analysis {
  id: string;
  provider: string;
  created_at: string;
  active: boolean;
  original_result: Result;
  code_mapping?: Record<string, string>;
  input_snapshot: { revision: number; selection_policy?: string };
  requirements: Requirement[];
  criteria?: (Result["criteria"][number] & {
    id: string;
    status: string;
    revision: number;
    original: Result["criteria"][number];
    revisions: {
      created_at: string;
      before: { given: string; when: string; then: string; status: string };
      after: { given: string; when: string; then: string; status: string };
      observations: string;
      action?: string;
      actor?: { id: string; label: string; kind: string };
    }[];
  })[];
}
export interface Artifact {
  id: string;
  created_at: string;
  files: string[];
}
export interface Preferences {
  profile: string;
  provider: string;
  model: string | null;
  language: string | null;
  storage: Record<string, string>;
  cpu_threads: number;
  max_upload_bytes: number;
  test_mode: boolean;
}
export interface AuthStatus {
  connected: boolean;
  account_id: string | null;
  accounts: { id: string; email: string; connected: boolean }[];
  email: string | null;
  plan_authorized: boolean;
  credits_zero_confirmed: boolean;
  quota_blocked: boolean;
  inference_verified: boolean;
  last_inference_at: number | null;
  last_inference_model: string | null;
  error: string | null;
  usage_url: string;
}
export interface AnalysisInput {
  input_hash: string;
  snapshot: {
    selection_policy: "reviewed_only_v1";
    selection_summary: {
      total: number;
      reviewed: number;
      discarded: number;
      pending: number;
      included: number;
    };
    provider: string;
    model: string | null;
    context: string;
    glossary: Record<string, string>;
    revision: number;
    segments: {
      id: string;
      start: number;
      end: number;
      text: string;
      doubtful: boolean;
    }[];
  };
}
export interface DashboardData {
  projects: Project[];
  project_count: number;
  meeting_count: number;
  pending_requirements: number;
  jobs: Job[];
}

export type AcceptanceCriterion = NonNullable<Analysis["criteria"]>[number];
