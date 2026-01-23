"use client";

/**
 * features/hr/mock/data.ts
 *
 * Centralized mock data for the HR Suite.
 * Keep it in one place so pages/components can stay focused on rendering.
 */

import type {
  HrCandidate,
  HrOnboardingEmployee,
  HrOpening,
  HrPipelineCard,
  HrPipelineStage,
  HrRunResult,
  HrScreeningRun,
} from "./types";

function iso(minutesAgo: number): string {
  const d = new Date(Date.now() - minutesAgo * 60_000);
  return d.toISOString();
}

export const HR_OPENINGS: HrOpening[] = [
  {
    id: "op_cashier",
    title: "Cashier",
    department: "Front Desk",
    location: "Dariyapur",
    status: "ACTIVE",
    created_at: iso(60 * 24 * 6),
    resumes_count: 42,
    in_pipeline_count: 14,
    last_run_id: "run_001",
  },
  {
    id: "op_sales_associate",
    title: "Sales Associate",
    department: "Grocery",
    location: "Dariyapur",
    status: "ACTIVE",
    created_at: iso(60 * 24 * 12),
    resumes_count: 31,
    in_pipeline_count: 8,
    last_run_id: "run_002",
  },
  {
    id: "op_security",
    title: "Security Guard",
    department: "Operations",
    location: "Dariyapur",
    status: "ARCHIVED",
    created_at: iso(60 * 24 * 40),
    resumes_count: 18,
    in_pipeline_count: 0,
    last_run_id: null,
  },
];

export const HR_RUNS: HrScreeningRun[] = [
  {
    id: "run_002",
    opening_id: "op_sales_associate",
    title: "Monthly refresh — Sales Associate",
    status: "DONE",
    created_at: iso(60 * 12),
    progress_total: 400,
    progress_done: 400,
  },
  {
    id: "run_001",
    opening_id: "op_cashier",
    title: "Top candidates — Cashier",
    status: "DONE",
    created_at: iso(60 * 6),
    progress_total: 400,
    progress_done: 400,
  },
  {
    id: "run_003",
    opening_id: "op_cashier",
    title: "Fast rerun — Cashier",
    status: "RUNNING",
    created_at: iso(18),
    progress_total: 400,
    progress_done: 160,
  },
];

const CANDIDATE_NAMES = [
  "Aamir Khan",
  "Anas Shaikh",
  "Ayesha Patel",
  "Bilal Ansari",
  "Chirag Mehta",
  "Deepak Singh",
  "Farhan Ali",
  "Fiza Khan",
  "Harsh Shah",
  "Irfan Qureshi",
  "Javed Shaikh",
  "Kiran Joshi",
  "Lina Fernandes",
  "Mehul Patel",
  "Naina Verma",
  "Omkar Desai",
  "Priya Nair",
  "Ravi Kumar",
  "Sahil Gupta",
  "Sana Khan",
  "Tanvi Shah",
  "Uday Singh",
  "Vikas Sharma",
  "Yash Patel",
  "Zara Khan",
];

function makeCandidate(openingId: string, i: number): HrCandidate {
  const name = CANDIDATE_NAMES[i % CANDIDATE_NAMES.length]!;
  const score = Math.max(42, Math.min(98, 92 - i * 2));
  const tags = [
    "POS",
    "Customer handling",
    i % 3 === 0 ? "Retail ops" : "Inventory",
    i % 4 === 0 ? "Team lead" : "Shift-ready",
  ].slice(0, 3);

  return {
    id: `resume_${openingId}_${i + 1}`,
    opening_id: openingId,
    name,
    current_title: i % 2 === 0 ? "Retail Associate" : "Cashier",
    score,
    tags,
    one_line_summary:
      "Strong retail fundamentals with consistent customer-facing experience.",
    matched_requirements: [
      "Customer service",
      "POS billing",
      "Shift flexibility",
      i % 2 === 0 ? "Inventory basics" : "Cash handling",
    ].slice(0, 3),
    missing_requirements: [
      i % 3 === 0 ? "High-volume store experience" : "Upselling practice",
    ],
    strengths: ["Clear communication", "Process discipline", "Fast learner"],
    risks: ["Limited leadership evidence", "Short tenures in last role"],
    evidence: [
      {
        claim: "Has POS billing experience",
        quote: "Handled POS billing and daily cash reconciliation",
      },
      {
        claim: "Customer-facing role",
        quote: "Assisted customers with product selection and returns",
      },
    ],
    has_explanation: i % 4 !== 1, // some rows show "Generating…" in UI
  };
}

function makeRunResults(runId: string, openingId: string): HrRunResult[] {
  return Array.from({ length: 18 }).map((_, i) => {
    const candidate = makeCandidate(openingId, i);
    return {
      run_id: runId,
      candidate,
      rank: i + 1,
      retrieval_score: Number((0.92 - i * 0.01).toFixed(3)),
      rerank_score: Number((0.88 - i * 0.012).toFixed(3)),
    };
  });
}

export const HR_RUN_RESULTS_BY_ID: Record<string, HrRunResult[]> = {
  run_001: makeRunResults("run_001", "op_cashier"),
  run_002: makeRunResults("run_002", "op_sales_associate"),
  run_003: makeRunResults("run_003", "op_cashier"),
};

export const HR_PIPELINE_STAGES: HrPipelineStage[] = [
  { key: "applied", name: "Applied", sort_order: 1, is_terminal: false },
  { key: "screened", name: "Screened", sort_order: 2, is_terminal: false },
  { key: "interview", name: "Interview", sort_order: 3, is_terminal: false },
  { key: "offer", name: "Offer", sort_order: 4, is_terminal: false },
  { key: "hired", name: "Hired", sort_order: 5, is_terminal: true },
  { key: "rejected", name: "Rejected", sort_order: 6, is_terminal: true },
];

export const HR_PIPELINE_CARDS: HrPipelineCard[] = [
  { id: "resume_op_cashier_1", stage: "screened", name: "Aamir Khan", score: 92, tags: ["POS", "Retail ops"] },
  { id: "resume_op_cashier_2", stage: "screened", name: "Anas Shaikh", score: 90, tags: ["Inventory", "Shift-ready"] },
  { id: "resume_op_cashier_3", stage: "interview", name: "Ayesha Patel", score: 88, tags: ["Customer handling"] },
  { id: "resume_op_cashier_4", stage: "offer", name: "Bilal Ansari", score: 86, tags: ["POS", "Team lead"] },
  { id: "resume_op_cashier_5", stage: "hired", name: "Chirag Mehta", score: 84, tags: ["Retail ops"] },
  { id: "resume_op_cashier_6", stage: "rejected", name: "Deepak Singh", score: 72, tags: ["Inventory"] },
];

export const HR_ONBOARDING: HrOnboardingEmployee[] = [
  {
    employee_id: "emp_001",
    employee_code: "E101",
    name: "Chirag Mehta",
    department: "Front Desk",
    progress_pct: 72,
    tasks: [
      { id: "t1", title: "Upload ID document", status: "DONE" },
      { id: "t2", title: "Upload signed contract", status: "PENDING" },
      { id: "t3", title: "Collect bank details", status: "PENDING" },
      { id: "t4", title: "Provision mobile access", status: "BLOCKED" },
    ],
    documents: [
      { id: "d1", doc_type: "ID", status: "VERIFIED" },
      { id: "d2", doc_type: "CONTRACT", status: "PENDING" },
      { id: "d3", doc_type: "BANK", status: "PENDING" },
      { id: "d4", doc_type: "PHOTO", status: "UPLOADED" },
    ],
  },
  {
    employee_id: "emp_002",
    employee_code: "E102",
    name: "Ayesha Patel",
    department: "Grocery",
    progress_pct: 36,
    tasks: [
      { id: "t1", title: "Upload ID document", status: "PENDING" },
      { id: "t2", title: "Upload signed contract", status: "PENDING" },
      { id: "t3", title: "Provision mobile access", status: "PENDING" },
    ],
    documents: [
      { id: "d1", doc_type: "ID", status: "PENDING" },
      { id: "d2", doc_type: "CONTRACT", status: "PENDING" },
      { id: "d3", doc_type: "PHOTO", status: "PENDING" },
      { id: "d4", doc_type: "BANK", status: "PENDING" },
    ],
  },
];

export function getOpeningById(id: string): HrOpening | undefined {
  return HR_OPENINGS.find((o) => o.id === id);
}

export function getRunById(id: string): HrScreeningRun | undefined {
  return HR_RUNS.find((r) => r.id === id);
}

export function getRunResults(id: string): HrRunResult[] {
  return HR_RUN_RESULTS_BY_ID[id] ?? [];
}

export function getOnboardingEmployee(employeeId: string): HrOnboardingEmployee | undefined {
  return HR_ONBOARDING.find((e) => e.employee_id === employeeId);
}

