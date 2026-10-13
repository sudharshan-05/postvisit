import { apiClient } from "./axios";
import {
  ConsultationQueueItem,
  LabReportItem,
  GuidelineFinding,
  AskAIResponse,
  PatientClinicalOverview,
} from "@/types";

export interface DoctorConsultationFilters {
  filter_type?: string;
  start_date?: string;
  end_date?: string;
  patient_id?: string;
  page?: number;
  page_size?: number;
}

export interface DoctorQueueResponse {
  consultations: ConsultationQueueItem[];
  items?: ConsultationQueueItem[];
  total: number;
  page: number;
  page_size: number;
  pending_review_count?: number;
  needs_attention_count?: number;
  completed_count?: number;
  processing_count?: number;
}

export const doctorApi = {
  async listConsultations(filters: DoctorConsultationFilters = {}): Promise<DoctorQueueResponse> {
    const params = new URLSearchParams();
    if (filters.filter_type) params.append("filter_type", filters.filter_type);
    if (filters.start_date) params.append("start_date", filters.start_date);
    if (filters.end_date) params.append("end_date", filters.end_date);
    if (filters.patient_id) params.append("patient_id", filters.patient_id);
    if (filters.page) params.append("page", filters.page.toString());
    if (filters.page_size) params.append("page_size", filters.page_size.toString());

    const res = await apiClient.get<any>(`/api/v1/doctor/consultations?${params.toString()}`);
    const rawItems = res.data?.items || res.data?.consultations || [];
    const normalizedConsultations: ConsultationQueueItem[] = rawItems.map((c: any) => ({
      ...c,
      id: c.consultation_id || c.id,
      consultation_id: c.consultation_id || c.id,
      created_at: c.last_updated_at || c.created_at || c.consultation_date,
    }));

    return {
      consultations: normalizedConsultations,
      items: normalizedConsultations,
      total: res.data?.total || normalizedConsultations.length,
      page: filters.page || 1,
      page_size: filters.page_size || 20,
      pending_review_count: res.data?.pending_review_count,
      needs_attention_count: res.data?.needs_attention_count,
      completed_count: res.data?.completed_count,
      processing_count: res.data?.processing_count,
    };
  },

  async getPatientClinicalOverview(patientId: string, consultationId?: string): Promise<PatientClinicalOverview> {
    let url = `/api/v1/doctor/patient/${patientId}/overview`;
    if (consultationId) url += `?consultation_id=${consultationId}`;
    const res = await apiClient.get<PatientClinicalOverview>(url);
    return res.data;
  },

  async getQuickSummary(consultationId: string) {
    const res = await apiClient.get(`/api/v1/doctor/consultations/${consultationId}/quick-summary`);
    return res.data;
  },

  async listLabReports(patientId?: string, consultationId?: string): Promise<{ lab_reports: LabReportItem[]; total: number }> {
    const params = new URLSearchParams();
    if (patientId) params.append("patient_id", patientId);
    if (consultationId) params.append("consultation_id", consultationId);
    const res = await apiClient.get<any>(`/api/v1/doctor/lab-reports?${params.toString()}`);
    const reports = res.data?.lab_reports || [];
    return {
      lab_reports: reports.map((r: any) => ({
        ...r,
        test_name: r.test_name || r.report_name || "Diagnostic Test",
        test_value: r.verified_value || r.test_value || r.patient_value,
        unit: r.verified_unit || r.unit || r.patient_unit,
        report_date: r.report_date || r.test_date,
      })),
      total: res.data?.total || reports.length,
    };
  },

  async reviewLabReport(
    reportId: string,
    payload: {
      decision: "verified" | "rejected" | "clarification_needed";
      verified_value?: string;
      verified_unit?: string;
      doctor_notes?: string;
      clarification_request?: string;
    }
  ) {
    const res = await apiClient.post(`/api/v1/doctor/lab-reports/${reportId}/review`, payload);
    return res.data;
  },

  async getGuidelines(consultationId: string): Promise<{ findings: GuidelineFinding[]; status: string; total: number }> {
    const res = await apiClient.get<any>(`/api/v1/doctor/consultations/${consultationId}/guidelines`);
    const findings = res.data?.findings || [];
    return {
      findings,
      status: res.data?.status || (findings.length > 0 ? "completed" : "not_configured"),
      total: res.data?.total || findings.length,
    };
  },

  async reviewGuidelineFinding(
    consultationId: string,
    findingId: string,
    payload: {
      decision: "relevant" | "not_relevant" | "review_later" | "add_note";
      doctor_notes?: string;
    }
  ) {
    const res = await apiClient.post(
      `/api/v1/doctor/consultations/${consultationId}/guidelines/${findingId}/review`,
      payload
    );
    return res.data;
  },

  async askAI(consultationId: string, query: string, contextType: string = "visit"): Promise<AskAIResponse> {
    const typeMap: Record<string, string> = {
      guidelines: "guideline",
      guideline: "guideline",
      summary: "visit",
      source: "visit",
      medication: "medication",
      lab_report: "lab_report",
      previous_visits: "previous_visits",
      visit: "visit",
      all: "visit",
    };
    const mappedType = typeMap[contextType] || "visit";

    const res = await apiClient.post<any>(`/api/v1/doctor/consultations/${consultationId}/ask`, {
      consultation_id: consultationId,
      query,
      context_type: mappedType,
    });
    return {
      answer: res.data.ai_summary || res.data.source_data || res.data.ai_interpretation || "Clinical response provided.",
      guideline_evidence: res.data.guideline_evidence,
      ai_interpretation: res.data.ai_interpretation,
      source_data: res.data.source_data,
      disclaimer: res.data.disclaimer,
      ...res.data,
    };
  },



  async transcribeVoiceNote(consultationId: string, audioBlob?: Blob) {
    if (audioBlob) {
      const formData = new FormData();
      const ext = audioBlob.type.includes("webm") ? "webm" : audioBlob.type.includes("ogg") ? "ogg" : "wav";
      formData.append("file", audioBlob, `voice_note.${ext}`);
      const res = await apiClient.post(`/api/v1/doctor/voice-note?consultation_id=${consultationId}`, formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      return {
        draft_id: res.data.draft_id,
        draft_transcript: res.data.transcript_text,
        ...res.data,
      };
    }
    const res = await apiClient.post(`/api/v1/doctor/consultations/${consultationId}/voice-note/transcribe`);
    return {
      draft_id: res.data.draft_id,
      draft_transcript: res.data.transcript_text,
      ...res.data,
    };
  },

  async confirmVoiceNote(
    consultationId: string,
    payload: {
      draft_id: string;
      final_note_text: string;
      category?: string;
    }
  ) {
    const res = await apiClient.post(`/api/v1/doctor/consultations/${consultationId}/voice-note/confirm`, {
      ...payload,
      consultation_id: consultationId,
      is_confirmed: true,
    });
    return res.data;
  },

  async getTimeline(consultationId: string) {
    const res = await apiClient.get(`/api/v1/doctor/consultations/${consultationId}/timeline`);
    return res.data;
  },

  async getAuditTrail(consultationId: string) {
    const res = await apiClient.get(`/api/v1/doctor/consultations/${consultationId}/audit-trail`);
    return res.data;
  },

  async updateTranscript(
    consultationId: string,
    payload: {
      transcript?: string;
      diarized_transcript?: any[];
      is_confirmed?: boolean;
    }
  ) {
    const res = await apiClient.put(`/api/v1/doctor/consultations/${consultationId}/transcript`, payload);
    return res.data;
  },

  async updateVitals(
    consultationId: string,
    payload: {
      height?: string | number;
      height_cm?: number;
      weight?: string | number;
      weight_kg?: number;
      blood_pressure?: string;
      pulse?: string | number;
      temperature?: string | number;
      temperature_f?: number;
      oxygen_saturation?: string | number;
      spo2?: number;
      fasting_glucose?: string | number;
      measured_at?: string;
      measurement_source?: string;
    }
  ) {
    const body: Record<string, any> = {
      height: payload.height !== undefined ? String(payload.height) : (payload.height_cm !== undefined ? `${payload.height_cm} cm` : undefined),
      weight: payload.weight !== undefined ? String(payload.weight) : (payload.weight_kg !== undefined ? `${payload.weight_kg} kg` : undefined),
      blood_pressure: payload.blood_pressure,
      pulse: payload.pulse !== undefined ? String(payload.pulse) : undefined,
      temperature: payload.temperature !== undefined ? String(payload.temperature) : (payload.temperature_f !== undefined ? `${payload.temperature_f}°F` : undefined),
      oxygen_saturation: payload.oxygen_saturation !== undefined ? String(payload.oxygen_saturation) : (payload.spo2 !== undefined ? `${payload.spo2}%` : undefined),
      fasting_glucose: payload.fasting_glucose !== undefined ? String(payload.fasting_glucose) : undefined,
      measured_at: payload.measured_at,
      measurement_source: payload.measurement_source,
    };
    const res = await apiClient.put(`/api/v1/doctor/consultations/${consultationId}/vitals`, body);
    return res.data;
  }
};
