// Plain-language labels for what the backend sends. The backend names checks
// (check_name) and words its own reasons; this file covers the rest.

const ACRONYMS = { dob: "DOB", crm: "CRM", id: "ID", nbn: "NBN", aud: "AUD", url: "URL" };

// "customer_name" -> "Customer name", "dob" -> "DOB"
export const humanize = (key) =>
  key.split("_").map((w, i) => ACRONYMS[w] ?? (i === 0 ? w.charAt(0).toUpperCase() + w.slice(1) : w)).join(" ");

export const mmss = (s) =>
  s == null ? "--:--" : `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(Math.floor(s % 60)).padStart(2, "0")}`;

export const timeRange = (start, end) =>
  start == null ? null : `${mmss(start)}–${mmss(end)}`;

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const ISO_DATE = /^(\d{4})-(\d{2})-(\d{2})$/;

// "2026-09-19" -> "19 Sep 2026"
export const formatDate = (s) => {
  const m = ISO_DATE.exec(s ?? "");
  return m ? `${Number(m[3])} ${MONTHS[Number(m[2]) - 1]} ${m[1]}` : s;
};

export const formatValue = (v) => {
  if (v === null || v === undefined || v === "") return "—";
  if (typeof v === "boolean") return v ? "Yes" : "No";
  if (typeof v === "object") return JSON.stringify(v);
  return formatDate(String(v));
};

// What each sale outcome means, in the words the QA process uses.
export const DECISION_INFO = {
  AUTO_PASS: {
    title: "Passed", severity: "success",
    text: "Every critical check passed. The sale goes through untouched.",
  },
  HOLD: {
    title: "Held", severity: "error",
    text: "A critical check failed, so the sale is held for the team leader. Fix it or challenge it, then it goes.",
  },
  HUMAN_QA: {
    title: "Needs human review", severity: "warning",
    text: "A result was unclear or low-confidence, so it was routed to QA instead of being passed automatically.",
  },
};

// One check's result. A failed check that is not critical is a coaching note, not a failure.
export const verdictInfo = (v) => {
  if (v.verdict === "pass") return { label: "Passed", color: "success" };
  if (v.verdict === "uncertain") return { label: "Unclear", color: "warning" };
  return v.critical ? { label: "Failed", color: "error" } : { label: "Note", color: "info" };
};

export const TYPE_LABEL = { verbatim: "Script", factual: "Facts", behaviour: "Behaviour" };

export const SPEAKER_LABEL = { AGENT: "Agent", CUSTOMER: "Customer" };

// CRM fields grouped for reading. Fields not listed here fall into "Other".
export const CRM_GROUPS = [
  ["Customer", ["customer_name", "preferred_name", "email", "phone", "dob"]],
  ["Addresses and timing", ["service_address", "delivery_address", "connection_date"]],
  ["Plan sold", ["plan_name", "download_speed", "upload_speed", "introductory_monthly_price",
    "intro_period_months", "standard_monthly_price", "contract_term", "modem", "modem_upfront_cost",
    "minimum_cost", "development_fee", "development_fee_applicable"]],
  ["Current service", ["current_provider", "current_monthly_price", "current_speed", "account_number"]],
  ["Application", ["reference_number"]],
];
