/**
 * PostVisit AI - API Client
 * Manages communication with FastAPI backend endpoints, role headers, and error handling.
 */

class PostVisitAPI {
  constructor() {
    this.baseUrl = window.location.origin;
    this.role = localStorage.getItem("postvisit_role") || "doctor"; // 'doctor' or 'patient'
    this.userId = localStorage.getItem("postvisit_user_id") || "Dr. A. Ramanathan";
  }

  setRole(role, userId) {
    this.role = role;
    this.userId = userId || (role === "doctor" ? "Dr. A. Ramanathan" : "patient_101");
    localStorage.setItem("postvisit_role", this.role);
    localStorage.setItem("postvisit_user_id", this.userId);
  }

  getHeaders(extraHeaders = {}) {
    return {
      "X-User-Role": this.role,
      "X-User-Id": this.userId,
      ...extraHeaders
    };
  }

  async handleResponse(res) {
    if (!res.ok) {
      let errDetail = "Request failed";
      try {
        const data = await res.json();
        errDetail = data?.error?.message || data?.detail || JSON.stringify(data);
      } catch (e) {
        errDetail = await res.text();
      }
      const error = new Error(errDetail);
      error.status = res.status;
      throw error;
    }
    return res.json();
  }

  // Consultations
  async listConsultations(limit = 50, offset = 0) {
    const res = await fetch(`${this.baseUrl}/api/v1/consultations?limit=${limit}&offset=${offset}`, {
      headers: this.getHeaders()
    });
    return this.handleResponse(res);
  }

  async getConsultation(id) {
    const res = await fetch(`${this.baseUrl}/api/v1/consultations/${id}`, {
      headers: this.getHeaders()
    });
    return this.handleResponse(res);
  }

  async getProgress(id) {
    const res = await fetch(`${this.baseUrl}/api/v1/consultations/${id}/progress`, {
      headers: this.getHeaders()
    });
    return this.handleResponse(res);
  }

  async uploadConsultation(file) {
    const formData = new FormData();
    formData.append("file", file);

    const res = await fetch(`${this.baseUrl}/api/v1/consultations/process`, {
      method: "POST",
      headers: {
        "X-User-Role": this.role,
        "X-User-Id": this.userId
      },
      body: formData
    });
    return this.handleResponse(res);
  }

  async submitDoctorReview(consultationId, doctorName, decision = "approved", notes = "", correctedRecord = null) {
    const payload = {
      doctor_name: doctorName || this.userId,
      decision: decision,
      notes: notes,
      corrected_medical_record: correctedRecord
    };

    const res = await fetch(`${this.baseUrl}/api/v1/consultations/${consultationId}/review`, {
      method: "POST",
      headers: this.getHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify(payload)
    });
    return this.handleResponse(res);
  }

  // Patient Summaries
  async listSummaries(consultationId, language = null) {
    let url = `${this.baseUrl}/api/v1/consultations/${consultationId}/summaries`;
    if (language) url += `?language=${language}`;

    const res = await fetch(url, {
      headers: this.getHeaders()
    });
    return this.handleResponse(res);
  }

  async getSummary(summaryId) {
    const res = await fetch(`${this.baseUrl}/api/v1/summaries/${summaryId}`, {
      headers: this.getHeaders()
    });
    return this.handleResponse(res);
  }

  async generateSummary(consultationId, targetLanguage = "en", idempotencyKey = null) {
    const payload = {
      target_language: targetLanguage,
      idempotency_key: idempotencyKey
    };

    const res = await fetch(`${this.baseUrl}/api/v1/consultations/${consultationId}/summaries`, {
      method: "POST",
      headers: this.getHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify(payload)
    });
    return this.handleResponse(res);
  }

  async reviewSummary(summaryId, doctorName, decision, notes = "", correctedSummary = null) {
    const payload = {
      doctor_name: doctorName || this.userId,
      decision: decision,
      notes: notes,
      corrected_summary: correctedSummary
    };

    const res = await fetch(`${this.baseUrl}/api/v1/summaries/${summaryId}/review`, {
      method: "POST",
      headers: this.getHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify(payload)
    });
    return this.handleResponse(res);
  }

  async getSummaryHistory(summaryId) {
    const res = await fetch(`${this.baseUrl}/api/v1/summaries/${summaryId}/history`, {
      headers: this.getHeaders()
    });
    return this.handleResponse(res);
  }

  // Clinical Guidelines
  async getGuidelines(consultationId) {
    const res = await fetch(`${this.baseUrl}/api/v1/consultations/${consultationId}/guidelines`, {
      headers: this.getHeaders()
    });
    return this.handleResponse(res);
  }

  async triggerGuidelineCrossReference(consultationId) {
    const res = await fetch(`${this.baseUrl}/api/v1/consultations/${consultationId}/guidelines/cross-reference`, {
      method: "POST",
      headers: this.getHeaders()
    });
    return this.handleResponse(res);
  }

  async reviewGuidelineFinding(consultationId, findingId, doctorName, decision = "acknowledged", notes = "") {
    const payload = {
      doctor_name: doctorName || this.userId,
      finding_id: findingId,
      decision: decision,
      notes: notes
    };

    const res = await fetch(`${this.baseUrl}/api/v1/consultations/${consultationId}/guidelines/review`, {
      method: "POST",
      headers: this.getHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify(payload)
    });
    return this.handleResponse(res);
  }

  async listGuidelineSources() {
    const res = await fetch(`${this.baseUrl}/api/v1/guidelines/sources`);
    return this.handleResponse(res);
  }

  // =========================================================================
  // Patient Portal Endpoints (Stage 5A)
  // =========================================================================
  async getPatientProfile(patientId = null) {
    let url = `${this.baseUrl}/api/v1/patient/profile`;
    if (patientId) url += `?patient_id=${patientId}`;
    const res = await fetch(url, { headers: this.getHeaders() });
    return this.handleResponse(res);
  }

  async getPatientOverview(patientId = null) {
    let url = `${this.baseUrl}/api/v1/patient/overview`;
    if (patientId) url += `?patient_id=${patientId}`;
    const res = await fetch(url, { headers: this.getHeaders() });
    return this.handleResponse(res);
  }

  async getLastVisitSummary(consultationId = null, patientId = null) {
    let url = `${this.baseUrl}/api/v1/patient/last-visit`;
    const params = [];
    if (consultationId) params.push(`consultation_id=${consultationId}`);
    if (patientId) params.push(`patient_id=${patientId}`);
    if (params.length) url += `?${params.join("&")}`;
    const res = await fetch(url, { headers: this.getHeaders() });
    return this.handleResponse(res);
  }

  async getVisitHistory(page = 1, pageSize = 10, statusFilter = null, patientId = null) {
    let url = `${this.baseUrl}/api/v1/patient/history?page=${page}&page_size=${pageSize}`;
    if (statusFilter) url += `&status_filter=${statusFilter}`;
    if (patientId) url += `&patient_id=${patientId}`;
    const res = await fetch(url, { headers: this.getHeaders() });
    return this.handleResponse(res);
  }

  async getRecoveryPlan(consultationId = null, patientId = null) {
    let url = `${this.baseUrl}/api/v1/patient/recovery-plan`;
    const params = [];
    if (consultationId) params.push(`consultation_id=${consultationId}`);
    if (patientId) params.push(`patient_id=${patientId}`);
    if (params.length) url += `?${params.join("&")}`;
    const res = await fetch(url, { headers: this.getHeaders() });
    return this.handleResponse(res);
  }

  async toggleRecoveryTask(consultationId, taskKey, completed, notes = null) {
    const res = await fetch(`${this.baseUrl}/api/v1/patient/recovery-plan/toggle`, {
      method: "POST",
      headers: this.getHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({
        consultation_id: consultationId,
        task_key: taskKey,
        completed: completed,
        notes: notes
      })
    });
    return this.handleResponse(res);
  }

  async getPatientMedications(consultationId = null, patientId = null) {
    let url = `${this.baseUrl}/api/v1/patient/medications`;
    const params = [];
    if (consultationId) params.push(`consultation_id=${consultationId}`);
    if (patientId) params.push(`patient_id=${patientId}`);
    if (params.length) url += `?${params.join("&")}`;
    const res = await fetch(url, { headers: this.getHeaders() });
    return this.handleResponse(res);
  }

  async listPatientLabReports(consultationId = null, patientId = null) {
    let url = `${this.baseUrl}/api/v1/patient/lab-reports`;
    const params = [];
    if (consultationId) params.push(`consultation_id=${consultationId}`);
    if (patientId) params.push(`patient_id=${patientId}`);
    if (params.length) url += `?${params.join("&")}`;
    const res = await fetch(url, { headers: this.getHeaders() });
    return this.handleResponse(res);
  }

  async createManualLabReport(payload) {
    const res = await fetch(`${this.baseUrl}/api/v1/patient/lab-reports/manual`, {
      method: "POST",
      headers: this.getHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify(payload)
    });
    return this.handleResponse(res);
  }

  async uploadPatientLabReport(formData) {
    const res = await fetch(`${this.baseUrl}/api/v1/patient/lab-reports/upload`, {
      method: "POST",
      headers: {
        "X-User-Role": this.role,
        "X-User-Id": this.userId
      },
      body: formData
    });
    return this.handleResponse(res);
  }

  async patientChat(message, consultationId = null, contextType = null, sessionId = null, language = "en") {
    const res = await fetch(`${this.baseUrl}/api/v1/patient/chat`, {
      method: "POST",
      headers: this.getHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({
        message: message,
        consultation_id: consultationId,
        context_type: contextType,
        session_id: sessionId,
        language: language
      })
    });
    return this.handleResponse(res);
  }

  async getPatientChatHistory(sessionId = null) {
    let url = `${this.baseUrl}/api/v1/patient/chat/history`;
    if (sessionId) url += `?session_id=${sessionId}`;
    const res = await fetch(url, { headers: this.getHeaders() });
    return this.handleResponse(res);
  }

  async transcribePatientVoice(audioBlob, language = "auto") {
    const formData = new FormData();
    formData.append("audio", audioBlob, "patient_recording.webm");
    formData.append("language", language);

    const res = await fetch(`${this.baseUrl}/api/v1/patient/voice-transcribe`, {
      method: "POST",
      headers: {
        "X-User-Role": this.role,
        "X-User-Id": this.userId
      },
      body: formData
    });
    return this.handleResponse(res);
  }

  // =========================================================================
  // DOCTOR SIDE APIS (Stage 5B)
  // =========================================================================
  async listDoctorConsultations(filterType = "all", startDate = null, endDate = null, patientId = null, page = 1, pageSize = 20) {
    let url = `${this.baseUrl}/api/v1/doctor/consultations?filter_type=${filterType}&page=${page}&page_size=${pageSize}`;
    if (startDate) url += `&start_date=${startDate}`;
    if (endDate) url += `&end_date=${endDate}`;
    if (patientId) url += `&patient_id=${patientId}`;
    const res = await fetch(url, { headers: this.getHeaders() });
    return this.handleResponse(res);
  }

  async getDoctorPatientOverview(patientId, consultationId = null) {
    let url = `${this.baseUrl}/api/v1/doctor/patient/${patientId}/overview`;
    if (consultationId) url += `?consultation_id=${consultationId}`;
    const res = await fetch(url, { headers: this.getHeaders() });
    return this.handleResponse(res);
  }

  async getDoctorQuickSummary(consultationId) {
    const res = await fetch(`${this.baseUrl}/api/v1/doctor/consultations/${consultationId}/quick-summary`, {
      headers: this.getHeaders()
    });
    return this.handleResponse(res);
  }

  async listDoctorLabReports(patientId = null, consultationId = null) {
    let url = `${this.baseUrl}/api/v1/doctor/lab-reports`;
    const params = [];
    if (patientId) params.push(`patient_id=${patientId}`);
    if (consultationId) params.push(`consultation_id=${consultationId}`);
    if (params.length) url += `?${params.join("&")}`;
    const res = await fetch(url, { headers: this.getHeaders() });
    return this.handleResponse(res);
  }

  async reviewDoctorLabReport(reportId, decision, verifiedValue = null, verifiedUnit = null, doctorNotes = null, clarificationRequest = null) {
    const res = await fetch(`${this.baseUrl}/api/v1/doctor/lab-reports/${reportId}/review`, {
      method: "POST",
      headers: this.getHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({
        decision: decision,
        verified_value: verifiedValue,
        verified_unit: verifiedUnit,
        doctor_notes: doctorNotes,
        clarification_request: clarificationRequest
      })
    });
    return this.handleResponse(res);
  }

  async getDoctorGuidelines(consultationId) {
    const res = await fetch(`${this.baseUrl}/api/v1/doctor/consultations/${consultationId}/guidelines`, {
      headers: this.getHeaders()
    });
    return this.handleResponse(res);
  }

  async reviewDoctorGuidelineFinding(consultationId, findingId, decision, doctorNotes = null) {
    const res = await fetch(`${this.baseUrl}/api/v1/doctor/consultations/${consultationId}/guidelines/${findingId}/review`, {
      method: "POST",
      headers: this.getHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({
        decision: decision,
        doctor_notes: doctorNotes
      })
    });
    return this.handleResponse(res);
  }

  async askDoctorAI(consultationId, query, contextType = "visit") {
    const res = await fetch(`${this.baseUrl}/api/v1/doctor/consultations/${consultationId}/ask`, {
      method: "POST",
      headers: this.getHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({
        consultation_id: consultationId,
        query: query,
        context_type: contextType
      })
    });
    return this.handleResponse(res);
  }

  async transcribeDoctorVoiceNote(consultationId, mockTranscript = null) {
    let url = `${this.baseUrl}/api/v1/doctor/consultations/${consultationId}/voice-note/transcribe`;
    if (mockTranscript) url += `?mock_transcript=${encodeURIComponent(mockTranscript)}`;
    const res = await fetch(url, {
      method: "POST",
      headers: this.getHeaders()
    });
    return this.handleResponse(res);
  }

  async confirmDoctorVoiceNote(consultationId, draftId, finalNoteText, category = "clinical_observation") {
    const res = await fetch(`${this.baseUrl}/api/v1/doctor/consultations/${consultationId}/voice-note/confirm`, {
      method: "POST",
      headers: this.getHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({
        draft_id: draftId,
        consultation_id: consultationId,
        final_note_text: finalNoteText,
        category: category,
        is_confirmed: true
      })
    });
    return this.handleResponse(res);
  }

  async getDoctorTimeline(consultationId) {
    const res = await fetch(`${this.baseUrl}/api/v1/doctor/consultations/${consultationId}/timeline`, {
      headers: this.getHeaders()
    });
    return this.handleResponse(res);
  }

  async getDoctorAuditTrail(consultationId) {
    const res = await fetch(`${this.baseUrl}/api/v1/doctor/consultations/${consultationId}/audit-trail`, {
      headers: this.getHeaders()
    });
    return this.handleResponse(res);
  }
}

window.api = new PostVisitAPI();
