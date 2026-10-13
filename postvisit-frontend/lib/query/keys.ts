export const queryKeys = {
  authMe: ["auth", "me"] as const,
  doctorQueue: (filters?: Record<string, any>) => ["doctor", "queue", filters] as const,
  doctorOverview: (patientId: string, consultationId?: string) =>
    ["doctor", "patient", patientId, consultationId] as const,
  doctorQuickSummary: (consultationId: string) =>
    ["doctor", "quickSummary", consultationId] as const,
  doctorLabReports: (patientId?: string, consultationId?: string) =>
    ["doctor", "labReports", patientId, consultationId] as const,
  doctorGuidelines: (consultationId: string) =>
    ["doctor", "guidelines", consultationId] as const,
  doctorTimeline: (consultationId: string) =>
    ["doctor", "timeline", consultationId] as const,
  doctorAuditTrail: (consultationId: string) =>
    ["doctor", "auditTrail", consultationId] as const,
  patientOverview: (patientId?: string) =>
    ["patient", "overview", patientId] as const,
  patientLastVisit: (consultationId?: string, patientId?: string) =>
    ["patient", "lastVisit", consultationId, patientId] as const,
  patientHistory: (page: number = 1, pageSize: number = 20, filter?: string) =>
    ["patient", "history", page, pageSize, filter] as const,
  patientMedications: (consultationId?: string) =>
    ["patient", "medications", consultationId] as const,
  patientRecoveryPlan: (consultationId?: string) =>
    ["patient", "recoveryPlan", consultationId] as const,
  patientLabReports: (consultationId?: string) =>
    ["patient", "labReports", consultationId] as const,
  consultationDetail: (id: string) =>
    ["consultation", "detail", id] as const,
  consultationProgress: (id: string) =>
    ["consultation", "progress", id] as const,
  summaryDetail: (id: string) =>
    ["summary", "detail", id] as const,
  guidelinesSearch: (query: string) =>
    ["guidelines", "search", query] as const,
  patientProfile: (patientId?: string) =>
    ["patient", "profile", patientId] as const,
  patientChatHistory: (sessionId?: string) =>
    ["patient", "chatHistory", sessionId] as const,
};
