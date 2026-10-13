import { apiClient } from "./axios";
import {
  HealthTrendPoint,
  MedicationItem,
  LabReportItem,
  RecoveryPlanTask,
  AskAIResponse,
  PatientProfileResponse,
} from "@/types";

export interface PatientOverviewNormalized {
  patient_id: string;
  patient_name: string;
  patient_profile?: PatientProfileResponse;
  last_visit_date?: string;
  most_recent_consultation_date?: string;
  last_consultation_id?: string;
  most_recent_consultation_id?: string;
  summary_status?: string;
  has_approved_summary?: boolean;
  latest_approved_summary?: any;
  health_trends: HealthTrendPoint[];
  raw_health_trends?: any[];
  active_medications_count: number;
  pending_lab_reports_count: number;
  contextual_questions?: string[];
}

export const patientApi = {
  async getProfile(patientId?: string): Promise<PatientProfileResponse> {
    let url = "/api/v1/patient/profile";
    if (patientId) url += `?patient_id=${patientId}`;
    const res = await apiClient.get<PatientProfileResponse>(url);
    return res.data;
  },

  async getOverview(patientId?: string): Promise<PatientOverviewNormalized> {
    let url = "/api/v1/patient/overview";
    if (patientId) url += `?patient_id=${patientId}`;
    const res = await apiClient.get<any>(url);
    const raw = res.data;

    const profile = raw.patient_profile;
    const patientName = profile?.full_name || profile?.name || raw.patient_name || "Ananya Patel";
    const patientIdVal = profile?.patient_id || raw.patient_id || "PT-89241";
    const lastDate = raw.most_recent_consultation_date || raw.last_visit_date;
    const lastCid = raw.most_recent_consultation_id || raw.last_consultation_id;

    // Normalize health trends series into flat trend points if needed
    const trendPoints: HealthTrendPoint[] = [];
    if (Array.isArray(raw.health_trends)) {
      // Check if it's series objects
      const bpSeries = raw.health_trends.find((s: any) => s.metric_name?.toLowerCase().includes("blood pressure") || s.metric_type?.includes("pressure"));
      const glucoseSeries = raw.health_trends.find((s: any) => s.metric_name?.toLowerCase().includes("glucose") || s.metric_type?.includes("glucose"));
      const weightSeries = raw.health_trends.find((s: any) => s.metric_name?.toLowerCase().includes("weight") || s.metric_type?.includes("weight"));

      const dates = new Set<string>();
      [bpSeries, glucoseSeries, weightSeries].forEach((series) => {
        if (series?.data_points) {
          series.data_points.forEach((dp: any) => {
            if (dp.recorded_at) dates.add(dp.recorded_at.substring(0, 10));
          });
        }
      });

      const sortedDates = Array.from(dates).sort();
      sortedDates.forEach((d) => {
        const bpPoint = bpSeries?.data_points?.find((p: any) => p.recorded_at?.startsWith(d));
        const glucosePoint = glucoseSeries?.data_points?.find((p: any) => p.recorded_at?.startsWith(d));
        const weightPoint = weightSeries?.data_points?.find((p: any) => p.recorded_at?.startsWith(d));

        trendPoints.push({
          date: d,
          systolic_bp: bpPoint?.numeric_value ?? bpPoint?.value,
          diastolic_bp: bpPoint?.secondary_value ?? bpPoint?.value_secondary,
          fasting_glucose: glucosePoint?.numeric_value ?? glucosePoint?.value,
          weight_kg: weightPoint?.numeric_value ?? weightPoint?.value,
        });
      });
    }

    const medsList = raw.doctor_approved_medications || raw.current_medications || [];
    const labsList = raw.recent_lab_reports || [];

    return {
      patient_id: patientIdVal,
      patient_name: patientName,
      patient_profile: profile,
      last_visit_date: lastDate,
      most_recent_consultation_date: lastDate,
      last_consultation_id: lastCid,
      most_recent_consultation_id: lastCid,
      summary_status: raw.has_approved_summary ? "approved" : "pending_doctor_review",
      has_approved_summary: !!raw.has_approved_summary,
      latest_approved_summary: raw.latest_approved_summary,
      health_trends: trendPoints,
      raw_health_trends: raw.health_trends,
      active_medications_count: medsList.length,
      pending_lab_reports_count: labsList.length,
      contextual_questions: raw.contextual_questions || [],
    };
  },

  async getLastVisit(consultationId?: string, patientId?: string) {
    const params = new URLSearchParams();
    if (consultationId) params.append("consultation_id", consultationId);
    if (patientId) params.append("patient_id", patientId);
    const query = params.toString() ? `?${params.toString()}` : "";
    const res = await apiClient.get<any>(`/api/v1/patient/last-visit${query}`);
    return res.data;
  },

  async getHistory(page = 1, pageSize = 20, statusFilter?: string) {
    const params = new URLSearchParams({
      page: page.toString(),
      page_size: pageSize.toString(),
    });
    if (statusFilter) params.append("status_filter", statusFilter);
    const res = await apiClient.get<any>(`/api/v1/patient/history?${params.toString()}`);
    const items = res.data?.items || res.data?.consultations || [];
    const normalized = items.map((i: any) => ({
      ...i,
      id: i.consultation_id || i.id,
      consultation_id: i.consultation_id || i.id,
      visit_date: i.date || i.consultation_date,
      reason: i.visit_reason || i.main_reason || "Clinical Encounter",
      summary_status: i.approved_summary_available || i.doctor_review_status === "approved" ? "approved" : "pending",
      summary_approved: i.approved_summary_available || i.doctor_review_status === "approved",
    }));

    return {
      consultations: normalized,
      items: normalized,
      total: res.data?.total || normalized.length,
      page: res.data?.page || page,
      page_size: res.data?.page_size || pageSize,
    };
  },

  async getMedications(consultationId?: string): Promise<{ medications: MedicationItem[] }> {
    let url = "/api/v1/patient/medications";
    if (consultationId) url += `?consultation_id=${consultationId}`;
    const res = await apiClient.get<any>(url);
    const rawMeds = res.data?.medications || [];
    const normalized = rawMeds.map((m: any) => ({
      ...m,
      name: m.medicine_name || m.name || "Prescribed Medication",
      dose: m.strength || m.dose || m.dosage,
      timing: m.timing || m.food_timing || "After food",
    }));
    return { medications: normalized };
  },

  async getRecoveryPlan(consultationId?: string): Promise<{ tasks: RecoveryPlanTask[]; total: number }> {
    let url = "/api/v1/patient/recovery-plan";
    if (consultationId) url += `?consultation_id=${consultationId}`;
    const res = await apiClient.get<any>(url);
    const planItems = res.data?.plan_items || res.data?.tasks || res.data?.items || [];
    const tasks: RecoveryPlanTask[] = planItems.map((item: any) => ({
      task_key: item.task_key,
      title: item.title,
      description: item.description,
      doctor_instruction: item.doctor_instruction,
      category: item.category || "monitoring",
      completed: item.patient_completed ?? item.completed ?? item.is_completed ?? false,
      is_completed: item.patient_completed ?? item.completed ?? item.is_completed ?? false,
      is_doctor_prescribed: item.is_doctor_prescribed,
      notes: item.notes,
    }));
    return { tasks, total: tasks.length };
  },

  async toggleRecoveryTask(consultationId: string, taskKey: string, completed: boolean, notes?: string) {
    const res = await apiClient.post("/api/v1/patient/recovery-plan/toggle", {
      consultation_id: consultationId,
      task_key: taskKey,
      completed,
      notes,
    });
    return res.data;
  },

  async listLabReports(consultationId?: string): Promise<{ lab_reports: LabReportItem[]; total: number }> {
    let url = "/api/v1/patient/lab-reports";
    if (consultationId) url += `?consultation_id=${consultationId}`;
    const res = await apiClient.get<any>(url);
    const reports = res.data?.lab_reports || res.data?.reports || [];
    return {
      lab_reports: reports.map((r: any) => ({
        ...r,
        test_name: r.test_name || r.report_name || "Diagnostic Test",
        test_value: r.test_value || r.test_result || r.patient_value,
        status: r.review_status || r.status || "unreviewed",
        report_date: r.report_date || r.test_date,
      })),
      total: res.data?.total || reports.length,
    };
  },

  async uploadLabReport(formData: FormData) {
    const res = await apiClient.post("/api/v1/patient/lab-reports/upload", formData, {
      headers: { "Content-Type": "multipart/form-data" },
    });
    return res.data;
  },

  async createManualLabReport(payload: {
    test_name: string;
    test_value?: string;
    unit?: string;
    report_date?: string;
    facility_name?: string;
    patient_notes?: string;
  }) {
    const res = await apiClient.post("/api/v1/patient/lab-reports/manual", payload);
    return res.data;
  },

  async confirmLabReport(
    reportId: string,
    payload: {
      patient_confirmed?: boolean;
      patient_notes?: string;
      corrected_results?: any[];
    }
  ) {
    const res = await apiClient.post(`/api/v1/patient/lab-reports/${reportId}/confirm`, {
      patient_confirmed: payload.patient_confirmed ?? true,
      ...payload,
    });
    return res.data;
  },

  async chat(message: string, consultationId?: string, contextType?: string, language: string = "en"): Promise<AskAIResponse> {
    const res = await apiClient.post<AskAIResponse>("/api/v1/patient/chat", {
      message,
      consultation_id: consultationId,
      context_type: contextType,
      language,
    });
    const data: any = res.data;
    return {
      answer: data.reply || data.answer || "Clinical response received.",
      disclaimer: data.disclaimer,
      safety_disclaimer: data.disclaimer,
      ...data,
    };
  },

  async getChatHistory(sessionId?: string): Promise<{ messages: any[] }> {
    let url = "/api/v1/patient/chat/history";
    if (sessionId) url += `?session_id=${sessionId}`;
    const res = await apiClient.get<any>(url);
    return { messages: res.data?.messages || [] };
  },

  async transcribeVoice(audioBlob: Blob, language: string = "auto") {
    const formData = new FormData();
    const ext = audioBlob.type.includes("webm") ? "webm" : audioBlob.type.includes("ogg") ? "ogg" : "wav";
    formData.append("audio", audioBlob, `patient_recording.${ext}`);
    formData.append("language", language);

    const res = await apiClient.post("/api/v1/patient/voice-transcribe", formData, {
      headers: { "Content-Type": "multipart/form-data" },
    });
    return res.data;
  }
};
