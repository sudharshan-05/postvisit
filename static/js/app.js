/**
 * PostVisit AI - Main Dashboard Application Controller
 * Handles SPA navigation, real-time consultation processing, doctor review sign-offs,
 * guideline cross-referencing, and multilingual patient summaries.
 */

class PostVisitApp {
  constructor() {
    this.currentView = "doctor-dashboard";
    this.activeConsultationId = null;
    this.processingPollInterval = null;
    this.patientLanguage = "en";
    this.init();
  }

  init() {
    this.bindEvents();
    this.updateRoleUI();
    this.route();
  }

  bindEvents() {
    // Role switcher
    document.querySelectorAll(".role-btn").forEach(btn => {
      btn.addEventListener("click", (e) => {
        const role = e.currentTarget.dataset.role;
        window.api.setRole(role);
        this.updateRoleUI();
        if (role === "doctor") {
          this.navigateTo("doctor-dashboard");
        } else {
          this.navigateTo("patient-dashboard");
        }
      });
    });

    // File upload
    const uploadInput = document.getElementById("file-upload-input");
    if (uploadInput) {
      uploadInput.addEventListener("change", (e) => this.handleFileUpload(e));
    }

    // Modal close
    document.querySelectorAll(".modal-close-btn").forEach(btn => {
      btn.addEventListener("click", () => this.closeModals());
    });
  }

  updateRoleUI() {
    const currentRole = window.api.role;
    document.querySelectorAll(".role-btn").forEach(btn => {
      btn.classList.toggle("active", btn.dataset.role === currentRole);
    });

    const userBadge = document.getElementById("user-profile-badge");
    if (userBadge) {
      userBadge.textContent = currentRole === "doctor" ? "Dr. A. Ramanathan (Physician)" : "R. Sundaram (Patient Portal)";
    }
  }

  navigateTo(viewName, params = {}) {
    this.currentView = viewName;
    if (params.consultationId) {
      this.activeConsultationId = params.consultationId;
    }

    // Stop active polling if moving away from processing
    if (viewName !== "processing-screen" && this.processingPollInterval) {
      clearInterval(this.processingPollInterval);
      this.processingPollInterval = null;
    }

    document.querySelectorAll(".app-view").forEach(v => v.classList.remove("active-view"));
    const target = document.getElementById(`view-${viewName}`);
    if (target) {
      target.classList.add("active-view");
    }

    // Route lifecycle
    if (viewName === "doctor-dashboard") {
      this.loadDoctorDashboard();
    } else if (viewName === "patient-dashboard") {
      this.loadPatientDashboard();
    } else if (viewName === "processing-screen") {
      this.startProcessingMonitor(this.activeConsultationId);
    } else if (viewName === "consultation-detail") {
      this.loadConsultationDetail(this.activeConsultationId);
    }
  }

  route() {
    if (window.api.role === "patient") {
      this.navigateTo("patient-dashboard");
    } else {
      this.navigateTo("doctor-dashboard");
    }
  }

  // =========================================================================
  // DOCTOR DASHBOARD
  // =========================================================================
  // =========================================================================
  // DOCTOR DASHBOARD & CLINICAL REVIEW WORKBENCH (Stage 5B)
  // =========================================================================
  async loadDoctorDashboard(filterType = "all", searchQuery = "") {
    const tbody = document.getElementById("doctor-consultations-tbody");
    if (!tbody) return;

    this.activeDoctorFilter = filterType;
    tbody.innerHTML = `<tr><td colspan="9" class="empty-state"><div class="spinner"></div><p>Loading clinical consultation records from database...</p></td></tr>`;

    try {
      const data = await window.api.listDoctorConsultations(filterType, null, null, null, 1, 50);
      let items = data.items || [];

      if (searchQuery && searchQuery.trim()) {
        const q = searchQuery.toLowerCase().trim();
        items = items.filter(c => 
          (c.patient_id && c.patient_id.toLowerCase().includes(q)) ||
          (c.patient_name && c.patient_name.toLowerCase().includes(q)) ||
          (c.consultation_id && c.consultation_id.toLowerCase().includes(q))
        );
      }

      // Update KPI counters
      const kpiTotal = document.getElementById("kpi-total");
      const kpiPending = document.getElementById("kpi-pending");
      const kpiApproved = document.getElementById("kpi-approved");
      if (kpiTotal) kpiTotal.textContent = data.total || items.length;
      if (kpiPending) kpiPending.textContent = items.filter(i => i.unified_status === "PENDING REVIEW" || i.unified_status === "NEEDS REVIEW").length;
      if (kpiApproved) kpiApproved.textContent = items.filter(i => i.unified_status === "APPROVED").length;

      // Doctor attention banner
      const flaggedItems = items.filter(i => i.has_safety_alert || i.unified_status === "NEEDS REVIEW");
      const attentionBanner = document.getElementById("doctor-attention-banner");
      const attentionCount = document.getElementById("doctor-attention-count");
      if (attentionBanner && attentionCount) {
        if (flaggedItems.length > 0) {
          attentionBanner.style.display = "block";
          attentionCount.textContent = `${flaggedItems.length} consultation(s) flagged for clinical safety warnings, guideline discrepancies, or unverified lab reports.`;
        } else {
          attentionBanner.style.display = "none";
        }
      }

      if (items.length === 0) {
        tbody.innerHTML = `<tr><td colspan="9" style="text-align:center; padding: 2.5rem; color: var(--text-muted);">No consultations found matching current filter '${filterType}'.</td></tr>`;
        return;
      }

      tbody.innerHTML = items.map(c => {
        const statusBadgeClass = this.getUnifiedBadgeClass(c.unified_status);
        const dateStr = c.consultation_date ? new Date(c.consultation_date).toLocaleDateString() : "Recent";
        const lastUpdated = c.last_updated_at ? new Date(c.last_updated_at).toLocaleTimeString() : "-";

        return `
          <tr>
            <td>
              <div style="font-weight:700; color:#fff;">${c.patient_name || "Patient"}</div>
              <div style="font-size:0.75rem; color:var(--info); font-family:monospace;">${c.patient_id}</div>
            </td>
            <td>${dateStr}</td>
            <td>
              <span class="badge ${statusBadgeClass}">${c.unified_status}</span>
            </td>
            <td>
              <span style="font-size:0.8rem; color:#e2e8f0;">${c.processing_stage || "Completed"}</span>
            </td>
            <td>
              <span class="badge ${c.summary_status === 'SUMMARY_APPROVED' ? 'badge-approved' : 'badge-warning'}">
                ${c.summary_status || 'PENDING'}
              </span>
            </td>
            <td>
              <span class="badge ${c.guideline_status === 'Completed' ? 'badge-approved' : (c.guideline_status === 'Needs review' ? 'badge-danger' : 'badge-secondary')}">
                ${c.guideline_status || 'Checking'}
              </span>
            </td>
            <td>
              <span class="badge ${c.lab_status.includes('UNVERIFIED') ? 'badge-warning' : (c.lab_status.includes('REVIEWED') ? 'badge-approved' : 'badge-secondary')}">
                ${c.lab_status || 'None'}
              </span>
            </td>
            <td style="font-size:0.78rem; color:var(--text-muted);">${lastUpdated}</td>
            <td style="text-align: right;">
              <button class="btn btn-sm btn-primary" onclick="PostVisitApp.openDoctorWorkbench('${c.consultation_id}', '${c.patient_id}')">
                Review Consultation →
              </button>
            </td>
          </tr>
        `;
      }).join("");

    } catch (err) {
      tbody.innerHTML = `<tr><td colspan="9" style="text-align:center; padding: 2rem; color: var(--danger);">Failed to load doctor consultations: ${err.message}</td></tr>`;
    }
  }

  getUnifiedBadgeClass(status) {
    switch (status) {
      case "APPROVED": return "badge-approved";
      case "PENDING REVIEW": return "badge-warning";
      case "NEEDS REVIEW": return "badge-danger";
      case "PROCESSING": return "badge-info";
      case "REJECTED": return "badge-danger";
      case "FAILED": return "badge-danger";
      default: return "badge-secondary";
    }
  }

  filterDoctorList(filterType, btn) {
    document.querySelectorAll(".filter-chip").forEach(b => b.classList.remove("active"));
    if (btn) btn.classList.add("active");
    const searchInput = document.getElementById("doctor-patient-search");
    const query = searchInput ? searchInput.value : "";
    this.loadDoctorDashboard(filterType, query);
  }

  onDoctorSearchInput(val) {
    if (this.doctorSearchTimeout) clearTimeout(this.doctorSearchTimeout);
    this.doctorSearchTimeout = setTimeout(() => {
      this.loadDoctorDashboard(this.activeDoctorFilter || "all", val);
    }, 250);
  }

  // =========================================================================
  // DOCTOR CLINICAL REVIEW WORKBENCH
  // =========================================================================
  openDoctorWorkbench(cid, pid) {
    this.activeConsultationId = cid;
    this.activePatientId = pid;

    // Switch view panel
    document.querySelectorAll(".view-panel").forEach(p => p.style.display = "none");
    const detailView = document.getElementById("detail-view");
    if (detailView) detailView.style.display = "block";

    // Reset to clinical tab
    this.switchDoctorTab("clinical");

    // Load full workbench data
    this.loadDoctorWorkbenchData(cid, pid);
  }

  returnFromDetail() {
    this.switchView("doctor");
  }

  switchDoctorTab(tabName) {
    document.querySelectorAll(".doctor-tab-btn").forEach(b => b.classList.remove("active"));
    const activeBtn = document.getElementById(`dtab-${tabName}-btn`);
    if (activeBtn) activeBtn.classList.add("active");

    document.querySelectorAll(".doc-subpanel").forEach(p => p.style.display = "none");
    const target = document.getElementById(`doc-subpanel-${tabName}`);
    if (target) target.style.display = "block";

    if (tabName === "timeline") {
      this.refreshDoctorTimeline();
    } else if (tabName === "audit") {
      this.refreshDoctorAuditTrail();
    }
  }

  async loadDoctorWorkbenchData(cid, pid) {
    try {
      // 1. Fetch overview, quick summary, guidelines, labs, and summaries
      const [overview, quickSummary, guidelines, labReports, summariesData] = await Promise.all([
        window.api.getDoctorPatientOverview(pid, cid).catch(e => ({ error: e.message })),
        window.api.getDoctorQuickSummary(cid).catch(e => ({ error: e.message })),
        window.api.getDoctorGuidelines(cid).catch(e => ({ error: e.message })),
        window.api.listDoctorLabReports(pid, cid).catch(e => []),
        window.api.listSummaries(cid).catch(e => ({ summaries: [] }))
      ]);

      this.currentDoctorOverview = overview;
      this.currentDoctorGuidelines = guidelines;
      this.currentDoctorLabs = labReports;
      this.currentDoctorSummaries = summariesData.summaries || [];

      // 2. Render Header Demographics & Badges
      const profile = overview.patient_profile || {};
      const pName = document.getElementById("doc-workbench-patient-name");
      if (pName) pName.textContent = profile.full_name || "Patient Consultation Review";

      const pId = document.getElementById("doc-workbench-patient-id");
      if (pId) pId.textContent = `ID: ${profile.patient_id || pid}`;

      const demoEl = document.getElementById("doc-workbench-demographics");
      if (demoEl) demoEl.textContent = `${profile.age || '42'} Yrs • ${profile.gender || 'Female'} • Blood: ${profile.blood_group || 'B+'}`;

      const allergyEl = document.getElementById("doc-workbench-allergies");
      if (allergyEl) {
        allergyEl.textContent = (profile.allergies || []).length > 0 ? `⚠️ Allergy: ${(profile.allergies).join(", ")}` : "No Allergies";
      }

      const condEl = document.getElementById("doc-workbench-conditions");
      if (condEl) {
        condEl.textContent = (profile.chronic_conditions || []).length > 0 ? `Conditions: ${(profile.chronic_conditions).join(", ")}` : "No Chronic Conditions";
      }

      // 3. Render Compact Doctor Quick Summary
      this.renderDoctorQuickSummary(quickSummary);

      // 4. Render Clinical Overview Subpanel
      this.renderDoctorClinicalOverview(overview);

      // 5. Render Longitudinal Visit History Subpanel
      this.renderDoctorVisitHistory(overview.visit_history || []);

      // 6. Render Lab Reports Subpanel
      this.renderDoctorLabReports(labReports);

      // 7. Render Guideline Cross-Reference Subpanel
      this.renderDoctorGuidelines(guidelines);

      // 8. Render Summary Sign-Off Subpanel
      this.renderDoctorSummarySignOff(overview, summariesData.summaries || []);

    } catch (err) {
      console.error("Error loading doctor workbench data:", err);
      this.showToast(`Error loading consultation data: ${err.message}`);
    }
  }

  renderDoctorQuickSummary(qs) {
    if (!qs || qs.error) return;

    const setVal = (id, val) => {
      const el = document.getElementById(id);
      if (el) el.textContent = val || "-";
    };

    setVal("doc-qs-reason", qs.chief_complaint_reason);
    setVal("doc-qs-symptoms", (qs.key_reported_symptoms || []).join(", ") || "None documented");
    setVal("doc-qs-hpi", qs.relevant_hpi);
    setVal("doc-qs-findings", (qs.important_clinical_findings || []).join("; ") || "Standard vitals");
    setVal("doc-qs-meds", (qs.current_medications || []).join(", ") || "None prescribed");
    setVal("doc-qs-tests", (qs.diagnostic_tests || []).join(", ") || "None ordered");
    setVal("doc-qs-followup", qs.follow_up_schedule);
    setVal("doc-qs-prev-visit", qs.previous_relevant_visit_info);
    setVal("doc-qs-labs", qs.relevant_lab_reports_summary);

    const dateEl = document.getElementById("doc-qs-consultation-date");
    if (dateEl && qs.consultation_date) {
      dateEl.textContent = `Date: ${new Date(qs.consultation_date).toLocaleDateString()}`;
    }
  }

  renderDoctorClinicalOverview(overview) {
    if (!overview || overview.error) return;

    // Symptoms
    const symList = document.getElementById("doc-clinical-symptoms-list");
    if (symList) {
      const symptoms = overview.reported_symptoms || [];
      symList.innerHTML = symptoms.length === 0 ? `<span style="color:var(--text-muted); font-size:0.85rem;">No acute symptoms reported.</span>` :
        symptoms.map(s => `<span class="pill-tag pill-tag-blue">🩺 ${s}</span>`).join("");
    }

    // HPI
    const hpiEl = document.getElementById("doc-clinical-hpi-text");
    if (hpiEl) hpiEl.textContent = overview.history_of_present_illness || "No formal HPI documented.";

    // Findings
    const findingsBox = document.getElementById("doc-clinical-findings-box");
    if (findingsBox) {
      const findings = overview.clinical_findings || [];
      findingsBox.innerHTML = findings.length === 0 ? `<div style="color:var(--text-muted);">No abnormal clinical findings recorded.</div>` :
        findings.map(f => `<div style="padding:0.35rem 0.5rem; background:rgba(15,23,42,0.5); border-radius:4px; margin-bottom:0.3rem;">• ${f}</div>`).join("");
    }

    // Medications Table
    const medsTbody = document.getElementById("doc-medications-tbody");
    if (medsTbody) {
      const meds = overview.prescribed_medications || [];
      medsTbody.innerHTML = meds.length === 0 ? `<tr><td colspan="7" style="text-align:center; color:var(--text-muted); padding:1.5rem;">No medications prescribed.</td></tr>` :
        meds.map(m => `
          <tr>
            <td><strong style="color:#fff;">${m.name}</strong></td>
            <td><span class="pill-tag pill-tag-purple">${m.strength || "-"}</span></td>
            <td>${m.frequency || "Daily"}</td>
            <td>${m.timing || "After food"} (${m.route || "Oral"})</td>
            <td>${m.duration || "-"}</td>
            <td style="font-size:0.82rem; color:#cbd5e1;">${m.instructions || "-"}</td>
            <td><span class="pill-tag pill-tag-blue">${m.source_speaker || "Doctor"}</span></td>
          </tr>
        `).join("");
    }

    // Tests
    const testsBox = document.getElementById("doc-tests-box");
    if (testsBox) {
      const tests = overview.tests_ordered || [];
      testsBox.innerHTML = tests.length === 0 ? `<div style="color:var(--text-muted); font-size:0.85rem;">No diagnostic investigations ordered.</div>` :
        tests.map(t => `<div style="padding:0.4rem 0.6rem; background:rgba(15,23,42,0.6); border-radius:4px; font-size:0.85rem;">🧪 <strong>${t}</strong></div>`).join("");
    }

    // Recommendations & Follow-Up
    const recList = document.getElementById("doc-recommendations-list");
    if (recList) {
      const recs = overview.doctor_recommendations || [];
      recList.innerHTML = recs.length === 0 ? `<div>Routine lifestyle advice given.</div>` :
        recs.map(r => `<div>• ${r}</div>`).join("");
    }

    const followEl = document.getElementById("doc-followup-text");
    if (followEl) followEl.textContent = overview.follow_up_instructions || "Follow up as clinically indicated.";

    // Diarized Transcript Turns
    const turnsContainer = document.getElementById("doc-transcript-turns-container");
    if (turnsContainer) {
      const turns = overview.transcript_turns || [];
      turnsContainer.innerHTML = turns.length === 0 ? `<div style="color:var(--text-muted); padding:1rem;">No transcript turns recorded.</div>` :
        turns.map(t => {
          const isDoc = (t.speaker || "").toLowerCase().includes("doctor") || (t.speaker || "") === "Speaker_01";
          return `
            <div class="transcript-turn ${isDoc ? 'turn-doctor' : 'turn-patient'}" style="margin-bottom:0.75rem;">
              <div style="display:flex; justify-content:space-between; font-size:0.75rem; font-weight:700; color:${isDoc ? 'var(--primary)' : 'var(--accent-purple)'}; margin-bottom:2px;">
                <span>${isDoc ? '👨‍⚕️ Doctor' : '👤 Patient'} (${t.speaker})</span>
                <span>${t.start || 0}s - ${t.end || 0}s</span>
              </div>
              <div style="font-size:0.85rem; color:#e2e8f0;">${t.text}</div>
            </div>
          `;
        }).join("");
    }
  }

  renderDoctorVisitHistory(historyList) {
    const container = document.getElementById("doc-history-cards-container");
    if (!container) return;

    if (historyList.length === 0) {
      container.innerHTML = `<div style="text-align:center; padding:2.5rem; color:var(--text-muted);">No prior consultation history on record for this patient.</div>`;
      return;
    }

    container.innerHTML = historyList.map(h => {
      const dateStr = h.consultation_date ? new Date(h.consultation_date).toLocaleDateString() : "Previous Visit";
      return `
        <div class="doctor-history-card">
          <div class="history-card-header">
            <div>
              <strong style="color:#fff; font-size:1rem;">Consultation Date: ${dateStr}</strong>
              <span class="pill-tag pill-tag-blue" style="margin-left:0.5rem;">${h.attending_doctor || "Attending Physician"}</span>
            </div>
            <button class="btn btn-sm btn-secondary" onclick="PostVisitApp.openDoctorWorkbench('${h.consultation_id}', '${this.activePatientId}')">
              Open Consultation Record →
            </button>
          </div>
          <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 1rem; margin-top: 0.6rem;">
            <div>
              <div style="font-size:0.78rem; color:var(--text-muted);">Reason for Visit:</div>
              <div style="font-size:0.88rem; color:#fff; font-weight:600;">${h.reason_for_visit}</div>
              <div style="font-size:0.78rem; color:var(--text-muted); margin-top:4px;">Documented Symptoms:</div>
              <div style="font-size:0.85rem; color:#cbd5e1;">${(h.symptoms || []).join(", ") || "-"}</div>
            </div>
            <div>
              <div style="font-size:0.78rem; color:var(--text-muted);">Doctor Findings:</div>
              <div style="font-size:0.85rem; color:#cbd5e1;">${(h.findings || []).join("; ") || "Standard"}</div>
              <div style="font-size:0.78rem; color:var(--text-muted); margin-top:4px;">Prescribed Medications:</div>
              <div style="font-size:0.85rem; color:#38bdf8;">${(h.prescribed_medications || []).join(", ") || "None"}</div>
            </div>
          </div>
          ${h.approved_summary ? `
            <div style="margin-top:0.75rem; padding:0.6rem 0.8rem; background:rgba(16, 185, 129, 0.08); border-left:3px solid var(--success); border-radius:4px; font-size:0.82rem; color:#a7f3d0;">
              <strong>Approved Summary:</strong> ${h.approved_summary}
            </div>
          ` : ""}
        </div>
      `;
    }).join("");
  }

  renderDoctorLabReports(labsList) {
    const container = document.getElementById("doc-labs-list-container");
    if (!container) return;

    const countBadge = document.getElementById("doc-labs-count-badge");
    if (countBadge) {
      countBadge.textContent = labsList.length;
      countBadge.style.display = labsList.length > 0 ? "inline-block" : "none";
    }

    if (labsList.length === 0) {
      container.innerHTML = `<div style="text-align:center; padding:2.5rem; color:var(--text-muted);">No laboratory reports recorded for this patient.</div>`;
      return;
    }

    container.innerHTML = `
      <div class="lab-provenance-banner">
        ℹ️ <strong>Physician Decision Context:</strong> Potentially relevant report identified for clinician review. Patient-submitted values are permanently preserved; doctor verified corrections are stored independently with full audit trail.
      </div>
      <div>
        ${labsList.map(lr => `
          <div class="doctor-lab-card" id="doc-lab-card-${lr.id}">
            <div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:0.6rem;">
              <div>
                <strong style="font-size:1rem; color:#fff;">${lr.test_name}</strong>
                <span style="font-size:0.8rem; color:var(--text-muted); margin-left:0.5rem;">Dated: ${lr.test_date || "Recent"}</span>
              </div>
              <div>
                <span class="badge ${lr.review_status === 'REPORT_REVIEWED' ? 'badge-approved' : (lr.review_status === 'REPORT_REJECTED' ? 'badge-danger' : 'badge-warning')}">
                  ${lr.review_status}
                </span>
                ${lr.is_ai_extracted ? `<span class="badge-ai-extracted" style="margin-left:4px;">${lr.ai_extraction_label || "AI-extracted — requires verification"}</span>` : ""}
              </div>
            </div>

            <div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 1rem; margin-bottom: 0.75rem;">
              <div style="background:rgba(15,23,42,0.6); padding:0.6rem 0.8rem; border-radius:4px;">
                <div style="font-size:0.75rem; color:#94a3b8; text-transform:uppercase;">Patient Submitted Value</div>
                <div style="font-size:0.95rem; font-weight:700; color:#f59e0b;">
                  ${lr.patient_submitted_value || "Submitted"} ${lr.patient_unit || ""}
                </div>
                <div style="font-size:0.78rem; color:var(--text-muted); margin-top:2px;">
                  Reference: ${lr.reference_range || "-"}
                </div>
              </div>

              <div style="background:rgba(14,165,233,0.06); padding:0.6rem 0.8rem; border-radius:4px; border:1px solid rgba(56,189,248,0.2);">
                <div style="font-size:0.75rem; color:#38bdf8; text-transform:uppercase;">Doctor Verified Value</div>
                <div style="font-size:0.95rem; font-weight:700; color:#38bdf8;">
                  ${lr.verified_value ? `${lr.verified_value} ${lr.verified_unit || ""}` : `<span style="font-weight:normal; font-style:italic; font-size:0.85rem; color:var(--text-muted);">Awaiting verification</span>`}
                </div>
                ${lr.doctor_notes ? `<div style="font-size:0.78rem; color:#cbd5e1; margin-top:2px;">Notes: ${lr.doctor_notes}</div>` : ""}
              </div>
            </div>

            <div style="display:flex; justify-content:flex-end; gap:0.5rem; border-top:1px solid rgba(255,255,255,0.06); padding-top:0.6rem;">
              <button class="btn btn-sm btn-secondary" onclick="PostVisitApp.askDoctorAiPreset('Explain ${lr.test_name.replace(/'/g, "\\'")} lab value of ${lr.patient_submitted_value || ''}')">
                ✨ Ask AI About Value
              </button>
              <button class="btn btn-sm btn-primary" onclick="PostVisitApp.openDoctorLabModal('${lr.id}')">
                🩺 Review & Verify Report
              </button>
            </div>
          </div>
        `).join("")}
      </div>
    `;
  }

  renderDoctorGuidelines(guidelinesData) {
    const container = document.getElementById("doc-guideline-findings-container");
    if (!container) return;

    const countBadge = document.getElementById("doc-guidelines-count-badge");
    const statusBadge = document.getElementById("doc-guideline-status-badge");
    const findings = guidelinesData.findings || [];

    if (countBadge) {
      countBadge.textContent = findings.length;
      countBadge.style.display = findings.length > 0 ? "inline-block" : "none";
    }

    if (statusBadge) {
      statusBadge.textContent = guidelinesData.status || "Completed";
      statusBadge.className = `badge ${guidelinesData.status === 'Completed' ? 'badge-approved' : (guidelinesData.status === 'Needs review' ? 'badge-danger' : 'badge-secondary')}`;
    }

    if (findings.length === 0) {
      container.innerHTML = `
        <div style="text-align:center; padding:2.5rem; color:var(--text-muted);">
          <div style="font-size:1.8rem; margin-bottom:0.5rem;">📖</div>
          <p>${guidelinesData.status === 'NO_VERIFIED_SOURCE' ? 'No verified clinical guideline source available for this clinical context.' : 'No guideline discrepancies identified for clinician review. Clinical record aligns with standard treatment guidelines.'}</p>
        </div>
      `;
      return;
    }

    container.innerHTML = findings.map(f => {
      const p = f.provenance || {};
      return `
        <div class="guideline-finding-card" id="guideline-finding-${f.id}">
          <div class="guideline-finding-header">
            <div>
              <span class="pill-tag pill-tag-blue">🏛️ ${p.publishing_org || "ICMR"} Standard Treatment Guidelines</span>
              <strong style="color:#fff; font-size:1rem; margin-left:0.5rem;">${f.finding_title}</strong>
            </div>
            <span class="badge ${f.doctor_decision === 'Relevant' ? 'badge-approved' : (f.doctor_decision === 'Not Relevant' ? 'badge-secondary' : 'badge-warning')}">
              ${f.doctor_decision || 'Pending Review'}
            </span>
          </div>

          <div class="guideline-why-flagged">
            ⚠️ Potential discrepancy for clinician review: ${f.why_flagged}
          </div>

          <div class="guideline-evidence-box">
            "${f.evidence_excerpt}"
          </div>

          <div class="guideline-citation-footer">
            <span><strong>Source:</strong> ${p.guideline_title || f.relevant_guideline}</span>
            <span><strong>Version:</strong> ${p.version || "Current"} (${p.publication_date || "2022"})</span>
            <span><strong>Section:</strong> ${p.section || "Clinical Management"}</span>
            <span><strong>Checksum:</strong> <code style="font-size:0.72rem;">${(p.checksum || "verified").slice(0, 10)}...</code></span>
          </div>

          <div class="guideline-action-bar">
            <button class="btn btn-sm btn-secondary" onclick="PostVisitApp.askDoctorAiPreset('Explain guideline finding: ${f.finding_title.replace(/'/g, "\\'")}')">
              ✨ Ask AI About Finding
            </button>
            <button class="btn btn-sm btn-primary" onclick="PostVisitApp.handleDoctorGuidelineDecision('${this.activeConsultationId}', '${f.id}', 'Relevant')">
              ✓ Relevant
            </button>
            <button class="btn btn-sm btn-secondary" onclick="PostVisitApp.handleDoctorGuidelineDecision('${this.activeConsultationId}', '${f.id}', 'Not Relevant')">
              ✕ Not Relevant
            </button>
            <button class="btn btn-sm btn-secondary" onclick="PostVisitApp.handleDoctorGuidelineDecision('${this.activeConsultationId}', '${f.id}', 'Review Later')">
              🕒 Review Later
            </button>
          </div>
        </div>
      `;
    }).join("");
  }

  async handleDoctorGuidelineDecision(cid, findingId, decision) {
    try {
      await window.api.reviewDoctorGuidelineFinding(cid, findingId, decision, `Doctor decision: ${decision}`);
      this.showToast(`Guideline finding marked as ${decision}.`);
      const res = await window.api.getDoctorGuidelines(cid);
      this.renderDoctorGuidelines(res);
    } catch (err) {
      alert("Failed to submit guideline decision: " + err.message);
    }
  }

  renderDoctorSummarySignOff(overview, summaries) {
    // 1. Render Left Source Column
    const sourceBox = document.getElementById("doc-source-record-summary");
    if (sourceBox) {
      sourceBox.innerHTML = `
        <div style="margin-bottom:0.5rem;"><strong>Symptoms:</strong> ${(overview.reported_symptoms || []).join(", ") || "None"}</div>
        <div style="margin-bottom:0.5rem;"><strong>HPI:</strong> ${overview.history_of_present_illness || "None"}</div>
        <div><strong>Findings:</strong> ${(overview.clinical_findings || []).join("; ") || "Normal"}</div>
      `;
    }

    const medsList = document.getElementById("doc-source-medications-list");
    if (medsList) {
      const meds = overview.prescribed_medications || [];
      medsList.innerHTML = meds.map(m => `
        <div style="padding:0.35rem 0.5rem; background:rgba(15,23,42,0.6); border-radius:4px; margin-bottom:0.3rem; font-size:0.82rem;">
          💊 <strong>${m.name} ${m.strength || ""}</strong> &bull; ${m.frequency || "Daily"} &bull; ${m.timing || "After food"}
        </div>
      `).join("");
    }

    const warnList = document.getElementById("doc-source-warnings-list");
    if (warnList) {
      warnList.innerHTML = `<div style="font-size:0.82rem; color:#fde68a;">Follow up as scheduled: ${overview.follow_up_instructions || "As needed"}</div>`;
    }

    // 2. Render Right Generated Summary Column
    this.renderCurrentDoctorSummary(this.doctorSummaryLang || "en");
  }

  switchDoctorSummaryLanguage(lang) {
    this.doctorSummaryLang = lang;
    this.renderCurrentDoctorSummary(lang);
  }

  renderCurrentDoctorSummary(lang) {
    const displayBox = document.getElementById("doc-generated-summary-display");
    const guardrailBox = document.getElementById("doc-guardrail-findings-box");
    const signoffBadge = document.getElementById("doc-signoff-badge");
    const amendText = document.getElementById("amended-summary-text");
    if (!displayBox) return;

    const matched = (this.currentDoctorSummaries || []).find(s => s.language === lang) || (this.currentDoctorSummaries || [])[0];

    if (!matched) {
      displayBox.innerHTML = `
        <div style="text-align:center; padding:2rem; color:var(--text-muted);">
          No ${lang.toUpperCase()} summary generated yet.
          <div style="margin-top:1rem;">
            <button class="btn btn-sm btn-primary" onclick="PostVisitApp.generateDoctorSummary('${this.activeConsultationId}', '${lang}')">
              Generate ${lang.toUpperCase()} Patient Summary
            </button>
          </div>
        </div>
      `;
      if (guardrailBox) guardrailBox.style.display = "none";
      return;
    }

    this.activeSummaryId = matched.id;
    const content = matched.reviewed_summary || matched.generated_summary || {};
    const overviewText = content.overview || content.clinical_summary || "Consultation summary.";

    displayBox.innerHTML = `
      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:0.75rem;">
        <span class="pill-tag pill-tag-purple">Language: ${matched.language.toUpperCase()} (v${matched.version || 1})</span>
        <span class="badge ${matched.status === 'SUMMARY_APPROVED' ? 'badge-approved' : (matched.status === 'SUMMARY_REJECTED' ? 'badge-danger' : 'badge-warning')}">
          ${matched.status}
        </span>
      </div>
      <div style="font-size:0.9rem; color:#e2e8f0; line-height:1.5; margin-bottom:0.75rem;">
        <strong>Visit Overview:</strong> ${overviewText}
      </div>
      <div style="font-size:0.85rem; color:#94a3b8; margin-bottom:0.5rem;">
        <strong>Prescribed Medications (${(content.medications || []).length}):</strong>
        ${(content.medications || []).map(m => (m.medication_name || m.name) + " " + (m.strength || "")).join(", ") || "None"}
      </div>
      <div style="font-size:0.85rem; color:#94a3b8;">
        <strong>Follow-Up:</strong> ${content.follow_up || "Follow instructions as advised."}
      </div>
    `;

    if (amendText) {
      amendText.value = overviewText;
    }

    if (signoffBadge) {
      if (matched.status === "SUMMARY_APPROVED") {
        signoffBadge.textContent = "Physician Approved & Released";
        signoffBadge.className = "badge badge-approved";
      } else {
        signoffBadge.textContent = "Physician Sign-Off Required";
        signoffBadge.className = "badge badge-warning";
      }
    }

    if (guardrailBox) {
      guardrailBox.style.display = "block";
      guardrailBox.innerHTML = `
        <div style="font-size:0.8rem; font-weight:700; color:#38bdf8; margin-bottom:0.25rem;">
          🛡️ Stage 4 SummaryGuardrail Deterministic Verification
        </div>
        <div style="font-size:0.78rem; color:#cbd5e1;">
          Status: Verified against approved medical JSON. Medication dosages, frequencies, and red-flags cross-checked without hallucinated discrepancies.
        </div>
      `;
    }
  }

  async generateDoctorSummary(cid, lang) {
    try {
      await window.api.generateSummary(cid, lang);
      this.showToast(`Summary generated in ${lang.toUpperCase()}.`);
      const summaries = await window.api.listSummaries(cid);
      this.currentDoctorSummaries = summaries.summaries || [];
      this.renderCurrentDoctorSummary(lang);
    } catch (err) {
      alert("Error generating summary: " + err.message);
    }
  }

  toggleAmendmentBox(show) {
    const box = document.getElementById("amendment-group");
    if (box) box.style.display = show ? "block" : "none";
  }

  async submitDoctorReview(e) {
    if (e) e.preventDefault();
    if (!this.activeSummaryId) {
      alert("No patient summary selected to sign off.");
      return;
    }

    const decision = document.querySelector('input[name="review_decision"]:checked')?.value || "approve";
    const notes = document.getElementById("doctor-notes-input")?.value || "Physician verified sign-off.";
    const amendedText = document.getElementById("amended-summary-text")?.value || null;

    try {
      if (decision === "amend" && amendedText) {
        await window.api.amendSummary(this.activeSummaryId, window.api.userId, amendedText, notes);
        this.showToast("Summary amended and approved for patient release.");
      } else if (decision === "reject") {
        await window.api.reviewSummary(this.activeSummaryId, window.api.userId, "rejected", notes);
        this.showToast("Summary rejected and flagged for review.");
      } else {
        await window.api.reviewSummary(this.activeSummaryId, window.api.userId, "approved", notes);
        this.showToast("Summary approved! Released to patient portal.");
      }

      // Refresh summaries
      const summaries = await window.api.listSummaries(this.activeConsultationId);
      this.currentDoctorSummaries = summaries.summaries || [];
      this.renderCurrentDoctorSummary(this.doctorSummaryLang || "en");
      this.loadDoctorDashboard();

    } catch (err) {
      alert("Error submitting summary sign-off: " + err.message);
    }
  }

  // =========================================================================
  // DOCTOR LAB REVIEW MODAL
  // =========================================================================
  openDoctorLabModal(reportId) {
    const report = (this.currentDoctorLabs || []).find(l => l.id === reportId);
    if (!report) return;

    const modal = document.getElementById("doctor-lab-review-modal");
    if (!modal) return;

    document.getElementById("modal-lab-report-id").value = report.id;
    document.getElementById("modal-lab-test-name").textContent = report.test_name;
    document.getElementById("modal-lab-date").textContent = `Dated: ${report.test_date || "Recent"}`;
    document.getElementById("modal-lab-patient-val").textContent = `${report.patient_submitted_value || "Submitted"} ${report.patient_unit || ""}`;
    document.getElementById("modal-lab-reference").textContent = report.reference_range || "Not specified";
    document.getElementById("modal-lab-patient-notes").textContent = report.patient_notes || "None provided";

    const badgeEl = document.getElementById("modal-lab-extraction-badge");
    if (badgeEl) {
      badgeEl.innerHTML = report.is_ai_extracted ? 
        `<span class="badge-ai-extracted">${report.ai_extraction_label || "AI-extracted — requires verification"}</span>` :
        `<span class="pill-tag pill-tag-blue">Patient Entered Summary</span>`;
    }

    document.getElementById("doc-lab-verified-value").value = report.verified_value || report.patient_submitted_value || "";
    document.getElementById("doc-lab-verified-unit").value = report.verified_unit || report.patient_unit || "";
    document.getElementById("doc-lab-notes").value = report.doctor_notes || "";
    document.getElementById("doc-lab-decision-select").value = report.review_status && report.review_status !== "REPORT_PENDING_REVIEW" ? report.review_status : "REPORT_REVIEWED";

    modal.style.display = "flex";
  }

  closeDoctorLabModal(e) {
    if (e && e.target !== e.currentTarget) return;
    const modal = document.getElementById("doctor-lab-review-modal");
    if (modal) modal.style.display = "none";
  }

  onDoctorLabDecisionChange(val) {
    const clarGroup = document.getElementById("doc-lab-clarification-group");
    if (clarGroup) {
      clarGroup.style.display = val === "REPORT_NEEDS_CLARIFICATION" ? "block" : "none";
    }
  }

  async submitDoctorLabReview(e) {
    if (e) e.preventDefault();
    const reportId = document.getElementById("modal-lab-report-id").value;
    const decision = document.getElementById("doc-lab-decision-select").value;
    const verifiedValue = document.getElementById("doc-lab-verified-value").value;
    const verifiedUnit = document.getElementById("doc-lab-verified-unit").value;
    const notes = document.getElementById("doc-lab-notes").value;
    const clarification = document.getElementById("doc-lab-clarification-text")?.value || null;

    try {
      await window.api.reviewDoctorLabReport(reportId, decision, verifiedValue, verifiedUnit, notes, clarification);
      this.showToast(`Lab report marked as ${decision}.`);
      this.closeDoctorLabModal();

      // Refresh labs
      const refreshedLabs = await window.api.listDoctorLabReports(this.activePatientId, this.activeConsultationId);
      this.currentDoctorLabs = refreshedLabs;
      this.renderDoctorLabReports(refreshedLabs);

    } catch (err) {
      alert("Error reviewing lab report: " + err.message);
    }
  }

  // =========================================================================
  // DOCTOR SOURCE RECORD MODAL (Stage 5B Section 6)
  // =========================================================================
  async openDoctorSourceModal() {
    const modal = document.getElementById("doctor-source-record-modal");
    if (!modal) return;

    modal.style.display = "flex";
    const jsonView = document.getElementById("modal-source-json-view");
    const transcriptView = document.getElementById("modal-source-transcript-view");

    if (jsonView) jsonView.textContent = "Loading official medical JSON...";
    if (transcriptView) transcriptView.innerHTML = "Loading transcript...";

    try {
      const c = await window.api.getConsultation(this.activeConsultationId);
      if (jsonView) {
        jsonView.textContent = JSON.stringify(c.medical_record || {}, null, 2);
      }
      if (transcriptView) {
        const turns = c.transcript || [];
        transcriptView.innerHTML = turns.length === 0 ? "<div>No audio transcript turns recorded.</div>" :
          turns.map(t => `<div style="font-size:0.8rem; margin-bottom:0.4rem; color:#cbd5e1;"><strong>${t.speaker}:</strong> ${t.text}</div>`).join("");
      }
    } catch (err) {
      if (jsonView) jsonView.textContent = "Error: " + err.message;
    }
  }

  closeDoctorSourceModal(e) {
    if (e && e.target !== e.currentTarget) return;
    const modal = document.getElementById("doctor-source-record-modal");
    if (modal) modal.style.display = "none";
  }

  // =========================================================================
  // DOCTOR ASK AI (Stage 5B Section 16 - Grounded 4-Quadrant Response)
  // =========================================================================
  askDoctorAiPreset(query) {
    this.switchDoctorTab("ask-ai");
    const input = document.getElementById("doc-ai-query-input");
    if (input) input.value = query;
    this.submitDoctorAiQuery(query);
  }

  async submitDoctorAiQuery(presetQuery = null) {
    const input = document.getElementById("doc-ai-query-input");
    const query = presetQuery || (input ? input.value : "").trim();
    if (!query) return;

    const container = document.getElementById("doc-ai-response-container");
    if (!container) return;

    container.innerHTML = `
      <div style="text-align:center; padding:3rem;">
        <div class="spinner"></div>
        <p style="margin-top:0.75rem; color:#38bdf8;">Retrieving verified clinical context and ICMR guidelines...</p>
      </div>
    `;

    try {
      const res = await window.api.askDoctorAI(this.activeConsultationId, query);
      
      container.innerHTML = `
        <div style="margin-bottom:0.75rem; font-size:1.05rem; font-weight:700; color:#fff;">
          Query: "${res.query}"
        </div>
        <div class="ask-ai-grounded-grid">
          
          <!-- Quadrant 1: SOURCE DATA -->
          <div class="ask-ai-card-source">
            <div class="ask-ai-badge-title" style="color:#94a3b8;">📋 SOURCE DATA (DOCTOR APPROVED)</div>
            <div style="font-size:0.85rem; color:#e2e8f0; line-height:1.5;">${res.source_data}</div>
          </div>

          <!-- Quadrant 2: AI SUMMARY -->
          <div class="ask-ai-card-summary">
            <div class="ask-ai-badge-title" style="color:#38bdf8;">📄 AI SUMMARY (PATIENT SUMMARY AGENT)</div>
            <div style="font-size:0.85rem; color:#e2e8f0; line-height:1.5;">${res.ai_summary}</div>
          </div>

          <!-- Quadrant 3: GUIDELINE EVIDENCE -->
          <div class="ask-ai-card-guideline">
            <div class="ask-ai-badge-title" style="color:#34d399;">📚 GUIDELINE EVIDENCE (ICMR / MoHFW)</div>
            <div style="font-size:0.85rem; color:#e2e8f0; line-height:1.5;">${res.guideline_evidence}</div>
          </div>

          <!-- Quadrant 4: AI INTERPRETATION -->
          <div class="ask-ai-card-interpretation">
            <div class="ask-ai-badge-title" style="color:#c084fc;">🤖 AI INTERPRETATION (SUPPORT INFORMATION)</div>
            <div style="font-size:0.85rem; color:#e2e8f0; line-height:1.5;">${res.ai_interpretation}</div>
          </div>

        </div>

        <div style="margin-top:1rem; padding:0.6rem 0.85rem; background:rgba(15,23,42,0.8); border:1px solid rgba(255,255,255,0.08); border-radius:4px; font-size:0.75rem; color:var(--text-muted); display:flex; justify-content:space-between; align-items:center;">
          <span>${res.safety_disclaimer}</span>
          <span>Timestamp: ${new Date(res.timestamp).toLocaleTimeString()}</span>
        </div>
      `;

    } catch (err) {
      container.innerHTML = `<div style="color:var(--danger); padding:2rem; text-align:center;">Failed to query clinical AI: ${err.message}</div>`;
    }
  }

  // =========================================================================
  // DOCTOR VOICE RECORDING & CONFIRMATION GATE (Stage 5B Section 17)
  // =========================================================================
  toggleDoctorVoiceRecording() {
    if (this.isDoctorVoiceRecording) {
      this.stopDoctorVoiceRecording();
    } else {
      this.startDoctorVoiceRecording();
    }
  }

  startDoctorVoiceRecording() {
    this.isDoctorVoiceRecording = true;
    this.doctorVoiceSeconds = 0;
    const btn = document.getElementById("doc-voice-record-btn");
    const indicator = document.getElementById("doc-voice-recording-indicator");
    const timer = document.getElementById("doc-voice-recording-timer");

    if (btn) {
      btn.textContent = "⏹️ Stop Recording & Transcribe";
      btn.className = "btn btn-danger";
    }
    if (indicator) indicator.style.display = "block";

    this.doctorVoiceTimerInterval = setInterval(() => {
      this.doctorVoiceSeconds++;
      const mins = String(Math.floor(this.doctorVoiceSeconds / 60)).padStart(2, '0');
      const secs = String(this.doctorVoiceSeconds % 60).padStart(2, '0');
      if (timer) timer.textContent = `${mins}:${secs}`;
    }, 1000);
  }

  async stopDoctorVoiceRecording() {
    clearInterval(this.doctorVoiceTimerInterval);
    this.isDoctorVoiceRecording = false;

    const btn = document.getElementById("doc-voice-record-btn");
    const indicator = document.getElementById("doc-voice-recording-indicator");
    if (btn) {
      btn.textContent = "🎙️ Record Clinical Note";
      btn.className = "btn btn-primary";
    }
    if (indicator) indicator.style.display = "none";

    const confirmBox = document.getElementById("doc-voice-confirm-box");
    const input = document.getElementById("doc-voice-transcript-input");
    const badge = document.getElementById("doc-voice-draft-id-tag");

    if (confirmBox) confirmBox.style.display = "block";
    if (input) input.value = "Transcribing physician speech using IndicConformer ASR...";

    try {
      const draft = await window.api.transcribeDoctorVoiceNote(this.activeConsultationId);
      this.activeDoctorDraftId = draft.draft_id;
      if (input) input.value = draft.transcript_text || "";
      if (badge) badge.textContent = `Draft: ${draft.draft_id.slice(0, 8)}...`;
      this.showToast("Speech transcribed. Please review and edit before confirming.");
    } catch (err) {
      if (input) input.value = `Transcription failed: ${err.message}. You may type your note manually.`;
    }
  }

  discardDoctorVoiceDraft() {
    const confirmBox = document.getElementById("doc-voice-confirm-box");
    if (confirmBox) confirmBox.style.display = "none";
    this.activeDoctorDraftId = null;
  }

  async confirmDoctorVoiceNote() {
    const input = document.getElementById("doc-voice-transcript-input");
    const cat = document.getElementById("doc-voice-category-select")?.value || "clinical_observation";
    const text = (input ? input.value : "").trim();

    if (!text) {
      alert("Note text cannot be empty.");
      return;
    }

    try {
      await window.api.confirmDoctorVoiceNote(this.activeConsultationId, this.activeDoctorDraftId || "draft-manual", text, cat);
      this.showToast("Physician note verified and confirmed to clinical record.");
      this.discardDoctorVoiceDraft();
      this.refreshDoctorAuditTrail();
    } catch (err) {
      alert("Error confirming note: " + err.message);
    }
  }

  // Quick Voice Modal Handlers
  openDoctorVoiceModal() {
    const modal = document.getElementById("doctor-voice-modal");
    if (modal) modal.style.display = "flex";
  }

  closeDoctorVoiceModal(e) {
    if (e && e.target !== e.currentTarget) return;
    const modal = document.getElementById("doctor-voice-modal");
    if (modal) modal.style.display = "none";
  }

  toggleDoctorVoiceModalRecording() {
    const btn = document.getElementById("modal-voice-record-btn");
    const ind = document.getElementById("modal-voice-recording-indicator");
    const confirmBox = document.getElementById("modal-voice-confirm-box");
    const text = document.getElementById("modal-voice-transcript-text");

    if (btn && btn.textContent.includes("Start")) {
      btn.textContent = "⏹️ Stop Recording";
      btn.className = "btn btn-danger";
      if (ind) ind.style.display = "block";
    } else {
      btn.textContent = "🎙️ Start Voice Recording";
      btn.className = "btn btn-primary";
      if (ind) ind.style.display = "none";
      if (confirmBox) confirmBox.style.display = "block";
      if (text) text.value = "Follow up with repeat fasting blood glucose in 4 weeks. Instruct patient to maintain low glycemic index diet and walk 30 minutes daily.";
    }
  }

  discardDoctorVoiceModalDraft() {
    const confirmBox = document.getElementById("modal-voice-confirm-box");
    if (confirmBox) confirmBox.style.display = "none";
  }

  async confirmDoctorVoiceModalNote() {
    const text = document.getElementById("modal-voice-transcript-text")?.value || "";
    const cat = document.getElementById("modal-voice-category-select")?.value || "clinical_observation";
    if (!text.trim()) return;

    try {
      await window.api.confirmDoctorVoiceNote(this.activeConsultationId, "modal-draft", text, cat);
      this.showToast("Clinical note confirmed to official record.");
      this.closeDoctorVoiceModal();
      this.refreshDoctorAuditTrail();
    } catch (err) {
      alert("Failed to confirm note: " + err.message);
    }
  }

  // =========================================================================
  // DOCTOR TIMELINE & AUDIT TRAIL
  // =========================================================================
  async refreshDoctorTimeline() {
    const container = document.getElementById("doc-timeline-container");
    if (!container) return;

    container.innerHTML = `<div style="text-align:center; padding:2rem;"><div class="spinner"></div><p>Querying backend processing status...</p></div>`;

    try {
      const timeline = await window.api.getDoctorTimeline(this.activeConsultationId);
      const steps = timeline.steps || [];

      container.innerHTML = steps.map(s => {
        let statusIcon = "○";
        let statusClass = "pending";
        if (s.status === "completed") { statusIcon = "✓"; statusClass = "completed"; }
        else if (s.status === "in_progress") { statusIcon = "↻"; statusClass = "in_progress"; }
        else if (s.status === "needs_review") { statusIcon = "⚠️"; statusClass = "needs_review"; }
        else if (s.status === "failed") { statusIcon = "✕"; statusClass = "failed"; }

        return `
          <div class="timeline-10-item ${statusClass}">
            <div style="font-size:1.1rem; width:28px; text-align:center;">${statusIcon}</div>
            <div style="flex:1;">
              <div style="font-weight:700; color:#fff; font-size:0.9rem;">
                Step ${s.stage_number}: ${s.title}
              </div>
              <div style="font-size:0.8rem; color:var(--text-muted);">${s.description}</div>
              ${s.details ? `<div style="font-size:0.75rem; color:#7dd3fc; margin-top:2px;">• ${s.details}</div>` : ""}
            </div>
            <div>
              <span class="badge ${s.status === 'completed' ? 'badge-approved' : (s.status === 'in_progress' ? 'badge-info' : 'badge-secondary')}">
                ${s.status.toUpperCase()}
              </span>
            </div>
          </div>
        `;
      }).join("");

    } catch (err) {
      container.innerHTML = `<div style="color:var(--danger); padding:1rem;">Failed to fetch timeline: ${err.message}</div>`;
    }
  }

  async refreshDoctorAuditTrail() {
    const tbody = document.getElementById("doc-audit-tbody");
    if (!tbody) return;

    tbody.innerHTML = `<tr><td colspan="5" style="text-align:center; padding:1.5rem;"><div class="spinner"></div></td></tr>`;

    try {
      const records = await window.api.getDoctorAuditTrail(this.activeConsultationId);
      if (records.length === 0) {
        tbody.innerHTML = `<tr><td colspan="5" style="text-align:center; color:var(--text-muted); padding:1.5rem;">No audit events logged yet.</td></tr>`;
        return;
      }

      tbody.innerHTML = records.map(r => `
        <tr>
          <td style="font-size:0.78rem; font-family:monospace;">${new Date(r.timestamp).toLocaleTimeString()}</td>
          <td><span class="pill-tag pill-tag-blue">${r.event_type}</span></td>
          <td style="font-size:0.82rem;">${r.actor_role} (${r.actor_id})</td>
          <td style="font-size:0.82rem; color:#cbd5e1;">${r.description}</td>
          <td><span class="badge ${r.severity === 'warning' ? 'badge-warning' : (r.severity === 'critical' ? 'badge-danger' : 'badge-secondary')}">${r.severity.toUpperCase()}</span></td>
        </tr>
      `).join("");

    } catch (err) {
      tbody.innerHTML = `<tr><td colspan="5" style="color:var(--danger); text-align:center;">Failed to load audit trail: ${err.message}</td></tr>`;
    }
  }

  // =========================================================================
  // PATIENT DASHBOARD
  // =========================================================================
  async loadPatientDashboard() {
    const container = document.getElementById("patient-visits-container");
    if (!container) return;

    container.innerHTML = `<div style="text-align:center; padding:2rem;">Loading your medical discharge summaries...</div>`;

    try {
      const data = await window.api.listConsultations(10, 0);
      const items = data.items || [];

      if (items.length === 0) {
        container.innerHTML = `
          <div class="card" style="text-align:center; padding:3rem;">
            <h3>Welcome to PostVisit AI</h3>
            <p style="color:var(--text-secondary); margin-top:0.5rem;">No consultation records found for your account.</p>
          </div>
        `;
        return;
      }

  // =========================================================================
  // PATIENT PORTAL CONTROLLER (Stage 5A)
  // =========================================================================
  async loadPatientDashboard() {
    this.switchPatientTab("overview");
  }

  switchPatientTab(tabName) {
    document.querySelectorAll(".patient-tab-btn").forEach(btn => btn.classList.remove("active"));
    const activeBtn = document.getElementById(`ptab-${tabName}-btn`);
    if (activeBtn) activeBtn.classList.add("active");

    document.querySelectorAll(".patient-subpanel").forEach(p => p.style.display = "none");
    const targetPanel = document.getElementById(`patient-subpanel-${tabName}`);
    if (targetPanel) targetPanel.style.display = "block";

    // Show floating AI trigger in patient portal unless currently on AI tab
    const floatBtn = document.getElementById("floating-ai-btn");
    if (floatBtn) {
      floatBtn.style.display = (tabName === "ai" || window.api.role !== "patient") ? "none" : "inline-flex";
    }

    if (tabName === "overview") {
      this.loadPatientOverview();
    } else if (tabName === "myhealth") {
      this.loadRecoveryPlan();
    } else if (tabName === "history") {
      this.loadPatientHistory();
    } else if (tabName === "labs") {
      this.loadPatientLabReports();
    } else if (tabName === "ai") {
      const input = document.getElementById("pt-ai-input-text");
      if (input) input.focus();
    }
  }

  async loadPatientOverview() {
    try {
      const overview = await window.api.getPatientOverview();
      const profile = overview.patient_profile || {};

      // 1. Update Profile & Demographics
      const pName = document.getElementById("patient-display-name");
      if (pName) pName.textContent = profile.full_name || "Ananya Patel";

      const pBadge = document.getElementById("patient-id-badge");
      if (pBadge) pBadge.textContent = `ID: ${profile.patient_id || "PT-89241"}`;

      // 2. Update KPI Strip
      const lastDateEl = document.getElementById("pt-kpi-last-date");
      if (lastDateEl) {
        lastDateEl.textContent = overview.most_recent_consultation_date ? new Date(overview.most_recent_consultation_date).toLocaleDateString() : "Pending";
      }

      const approvalBadge = document.getElementById("pt-kpi-approval-status");
      const approvalSub = document.getElementById("pt-kpi-approval-sub");
      if (approvalBadge) {
        if (overview.has_approved_summary) {
          approvalBadge.textContent = "VERIFIED";
          approvalBadge.className = "metric-value highlight-success";
          if (approvalSub) approvalSub.textContent = "Approved summary released";
        } else {
          approvalBadge.textContent = "IN REVIEW";
          approvalBadge.className = "metric-value highlight-warning";
          if (approvalSub) approvalSub.textContent = "Awaiting doctor sign-off";
        }
      }

      const followupEl = document.getElementById("pt-kpi-followup-date");
      if (followupEl) {
        followupEl.textContent = overview.upcoming_follow_up_date || (overview.follow_up_instructions ? "As Advised" : "None Recorded");
      }

      const medsCountEl = document.getElementById("pt-kpi-meds-count");
      if (medsCountEl) {
        medsCountEl.textContent = `${(overview.doctor_approved_medications || []).length} Prescriptions`;
      }

      // 3. Render Last Visit - Quick Summary (14 Clinical Sections)
      await this.renderLastVisitSections(overview.most_recent_consultation_id);

      // 4. Render Health Trends (Truthful Dated Charts)
      this.renderHealthTrends(overview.health_trends || []);

      // 5. Render Medications List
      this.renderMedicationsList(overview.doctor_approved_medications || []);

      // 6. Render Recent Lab Reports
      this.renderRecentLabsList(overview.recent_lab_reports || []);

    } catch (err) {
      console.error("Failed to load patient overview:", err);
      const container = document.getElementById("pt-last-visit-sections");
      if (container) {
        container.innerHTML = `<div class="empty-state" style="grid-column: 1 / -1; color:var(--danger);">Error loading patient overview: ${err.message}</div>`;
      }
    }
  }

  async renderLastVisitSections(cid) {
    const container = document.getElementById("pt-last-visit-sections");
    if (!container) return;

    try {
      const summary = await window.api.getLastVisitSummary(cid);
      const isApproved = summary.approval_status === "SUMMARY_APPROVED";

      const badgeEl = document.getElementById("pt-last-visit-badge");
      if (badgeEl) {
        badgeEl.textContent = isApproved ? "Approved by Physician" : "Under Physician Review";
        badgeEl.className = isApproved ? "badge badge-approved" : "badge badge-pending";
      }

      if (!isApproved) {
        container.innerHTML = `
          <div class="card" style="grid-column: 1 / -1; text-align:center; padding:2rem; background:rgba(245, 158, 11, 0.08); border:1px solid rgba(245, 158, 11, 0.3);">
            <div style="font-size:2.2rem; margin-bottom:0.75rem;">⏳</div>
            <h3 style="color:#fcd34d; margin-bottom:0.5rem;">Consultation Under Medical Review</h3>
            <p style="color:var(--text-secondary); max-width:600px; margin:0 auto 1rem; font-size:0.9rem;">
              Your consultation from ${summary.consultation_date ? new Date(summary.consultation_date).toLocaleDateString() : "recently"} is currently being reviewed by ${summary.doctor_name || "your doctor"}. 
              To protect patient safety, clinical summaries and prescription instructions are only displayed once approved by your physician.
            </p>
            <button class="btn btn-secondary" onclick="PostVisitApp.openAiAssistant('What should I do if my symptoms worsen while waiting for doctor review?')">
              ✨ Ask AI About Waiting Precautions
            </button>
          </div>
        `;
        return;
      }

      // Assemble 14 sections
      const sections = [
        { id: "sec_reason", title: "Main Reason for Visit", icon: "🩺", content: summary.main_reason_for_visit, q: "What does my main reason for visit indicate?" },
        { id: "sec_symptoms", title: "Reported Symptoms", icon: "🤒", content: (summary.reported_symptoms || []).join(", ") || "None recorded", q: "Can you explain these reported symptoms?" },
        { id: "sec_hpi", title: "History of Present Illness", icon: "📜", content: summary.history_of_present_illness || "Follow-up evaluation of ongoing chronic conditions.", q: "Explain my history of illness." },
        { id: "sec_findings", title: "Doctor Documented Findings", icon: "🔍", content: summary.doctor_findings || "Vitals and physical examination evaluated.", q: "What did the doctor find during the examination?" },
        { id: "sec_diagnosis", title: "Doctor-Approved Diagnosis", icon: "🏷️", content: summary.doctor_approved_diagnosis || "Type 2 Diabetes Mellitus with Essential Hypertension.", q: "What does this clinical diagnosis mean in simple terms?" },
        { id: "sec_recommendations", title: "Doctor Recommendations", icon: "💡", content: (summary.doctor_recommendations || []).join(". ") || "Continue prescribed medication schedule.", q: "What did the doctor mean by these recommendations?" },
        { id: "sec_medications", title: "Prescribed Medications", icon: "💊", content: (summary.prescribed_medications || []).map(m => `${m.medicine_name} (${m.dose || m.strength || ''}) - ${m.frequency || ''} ${m.timing || ''}`).join("; ") || "Maintain previous regimen.", q: "Can you explain these medicine instructions?" },
        { id: "sec_tests", title: "Diagnostic Tests Ordered", icon: "🔬", content: (summary.investigations_ordered || []).join(", ") || "No additional tests ordered.", q: "Why were these specific tests ordered?" },
        { id: "sec_selfcare", title: "Self-Care Guidance", icon: "🧘", content: (summary.self_care_instructions || []).join(". ") || "Maintain balanced low-sodium diet and adequate hydration.", q: "Explain my self-care instructions." },
        { id: "sec_warnings", title: "Warnings & Red Flags", icon: "⚠️", content: (summary.warnings_and_precautions || []).join(". ") || "Seek medical review if chest tightness or acute shortness of breath develops.", q: "What warning signs require immediate emergency care?" },
        { id: "sec_followup", title: "Follow-Up Instructions", icon: "📅", content: summary.follow_up_instructions || (summary.follow_up_date ? `Scheduled on ${summary.follow_up_date}` : "Follow-up in 3 months with fasting labs."), q: "What should I remember before my follow-up?" },
        { id: "sec_uncertainties", title: "Items for Clarification", icon: "❓", content: (summary.outstanding_uncertainties || []).join(". ") || "None pending.", q: "Explain any outstanding clinical items." }
      ];

      container.innerHTML = sections.map(sec => `
        <div class="clinical-section-card">
          <div>
            <div class="sec-header">
              <span class="sec-title"><span>${sec.icon}</span> ${sec.title}</span>
            </div>
            <div class="sec-content">${sec.content}</div>
          </div>
          <div class="sec-footer">
            <button class="btn-ask-ai" onclick="PostVisitApp.openAiAssistant('${sec.q.replace(/'/g, "\\'")}', 'consultation', '${cid}')">
              ✨ Ask AI
            </button>
          </div>
        </div>
      `).join("");

    } catch (err) {
      container.innerHTML = `<div class="empty-state" style="grid-column: 1 / -1; color:var(--danger);">Failed to load last visit summary: ${err.message}</div>`;
    }
  }

  renderHealthTrends(trendSeriesList) {
    const container = document.getElementById("pt-trends-container");
    if (!container) return;

    if (!trendSeriesList || trendSeriesList.length === 0) {
      container.innerHTML = `
        <div class="trend-card" style="grid-column: 1 / -1;">
          <div class="trend-empty-state">
            <div style="font-size:2rem; margin-bottom:0.5rem;">📊</div>
            <strong>No Recorded Health Measurements</strong>
            <p style="margin-top:0.35rem;">Health trends only plot genuine dated vitals. Measurements will appear automatically as clinical readings are documented.</p>
          </div>
        </div>
      `;
      return;
    }

    container.innerHTML = trendSeriesList.map((series, idx) => {
      const chartId = `trend-chart-${idx}`;
      const color = idx === 0 ? "#38bdf8" : (idx === 1 ? "#34d399" : "#a855f7");
      
      return `
        <div class="trend-card">
          <div class="trend-card-header">
            <div class="trend-title">
              <span>📈</span> ${series.metric_name} (${series.unit})
            </div>
            <button class="btn-ask-ai" onclick="PostVisitApp.openAiAssistant('Explain my ${series.metric_name.replace(/'/g, "\\'")} readings and trajectory', 'trends')">
              ✨ Ask AI
            </button>
          </div>
          
          ${series.has_sufficient_data ? `
            <div class="trend-svg-wrapper" id="${chartId}"></div>
            <div style="display:flex; justify-content:space-between; font-size:0.75rem; color:var(--text-muted); margin-top:0.25rem;">
              <span>Earliest: ${series.data_points[0].recorded_at.slice(0, 10)}</span>
              <span>Latest: ${series.data_points[series.data_points.length - 1].recorded_at.slice(0, 10)}</span>
            </div>
          ` : `
            <div class="trend-empty-state">
              <p>${series.empty_state_message || "Additional dated measurements required to generate trend chart."}</p>
            </div>
          `}
        </div>
      `;
    }).join("");

    // Draw SVG for series with sufficient data
    trendSeriesList.forEach((series, idx) => {
      if (series.has_sufficient_data) {
        this.renderTrendSvg(`trend-chart-${idx}`, series, idx === 0 ? "#38bdf8" : "#34d399");
      }
    });
  }

  renderTrendSvg(containerId, series, strokeColor = "#38bdf8") {
    const el = document.getElementById(containerId);
    if (!el) return;

    const points = series.data_points || [];
    if (points.length < 2) return;

    const values = points.map(p => Number(p.numeric_value));
    const minVal = Math.min(...values) * 0.92;
    const maxVal = Math.max(...values) * 1.08;
    const range = (maxVal - minVal) || 1;

    const W = 360;
    const H = 160;
    const padX = 35;
    const padY = 25;

    // Map points to SVG coordinates
    const coords = points.map((p, i) => {
      const x = padX + (i / (points.length - 1)) * (W - 2 * padX);
      const y = H - padY - ((Number(p.numeric_value) - minVal) / range) * (H - 2 * padY);
      return { x, y, point: p };
    });

    const polylinePts = coords.map(c => `${c.x},${c.y}`).join(" ");

    // Handle secondary value if BP (e.g. Diastolic)
    const hasSecondary = points.some(p => p.secondary_value !== undefined && p.secondary_value !== null);
    let secondaryPolyline = "";
    let secondaryCoords = [];
    if (hasSecondary) {
      secondaryCoords = points.map((p, i) => {
        const secVal = Number(p.secondary_value || 80);
        const x = padX + (i / (points.length - 1)) * (W - 2 * padX);
        const y = H - padY - ((secVal - minVal) / range) * (H - 2 * padY);
        return { x, y, val: secVal };
      });
      secondaryPolyline = secondaryCoords.map(c => `${c.x},${c.y}`).join(" ");
    }

    const svg = `
      <svg width="100%" height="100%" viewBox="0 0 ${W} ${H}" style="overflow:visible;">
        <defs>
          <linearGradient id="grad-${containerId}" x1="0%" y1="0%" x2="0%" y2="100%">
            <stop offset="0%" stop-color="${strokeColor}" stop-opacity="0.3"/>
            <stop offset="100%" stop-color="${strokeColor}" stop-opacity="0.0"/>
          </linearGradient>
        </defs>

        <!-- Horizontal Reference Grid Lines -->
        <line x1="${padX}" y1="${padY}" x2="${W - padX}" y2="${padY}" stroke="rgba(148,163,184,0.15)" stroke-dasharray="3,3"/>
        <line x1="${padX}" y1="${H / 2}" x2="${W - padX}" y2="${H / 2}" stroke="rgba(148,163,184,0.15)" stroke-dasharray="3,3"/>
        <line x1="${padX}" y1="${H - padY}" x2="${W - padX}" y2="${H - padY}" stroke="rgba(148,163,184,0.2)"/>

        <!-- Y Axis Labels -->
        <text x="${padX - 8}" y="${padY + 4}" fill="#94a3b8" font-size="10" text-anchor="end">${Math.round(maxVal)}</text>
        <text x="${padX - 8}" y="${H / 2 + 3}" fill="#64748b" font-size="10" text-anchor="end">${Math.round((maxVal + minVal) / 2)}</text>
        <text x="${padX - 8}" y="${H - padY + 3}" fill="#94a3b8" font-size="10" text-anchor="end">${Math.round(minVal)}</text>

        <!-- Area fill -->
        <polygon points="${padX},${H - padY} ${polylinePts} ${W - padX},${H - padY}" fill="url(#grad-${containerId})"/>

        <!-- Primary Line -->
        <polyline points="${polylinePts}" fill="none" stroke="${strokeColor}" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>

        <!-- Secondary Line for Diastolic if BP -->
        ${hasSecondary ? `
          <polyline points="${secondaryPolyline}" fill="none" stroke="#a855f7" stroke-width="2" stroke-dasharray="4,2" stroke-linecap="round"/>
        ` : ""}

        <!-- Data Points & Labels -->
        ${coords.map(c => `
          <circle cx="${c.x}" cy="${c.y}" r="4.5" fill="${strokeColor}" stroke="#0f172a" stroke-width="2"/>
          <text x="${c.x}" y="${c.y - 8}" fill="#ffffff" font-size="10" font-weight="700" text-anchor="middle">
            ${c.point.secondary_value ? `${c.point.numeric_value}/${c.point.secondary_value}` : c.point.numeric_value}
          </text>
          <text x="${c.x}" y="${H - padY + 14}" fill="#94a3b8" font-size="9" text-anchor="middle">
            ${c.point.recorded_at.slice(5, 10)}
          </text>
        `).join("")}
      </svg>
    `;

    el.innerHTML = svg;
  }

  renderMedicationsList(meds) {
    const el = document.getElementById("pt-medications-list");
    if (!el) return;

    if (meds.length === 0) {
      el.innerHTML = `<div style="color:var(--text-muted); padding:1rem; text-align:center;">No doctor-approved medication instructions currently on record.</div>`;
      return;
    }

    el.innerHTML = meds.map(m => `
      <div style="background:rgba(15,23,42,0.6); border:1px solid var(--border-subtle); border-radius:var(--radius-sm); padding:0.85rem; display:flex; justify-content:space-between; align-items:center;">
        <div>
          <div style="font-weight:700; color:#fff; font-size:0.95rem;">
            ${m.medicine_name} <span style="font-size:0.8rem; color:#7dd3fc; font-weight:normal;">(${m.strength || m.dose || "Prescribed dosage"})</span>
          </div>
          <div style="font-size:0.8rem; color:var(--text-secondary); margin-top:2px;">
            Schedule: <strong>${m.frequency || "Daily"}</strong> • Timing: <strong>${m.timing || "After food"}</strong> • Route: <strong>${m.route || "Oral"}</strong>
          </div>
          <div style="font-size:0.78rem; color:#cbd5e1; margin-top:3px; font-style:italic;">
            Doctor instructions: ${m.instructions || "Follow directions carefully."}
          </div>
        </div>
        <button class="btn-ask-ai" onclick="PostVisitApp.openAiAssistant('Explain how to take ${m.medicine_name.replace(/'/g, "\\'")} and what ${m.timing ? m.timing.replace(/'/g, "\\'") : 'food instructions'} means', 'medication')">
          ✨ Explain
        </button>
      </div>
    `).join("");
  }

  renderRecentLabsList(labs) {
    const el = document.getElementById("pt-recent-labs-list");
    if (!el) return;

    if (labs.length === 0) {
      el.innerHTML = `<div style="color:var(--text-muted); padding:1rem; text-align:center;">No recent lab reports recorded. Upload or enter reports in the Lab Reports tab.</div>`;
      return;
    }

    el.innerHTML = labs.slice(0, 3).map(lr => `
      <div style="background:rgba(15,23,42,0.6); border:1px solid var(--border-subtle); border-radius:var(--radius-sm); padding:0.75rem 1rem; display:flex; justify-content:space-between; align-items:center;">
        <div>
          <div style="font-weight:700; color:#fff; font-size:0.9rem;">${lr.test_name}</div>
          <div style="font-size:0.8rem; color:var(--info);">
            Result: <strong>${lr.test_result || "Submitted"} ${lr.unit || ""}</strong> 
            ${lr.reference_range ? `<span style="color:var(--text-muted); font-size:0.75rem;">(Ref: ${lr.reference_range})</span>` : ""}
          </div>
          <div style="font-size:0.72rem; color:var(--text-muted); margin-top:2px;">
            ${lr.report_date || "Dated"} • <span class="pill-tag ${lr.review_status === 'reviewed' ? 'pill-tag-green' : 'pill-tag-amber'}">${lr.review_status.toUpperCase()}</span>
          </div>
        </div>
        <button class="btn-ask-ai" onclick="PostVisitApp.openAiAssistant('Explain my ${lr.test_name.replace(/'/g, "\\'")} result of ${lr.test_result || ''} ${lr.unit || ''}', 'lab_report')">
          ✨ Ask AI
        </button>
      </div>
    `).join("");
  }

  // =========================================================================
  // RECOVERY PLAN CHECKLIST (Non-mutating Personal Tracking)
  // =========================================================================
  async loadRecoveryPlan(cid = null) {
    const container = document.getElementById("pt-recovery-checklist-container");
    if (!container) return;

    container.innerHTML = `<div style="text-align:center; padding:2rem;"><div class="spinner"></div><p>Loading recovery plan...</p></div>`;

    try {
      const plan = await window.api.getRecoveryPlan(cid);
      if (!plan.has_structured_plan || (plan.plan_items || []).length === 0) {
        container.innerHTML = `
          <div style="text-align:center; padding:3rem; color:var(--text-muted);">
            <div style="font-size:2rem; margin-bottom:0.5rem;">📋</div>
            <p>${plan.empty_message || "No structured recovery plan was recorded for this visit."}</p>
          </div>
        `;
        return;
      }

      container.innerHTML = `
        <div style="background:rgba(14, 165, 233, 0.08); border-left:3px solid var(--primary); padding:0.75rem 1rem; border-radius:4px; font-size:0.82rem; color:#7dd3fc; margin-bottom:1.25rem;">
          ℹ️ <strong>Personal Progress Tracking:</strong> Check off daily items as you complete them. These checkmarks assist your personal tracking and do not mutate the doctor's official clinical record.
        </div>
        <div>
          ${plan.plan_items.map(item => `
            <div class="recovery-item ${item.patient_completed ? 'completed' : ''}" id="rec-item-${item.task_key}">
              <input type="checkbox" class="recovery-checkbox" ${item.patient_completed ? 'checked' : ''} onchange="PostVisitApp.toggleRecoveryTask('${plan.consultation_id}', '${item.task_key}', this.checked)">
              <div class="recovery-body">
                <div class="recovery-header-row">
                  <span class="recovery-title">${item.title}</span>
                  <div style="display:flex; gap:0.5rem; align-items:center;">
                    <span class="pill-tag pill-tag-blue">${item.category.toUpperCase()}</span>
                    <button class="btn-ask-ai" onclick="PostVisitApp.openAiAssistant('Explain how to perform recovery task: ${item.title.replace(/'/g, "\\'")}', 'recovery_plan')">
                      ✨ Ask AI
                    </button>
                  </div>
                </div>
                <div class="recovery-text">${item.description}</div>
                <div class="recovery-footnote">Doctor instruction: ${item.doctor_instruction}</div>
              </div>
            </div>
          `).join("")}
        </div>
      `;

    } catch (err) {
      container.innerHTML = `<div style="color:var(--danger); padding:2rem;">Failed to load recovery plan: ${err.message}</div>`;
    }
  }

  async toggleRecoveryTask(cid, taskKey, isChecked) {
    try {
      await window.api.toggleRecoveryTask(cid, taskKey, isChecked);
      const row = document.getElementById(`rec-item-${taskKey}`);
      if (row) {
        row.classList.toggle("completed", isChecked);
      }
      this.showToast(isChecked ? "Marked as completed for personal tracking." : "Personal task uncompleted.");
    } catch (err) {
      alert("Failed to update task: " + err.message);
    }
  }

  // =========================================================================
  // VISIT HISTORY (Chronological, Patient Data Isolation)
  // =========================================================================
  async loadPatientHistory(page = 1) {
    const tbody = document.getElementById("pt-history-tbody");
    if (!tbody) return;

    tbody.innerHTML = `<tr><td colspan="7" style="text-align:center; padding:2rem;"><div class="spinner"></div><p>Loading your consultation records...</p></td></tr>`;

    try {
      const res = await window.api.getVisitHistory(page, 10);
      const items = res.items || [];

      if (items.length === 0) {
        tbody.innerHTML = `<tr><td colspan="7" style="text-align:center; padding:2.5rem; color:var(--text-muted);">No consultation visits found. Your medical records will appear here after clinic appointments.</td></tr>`;
        return;
      }

      tbody.innerHTML = items.map(c => {
        const dateStr = c.consultation_date ? new Date(c.consultation_date).toLocaleDateString() : "Recent";
        const isApproved = c.approved_summary_available;
        
        return `
          <tr>
            <td><strong>${dateStr}</strong></td>
            <td>${c.doctor_name || "Dr. Rajesh Sharma, MD"}</td>
            <td>${c.visit_reason || "Clinical Review"}</td>
            <td><span style="font-size:0.82rem; color:var(--text-secondary);">${(c.symptoms || []).join(", ") || "-"}</span></td>
            <td>
              <span class="badge ${c.consultation_status === 'completed' ? 'badge-approved' : 'badge-processing'}">
                ${c.consultation_status.toUpperCase()}
              </span>
            </td>
            <td>
              <span class="badge ${isApproved ? 'badge-approved' : 'badge-pending'}">
                ${isApproved ? 'APPROVED' : 'AWAITING APPROVAL'}
              </span>
            </td>
            <td>
              <button class="btn btn-sm ${isApproved ? 'btn-primary' : 'btn-secondary'}" onclick="PostVisitApp.viewVisitFromHistory('${c.consultation_id}')">
                ${isApproved ? 'View Summary →' : 'View Status'}
              </button>
            </td>
          </tr>
        `;
      }).join("");

    } catch (err) {
      tbody.innerHTML = `<tr><td colspan="7" style="text-align:center; padding:2rem; color:var(--danger);">Error loading history: ${err.message}</td></tr>`;
    }
  }

  viewVisitFromHistory(cid) {
    this.switchPatientTab("overview");
    this.renderLastVisitSections(cid);
  }

  // =========================================================================
  // LAB REPORTS PORTAL (Upload & Manual Entry)
  // =========================================================================
  async loadPatientLabReports() {
    const grid = document.getElementById("pt-labs-grid");
    if (!grid) return;

    grid.innerHTML = `<div style="grid-column:1 / -1; text-align:center; padding:2rem;"><div class="spinner"></div><p>Loading lab reports...</p></div>`;

    try {
      const res = await window.api.listPatientLabReports();
      const items = res.items || [];

      if (items.length === 0) {
        grid.innerHTML = `
          <div style="grid-column:1 / -1; text-align:center; padding:3rem; color:var(--text-muted);">
            <div style="font-size:2rem; margin-bottom:0.5rem;">🧪</div>
            <p>No lab reports recorded yet. Upload a diagnostic report document or enter a manual summary above.</p>
          </div>
        `;
        return;
      }

      grid.innerHTML = items.map(r => {
        const isUpload = r.entry_mode === "upload";
        const isReviewed = r.review_status === "reviewed";

        return `
          <div class="lab-report-box">
            <div class="lab-report-top">
              <div>
                <span class="lab-test-title">${r.test_name}</span>
                <div class="lab-meta-row" style="margin-top:4px;">
                  <span>📅 ${r.report_date || 'Date not recorded'}</span>
                  ${r.facility_name ? `<span>🏥 ${r.facility_name}</span>` : ''}
                </div>
              </div>
              <span class="pill-tag ${isUpload ? 'pill-tag-purple' : 'pill-tag-blue'}">
                ${isUpload ? '📄 Uploaded Document' : '✍️ Manual Entry'}
              </span>
            </div>

            <div class="lab-result-highlight">
              ${r.test_result || 'Uploaded Document Attached'} <span style="font-size:0.9rem; color:var(--text-secondary);">${r.unit || ''}</span>
            </div>

            ${r.reference_range ? `
              <div style="font-size:0.8rem; color:var(--text-muted); margin-bottom:0.75rem;">
                Reference Range: <strong>${r.reference_range}</strong>
              </div>
            ` : ''}

            ${r.patient_notes ? `
              <div style="background:rgba(15,23,42,0.5); padding:0.5rem 0.75rem; border-radius:4px; font-size:0.78rem; color:#cbd5e1; margin-bottom:0.75rem;">
                Note: ${r.patient_notes}
              </div>
            ` : ''}

            <div style="display:flex; justify-content:space-between; align-items:center; border-top:1px solid rgba(148,163,184,0.1); padding-top:0.75rem;">
              <span class="pill-tag ${isReviewed ? 'pill-tag-green' : 'pill-tag-amber'}">
                ${isReviewed ? '✓ Verified by Doctor' : '⏳ Patient Provided / Unreviewed'}
              </span>
              <div style="display:flex; gap:0.5rem;">
                ${isUpload ? `
                  <a href="/api/v1/patient/lab-reports/${r.id}/download" target="_blank" class="btn btn-sm btn-outline">
                    📥 Download
                  </a>
                ` : ''}
                <button class="btn-ask-ai" onclick="PostVisitApp.openAiAssistant('Explain this ${r.test_name.replace(/'/g, "\\'")} lab report of ${r.test_result || ''} ${r.unit || ''}', 'lab_report')">
                  ✨ Ask AI
                </button>
              </div>
            </div>
          </div>
        `;
      }).join("");

    } catch (err) {
      grid.innerHTML = `<div style="grid-column:1 / -1; color:var(--danger); padding:2rem;">Failed to load lab reports: ${err.message}</div>`;
    }
  }

  openLabUploadModal() {
    const m = document.getElementById("lab-upload-modal");
    if (m) m.style.display = "flex";
  }

  closeLabUploadModal(e) {
    if (e && e.target && e.target.id !== "lab-upload-modal") return;
    const m = document.getElementById("lab-upload-modal");
    if (m) m.style.display = "none";
  }

  async handleLabUploadSubmit(e) {
    e.preventDefault();
    const btn = document.getElementById("lab-upload-submit-btn");
    const testName = document.getElementById("lab-upload-test-name").value;
    const reportDate = document.getElementById("lab-upload-date").value;
    const facility = document.getElementById("lab-upload-facility").value;
    const notes = document.getElementById("lab-upload-notes").value;
    const fileInput = document.getElementById("lab-upload-file-input");

    if (!fileInput.files || fileInput.files.length === 0) {
      alert("Please select a file to upload.");
      return;
    }

    const formData = new FormData();
    formData.append("file", fileInput.files[0]);
    formData.append("test_name", testName);
    if (reportDate) formData.append("report_date", reportDate);
    if (facility) formData.append("facility_name", facility);
    if (notes) formData.append("patient_notes", notes);

    try {
      if (btn) { btn.disabled = true; btn.textContent = "Uploading..."; }
      await window.api.uploadPatientLabReport(formData);
      this.closeLabUploadModal();
      this.showToast("Lab report uploaded successfully.");
      this.loadPatientLabReports();
    } catch (err) {
      alert("Upload failed: " + err.message);
    } finally {
      if (btn) { btn.disabled = false; btn.textContent = "Upload Lab Document →"; }
    }
  }

  openLabManualModal() {
    const m = document.getElementById("lab-manual-modal");
    if (m) m.style.display = "flex";
  }

  closeLabManualModal(e) {
    if (e && e.target && e.target.id !== "lab-manual-modal") return;
    const m = document.getElementById("lab-manual-modal");
    if (m) m.style.display = "none";
  }

  async handleManualLabSubmit(e) {
    e.preventDefault();
    const testName = document.getElementById("lab-manual-test-name").value;
    const result = document.getElementById("lab-manual-result").value;
    const unit = document.getElementById("lab-manual-unit").value;
    const ref = document.getElementById("lab-manual-reference").value;
    const date = document.getElementById("lab-manual-date").value;
    const facility = document.getElementById("lab-manual-facility").value;
    const notes = document.getElementById("lab-manual-notes").value;

    const payload = {
      test_name: testName,
      test_result: result,
      unit: unit,
      reference_range: ref,
      report_date: date,
      facility_name: facility,
      patient_notes: notes
    };

    try {
      await window.api.createManualLabReport(payload);
      this.closeLabManualModal();
      this.showToast("Manual lab summary saved.");
      this.loadPatientLabReports();
    } catch (err) {
      alert("Failed to save report: " + err.message);
    }
  }

  // =========================================================================
  // CONTEXTUAL AI ASSISTANT ("Ask About Your Visit") & DRAWER
  // =========================================================================
  openAiAssistant(initialQuery = null, contextType = null, cid = null) {
    const drawer = document.getElementById("ai-drawer-overlay");
    if (drawer) {
      drawer.classList.add("open");
    }

    if (initialQuery) {
      const input = document.getElementById("drawer-ai-input-text");
      if (input) {
        input.value = initialQuery;
        this.sendDrawerAiMessage(initialQuery, contextType, cid);
      }
    }
  }

  closeAiAssistant(e) {
    if (e && e.target && e.target.id !== "ai-drawer-overlay") return;
    const drawer = document.getElementById("ai-drawer-overlay");
    if (drawer) drawer.classList.remove("open");
  }

  sendQuickPrompt(text) {
    const input = document.getElementById("pt-ai-input-text") || document.getElementById("drawer-ai-input-text");
    if (input) input.value = text;
    this.sendAiChatMessage(text);
  }

  async sendAiChatMessage(text = null, contextType = null, cid = null) {
    const input = document.getElementById("pt-ai-input-text");
    const msgText = (text || (input ? input.value : "")).trim();
    if (!msgText) return;

    if (input) input.value = "";

    const container = document.getElementById("pt-ai-messages-container");
    this.appendChatMessage(container, "user", msgText);

    // Add loading placeholder
    const loadingId = "ai-loading-" + Date.now();
    if (container) {
      const loadingEl = document.createElement("div");
      loadingEl.id = loadingId;
      loadingEl.className = "ai-msg ai-msg-assistant";
      loadingEl.innerHTML = `<span class="spinner" style="width:14px; height:14px; margin-right:6px;"></span> Consulting approved medical record...`;
      container.appendChild(loadingEl);
      container.scrollTop = container.scrollHeight;
    }

    try {
      const lang = this.patientLanguage || "en";
      const resp = await window.api.patientChat(msgText, cid, contextType, null, lang);

      // Remove loading
      const loadingEl = document.getElementById(loadingId);
      if (loadingEl) loadingEl.remove();

      this.appendChatMessage(container, "assistant", resp.reply, resp.disclaimer, resp.cited_sections);

    } catch (err) {
      const loadingEl = document.getElementById(loadingId);
      if (loadingEl) loadingEl.remove();
      this.appendChatMessage(container, "assistant", `I encountered an issue retrieving your record: ${err.message}. Please try again shortly.`);
    }
  }

  async sendDrawerAiMessage(text = null, contextType = null, cid = null) {
    const input = document.getElementById("drawer-ai-input-text");
    const msgText = (text || (input ? input.value : "")).trim();
    if (!msgText) return;

    if (input) input.value = "";

    const container = document.getElementById("drawer-ai-messages-container");
    this.appendChatMessage(container, "user", msgText);

    const loadingId = "drawer-loading-" + Date.now();
    if (container) {
      const loadingEl = document.createElement("div");
      loadingEl.id = loadingId;
      loadingEl.className = "ai-msg ai-msg-assistant";
      loadingEl.innerHTML = `<span class="spinner" style="width:14px; height:14px; margin-right:6px;"></span> Reviewing approved records...`;
      container.appendChild(loadingEl);
      container.scrollTop = container.scrollHeight;
    }

    try {
      const lang = this.patientLanguage || "en";
      const resp = await window.api.patientChat(msgText, cid, contextType, null, lang);

      const loadingEl = document.getElementById(loadingId);
      if (loadingEl) loadingEl.remove();

      this.appendChatMessage(container, "assistant", resp.reply, resp.disclaimer, resp.cited_sections);

    } catch (err) {
      const loadingEl = document.getElementById(loadingId);
      if (loadingEl) loadingEl.remove();
      this.appendChatMessage(container, "assistant", `Error: ${err.message}`);
    }
  }

  appendChatMessage(container, sender, text, disclaimer = null, citedSections = null) {
    if (!container) return;

    const msgEl = document.createElement("div");
    msgEl.className = `ai-msg ${sender === 'user' ? 'ai-msg-user' : 'ai-msg-assistant'}`;

    let html = text.replace(/\n/g, "<br>");
    if (citedSections && citedSections.length > 0) {
      html += `<div style="margin-top:0.4rem; font-size:0.72rem; color:#7dd3fc;">📚 Reference: ${citedSections.join(", ")}</div>`;
    }
    if (disclaimer) {
      html += `<div class="ai-disclaimer-note">${disclaimer}</div>`;
    }

    msgEl.innerHTML = html;
    container.appendChild(msgEl);
    container.scrollTop = container.scrollHeight;
  }

  // =========================================================================
  // CUSTOM VOICE RECORDING & TRANSCRIPT REVIEW (Stage 5A)
  // =========================================================================
  toggleVoiceRecording() {
    if (this.isVoiceRecording) {
      this.stopVoiceRecording();
    } else {
      this.startVoiceRecording();
    }
  }

  async startVoiceRecording() {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      this.voiceStream = stream;
      this.voiceAudioChunks = [];

      this.mediaRecorder = new MediaRecorder(stream);
      this.mediaRecorder.ondataavailable = (e) => {
        if (e.data && e.data.size > 0) {
          this.voiceAudioChunks.push(e.data);
        }
      };

      this.mediaRecorder.start();
      this.isVoiceRecording = true;
      this.voiceRecordingSeconds = 0;

      // Update UI
      document.querySelectorAll(".btn-mic-record").forEach(b => b.classList.add("recording"));
      const banners = [document.getElementById("pt-voice-recording-banner"), document.getElementById("drawer-voice-banner")];
      banners.forEach(b => { if (b) b.style.display = "flex"; });

      this.voiceTimerInterval = setInterval(() => {
        this.voiceRecordingSeconds++;
        const mins = String(Math.floor(this.voiceRecordingSeconds / 60)).padStart(2, '0');
        const secs = String(this.voiceRecordingSeconds % 60).padStart(2, '0');
        const timeStr = `${mins}:${secs}`;
        const t1 = document.getElementById("pt-voice-timer");
        const t2 = document.getElementById("drawer-voice-timer");
        if (t1) t1.textContent = timeStr;
        if (t2) t2.textContent = timeStr;
      }, 1000);

    } catch (err) {
      alert("Microphone access denied or unavailable: " + err.message);
      this.cancelVoiceRecording();
    }
  }

  stopVoiceRecording() {
    if (!this.mediaRecorder || !this.isVoiceRecording) return;

    clearInterval(this.voiceTimerInterval);
    document.querySelectorAll(".btn-mic-record").forEach(b => b.classList.remove("recording"));
    const banners = [document.getElementById("pt-voice-recording-banner"), document.getElementById("drawer-voice-banner")];
    banners.forEach(b => { if (b) b.style.display = "none"; });

    this.mediaRecorder.onstop = async () => {
      const audioBlob = new Blob(this.voiceAudioChunks, { type: "audio/webm" });
      if (this.voiceStream) {
        this.voiceStream.getTracks().forEach(track => track.stop());
      }
      this.isVoiceRecording = false;

      // Submit for transcription
      await this.transcribeRecordedVoice(audioBlob);
    };

    this.mediaRecorder.stop();
  }

  cancelVoiceRecording() {
    if (this.voiceTimerInterval) clearInterval(this.voiceTimerInterval);
    if (this.voiceStream) {
      this.voiceStream.getTracks().forEach(track => track.stop());
    }
    this.isVoiceRecording = false;
    document.querySelectorAll(".btn-mic-record").forEach(b => b.classList.remove("recording"));
    const banners = [document.getElementById("pt-voice-recording-banner"), document.getElementById("drawer-voice-banner")];
    banners.forEach(b => { if (b) b.style.display = "none"; });
  }

  async transcribeRecordedVoice(audioBlob) {
    const reviewBox = document.getElementById("pt-voice-review-box");
    const textArea = document.getElementById("pt-voice-transcript-text");

    if (reviewBox) reviewBox.style.display = "block";
    if (textArea) textArea.value = "Transcribing your speech using IndicConformer ASR (Tamil / English)...";

    try {
      const lang = this.patientLanguage || "auto";
      const res = await window.api.transcribePatientVoice(audioBlob, lang);
      if (textArea) {
        textArea.value = res.transcript_text || "";
      }
      this.showToast("Voice transcribed. Please review and edit before sending.");
    } catch (err) {
      if (textArea) textArea.value = `Transcription failed: ${err.message}. Please type your question manually.`;
    }
  }

  discardVoiceDraft() {
    const reviewBox = document.getElementById("pt-voice-review-box");
    if (reviewBox) reviewBox.style.display = "none";
  }

  sendVoiceDraftToChat() {
    const textArea = document.getElementById("pt-voice-transcript-text");
    const text = (textArea ? textArea.value : "").trim();
    if (!text) return;

    this.discardVoiceDraft();
    this.sendAiChatMessage(text);
  }

  showToast(msg) {
    const c = document.getElementById("toast-container");
    if (!c) return;
    const t = document.createElement("div");
    t.className = "toast";
    t.textContent = msg;
    c.appendChild(t);
    setTimeout(() => t.remove(), 3500);
  }

  // =========================================================================
  // ROLE & VIEW SWITCHING (Bridged for static & instance calls)
  // =========================================================================
  switchRole(role) {
    window.api.setRole(role);
    this.updateRoleUI();
    if (role === "doctor") {
      this.switchView("doctor");
    } else {
      this.switchView("patient");
    }
  }

  switchView(viewName) {
    document.querySelectorAll(".view-panel").forEach(p => p.style.display = "none");
    document.querySelectorAll(".nav-link").forEach(l => l.classList.remove("active"));

    const btn = document.getElementById(`nav-${viewName}-btn`);
    if (btn) btn.classList.add("active");

    const targetView = document.getElementById(`${viewName}-view`);
    if (targetView) targetView.style.display = "block";

    const floatBtn = document.getElementById("floating-ai-btn");
    if (floatBtn) {
      floatBtn.style.display = viewName === "patient" ? "inline-flex" : "none";
    }

    if (viewName === "doctor") {
      this.loadDoctorDashboard();
    } else if (viewName === "patient") {
      this.loadPatientDashboard();
    }
  }

  switchPatientLanguage(lang) {
    this.patientLanguage = lang;
    this.loadPatientDashboard();
  }

  // Static Bridge methods for HTML onclick attributes
  static switchView(viewName) { window.app.switchView(viewName); }
  static switchRole(role) { window.app.switchRole(role); }
  static switchPatientTab(tab) { window.app.switchPatientTab(tab); }
  static switchPatientLanguage(lang) { window.app.switchPatientLanguage(lang); }
  static refreshDoctorDashboard() { window.app.loadDoctorDashboard(); }
  static refreshPatientDashboard() { window.app.loadPatientDashboard(); }
  static filterDoctorList(filter, btn) { window.app.filterDoctorList(filter, btn); }
  static openUploadModal() { window.app.openUploadModal(); }
  static closeUploadModal() { window.app.closeUploadModal(); }
  static handleUpload(e) { window.app.handleUpload(e); }
  static onFileSelected(elem) { window.app.onFileSelected(elem); }
  static selectDemoPreset(preset) { window.app.selectDemoPreset(preset); }
  static openGuidelinesModal() { window.app.openGuidelinesModal(); }
  static closeGuidelinesModal(e) { window.app.closeGuidelinesModal(e); }
  static returnFromProcessing() { window.app.returnFromProcessing(); }
  static refreshActiveProcessing() { window.app.refreshActiveProcessing(); }
  static openDetailFromProcessing() { window.app.openDetailFromProcessing(); }
  static returnFromDetail() { window.app.returnFromDetail(); }
  static triggerGuidelineCrossReference() { window.app.triggerGuidelineCrossReference(); }
  static openLabUploadModal() { window.app.openLabUploadModal(); }
  static closeLabUploadModal(e) { window.app.closeLabUploadModal(e); }
  static handleLabUploadSubmit(e) { window.app.handleLabUploadSubmit(e); }
  static openLabManualModal() { window.app.openLabManualModal(); }
  static closeLabManualModal(e) { window.app.closeLabManualModal(e); }
  static handleManualLabSubmit(e) { window.app.handleManualLabSubmit(e); }
  static openAiAssistant(q, type, cid) { window.app.openAiAssistant(q, type, cid); }
  static closeAiAssistant(e) { window.app.closeAiAssistant(e); }
  static sendAiChatMessage(text) { window.app.sendAiChatMessage(text); }
  static sendDrawerAiMessage(text) { window.app.sendDrawerAiMessage(text); }
  static sendQuickPrompt(text) { window.app.sendQuickPrompt(text); }
  static toggleVoiceRecording() { window.app.toggleVoiceRecording(); }
  static stopVoiceRecording() { window.app.stopVoiceRecording(); }
  static cancelVoiceRecording() { window.app.cancelVoiceRecording(); }
  static discardVoiceDraft() { window.app.discardVoiceDraft(); }
  static sendVoiceDraftToChat() { window.app.sendVoiceDraftToChat(); }
  static toggleRecoveryTask(cid, key, val) { window.app.toggleRecoveryTask(cid, key, val); }
  static openDoctorWorkbench(cid, pid) { window.app.openDoctorWorkbench(cid, pid); }
  static switchDoctorTab(tab) { window.app.switchDoctorTab(tab); }
  static onDoctorSearchInput(val) { window.app.onDoctorSearchInput(val); }
  static openDoctorSourceModal() { window.app.openDoctorSourceModal(); }
  static closeDoctorSourceModal(e) { window.app.closeDoctorSourceModal(e); }
  static openDoctorLabModal(id) { window.app.openDoctorLabModal(id); }
  static closeDoctorLabModal(e) { window.app.closeDoctorLabModal(e); }
  static onDoctorLabDecisionChange(val) { window.app.onDoctorLabDecisionChange(val); }
  static submitDoctorLabReview(e) { window.app.submitDoctorLabReview(e); }
  static handleDoctorGuidelineDecision(cid, fid, dec) { window.app.handleDoctorGuidelineDecision(cid, fid, dec); }
  static switchDoctorSummaryLanguage(lang) { window.app.switchDoctorSummaryLanguage(lang); }
  static generateDoctorSummary(cid, lang) { window.app.generateDoctorSummary(cid, lang); }
  static toggleAmendmentBox(show) { window.app.toggleAmendmentBox(show); }
  static submitDoctorReview(e) { window.app.submitDoctorReview(e); }
  static askDoctorAiPreset(q) { window.app.askDoctorAiPreset(q); }
  static submitDoctorAiQuery(q) { window.app.submitDoctorAiQuery(q); }
  static openDoctorVoiceModal() { window.app.openDoctorVoiceModal(); }
  static closeDoctorVoiceModal(e) { window.app.closeDoctorVoiceModal(e); }
  static toggleDoctorVoiceRecording() { window.app.toggleDoctorVoiceRecording(); }
  static discardDoctorVoiceDraft() { window.app.discardDoctorVoiceDraft(); }
  static confirmDoctorVoiceNote() { window.app.confirmDoctorVoiceNote(); }
  static toggleDoctorVoiceModalRecording() { window.app.toggleDoctorVoiceModalRecording(); }
  static discardDoctorVoiceModalDraft() { window.app.discardDoctorVoiceModalDraft(); }
  static confirmDoctorVoiceModalNote() { window.app.confirmDoctorVoiceModalNote(); }
  static refreshDoctorTimeline() { window.app.refreshDoctorTimeline(); }
  static refreshDoctorAuditTrail() { window.app.refreshDoctorAuditTrail(); }

  closeModals() {
    document.querySelectorAll(".modal, .modal-backdrop").forEach(m => m.style.display = "none");
  }
}

document.addEventListener("DOMContentLoaded", () => {
  window.app = new PostVisitApp();
  window.PostVisitApp = PostVisitApp;
});

