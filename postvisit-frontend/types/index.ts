// TypeScript Domain Types for PostVisit AI Frontend

export type UserRole = "doctor" | "patient" | "admin";

export interface UserProfile {
  user_id: string;
  name: string;
  role: UserRole;
  patient_id?: string;
  permissions: string[];
  is_test_identity?: boolean;
}

export type ConsultationStatus =
  | "queued"
  | "processing"
  | "pending_doctor_review"
  | "awaiting_review"
  | "completed"
  | "approved"
  | "rejected"
  | "failed"
  | "NEEDS REVIEW"
  | "PENDING REVIEW"
  | "APPROVED"
  | "REJECTED"
  | "FAILED"
  | "PROCESSING";

export interface MedicationItem {
  medicine_name?: string;
  name?: string;
  dose?: string;
  strength?: string;
  frequency?: string;
  timing?: string;
  duration?: string;
  route?: string;
  instructions?: string;
  notes?: string;
  approval_status?: string;
  review_status?: string;
  source_speaker?: string;
}

export interface VitalSigns {
  blood_pressure?: string;
  systolic_bp?: number;
  diastolic_bp?: number;
  pulse?: number;
  fasting_glucose?: number;
  weight_kg?: number;
  height_cm?: number;
  temperature?: string;
  spo2?: string;
}

export interface MedicalRecordData {
  patient?: {
    name?: string;
    patient_id?: string;
    age?: number;
    gender?: string;
    blood_group?: string;
  };
  symptoms?: string[];
  symptoms_mentioned?: string[];
  hpi?: string;
  examination_findings?: string[];
  vital_signs?: VitalSigns;
  medications?: MedicationItem[];
  investigations?: Array<string | { name: string; timing?: string; instructions?: string }>;
  tests?: Array<string | { name: string; timing?: string; instructions?: string }>;
  tests_recommended?: string[];
  recommendations?: string[];
  doctor_recommendations?: string[];
  instructions?: string[];
  follow_up?: any;
  follow_up_instructions?: string;
  warnings?: string[];
  red_flags?: string[];
  uncertain_items?: string[];
  requires_doctor_review?: boolean;
}

export interface DiarizedTurn {
  speaker: string;
  speaker_role?: "doctor" | "patient" | "speaker";
  start?: number;
  end?: number;
  start_time?: number;
  end_time?: number;
  text: string;
  translated_text?: string;
}

export interface ConsultationDetail {
  id?: string;
  consultation_id: string;
  patient_id?: string;
  patient_name?: string;
  patient_age?: number;
  patient_gender?: string;
  status: ConsultationStatus;
  active_step?: string;
  current_step?: string;
  doctor_reviewed?: boolean;
  requires_doctor_review?: boolean;
  input?: {
    filename?: string;
    media_type?: string;
    duration_seconds?: number;
  };
  audio_metadata?: {
    duration?: number;
    channels?: number;
    original_filename?: string;
  };
  media_storage_path?: string;
  created_at: string;
  updated_at?: string;
  medical_record?: MedicalRecordData;
  medical_data?: MedicalRecordData;
  diarized_transcript?: DiarizedTurn[];
  transcript?: DiarizedTurn[] | string;
  validation?: {
    status: string;
    errors: string[];
    warnings: string[];
  };
  error?: {
    code: string;
    message: string;
  };
}

export interface ConsultationQueueItem {
  id?: string;
  consultation_id: string;
  patient_id: string;
  patient_name?: string;
  consultation_date?: string;
  created_at?: string;
  status: string;
  processing_stage?: string;
  summary_status?: string;
  guideline_status?: string;
  lab_report_status?: string;
  last_updated_at?: string;
  assigned_doctor?: string;
  chief_complaint?: string;
  language?: string;
  duration_seconds?: number;
  needs_attention?: boolean;
}

export interface PatientSummaryContent {
  patient_name?: string;
  visit_date?: string;
  doctor_name?: string;
  reason_for_visit?: string;
  diagnosis_summary?: string;
  symptoms_explained?: string[];
  findings?: string;
  medications_list?: Array<{
    name: string;
    dosage?: string;
    instructions?: string;
    timing?: string;
  }>;
  tests_explained?: string[];
  doctor_instructions?: string[];
  lifestyle_guidance?: string[];
  precautions?: string[];
  follow_up?: string;
  emergency_contacts?: string;
}

export interface PatientSummary {
  id: string;
  consultation_id: string;
  patient_id: string;
  language: string;
  doctor_reviewed: boolean;
  status?: string;
  review_decision?: "approved" | "rejected" | "amended" | "pending";
  review_notes?: string;
  doctor_name?: string;
  version: number;
  guardrail_status?: "passed" | "needs_review" | "failed";
  summary_content: PatientSummaryContent;
  created_at: string;
  updated_at?: string;
}

export type LabReportStatus =
  | "submitted"
  | "processing"
  | "awaiting_doctor_review"
  | "pending"
  | "clarification_needed"
  | "verified"
  | "reviewed"
  | "rejected"
  | "REPORT_REVIEWED"
  | "REPORT_PENDING_REVIEW";

export interface LabReportItem {
  id: string;
  patient_id: string;
  consultation_id?: string;
  report_name?: string;
  test_name: string;
  test_value?: string;
  test_result?: string;
  unit?: string;
  reference_range?: string;
  status?: LabReportStatus;
  review_status?: string;
  source_type?: "patient_uploaded" | "patient_manual" | "hospital_lab";
  entry_mode?: string;
  document_url?: string;
  file_url?: string;
  filename?: string;
  file_name?: string;
  report_date?: string;
  test_date?: string;
  facility_name?: string;
  patient_notes?: string;
  doctor_notes?: string;
  verified_value?: string;
  verified_unit?: string;
  clarification_request?: string;
  clinical_relevance_label?: string;
  is_ai_extracted?: boolean;
  created_at?: string;
}

export interface GuidelineFinding {
  id: string;
  consultation_id?: string;
  guideline_source: string;
  organization: string;
  edition_year?: string;
  condition: string;
  finding_title: string;
  evidence: string;
  section?: string;
  status?: "awaiting_doctor_review" | "reviewed";
  decision?: "relevant" | "not_relevant" | "review_later" | "add_note";
  doctor_notes?: string;
  created_at?: string;
}

export interface HealthTrendPoint {
  date: string;
  systolic_bp?: number;
  diastolic_bp?: number;
  fasting_glucose?: number;
  weight_kg?: number;
  pulse?: number;
}

export interface RecoveryPlanTask {
  task_key: string;
  title: string;
  description?: string;
  doctor_instruction?: string;
  category: "medication" | "diet" | "exercise" | "monitoring" | "followup" | "follow_up";
  completed?: boolean;
  is_completed?: boolean;
  patient_completed?: boolean;
  is_doctor_prescribed?: boolean;
  notes?: string;
}

export interface AskAIResponse {
  answer: string;
  source_data_used?: string[];
  ai_summary_used?: string;
  guideline_evidence?: string;
  ai_interpretation?: string;
  session_id?: string;
  safety_disclaimer?: string;
  grounded_sources?: string[];
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  createdAt: string;
  consultationId?: string;
  contextType?: string;
  data?: AskAIResponse;
  disclaimer?: string;
  isError?: boolean;
}

export interface PatientProfileResponse {
  patient_id: string;
  full_name: string;
  name?: string;
  age?: number;
  gender?: string;
  phone?: string;
  email?: string;
  preferred_language?: string;
  blood_group?: string;
  allergies: string[];
  chronic_conditions: string[];
  date_of_birth?: string;
  emergency_contact?: string;
  profile_completeness?: number;
  created_at?: string;
}

export interface PreviousVisitSummary {
  consultation_id: string;
  date: string;
  reason_for_visit?: string;
  reported_symptoms?: string[];
  doctor_recommendations?: string[];
  summary_approved?: boolean;
}

export interface PatientClinicalOverview {
  patient_id: string;
  name: string;
  age?: number;
  gender?: string;
  blood_group?: string;
  allergies: string[];
  chronic_conditions: string[];
  last_visit?: PreviousVisitSummary;
  visit_history: PreviousVisitSummary[];
  consultation_id?: string;
  consultation_date?: string;
  reported_symptoms: string[];
  history_of_present_illness?: string;
  clinical_findings: string[];
  vitals: Record<string, any>;
  medications: MedicationItem[];
  tests_ordered: string[];
  doctor_recommendations: string[];
  follow_up_instructions?: string;
  warnings_and_red_flags: string[];
  uncertainties: string[];
  lab_reports: LabReportItem[];
  guideline_findings: GuidelineFinding[];
  patient_summary?: PatientSummary;
  audit_history: Array<{
    id?: string;
    event_type?: string;
    action?: string;
    actor_id?: string;
    actor_role?: string;
    timestamp?: string;
    details?: any;
    action_description?: string;
  }>;
}
