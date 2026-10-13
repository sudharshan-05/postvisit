import { apiClient } from "./axios";
import { GuidelineFinding } from "@/types";

export interface GuidelineSearchResult {
  id: string;
  source: string;
  organization: string;
  condition: string;
  title: string;
  recommendations?: string[];
  evidence_level?: string;
  publication_year?: number;
}

export const guidelinesApi = {
  async search(query: string = ""): Promise<{ results: GuidelineSearchResult[]; count: number }> {
    const res = await apiClient.get(`/api/v1/guidelines/search?q=${encodeURIComponent(query)}`);
    return res.data;
  },

  async getById(id: string): Promise<GuidelineSearchResult> {
    const res = await apiClient.get(`/api/v1/guidelines/${id}`);
    return res.data;
  },

  async getFindingsForConsultation(consultationId: string): Promise<{ findings: GuidelineFinding[] }> {
    const res = await apiClient.get(`/api/v1/consultations/${consultationId}/guidelines`);
    return res.data;
  },

  async triggerCrossReference(consultationId: string) {
    const res = await apiClient.post(`/api/v1/consultations/${consultationId}/cross-reference`);
    return res.data;
  }
};
