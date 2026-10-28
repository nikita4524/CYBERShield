/**
 * @file api.ts — CyberShield AI Frontend API Client
 */

import { API_BASE_URL } from "./constants";
import type {
  AuthResponse,
  OtpRequestResponse,
  RefreshResponse,
  AnalysisResponse,
  QrAnalysisResponse,
  QuizResponse,
  QuizSessionResponse,
  QuizResultResponse,
  QuizAnswer,
  DemoSamplesResponse,
  AnalysisSummary,
  AnalysisListResponse,
  PaginatedResponse,
  OrgMetrics,
  User,
  SecurityIncident,
  IncidentListResponse,
  IncidentStats,
  ThreatExplanationRequest,
  ThreatExplanationResponse,
} from "./types";

export interface EmailAnalysisRequest {
  subject: string;
  body: string;
  sender?: string;
  urls?: string[];
}

export interface EmlParseResult {
  subject: string;
  sender: string;
  to: string;
  cc: string;
  reply_to: string;
  date: string;
  body: string;
  html_body: string;
  urls: string[];
  domains: string[];
  ips: string[];
  attachments: { name: string; content_type: string }[];
  headers: Record<string, string>;
  auth: { spf: string; dkim: string; dmarc: string };
}

/* ── Local Storage Cache for guest users ── */
const LOCAL_ANALYSES_KEY = "cs-recent-analyses";
const MAX_LOCAL_ANALYSES = 20;

function getLocalAnalyses(): AnalysisSummary[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = localStorage.getItem(LOCAL_ANALYSES_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

function saveLocalAnalysis(analysis: AnalysisSummary) {
  if (typeof window === "undefined") return;
  try {
    const existing = getLocalAnalyses();
    // Prepend new, deduplicate, limit
    const updated = [
      analysis,
      ...existing.filter((a) => a.id !== analysis.id),
    ].slice(0, MAX_LOCAL_ANALYSES);
    localStorage.setItem(LOCAL_ANALYSES_KEY, JSON.stringify(updated));
  } catch {
    // Quota exceeded — silently ignore
  }
}

/* ── Local Storage Cache for quizzes ── */
const LOCAL_QUIZZES_KEY = "cs-recent-quizzes";
const MAX_LOCAL_QUIZZES = 30;

export interface LocalQuizSession {
  id: string;
  category: string;
  total_questions: number;
  correct_count: number;
  score_pct: number;
  badge_earned: string | null;
  started_at?: string;
  completed_at: string;
}

export function getLocalQuizSessions(): LocalQuizSession[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = localStorage.getItem(LOCAL_QUIZZES_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

export function saveLocalQuizSession(session: LocalQuizSession) {
  if (typeof window === "undefined") return;
  try {
    const existing = getLocalQuizSessions();
    const updated = [
      session,
      ...existing.filter((s) => s.id !== session.id),
    ].slice(0, MAX_LOCAL_QUIZZES);
    localStorage.setItem(LOCAL_QUIZZES_KEY, JSON.stringify(updated));
  } catch {
    // Quota exceeded
  }
}

/** Convert an AnalysisResponse to a storable AnalysisSummary */
function responseToSummary(
  res: AnalysisResponse,
  type: AnalysisSummary["type"]
): AnalysisSummary {
  return {
    id: res.analysis_id,
    type,
    risk_score: res.risk_score,
    risk_label: res.risk_label,
    explanation_summary:
      res.explanation?.summary || `${type} analysis completed`,
    processing_time_ms: res.processing_time_ms,
    created_at: new Date().toISOString(),
  };
}

/* ── API Error Class ── */
export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public details?: Record<string, unknown>
  ) {
    super(message);
    this.name = "ApiError";
  }
}

/* ── API Client ── */
class ApiClient {
  private baseUrl: string;

  constructor(baseUrl: string = API_BASE_URL) {
    this.baseUrl = baseUrl;
  }

  private getToken(): string | null {
    if (typeof window === "undefined") return null;
    return localStorage.getItem("access_token");
  }

  private isAuthenticated(): boolean {
    return !!this.getToken();
  }

  async request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
    const token = this.getToken();

    const headers: Record<string, string> = {};

    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }

    // Don't set Content-Type for FormData
    if (!(options.body instanceof FormData)) {
      headers["Content-Type"] = "application/json";
    }

    let response: Response;
    try {
      response = await fetch(`${this.baseUrl}${endpoint}`, {
        ...options,
        headers: {
          ...headers,
          ...(options.headers as Record<string, string>),
        },
      });
    } catch {
      throw new ApiError(
        0,
        "network_error",
        `Cannot reach API at ${this.baseUrl}. Start backend and verify NEXT_PUBLIC_API_URL.`
      );
    }

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({
        error: "unknown_error",
        message: `Request failed with status ${response.status}`,
      }));

      const detailMessage =
        typeof errorData?.detail === "string"
          ? errorData.detail
          : Array.isArray(errorData?.detail)
            ? errorData.detail
                .map((d: any) => d?.msg || JSON.stringify(d))
                .join(", ")
            : undefined;

      throw new ApiError(
        response.status,
        errorData.error || "unknown_error",
        errorData.message ||
          detailMessage ||
          "An unexpected error occurred",
        (errorData.details ?? errorData.detail) as Record<string, unknown> | undefined
      );
    }

    // Handle 204 No Content
    if (response.status === 204) {
      return {} as T;
    }

    return response.json();
  }

  /* ── Auth ── */
  requestOtp(email: string, purpose: "login" | "signup" = "login") {
    return this.request<OtpRequestResponse>("/auth/request-otp", {
      method: "POST",
      body: JSON.stringify({ email, purpose }),
    });
  }

  verifyOtp(
    email: string,
    otp: string,
    purpose: "login" | "signup" = "login",
    displayName?: string
  ) {
    return this.request<AuthResponse>("/auth/verify-otp", {
      method: "POST",
      body: JSON.stringify({ email, otp, purpose, display_name: displayName }),
    });
  }

  register(email: string, password: string, displayName?: string) {
    return this.request<AuthResponse>("/auth/register", {
      method: "POST",
      body: JSON.stringify({ email, password, display_name: displayName }),
    });
  }

  loginWithPassword(email: string, password: string) {
    return this.request<AuthResponse>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    });
  }

  refreshToken(refreshToken: string) {
    return this.request<RefreshResponse>("/auth/refresh", {
      method: "POST",
      body: JSON.stringify({ refresh_token: refreshToken }),
    });
  }

  logout() {
    return this.request<{ status: string }>("/auth/logout", {
      method: "POST",
    });
  }

  getMe() {
    return this.request<User>("/auth/me");
  }

  /* ── Analysis (with local caching) ── */
  async analyzeEmail(data: EmailAnalysisRequest) {
    const result = await this.request<AnalysisResponse>("/analyze/email", {
      method: "POST",
      body: JSON.stringify(data),
    });
    saveLocalAnalysis(responseToSummary(result, "email"));
    return result;
  }

  async parseEml(file: File): Promise<EmlParseResult> {
    const form = new FormData();
    form.append("file", file);
    return this.request<EmlParseResult>("/analyze/email/parse-eml", {
      method: "POST",
      body: form,
    });
  }

  async analyzeUrl(url: string) {
    const result = await this.request<AnalysisResponse>("/analyze/url", {
      method: "POST",
      body: JSON.stringify({ url }),
    });
    saveLocalAnalysis(responseToSummary(result, "url"));
    return result;
  }

  async analyzeQr(file: File) {
    const form = new FormData();
    form.append("file", file);
    const result = await this.request<QrAnalysisResponse>("/analyze/qr", {
      method: "POST",
      body: form,
    });
    saveLocalAnalysis(responseToSummary(result, "qr"));
    return result;
  }

  async analyzeAudio(file: File) {
    const form = new FormData();
    form.append("file", file);
    const result = await this.request<AnalysisResponse>("/analyze/audio", {
      method: "POST",
      body: form,
    });
    saveLocalAnalysis(responseToSummary(result, "audio"));
    return result;
  }

  async analyzeVideo(file: File) {
    const form = new FormData();
    form.append("file", file);
    const result = await this.request<AnalysisResponse>("/analyze/video", {
      method: "POST",
      body: form,
    });
    saveLocalAnalysis(responseToSummary(result, "video"));
    return result;
  }

  async analyzeImage(file: File) {
    const form = new FormData();
    form.append("file", file);
    const result = await this.request<AnalysisResponse>("/analyze/image", {
      method: "POST",
      body: form,
    });
    saveLocalAnalysis(responseToSummary(result, "image"));
    return result;
  }

  /* ── Reports ── */

  /**
   * Get analysis history.
   * - Authenticated users → fetches from backend API
   * - Guest users → returns from localStorage cache
   *
   * Backend returns { analyses: [...] } so we map to { items: [...] }
   */
  async getAnalysisHistory(
    page = 1,
    limit = 20
  ): Promise<PaginatedResponse<AnalysisSummary>> {
    if (!this.isAuthenticated()) {
      // Guest mode: return cached local analyses
      const local = getLocalAnalyses();
      const start = (page - 1) * limit;
      const slice = local.slice(start, start + limit);
      return {
        total: local.length,
        page,
        limit,
        items: slice,
      };
    }

    try {
      // Backend returns { total, page, limit, analyses: [...] }
      const raw = await this.request<AnalysisListResponse>(
        `/reports/analyses?page=${page}&limit=${limit}`
      );
      return {
        total: raw.total,
        page: raw.page,
        limit: raw.limit,
        items: raw.analyses ?? [],
      };
    } catch (err) {
      // If 401 (token expired), fall back to local cache
      if (err instanceof ApiError && err.status === 401) {
        const local = getLocalAnalyses();
        const start = (page - 1) * limit;
        return {
          total: local.length,
          page,
          limit,
          items: local.slice(start, start + limit),
        };
      }
      throw err;
    }
  }

  getAnalysisDetail(id: string) {
    return this.request<AnalysisResponse>(`/reports/analyses/${id}`);
  }

  /** Get local (client-side cached) analyses for immediate display */
  getLocalAnalyses(): AnalysisSummary[] {
    return getLocalAnalyses();
  }

  /**
   * Export an active analysis result as a CERT-In aligned forensic PDF report.
   */
  async exportAnalysisPdf(analysis: {
    analysis_id?: string;
    type?: string;
    risk_score: number;
    risk_label: string;
    explanation_summary?: string;
    explanation?: any;
    model_scores?: any;
    contributing_factors?: any[];
  }) {
    const token = this.getToken();
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
    };
    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }

    const res = await fetch(`${API_BASE_URL}/reports/analyses/export-pdf`, {
      method: "POST",
      headers,
      body: JSON.stringify(analysis),
    });

    if (!res.ok) {
      throw new Error(`Failed to generate PDF: ${res.statusText}`);
    }

    const blob = await res.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    const safeId = (analysis.analysis_id || "evidence").slice(0, 8);
    a.download = `CyberShield_Forensic_Report_${safeId}.pdf`;
    document.body.appendChild(a);
    a.click();
    window.URL.revokeObjectURL(url);
    document.body.removeChild(a);
  }

  /**
   * Download a stored analysis forensic PDF by its database ID.
   */
  async downloadAnalysisPdfById(analysisId: string) {
    const token = this.getToken();
    const headers: Record<string, string> = {};
    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }

    const res = await fetch(`${API_BASE_URL}/reports/analyses/${analysisId}/pdf`, {
      headers,
    });

    if (!res.ok) {
      throw new Error(`Failed to download report: ${res.statusText}`);
    }

    const blob = await res.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `CyberShield_Forensic_Report_${analysisId.slice(0, 8)}.pdf`;
    document.body.appendChild(a);
    a.click();
    window.URL.revokeObjectURL(url);
    document.body.removeChild(a);
  }

  /* ── Awareness ── */
  getQuizzes(category: string, language = "en") {
    return this.request<QuizResponse>(
      `/awareness/quizzes?category=${category}&language=${language}`
    );
  }

  startQuizSession(category: string, language = "en") {
    return this.request<QuizSessionResponse>("/awareness/quiz-sessions", {
      method: "POST",
      body: JSON.stringify({ category, language }),
    });
  }

  async submitQuizAnswers(sessionId: string, answers: QuizAnswer[]) {
    const res = await this.request<QuizResultResponse>(
      `/awareness/quiz-sessions/${sessionId}/answers`,
      {
        method: "POST",
        body: JSON.stringify({ answers }),
      }
    );
    if (res) {
      saveLocalQuizSession({
        id: res.session_id || sessionId,
        category: res.category || "general",
        total_questions: res.total_questions || answers.length,
        correct_count: res.correct_count || 0,
        score_pct: res.score_pct || 0,
        badge_earned: res.badge_earned || null,
        completed_at: new Date().toISOString(),
      });
    }
    return res;
  }

  async getQuizHistory(page = 1, limit = 20, category?: string) {
    try {
      const params = new URLSearchParams({
        page: String(page),
        limit: String(limit),
      });
      if (category && category !== "all") {
        params.set("category", category);
      }
      const res = await this.request<{ total: number; page: number; limit: number; sessions: any[] }>(
        `/reports/quizzes?${params.toString()}`
      );
      if (res && res.sessions && res.sessions.length > 0) {
        return res;
      }
    } catch {
      // Fallback to local
    }
    const local = getLocalQuizSessions();
    const filtered = category && category !== "all" ? local.filter((s) => s.category === category) : local;
    return {
      total: filtered.length,
      page,
      limit,
      sessions: filtered.slice((page - 1) * limit, page * limit),
    };
  }

  getLocalQuizSessions(): LocalQuizSession[] {
    return getLocalQuizSessions();
  }

  getScenarios() {
    return this.request<{ scenarios: any[] }>("/awareness/scenarios");
  }

  getScenario(id: string) {
    return this.request<any>(`/awareness/scenarios/${id}`);
  }

  getAwarenessSummary() {
    return this.request<any>("/awareness/summary");
  }

  /* ── Demo ── */
  getDemoSamples() {
    return this.request<DemoSamplesResponse>("/demo/samples");
  }

  /* ── Admin ── */
  getOrgMetrics(period = "last_30_days") {
    return this.request<OrgMetrics>(`/admin/metrics?period=${period}`);
  }

  /* ── IoT ── */
  registerIoTDevice(data: RegisterIoTDeviceRequest) {
    return this.request<IoTDevice>("/iot/devices/register", {
      method: "POST",
      body: JSON.stringify(data),
    });
  }

  getIoTDevices() {
    return this.request<IoTDeviceListResponse>("/iot/devices");
  }

  deleteIoTDevice(deviceId: string) {
    return this.request<void>(`/iot/devices/${deviceId}`, {
      method: "DELETE",
    });
  }

  seedIoTDemoDevices() {
    return this.request<{ message: string; devices: IoTDevice[] }>(
      "/iot/devices/seed-demo",
      { method: "POST" }
    );
  }

  getIoTAlerts(page = 1, limit = 20, isResolved?: boolean) {
    const params = new URLSearchParams({
      page: String(page),
      limit: String(limit),
    });
    if (isResolved !== undefined) {
      params.set("is_resolved", String(isResolved));
    }
    return this.request<IoTAlertListResponse>(`/iot/alerts?${params}`);
  }

  resolveIoTAlert(alertId: string) {
    return this.request<IoTAlert>(`/iot/alerts/${alertId}/resolve`, {
      method: "PATCH",
    });
  }

  /**
   * Send a simulated telemetry event to the backend rule engine.
   * NOT connected to real hardware — simulation only.
   */
  simulateTelemetry(data: TelemetryIngestRequest) {
    return this.request<TelemetryIngestResponse>("/iot/telemetry", {
      method: "POST",
      body: JSON.stringify(data),
    });
  }

  /**
   * Fetch recent telemetry history for a registered virtual device.
   */
  getIoTTelemetry(deviceId: string, page = 1, limit = 20) {
    const params = new URLSearchParams({
      device_id: deviceId,
      page: String(page),
      limit: String(limit),
    });
    return this.request<IoTTelemetryHistoryResponse>(`/iot/telemetry?${params}`);
  }

  /* ── Security Incidents ── */
  getIncidents(params: {
    page?: number;
    limit?: number;
    threat_type?: string;
    severity?: string;
    action?: string;
    status?: string;
    source?: string;
  } = {}) {
    const searchParams = new URLSearchParams();
    if (params.page) searchParams.set("page", String(params.page));
    if (params.limit) searchParams.set("limit", String(params.limit));
    if (params.threat_type) searchParams.set("threat_type", params.threat_type);
    if (params.severity) searchParams.set("severity", params.severity);
    if (params.action) searchParams.set("action", params.action);
    if (params.status) searchParams.set("status", params.status);
    if (params.source) searchParams.set("source", params.source);

    const query = searchParams.toString();
    return this.request<IncidentListResponse>(`/incidents${query ? `?${query}` : ""}`);
  }

  getIncident(idOrNumber: string) {
    return this.request<SecurityIncident>(`/incidents/${idOrNumber}`);
  }

  updateIncidentStatus(
    idOrNumber: string,
    status: "OPEN" | "REVIEWING" | "RESOLVED" | "FALSE_POSITIVE",
    resolution_note?: string
  ) {
    return this.request<SecurityIncident>(`/incidents/${idOrNumber}`, {
      method: "PATCH",
      body: JSON.stringify({ status, resolution_note }),
    });
  }

  getIncidentStats() {
    return this.request<IncidentStats>("/incidents/stats");
  }

  /* ── Threat Explanation (AI Security Context) ── */
  explainThreat(data: ThreatExplanationRequest) {
    return this.request<ThreatExplanationResponse>("/assistant/analyze-context", {
      method: "POST",
      body: JSON.stringify(data),
    });
  }
}

/** Singleton API client instance */
export const api = new ApiClient();