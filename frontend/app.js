// State
let currentScenarios = [];
let currentDraft = null;
let currentProfile = null;
let activeTab = "console";

// DOM Elements
const scenarioDropdown = document.getElementById("scenario-dropdown");
const scenarioNotes = document.getElementById("scenario-notes");
const queueBadge = document.getElementById("queue-badge");

// Initialize on Load
document.addEventListener("DOMContentLoaded", async () => {
  await loadScenarios();
  await loadConfigurations();
  await loadQueue();
  await loadAnalytics();

  // Run initial scenario 1 by default
  if (currentScenarios.length > 0) {
    applyScenario(currentScenarios[0]);
    runGeneration();
  }
});

// Tab Switcher
function switchTab(tabId) {
  activeTab = tabId;
  document.querySelectorAll(".tab-content").forEach((el) => el.classList.remove("active"));
  document.querySelectorAll(".tab-btn").forEach((el) => el.classList.remove("active"));

  const targetContent = document.getElementById(`tab-${tabId}`);
  if (targetContent) targetContent.classList.add("active");

  const btnIndex = ["console", "queue", "policies", "analytics", "evaluation"].indexOf(tabId);
  const btns = document.querySelectorAll(".tab-btn");
  if (btns[btnIndex]) btns[btnIndex].classList.add("active");

  if (tabId === "queue") loadQueue();
  if (tabId === "analytics") {
    loadAnalytics();
    loadAudit();
  }
}

// Scenarios
async function loadScenarios() {
  try {
    const res = await fetch("/api/scenarios");
    currentScenarios = await res.json();
    scenarioDropdown.innerHTML = '<option value="">-- Choose a Preloaded Scenario --</option>';
    currentScenarios.forEach((sc, idx) => {
      const opt = document.createElement("option");
      opt.value = sc.scenario_id;
      opt.textContent = `${idx + 1}. ${sc.scenario_title} [${sc.expected_segment}]`;
      scenarioDropdown.appendChild(opt);
    });
  } catch (err) {
    console.error("Error loading scenarios:", err);
  }
}

function onScenarioSelect() {
  const selectedId = scenarioDropdown.value;
  const sc = currentScenarios.find((s) => s.scenario_id === selectedId);
  if (sc) {
    applyScenario(sc);
    runGeneration();
  }
}

function applyScenario(sc) {
  scenarioNotes.innerHTML = `<strong>${sc.scenario_title}</strong>: ${sc.description}<br/><em style="color:#38bdf8;">Expected: ${sc.expected_action}</em>`;
  const p = sc.profile;

  document.getElementById("cust-id").value = p.customer_id;
  document.getElementById("cust-name").value = p.full_name;
  document.getElementById("cust-email").value = p.email;
  document.getElementById("cust-plan").value = p.engagement.current_plan_name;
  document.getElementById("cust-tier").value = p.engagement.loyalty_tier;
  document.getElementById("cust-tenure").value = p.engagement.tenure_months;
  document.getElementById("cust-spend").value = p.engagement.monthly_spend;
  document.getElementById("cust-trend").value = p.engagement.usage_trend_pct;
  document.getElementById("cust-inactive").value = p.engagement.days_since_last_activity;
  document.getElementById("cust-overdue-amt").value = p.billing.outstanding_balance;
  document.getElementById("cust-overdue-days").value = p.billing.days_overdue;
  document.getElementById("cust-due-date").value = p.billing.due_date || "2026-11-28";
  document.getElementById("cust-csat").value = p.engagement.csat_score || 8.0;
  document.getElementById("cust-opt-in").checked = p.communication.email_opt_in;
}

function getFormProfile() {
  return {
    customer_id: document.getElementById("cust-id").value,
    full_name: document.getElementById("cust-name").value,
    email: document.getElementById("cust-email").value,
    account_type: "POSTPAID_MOBILE",
    billing: {
      outstanding_balance: parseFloat(document.getElementById("cust-overdue-amt").value) || 0.0,
      days_overdue: parseInt(document.getElementById("cust-overdue-days").value) || 0,
      invoice_number: `INV-${document.getElementById("cust-id").value}`,
      due_date: document.getElementById("cust-due-date").value || null,
      late_payment_count_12m: parseInt(document.getElementById("cust-overdue-days").value) > 0 ? 1 : 0
    },
    engagement: {
      tenure_months: parseInt(document.getElementById("cust-tenure").value) || 0,
      current_plan_name: document.getElementById("cust-plan").value,
      monthly_spend: parseFloat(document.getElementById("cust-spend").value) || 0.0,
      loyalty_tier: document.getElementById("cust-tier").value,
      csat_score: parseFloat(document.getElementById("cust-csat").value) || 8.0,
      usage_trend_pct: parseFloat(document.getElementById("cust-trend").value) || 0.0,
      days_since_last_activity: parseInt(document.getElementById("cust-inactive").value) || 0
    },
    communication: {
      last_contact_date: "2026-10-01",
      email_opt_in: document.getElementById("cust-opt-in").checked,
      sms_opt_in: true
    },
    tags: []
  };
}

function resetForm() {
  if (currentScenarios.length > 0) {
    applyScenario(currentScenarios[0]);
    scenarioDropdown.value = currentScenarios[0].scenario_id;
    runGeneration();
  }
}

// Generate & Review Workflow
async function runGeneration() {
  const btn = document.getElementById("btn-run");
  btn.disabled = true;
  btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Processing Grounded Draft...';

  try {
    currentProfile = getFormProfile();
    const res = await fetch("/api/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ profile: currentProfile })
    });

    if (!res.ok) {
      throw new Error(`Generation failed with status ${res.status}`);
    }

    currentDraft = await res.json();
    renderConsole(currentDraft);
    await loadQueue();
  } catch (err) {
    alert("Error executing generation pipeline: " + err.message);
  } finally {
    btn.disabled = false;
    btn.innerHTML = '<i class="fa-solid fa-play"></i> Classify & Generate Draft';
  }
}

function renderConsole(draft) {
  // Classification badge & Segment
  document.getElementById("draft-id-tag").textContent = draft.draft_id;
  document.getElementById("res-segment-name").textContent = formatSegmentName(draft.primary_segment);
  
  // Strategy & Tone
  document.getElementById("res-strategy-obj").textContent = draft.strategy_objective;
  document.getElementById("res-strategy-tone").textContent = draft.tone;

  const reminderRow = document.getElementById("res-reminder-stage-row");
  if (draft.primary_segment === "payment_reminder") {
    reminderRow.style.display = "flex";
    const days = currentProfile.billing.days_overdue;
    const stageStr = days <= 15 ? "Stage 1 (Courteous)" : (days <= 30 ? "Stage 2 (Urgent)" : "Stage 3 (Final Notice)");
    document.getElementById("res-reminder-stage").textContent = stageStr;
  } else {
    reminderRow.style.display = "none";
  }

  // Offer
  const offerRow = document.getElementById("res-offer-row");
  if (draft.offer) {
    offerRow.style.display = "block";
    document.getElementById("res-offer-name").textContent = draft.offer.name;
    document.getElementById("res-offer-terms").textContent = `${draft.offer.value_description} | Code: ${draft.offer.offer_id} (Expires ${draft.offer.expiry_date})`;
  } else {
    offerRow.style.display = "none";
  }

  // Render Reason Codes
  renderReasonCodes(draft.primary_segment);

  // Email Preview
  document.getElementById("preview-to").textContent = draft.recipient_email;
  document.getElementById("preview-plan").textContent = currentProfile.engagement.current_plan_name;
  document.getElementById("preview-subject").textContent = draft.subject;
  document.getElementById("preview-body").textContent = draft.body_text;

  // Status Badge
  const statusBadge = document.getElementById("draft-status-badge");
  statusBadge.textContent = draft.status;
  statusBadge.className = `pill ${getStatusPillClass(draft.status)}`;

  // Guardrails
  renderGuardrails(draft.validation);

  // Action Buttons state
  const isApproved = draft.status === "APPROVED";
  const isDelivered = draft.status === "DELIVERED";
  const isBlocked = draft.status === "BLOCKED";

  document.getElementById("btn-approve").disabled = isApproved || isDelivered || isBlocked;
  document.getElementById("btn-edit").disabled = isDelivered;
  document.getElementById("btn-reject").disabled = draft.status === "REJECTED" || isDelivered;
  
  const deliverBtn = document.getElementById("btn-deliver");
  deliverBtn.disabled = !isApproved || isDelivered || isBlocked;
  deliverBtn.innerHTML = isDelivered ? '<i class="fa-solid fa-check-double"></i> Delivered' : '<i class="fa-solid fa-paper-plane"></i> Mock Send';
}

function renderReasonCodes(segment) {
  const container = document.getElementById("reason-codes-container");
  container.innerHTML = "";

  const reasons = [];
  if (segment === "payment_reminder") {
    reasons.push({
      code: "BILLING_OVERDUE_BALANCE",
      text: `Account has unpaid balance of $${currentProfile.billing.outstanding_balance.toFixed(2)} overdue by ${currentProfile.billing.days_overdue} days.`
    });
    reasons.push({
      code: "PROMOTIONAL_OFFERS_PROHIBITED",
      text: "Hard policy prohibition: Incompatible to offer gifts while invoice is past due."
    });
  } else if (segment === "loyalty_candidate") {
    reasons.push({
      code: "TENURE_LOYALTY_QUALIFIED",
      text: `Customer tenure of ${currentProfile.engagement.tenure_months} months meets VIP qualification threshold (>=12m).`
    });
    reasons.push({
      code: "HIGH_SPEND_OR_TIER",
      text: `Customer spend of $${currentProfile.engagement.monthly_spend.toFixed(2)} with tier ${currentProfile.engagement.loyalty_tier}.`
    });
  } else if (segment === "declining_activity") {
    reasons.push({
      code: "USAGE_TREND_DECLINE",
      text: `Usage dropped by ${Math.abs(currentProfile.engagement.usage_trend_pct)}% over past 90 days (threshold: -20%).`
    });
  } else if (segment === "dormant") {
    reasons.push({
      code: "INACTIVITY_EXCEEDED",
      text: `Zero customer activity for ${currentProfile.engagement.days_since_last_activity} days (>45 days limit).`
    });
  } else {
    reasons.push({
      code: "STABLE_ENGAGEMENT",
      text: `Stable usage trend (${currentProfile.engagement.usage_trend_pct}%) with regular payments and ${currentProfile.engagement.tenure_months}m tenure.`
    });
  }

  reasons.forEach((r) => {
    const box = document.createElement("div");
    box.className = "reason-box";
    box.innerHTML = `<span class="reason-code-badge">${r.code}</span><div>${r.text}</div>`;
    container.appendChild(box);
  });
}

function renderGuardrails(validation) {
  const container = document.getElementById("guardrails-container");
  container.innerHTML = "";

  const summaryPill = document.getElementById("guardrail-summary-pill");
  if (!validation.can_deliver) {
    summaryPill.className = "pill pill-red";
    summaryPill.textContent = `${validation.critical_count} Critical Violation(s)`;
  } else if (validation.warning_count > 0) {
    summaryPill.className = "pill pill-amber";
    summaryPill.textContent = `${validation.warning_count} Warning(s)`;
  } else {
    summaryPill.className = "pill pill-green";
    summaryPill.textContent = "All 6 Guardrails Passed";
  }

  validation.checks.forEach((c) => {
    const item = document.createElement("div");
    const statusClass = !c.passed ? (c.severity === "CRITICAL" ? "critical" : "warning") : "passed";
    const icon = !c.passed ? '<i class="fa-solid fa-triangle-exclamation"></i>' : '<i class="fa-solid fa-circle-check"></i>';

    item.className = `guardrail-item ${statusClass}`;
    item.innerHTML = `
      <div style="font-size:1.1rem; margin-top:0.1rem;">${icon}</div>
      <div>
        <div style="font-weight:600; display:flex; gap:0.4rem; align-items:center;">
          <span>${c.check_name}</span>
          <span style="font-size:0.65rem; padding:0.1rem 0.3rem; border-radius:0.2rem; background:rgba(255,255,255,0.1);">${c.category}</span>
        </div>
        <div style="font-size:0.75rem; margin-top:0.2rem;">${c.message}</div>
      </div>
    `;
    container.appendChild(item);
  });
}

// Helpers
function formatSegmentName(key) {
  const map = {
    consistent: "Consistent & Reliable Customer",
    loyalty_candidate: "Loyalty & VIP Candidate",
    declining_activity: "Declining Activity",
    dormant: "Dormant / Inactive Customer",
    payment_reminder: "Payment Follow-up / Overdue"
  };
  return map[key] || key;
}

function getStatusPillClass(st) {
  if (st === "APPROVED") return "pill-green";
  if (st === "DELIVERED") return "pill-green";
  if (st === "BLOCKED") return "pill-red";
  if (st === "REJECTED") return "pill-red";
  return "pill-amber";
}

// Modal Handlers
function closeModal(id) {
  document.getElementById(id).classList.remove("active");
}

function openApproveModal() {
  document.getElementById("modal-approve").classList.add("active");
}

async function submitApproval() {
  if (!currentDraft) return;
  const feedback = {
    reviewer_id: "reviewer_supervisor_1",
    action: "APPROVE",
    rating_relevance: parseInt(document.getElementById("rubric-relevance").value) || 5,
    rating_clarity: parseInt(document.getElementById("rubric-clarity").value) || 5,
    rating_tone: parseInt(document.getElementById("rubric-tone").value) || 5,
    rating_cta: parseInt(document.getElementById("rubric-cta").value) || 5,
    notes: document.getElementById("rubric-notes").value || "Approved without edits."
  };

  try {
    const res = await fetch(`/api/drafts/${currentDraft.draft_id}/approve`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(feedback)
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Approval failed.");
    }

    currentDraft = await res.json();
    closeModal("modal-approve");
    renderConsole(currentDraft);
    await loadQueue();
    alert("Draft approved successfully! It is now unlocked for mock delivery.");
  } catch (e) {
    alert("Approval blocked: " + e.message);
  }
}

function openEditModal() {
  if (!currentDraft) return;
  document.getElementById("edit-subject").value = currentDraft.subject;
  document.getElementById("edit-body").value = currentDraft.body_text;
  document.getElementById("modal-edit").classList.add("active");
}

async function submitEdit() {
  if (!currentDraft) return;
  const newSubject = document.getElementById("edit-subject").value;
  const newBody = document.getElementById("edit-body").value;
  const notes = document.getElementById("edit-notes").value;

  try {
    const res = await fetch(`/api/drafts/${currentDraft.draft_id}/edit`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        subject: newSubject,
        body: newBody,
        reviewer_id: "reviewer_supervisor_1",
        notes: notes || "Edited by supervisor"
      })
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Edit failed.");
    }

    currentDraft = await res.json();
    closeModal("modal-edit");
    renderConsole(currentDraft);
    await loadQueue();
    alert("Draft updated! Guardrails automatically re-evaluated the modified text.");
  } catch (e) {
    alert("Edit error: " + e.message);
  }
}

function openRejectModal() {
  document.getElementById("modal-reject").classList.add("active");
}

async function submitRejection() {
  if (!currentDraft) return;
  const reason = document.getElementById("reject-reason").value;
  const notes = document.getElementById("reject-notes").value;

  const feedback = {
    reviewer_id: "reviewer_supervisor_1",
    action: "REJECT",
    rejection_reason: reason,
    notes: notes
  };

  try {
    const res = await fetch(`/api/drafts/${currentDraft.draft_id}/reject`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(feedback)
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Rejection failed.");
    }

    currentDraft = await res.json();
    closeModal("modal-reject");
    renderConsole(currentDraft);
    await loadQueue();
    alert("Draft rejected.");
  } catch (e) {
    alert("Rejection error: " + e.message);
  }
}

async function deliverActiveDraft() {
  if (!currentDraft) return;
  try {
    const res = await fetch(`/api/drafts/${currentDraft.draft_id}/deliver`, {
      method: "POST"
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Delivery refused.");
    }

    const data = await res.json();
    currentDraft.status = "DELIVERED";
    renderConsole(currentDraft);
    await loadQueue();
    await loadAnalytics();

    // Show Receipt Modal
    const rc = data.receipt;
    document.getElementById("delivery-receipt-details").innerHTML = `
      <p><strong>Tracking ID:</strong> <code>${rc.tracking_id}</code></p>
      <p><strong>Delivery ID:</strong> <code>${rc.delivery_id}</code></p>
      <p><strong>Recipient:</strong> ${rc.recipient_email}</p>
      <p><strong>Subject:</strong> ${rc.subject}</p>
      <p><strong>Timestamp:</strong> ${rc.dispatched_at}</p>
      <p><strong>Payload Size:</strong> ${rc.message_size_bytes} bytes</p>
      <p style="margin-top:0.75rem; color:#34d399;"><i class="fa-solid fa-circle-check"></i> Guardrails verified. Delivery receipt registered to audit trail.</p>
    `;
    document.getElementById("modal-delivery").classList.add("active");
  } catch (e) {
    alert("DELIVERY GATE REFUSAL: " + e.message);
  }
}

// Queue
async function loadQueue() {
  try {
    const statusFilter = document.getElementById("filter-queue-status").value;
    const url = statusFilter ? `/api/drafts?status=${statusFilter}` : "/api/drafts";
    const res = await fetch(url);
    const drafts = await res.json();

    const tbody = document.getElementById("queue-tbody");
    tbody.innerHTML = "";

    // Count pending
    const pendingCount = drafts.filter((d) => d.status === "PENDING_REVIEW").length;
    queueBadge.textContent = pendingCount;

    if (drafts.length === 0) {
      tbody.innerHTML = '<tr><td colspan="9" style="text-align:center; color:var(--text-muted); padding:2rem;">No drafts in review queue.</td></tr>';
      return;
    }

    drafts.forEach((d) => {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td style="font-family:monospace; color:#38bdf8;">${d.draft_id}</td>
        <td><strong>${d.customer_name}</strong><br/><span style="font-size:0.75rem; color:var(--text-muted);">${d.recipient_email}</span></td>
        <td><span class="pill pill-blue">${d.primary_segment}</span></td>
        <td style="font-size:0.75rem;">${d.strategy_objective}</td>
        <td style="max-width:200px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">${d.subject}</td>
        <td><span class="pill ${d.validation.can_deliver ? 'pill-green' : 'pill-red'}">${d.validation.can_deliver ? 'Passed' : 'Blocked'}</span></td>
        <td><span class="pill ${getStatusPillClass(d.status)}">${d.status}</span></td>
        <td style="font-size:0.75rem; color:var(--text-muted);">${d.created_at}</td>
        <td>
          <button class="btn btn-secondary" style="font-size:0.75rem; padding:0.25rem 0.5rem;" onclick="loadDraftToConsole('${d.draft_id}')">
            <i class="fa-solid fa-arrow-up-right-from-square"></i> Inspect
          </button>
        </td>
      `;
      tbody.appendChild(tr);
    });
  } catch (err) {
    console.error("Error loading review queue:", err);
  }
}

async function loadDraftToConsole(draftId) {
  try {
    const res = await fetch(`/api/drafts/${draftId}`);
    if (!res.ok) throw new Error("Could not find draft");
    currentDraft = await res.json();

    // Populate customer form if matching customer exists
    const matching = currentScenarios.find((s) => s.profile.customer_id === currentDraft.customer_id);
    if (matching) {
      applyScenario(matching);
    }

    switchTab("console");
    renderConsole(currentDraft);
  } catch (e) {
    alert("Error loading draft: " + e.message);
  }
}

// Config tab
async function loadConfigurations() {
  try {
    const res = await fetch("/api/config");
    const data = await res.json();
    document.getElementById("policies-json-view").textContent = JSON.stringify(data.policies, null, 2);
    document.getElementById("campaigns-json-view").textContent = JSON.stringify(data.campaigns, null, 2);
  } catch (e) {
    console.error("Config fetch error:", e);
  }
}

// Analytics & Audit
async function loadAnalytics() {
  try {
    const res = await fetch("/api/observability");
    const data = await res.json();
    document.getElementById("stat-total").textContent = data.total_drafts_processed;
    document.getElementById("stat-pass-rate").textContent = `${data.guardrail_pass_rate_pct}%`;
    document.getElementById("stat-approval-rate").textContent = `${data.reviewer_approval_rate_pct}%`;
    document.getElementById("stat-delivered").textContent = data.delivered_count;
  } catch (e) {
    console.error("Error loading analytics:", e);
  }
}

async function loadAudit() {
  try {
    const res = await fetch("/api/audit");
    const entries = await res.json();
    const tbody = document.getElementById("audit-tbody");
    tbody.innerHTML = "";

    if (entries.length === 0) {
      tbody.innerHTML = '<tr><td colspan="8" style="text-align:center; color:var(--text-muted); padding:2rem;">No audit records found.</td></tr>';
      return;
    }

    entries.forEach((e) => {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td style="font-family:monospace; color:#38bdf8;">${e.audit_id}</td>
        <td style="font-size:0.75rem; color:var(--text-muted);">${e.timestamp}</td>
        <td><code>${e.customer_email_masked}</code> (${e.customer_id})</td>
        <td><span class="pill pill-blue">${e.primary_segment}</span></td>
        <td style="font-size:0.75rem;">${e.model_version}</td>
        <td style="font-size:0.75rem; max-width:240px;">${e.guardrail_verdict}</td>
        <td>${e.reviewer_action ? `<span class="pill pill-green">${e.reviewer_action}</span>` : '<span style="color:var(--text-muted);">None</span>'}</td>
        <td><span class="pill ${getStatusPillClass(e.send_status)}">${e.send_status}</span></td>
      `;
      tbody.appendChild(tr);
    });
  } catch (e) {
    console.error("Error loading audit entries:", e);
  }
}
