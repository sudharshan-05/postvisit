import { apiClient } from "./axios";
import { PatientSummary } from "@/types";

export const summariesApi = {
  async getById(summaryId: string): Promise<PatientSummary> {
    const res = await apiClient.get<PatientSummary>(`/api/v1/summaries/${summaryId}`);
    return res.data;
  },

  async listForConsultation(consultationId: string, language?: string): Promise<{ summaries: PatientSummary[]; total: number }> {
    let url = `/api/v1/consultations/${consultationId}/summaries`;
    if (language) url += `?language=${language}`;
    const res = await apiClient.get(url);
    return res.data;
  },

  async generate(consultationId: string, targetLanguage: string = "en", idempotencyKey?: string) {
    const res = await apiClient.post(`/api/v1/consultations/${consultationId}/summaries`, {
      target_language: targetLanguage,
      idempotency_key: idempotencyKey,
    });
    return res.data;
  },

  async review(
    summaryId: string,
    payload: {
      doctor_name: string;
      decision: "approved" | "rejected" | "amended";
      notes?: string;
      corrected_summary?: any;
    }
  ) {
    const res = await apiClient.post(`/api/v1/summaries/${summaryId}/review`, payload);
    return res.data;
  },

  async getAuditHistory(summaryId: string) {
    const res = await apiClient.get(`/api/v1/summaries/${summaryId}/history`);
    return res.data;
  }
};
