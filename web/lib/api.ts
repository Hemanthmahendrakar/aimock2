const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL || "";

export type ApiError = {
  code: string;
  message: string;
  details?: { field: string; message: string }[];
};

export class ApiRequestError extends Error {
  code: string;
  status: number;
  details?: { field: string; message: string }[];

  constructor(status: number, err: ApiError) {
    super(err.message);
    this.code = err.code;
    this.status = status;
    this.details = err.details;
  }
}

let refreshInFlight: Promise<boolean> | null = null;

async function refreshSession(): Promise<boolean> {
  if (!refreshInFlight) {
    refreshInFlight = fetch(`${API_BASE_URL}/api/v1/institute/auth/refresh`, {
      method: "POST", credentials: "include",
    }).then((response) => response.ok).catch(() => false).finally(() => { refreshInFlight = null; });
  }
  return refreshInFlight;
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const send = () => fetch(`${API_BASE_URL}${path}`, {
    ...options,
    credentials: "include",
    headers: { "Content-Type": "application/json", ...options.headers },
  });

  let res = await send();
  if (res.status === 401 && !path.endsWith("/auth/refresh") && !path.endsWith("/auth/login") && !path.endsWith("/auth/register")) {
    if (await refreshSession()) res = await send();
  }
  const body = await res.json().catch(() => null);
  if (!res.ok || !body?.success) {
    const err: ApiError = body?.error ?? { code: "unknown_error", message: "Something went wrong. Please try again." };
    throw new ApiRequestError(res.status, err);
  }
  return body.data as T;
}

export type CurrentUser = {
  id: string;
  email: string;
  full_name: string;
  status: string;
  institute_id: string | null;
  roles: string[];
  email_verified: boolean;
};

export const authApi = {
  register: (payload: {
    institute_name: string;
    institute_email: string;
    admin_full_name: string;
    admin_email: string;
    password: string;
  }) =>
    request<{ institute: { id: string; name: string }; user: { id: string; email: string; status: string }; message: string }>(
      "/api/v1/institute/auth/register",
      { method: "POST", body: JSON.stringify(payload) }
    ),

  login: (payload: { email: string; password: string }) =>
    request<{ user: CurrentUser }>("/api/v1/institute/auth/login", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  logout: () =>
    request<{ message: string }>("/api/v1/institute/auth/logout", {
      method: "POST",
    }),

  me: () => request<CurrentUser>("/api/v1/institute/auth/me"),

  verifyEmail: (token: string) =>
    request<{ user: { id: string; status: string } }>(
      "/api/v1/institute/auth/verify-email",
      { method: "POST", body: JSON.stringify({ token }) }
    ),

  forgotPassword: (email: string) =>
    request<{ message: string }>("/api/v1/institute/auth/forgot-password", {
      method: "POST",
      body: JSON.stringify({ email }),
    }),

  resetPassword: (payload: { token: string; new_password: string }) =>
    request<{ message: string }>("/api/v1/institute/auth/reset-password", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
};

export type InstituteDashboard = {
  institute_id: string;
  stats: { total_students: number; total_campaigns: number; active_campaigns: number; assigned_interviews: number; completed_interviews: number; reports_ready: number; completion_rate: number };
  recent_campaigns: { id: string; name: string; role: string; status: string; created_at: string | null }[];
};

export const dashboardApi = { get: () => request<InstituteDashboard>("/api/v1/institute/dashboard") };

export type InstituteProfile = {
  id: string;
  name: string;
  email: string;
  phone: string | null;
  address: string | null;
  website: string | null;
  logo_url: string | null;
  branding: { primary_color?: string; secondary_color?: string };
  status: string;
};

export const instituteApi = {  getProfile: () => request<InstituteProfile>("/api/v1/institute/profile"),

  updateProfile: (payload: {
    name?: string;
    phone?: string;
    address?: string;
    website?: string;
  }) =>
    request<InstituteProfile>("/api/v1/institute/profile", {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),

  updateBranding: (payload: { primary_color?: string; secondary_color?: string }) =>
    request<InstituteProfile>("/api/v1/institute/branding", {
      method: "PUT",
      body: JSON.stringify(payload),
    }),

  uploadLogo: async (file: File): Promise<InstituteProfile> => {
    const formData = new FormData();
    formData.append("file", file);
    const res = await fetch(`${API_BASE_URL}/api/v1/institute/logo`, {
      method: "POST",
      credentials: "include",
      body: formData,
    });
    const body = await res.json().catch(() => null);
    if (!res.ok || !body?.success) {
      const err = body?.error ?? { code: "unknown_error", message: "Upload failed." };
      throw new ApiRequestError(res.status, err);
    }
    return body.data as InstituteProfile;
  },

  deleteLogo: () =>
    request<InstituteProfile>("/api/v1/institute/logo", { method: "DELETE" }),
};

export type Student = {
  id: string;
  name: string;
  email: string;
  roll_number: string | null;
  department: string | null;
  batch: string | null;
  phone: string | null;
  campus_id?: string | null;
  course?: string | null;
  graduation_year?: number | null;
  experience_level?: string | null;
  status: string;
  created_at: string;
  updated_at: string;
};

export type StudentListResult = {
  items: Student[];
  pagination: { page: number; per_page: number; total: number };
};

export type ImportResult = {
  total_rows: number;
  created: number;
  skipped: number;
  errors: { row: number; message: string }[];
};

export const studentsApi = {
  list: (params: {
    page?: number;
    per_page?: number;
    search?: string;
    department?: string;
    batch?: string;
    status?: string;
  }) => {
    const qs = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== "") qs.set(k, String(v));
    });
    return request<StudentListResult>(`/api/v1/institute/students?${qs.toString()}`);
  },

  get: (id: string) => request<Student>(`/api/v1/institute/students/${id}`),

  create: (payload: {
    name: string;
    email: string;
    roll_number?: string;
    department?: string;
    batch?: string;
    phone?: string;
    campus_id?: string;
    course?: string;
    graduation_year?: number;
    experience_level?: string;
  }) =>
    request<Student>("/api/v1/institute/students", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  update: (id: string, payload: Partial<Omit<Student, "id" | "created_at" | "updated_at">>) =>
    request<Student>(`/api/v1/institute/students/${id}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),

  remove: (id: string) =>
    request<{ message: string }>(`/api/v1/institute/students/${id}`, {
      method: "DELETE",
    }),

  importCsv: async (file: File): Promise<ImportResult> => {
    const formData = new FormData();
    formData.append("file", file);
    const res = await fetch(`${API_BASE_URL}/api/v1/institute/students/import`, {
      method: "POST",
      credentials: "include",
      body: formData,
    });
    const body = await res.json().catch(() => null);
    if (!res.ok || !body?.success) {
      const err = body?.error ?? { code: "unknown_error", message: "Import failed." };
      throw new ApiRequestError(res.status, err);
    }
    return body.data as ImportResult;
  },
};

export type Campaign = {
  id: string;
  name: string;
  role: string;
  company_id?: string | null;
  campus_id?: string | null;
  job_description?: string | null;
  question_source?: "ai" | "custom" | "mixed";
  experience_level: string | null;
  department: string | null;
  batch: string | null;
  interview_template_id: string | null;
  technical_duration_minutes: number;
  managerial_duration_minutes: number;
  hr_duration_minutes: number;
  total_duration_minutes: number;
  technical_instructions: string | null;
  managerial_instructions: string | null;
  hr_instructions: string | null;
  interviewer_avatar: string | null;
  interviewer_voice: string | null;
  interview_style: string | null;
  difficulty: "easy" | "medium" | "hard";
  question_categories: string[];
  evaluation_criteria: Record<string, unknown>;
  status: "draft" | "active" | "completed" | "archived";
  assigned_student_count?: number;
  created_at: string;
  updated_at: string;
};

export type CampaignListResult = {
  items: Campaign[];
  pagination: { page: number; per_page: number; total: number };
};

export type AssignStudentsResult = {
  assigned: number;
  already_assigned: number;
  not_found: string[];
  invalid_ids: string[];
};

export const campaignsApi = {
  list: (params: { page?: number; per_page?: number; status?: string }) => {
    const qs = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== "") qs.set(k, String(v));
    });
    return request<CampaignListResult>(`/api/v1/institute/campaigns?${qs.toString()}`);
  },

  get: (id: string) => request<Campaign>(`/api/v1/institute/campaigns/${id}`),

  create: (payload: {
    name: string;
    role: string;
    experience_level?: string;
    department?: string;
    batch?: string;
    company_id?: string;
    campus_id?: string;
    job_description?: string;
    question_source?: "ai" | "custom" | "mixed";
    interview_template_id?: string;
    technical_duration_minutes?: number;
    managerial_duration_minutes?: number;
    hr_duration_minutes?: number;
    difficulty?: string;
    question_categories?: string[];
  }) =>
    request<Campaign>("/api/v1/institute/campaigns", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  update: (id: string, payload: Partial<Campaign>) =>
    request<Campaign>(`/api/v1/institute/campaigns/${id}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),

  remove: (id: string) =>
    request<{ message: string }>(`/api/v1/institute/campaigns/${id}`, { method: "DELETE" }),

  activate: (id: string) =>
    request<Campaign>(`/api/v1/institute/campaigns/${id}/activate`, { method: "POST" }),
  complete: (id: string) =>
    request<Campaign>(`/api/v1/institute/campaigns/${id}/complete`, { method: "POST" }),
  archive: (id: string) =>
    request<Campaign>(`/api/v1/institute/campaigns/${id}/archive`, { method: "POST" }),

  listStudents: (id: string, params: { page?: number; per_page?: number }) => {
    const qs = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined) qs.set(k, String(v));
    });
    return request<StudentListResult>(
      `/api/v1/institute/campaigns/${id}/students?${qs.toString()}`
    );
  },

  assignStudents: (id: string, studentIds: string[]) =>
    request<AssignStudentsResult>(`/api/v1/institute/campaigns/${id}/students`, {
      method: "POST",
      body: JSON.stringify({ student_ids: studentIds }),
    }),

  unassignStudent: (id: string, studentId: string) =>
    request<{ message: string }>(
      `/api/v1/institute/campaigns/${id}/students/${studentId}`,
      { method: "DELETE" }
    ),
};

export type RoundType = "technical" | "managerial" | "hr";

export type TemplateRound = {
  round_type: RoundType;
  sequence_order: number;
  duration_minutes: number;
  question_categories: string[];
  evaluation_criteria: Record<string, unknown>;
  instructions: string | null;
};

export type InterviewTemplate = {
  id: string;
  name: string;
  description: string | null;
  is_default: boolean;
  rounds: TemplateRound[];
  created_at: string;
  updated_at: string;
};

export type TemplateListResult = {
  items: InterviewTemplate[];
  pagination: { page: number; per_page: number; total: number };
};

export type RoundConfigInput = {
  round_type: RoundType;
  duration_minutes: number;
  question_categories?: string[];
  evaluation_criteria?: Record<string, unknown>;
  instructions?: string;
};

export const interviewTemplatesApi = {
  list: (params: { page?: number; per_page?: number } = {}) => {
    const qs = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined) qs.set(k, String(v));
    });
    return request<TemplateListResult>(
      `/api/v1/institute/interview-templates?${qs.toString()}`
    );
  },

  get: (id: string) =>
    request<InterviewTemplate>(`/api/v1/institute/interview-templates/${id}`),

  create: (payload: {
    name: string;
    description?: string;
    is_default?: boolean;
    rounds?: RoundConfigInput[];
  }) =>
    request<InterviewTemplate>("/api/v1/institute/interview-templates", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  update: (
    id: string,
    payload: Partial<{
      name: string;
      description: string;
      is_default: boolean;
      rounds: RoundConfigInput[];
    }>
  ) =>
    request<InterviewTemplate>(`/api/v1/institute/interview-templates/${id}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),

  remove: (id: string) =>
    request<{ message: string }>(`/api/v1/institute/interview-templates/${id}`, {
      method: "DELETE",
    }),
};

export type ProcessingStatus = "pending" | "processing" | "completed" | "failed";

export type CandidateProfile = {
  id: string;
  education: string[];
  skills: string[];
  programming_languages: string[];
  technologies: string[];
  projects: string[];
  internships: string[];
  experience: string[];
  certifications: string[];
  achievements: string[];
  extraction_method: string | null;
  analysis_status: ProcessingStatus;
  analysis_error: string | null;
};

export type ResumeVersion = {
  id: string;
  resume_id: string;
  version_number: number;
  original_filename: string;
  file_size_bytes: number;
  content_type: string;
  file_url: string | null;
  extraction_status: ProcessingStatus;
  extraction_error: string | null;
  extracted_text: string | null;
  candidate_profile?: CandidateProfile | null;
  created_at: string;
};

export type ResumeVersionListResult = {
  items: ResumeVersion[];
  pagination: { page: number; per_page: number; total: number };
};

export const resumeApi = {
  getCurrent: (studentId: string) =>
    request<ResumeVersion>(`/api/v1/institute/students/${studentId}/resume`),

  listVersions: (studentId: string, params: { page?: number; per_page?: number } = {}) => {
    const qs = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined) qs.set(k, String(v));
    });
    return request<ResumeVersionListResult>(
      `/api/v1/institute/students/${studentId}/resume/versions?${qs.toString()}`
    );
  },

  getVersion: (studentId: string, versionId: string) =>
    request<ResumeVersion>(
      `/api/v1/institute/students/${studentId}/resume/versions/${versionId}`
    ),

  upload: async (studentId: string, file: File): Promise<ResumeVersion> => {
    const formData = new FormData();
    formData.append("file", file);
    const res = await fetch(
      `${API_BASE_URL}/api/v1/institute/students/${studentId}/resume`,
      { method: "POST", credentials: "include", body: formData }
    );
    const body = await res.json().catch(() => null);
    if (!res.ok || !body?.success) {
      const err = body?.error ?? { code: "unknown_error", message: "Upload failed." };
      throw new ApiRequestError(res.status, err);
    }
    return body.data as ResumeVersion;
  },
};

export type InterviewRoundType = "technical" | "managerial" | "hr";

export type InterviewQuestionPublic = {
  id: string;
  sequence_order: number;
  question_text: string;
};

export type InterviewState = {
  id: string;
  status:
    | "created"
    | "ready"
    | "in_progress"
    | "completed"
    | "evaluating"
    | "report_generating"
    | "report_ready"
    | "failed"
    | "cancelled";
  current_round: InterviewRoundType | null;
  seconds_remaining: number | null;
  resume_verified: boolean;
  device_checked: boolean;
  technical_duration_minutes: number;
  managerial_duration_minutes: number;
  hr_duration_minutes: number;
  current_question: InterviewQuestionPublic | null;
  started_at: string | null;
  completed_at: string | null;
};

// Separate base request helper: these routes live under /api/v1/interview
// (student session), not /api/v1/institute/*, and errors here should
// never be confused with institute-admin auth errors by the caller.
async function interviewRequest<T>(path: string, options: RequestInit = {}): Promise<T> {
  const res = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    credentials: "include",
    headers: { "Content-Type": "application/json", ...options.headers },
  });
  const body = await res.json().catch(() => null);
  if (!res.ok || !body?.success) {
    const err = body?.error ?? { code: "unknown_error", message: "Something went wrong." };
    throw new ApiRequestError(res.status, err);
  }
  return body.data as T;
}

export const interviewSessionApi = {
  exchangeAccessToken: (interviewId: string, token: string) =>
    interviewRequest<InterviewState>(`/api/v1/interview/${interviewId}/access`, {
      method: "POST",
      body: JSON.stringify({ token }),
    }),

  getState: () => interviewRequest<InterviewState>("/api/v1/interview/me"),

  resumeCheck: () =>
    interviewRequest<InterviewState>("/api/v1/interview/resume-check", { method: "POST" }),

  deviceCheck: () =>
    interviewRequest<InterviewState>("/api/v1/interview/device-check", { method: "POST" }),

  start: () => interviewRequest<InterviewState>("/api/v1/interview/start", { method: "POST" }),

  submitAnswer: (questionId: string, transcriptText: string) =>
    interviewRequest<InterviewState>("/api/v1/interview/answer", {
      method: "POST",
      body: JSON.stringify({ question_id: questionId, transcript_text: transcriptText }),
    }),

  // Speech-to-text: uploads a recording, returns transcript text only —
  // does not submit an answer. Caller passes the text to submitAnswer.
  transcribeAnswer: async (audioBlob: Blob): Promise<{ text: string; source: string }> => {
    const formData = new FormData();
    formData.append("file", audioBlob, "answer.webm");
    const res = await fetch(`${API_BASE_URL}/api/v1/interview/transcribe`, {
      method: "POST",
      credentials: "include",
      body: formData,
    });
    const body = await res.json().catch(() => null);
    if (!res.ok || !body?.success) {
      const err = body?.error ?? { code: "unknown_error", message: "Transcription failed." };
      throw new ApiRequestError(res.status, err);
    }
    return body.data;
  },

  // Text-to-speech for the current question. Returns null (not a
  // thrown error) when no TTS provider is configured (501) — callers
  // should treat that as "fall back to browser speechSynthesis."
  getQuestionAudio: async (): Promise<Blob | null> => {
    const res = await fetch(`${API_BASE_URL}/api/v1/interview/question-audio`, {
      credentials: "include",
    });
    if (res.status === 501) return null;
    if (!res.ok) {
      const body = await res.json().catch(() => null);
      const err = body?.error ?? { code: "unknown_error", message: "Couldn't load audio." };
      throw new ApiRequestError(res.status, err);
    }
    return res.blob();
  },

  getAvatarSession: () =>
    interviewRequest<{ provider: string; embed_url: string | null; session_token: string | null }>(
      "/api/v1/interview/avatar-session"
    ),
};

export type InterviewSummary = {
  id: string;
  student_id: string;
  status: string;
  current_round: string | null;
  started_at: string | null;
  completed_at: string | null;
};

export type InterviewSummaryListResult = {
  items: InterviewSummary[];
  pagination: { page: number; per_page: number; total: number };
};

export const instituteInterviewsApi = {
  listForCampaign: (campaignId: string, params: { page?: number; per_page?: number } = {}) => {
    const qs = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined) qs.set(k, String(v));
    });
    return request<InterviewSummaryListResult>(
      `/api/v1/institute/campaigns/${campaignId}/interviews?${qs.toString()}`
    );
  },

  cancel: (interviewId: string) =>
    request<{ status: string }>(`/api/v1/institute/interviews/${interviewId}/cancel`, {
      method: "POST",
    }),
};

export type Report = {
  version_number: number;
  overall_score: number;
  technical_score: number;
  communication_score: number;
  managerial_score: number;
  hr_score: number;
  problem_solving_score: number;
  strengths: string[];
  weaknesses: string[];
  technical_skill_gaps: string[];
  communication_improvements: string[];
  interview_highlights: string[];
  recommended_preparation: string[];
  improvement_plan: string[];
  model_version: string | null;
  prompt_version: string;
  evaluation_version: string;
  report_source: string;
  generated_at: string;
};

export type EvaluationDetail = {
  dimension: string;
  score: number;
  criteria_scores: Record<string, number>;
  evidence: string[];
  strengths: string[];
  weaknesses: string[];
  improvement_suggestions: string[];
  evaluation_source: string;
};

export type InterviewAdminDetail = {
  id: string;
  student_id: string;
  status: string;
  current_round: string | null;
  started_at: string | null;
  completed_at: string | null;
  rounds: {
    round_type: string;
    status: string;
    questions: { id: string; question_text: string; question_source: string; topic: string | null }[];
  }[];
  evaluations: EvaluationDetail[];
};

export const reportsApi = {
  // Institute-admin view of a specific interview's report.
  getForInterview: (interviewId: string) =>
    request<Report>(`/api/v1/institute/interviews/${interviewId}/report`),

  getInterviewDetail: (interviewId: string) =>
    request<InterviewAdminDetail>(`/api/v1/institute/interviews/${interviewId}`),

  // Student's own report, via their interview session cookie.
  getMyReport: () => interviewRequest<Report>("/api/v1/interview/report"),
};

export type ReadinessBand = "needs_improvement" | "developing" | "ready" | "excellent";

export type AnalyticsDashboard = {
  filters_applied: {
    campaign_id: string | null;
    department: string | null;
    batch: string | null;
    role: string | null;
    date_from: string | null;
    date_to: string | null;
  };
  total_students: number;
  assigned_interviews: number;
  started_interviews: number;
  completed_interviews: number;
  completion_rate: number;
  average_score: number | null;
  highest_score: number | null;
  lowest_score: number | null;
  scored_interviews: number;
  dimension_performance: {
    technical: number | null;
    communication: number | null;
    managerial: number | null;
    hr: number | null;
  };
  readiness_distribution: Record<ReadinessBand, number>;
  department_performance: { name: string; average_score: number; count: number }[];
  batch_performance: { name: string; average_score: number; count: number }[];
  skill_gaps: { gap: string; count: number }[];
};

export type AnalyticsFilterOptions = {
  departments: string[];
  batches: string[];
};

export const analyticsApi = {
  getDashboard: (params: {
    campaign_id?: string;
    department?: string;
    batch?: string;
    role?: string;
    date_from?: string;
    date_to?: string;
  }) => {
    const qs = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v) qs.set(k, v);
    });
    return request<AnalyticsDashboard>(`/api/v1/institute/analytics?${qs.toString()}`);
  },

  getFilterOptions: () =>
    request<AnalyticsFilterOptions>("/api/v1/institute/analytics/filter-options"),
};

export type Campus = { id: string; institute_id: string; name: string; code: string | null; location: string | null; is_active: boolean };
export type Company = { id: string; institute_id: string | null; name: string; website: string | null; description: string | null };
export type BankQuestion = { id: string; institute_id: string; company_id: string | null; question: string; expected_answer_criteria: string | null; role: string | null; round_type: "technical" | "managerial" | "hr"; category: string | null; difficulty: "easy" | "medium" | "hard"; is_active: boolean };

export const campusApi = {
  list: () => request<Campus[]>("/api/v1/institute/campuses"),
  create: (payload: { name: string; code?: string; location?: string }) => request<Campus>("/api/v1/institute/campuses", { method: "POST", body: JSON.stringify(payload) }),
  update: (id: string, payload: Partial<Pick<Campus, "name" | "code" | "location" | "is_active">>) => request<Campus>(`/api/v1/institute/campuses/${id}`, { method: "PATCH", body: JSON.stringify(payload) }),
  remove: (id: string) => request<{ message: string }>(`/api/v1/institute/campuses/${id}`, { method: "DELETE" }),
};

export const companiesApi = {
  list: () => request<Company[]>("/api/v1/institute/companies"),
  create: (payload: { name: string; website?: string; description?: string }) => request<Company>("/api/v1/institute/companies", { method: "POST", body: JSON.stringify(payload) }),
};

export const questionBankApi = {
  list: (params: { round_type?: string; difficulty?: string; company_id?: string } = {}) => {
    const qs = new URLSearchParams(); Object.entries(params).forEach(([k, v]) => { if (v) qs.set(k, v); });
    return request<BankQuestion[]>(`/api/v1/institute/question-bank?${qs.toString()}`);
  },
  create: (payload: { question: string; expected_answer_criteria?: string; role?: string; round_type: string; category?: string; difficulty: string; company_id?: string }) => request<BankQuestion>("/api/v1/institute/question-bank", { method: "POST", body: JSON.stringify(payload) }),
  update: (id: string, payload: Partial<BankQuestion>) => request<BankQuestion>(`/api/v1/institute/question-bank/${id}`, { method: "PATCH", body: JSON.stringify(payload) }),
  remove: (id: string) => request<{ message: string }>(`/api/v1/institute/question-bank/${id}`, { method: "DELETE" }),
};
