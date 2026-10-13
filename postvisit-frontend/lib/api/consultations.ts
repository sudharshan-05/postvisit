import { apiClient } from "./axios";
import { ConsultationDetail, ConsultationQueueItem, DiarizedTurn } from "@/types";

export interface UploadConsultationResponse {
  consultation_id: string;
  status: string;
  workflow_job_id?: string;
  filename?: string;
}

export interface ProgressStep {
  name: string;
  status: "pending" | "in_progress" | "completed" | "failed" | "not_configured";
  elapsed_seconds?: number;
}

export interface WorkflowProgressResponse {
  consultation_id: string;
  status: string;
  current_stage?: string;
  steps: ProgressStep[];
  is_completed: boolean;
}

export const consultationsApi = {
  async upload(file: File | Blob, sync: boolean = false, filenameOverride?: string): Promise<UploadConsultationResponse> {
    const formData = new FormData();
    const finalName = filenameOverride || (file instanceof File ? file.name : "encounter_audio.wav");
    formData.append("file", file, finalName);

    const res = await apiClient.post<UploadConsultationResponse>(
      `/api/v1/consultations/process?sync=${sync}`,
      formData,
      {
        headers: { "Content-Type": "multipart/form-data" },
      }
    );
    return res.data;
  },

  async getById(id: string): Promise<ConsultationDetail> {
    const res = await apiClient.get<any>(`/api/v1/consultations/${id}`);
    const raw = res.data;

    // Normalize transcript turns into DiarizedTurn[]
    let diarized: DiarizedTurn[] = [];
    if (Array.isArray(raw.transcript)) {
      diarized = raw.transcript.map((t: any) => ({
        speaker: t.speaker || (t.speaker_role === "doctor" ? "Doctor" : "Speaker"),
        speaker_role: t.speaker_role || (t.speaker?.toLowerCase().includes("doc") ? "doctor" : "patient"),
        start: t.start ?? t.start_time ?? 0,
        end: t.end ?? t.end_time ?? 0,
        start_time: t.start ?? t.start_time ?? 0,
        end_time: t.end ?? t.end_time ?? 0,
        text: t.text || "",
        translated_text: t.translated_text || t.translation || t.text || "",
      }));
    } else if (typeof raw.transcript === "string" && raw.transcript.trim().startsWith("[")) {
      try {
        const parsed = JSON.parse(raw.transcript);
        if (Array.isArray(parsed)) {
          diarized = parsed.map((t: any) => ({
            speaker: t.speaker || "Speaker",
            speaker_role: t.speaker?.toLowerCase().includes("doc") ? "doctor" : "patient",
            start: t.start ?? 0,
            end: t.end ?? 0,
            start_time: t.start ?? 0,
            end_time: t.end ?? 0,
            text: t.text || "",
            translated_text: t.translated_text || t.text || "",
          }));
        }
      } catch {
        // Fall back to raw string
      }
    }

    const medRecord = raw.medical_record || raw.medical_data || {};
    const patientObj = medRecord.patient || {};
    const cid = raw.consultation_id || raw.id || id;

    return {
      id: cid,
      consultation_id: cid,
      patient_id: patientObj.patient_id || raw.patient_id || "PT-89241",
      patient_name: patientObj.name || raw.patient_name || "Ananya Patel",
      patient_age: patientObj.age || raw.patient_age,
      patient_gender: patientObj.gender || raw.patient_gender,
      status: raw.status || "processing",
      active_step: raw.current_step || raw.active_step,
      current_step: raw.current_step || raw.active_step,
      doctor_reviewed: !raw.requires_doctor_review,
      requires_doctor_review: raw.requires_doctor_review,
      input: raw.input,
      audio_metadata: {
        duration: raw.input?.duration_seconds,
        original_filename: raw.input?.filename,
      },
      media_storage_path: raw.media_storage_path,
      created_at: raw.created_at || new Date().toISOString(),
      updated_at: raw.updated_at,
      medical_record: medRecord,
      medical_data: medRecord,
      diarized_transcript: diarized,
      transcript: raw.transcript,
      validation: raw.validation,
      error: raw.error,
    };
  },

  async getProgress(id: string): Promise<WorkflowProgressResponse> {
    const res = await apiClient.get<WorkflowProgressResponse>(`/api/v1/consultations/${id}/progress`);
    return res.data;
  },

  async list(limit = 50, offset = 0): Promise<{ consultations: ConsultationQueueItem[]; total: number }> {
    const res = await apiClient.get<any>(`/api/v1/consultations?limit=${limit}&offset=${offset}`);
    const items = res.data?.items || res.data?.consultations || [];
    return {
      consultations: items.map((i: any) => ({
        ...i,
        id: i.consultation_id || i.id,
        consultation_id: i.consultation_id || i.id,
      })),
      total: res.data?.total || items.length,
    };
  },

  async review(
    consultationId: string,
    payload: {
      doctor_name: string;
      decision: "approved" | "rejected" | "amended";
      notes?: string;
      corrected_medical_record?: any;
    }
  ) {
    const res = await apiClient.post(`/api/v1/consultations/${consultationId}/review`, payload);
    return res.data;
  }
};
