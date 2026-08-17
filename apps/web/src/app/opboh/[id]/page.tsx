"use client";

import { useEffect, useState, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import { useActor } from "@/lib/actor";
import {
  api,
  ApiError,
  DomainWithQuestions,
  OpbohAssessment,
  ResponseOut,
} from "@/lib/api";

const STATUS_LABEL: Record<string, string> = {
  draft: "Draft",
  evidence_requested: "Evidence Requested",
  submitted: "Submitted",
  under_assessment: "Under Assessment",
  clarification_requested: "Clarification Requested",
  independently_reviewed: "Independently Reviewed",
  conditionally_accepted: "Conditionally Accepted",
  accepted: "Accepted",
  rejected: "Rejected",
  reopened: "Reopened",
  superseded: "Superseded",
};

export default function AssessmentPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const { actor } = useActor();

  const [assessment, setAssessment] = useState<OpbohAssessment | null>(null);
  const [domains, setDomains] = useState<DomainWithQuestions[]>([]);
  const [responses, setResponses] = useState<Record<string, ResponseOut>>({});
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [decisionSummary, setDecisionSummary] = useState("");
  const [reopenReason, setReopenReason] = useState("");

  const load = useCallback(async () => {
    const a = await api.getAssessment(actor, id);
    setAssessment(a);
    const d = await api.getCatalogue(actor, a.framework_version_id);
    setDomains(d);
    if (expanded.size === 0 && d.length > 0) setExpanded(new Set([d[0].id]));
  }, [actor, id]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    // Standard fetch-on-mount error handling, same reasoning
    // app/page.tsx documents.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    load().catch((e) => setError(e instanceof ApiError ? e.message : String(e)));
  }, [load]);

  const totalQuestions = domains.reduce((n, d) => n + d.questions.length, 0);
  const answeredCount = Object.keys(responses).length;

  async function answer(questionId: string, value: "yes" | "no" | "not_applicable", score: number) {
    if (!assessment) return;
    try {
      const r = await api.upsertResponse(actor, assessment.id, {
        question_id: questionId,
        response_value: value,
        score,
        evidence_sufficiency_factor: 1.0,
      });
      setResponses((prev) => ({ ...prev, [questionId]: r }));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not save response.");
    }
  }

  async function quickFillRemaining() {
    if (!assessment) return;
    setBusy(true);
    setError(null);
    try {
      const unanswered = domains
        .flatMap((d) => d.questions)
        .filter((q) => !responses[q.id]);
      const results = await Promise.all(
        unanswered.map((q) =>
          api.upsertResponse(actor, assessment.id, {
            question_id: q.id,
            response_value: "yes",
            score: 5,
            evidence_sufficiency_factor: 1.0,
          })
        )
      );
      setResponses((prev) => {
        const next = { ...prev };
        for (const r of results) next[r.question_id] = r;
        return next;
      });
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Quick-fill failed.");
    } finally {
      setBusy(false);
    }
  }

  async function runAction(fn: () => Promise<OpbohAssessment>) {
    setBusy(true);
    setError(null);
    try {
      const updated = await fn();
      setAssessment(updated);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Action failed.");
    } finally {
      setBusy(false);
    }
  }

  if (!assessment) {
    return <p className="text-slate-500">{error ?? "Loading…"}</p>;
  }

  const status = assessment.status;

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-xs uppercase tracking-wide text-slate-400 mb-1">
            OPBOH Assessment
          </p>
          <h1 className="text-2xl font-bold text-[#0B1F3A]">
            {answeredCount} / {totalQuestions} questions answered
          </h1>
        </div>
        <StatusBadge status={status} />
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-800 text-sm rounded-lg px-4 py-3">
          {error}
        </div>
      )}

      <div className="bg-white border border-slate-200 rounded-xl p-5 flex flex-wrap items-center gap-3">
        <span className="text-sm text-slate-500 mr-2">
          Prepared by <b>{assessment.prepared_by}</b>
          {assessment.assessed_by && (
            <>
              {" "}
              · Assessed by <b>{assessment.assessed_by}</b>
            </>
          )}
          {assessment.reviewed_by && (
            <>
              {" "}
              · Reviewed by <b>{assessment.reviewed_by}</b>
            </>
          )}
        </span>
        <div className="flex-1" />

        {status === "draft" && (
          <>
            <button
              disabled={busy || answeredCount === 0}
              onClick={quickFillRemaining}
              className="px-3 py-2 rounded-lg border border-slate-300 text-slate-600 text-sm hover:bg-slate-50 disabled:opacity-50"
            >
              Quick-fill remaining as Yes
            </button>
            <button
              disabled={busy || answeredCount === 0}
              onClick={() => runAction(() => api.submitAssessment(actor, assessment.id))}
              className="px-4 py-2 rounded-lg bg-[#1F5A94] text-white text-sm font-medium hover:bg-[#164572] disabled:opacity-50"
            >
              Submit
            </button>
          </>
        )}
        {status === "submitted" && (
          <button
            disabled={busy}
            onClick={() => runAction(() => api.beginAssessment(actor, assessment.id))}
            className="px-4 py-2 rounded-lg bg-[#1F5A94] text-white text-sm font-medium hover:bg-[#164572] disabled:opacity-50"
          >
            Begin Assessment (as {actor})
          </button>
        )}
        {status === "under_assessment" && (
          <button
            disabled={busy}
            onClick={() => runAction(() => api.independentlyReview(actor, assessment.id))}
            className="px-4 py-2 rounded-lg bg-[#1F5A94] text-white text-sm font-medium hover:bg-[#164572] disabled:opacity-50"
          >
            Independently Review (as {actor})
          </button>
        )}
        {status === "independently_reviewed" && (
          <div className="flex flex-wrap items-center gap-2 w-full justify-end">
            <input
              value={decisionSummary}
              onChange={(e) => setDecisionSummary(e.target.value)}
              placeholder="Decision summary (optional)"
              className="border border-slate-300 rounded-lg px-3 py-2 text-sm w-64"
            />
            <button
              disabled={busy}
              onClick={() =>
                runAction(() =>
                  api.decide(actor, assessment.id, "accepted", decisionSummary || undefined)
                )
              }
              className="px-3 py-2 rounded-lg bg-emerald-600 text-white text-sm font-medium hover:bg-emerald-700 disabled:opacity-50"
            >
              Accept
            </button>
            <button
              disabled={busy}
              onClick={() =>
                runAction(() =>
                  api.decide(
                    actor,
                    assessment.id,
                    "conditionally_accepted",
                    decisionSummary || undefined
                  )
                )
              }
              className="px-3 py-2 rounded-lg bg-amber-500 text-white text-sm font-medium hover:bg-amber-600 disabled:opacity-50"
            >
              Accept with Conditions
            </button>
            <button
              disabled={busy}
              onClick={() =>
                runAction(() =>
                  api.decide(actor, assessment.id, "rejected", decisionSummary || undefined)
                )
              }
              className="px-3 py-2 rounded-lg bg-red-600 text-white text-sm font-medium hover:bg-red-700 disabled:opacity-50"
            >
              Reject
            </button>
          </div>
        )}
        {(status === "accepted" ||
          status === "conditionally_accepted" ||
          status === "rejected") && (
          <>
            <button
              onClick={() => router.push(`/opboh/${assessment.id}/report`)}
              className="px-4 py-2 rounded-lg bg-[#0B1F3A] text-white text-sm font-medium hover:bg-[#132c52]"
            >
              View Bill of Health Report
            </button>
            <div className="flex items-center gap-2">
              <input
                value={reopenReason}
                onChange={(e) => setReopenReason(e.target.value)}
                placeholder="Reason to reopen"
                className="border border-slate-300 rounded-lg px-3 py-2 text-sm w-56"
              />
              <button
                disabled={busy || !reopenReason.trim()}
                onClick={() =>
                  runAction(() => api.reopen(actor, assessment.id, reopenReason.trim()))
                }
                className="px-3 py-2 rounded-lg border border-slate-300 text-slate-600 text-sm hover:bg-slate-50 disabled:opacity-50"
              >
                Reopen
              </button>
            </div>
          </>
        )}
      </div>

      <div className="space-y-3">
        {domains.map((domain) => {
          const domainAnswered = domain.questions.filter((q) => responses[q.id]).length;
          const isOpen = expanded.has(domain.id);
          return (
            <div key={domain.id} className="bg-white border border-slate-200 rounded-xl">
              <button
                onClick={() =>
                  setExpanded((prev) => {
                    const next = new Set(prev);
                    if (next.has(domain.id)) next.delete(domain.id);
                    else next.add(domain.id);
                    return next;
                  })
                }
                className="w-full flex items-center justify-between px-5 py-4 text-left"
              >
                <div>
                  <span className="text-xs text-[#1F5A94] font-mono mr-2">{domain.code}</span>
                  <span className="font-semibold text-[#0B1F3A]">{domain.name}</span>
                </div>
                <span className="text-sm text-slate-400">
                  {domainAnswered}/{domain.questions.length} · {isOpen ? "▲" : "▼"}
                </span>
              </button>
              {isOpen && (
                <div className="border-t border-slate-100 divide-y divide-slate-100">
                  {domain.questions.map((q) => {
                    const r = responses[q.id];
                    return (
                      <div key={q.id} className="px-5 py-4 flex items-start justify-between gap-4">
                        <div>
                          <p className="text-sm font-medium text-slate-800">
                            {q.control_objective}
                            {q.is_critical_control && (
                              <span className="ml-2 text-[10px] uppercase tracking-wide bg-red-100 text-red-700 px-1.5 py-0.5 rounded">
                                Critical
                              </span>
                            )}
                          </p>
                          <p className="text-xs text-slate-500 mt-0.5">{q.question_text}</p>
                          {q.evidence_type_hint && (
                            <p className="text-[11px] text-slate-400 mt-1">
                              Evidence: {q.evidence_type_hint}
                            </p>
                          )}
                        </div>
                        <div className="flex gap-1.5 shrink-0">
                          <AnswerButton
                            label="Yes"
                            active={r?.response_value === "yes"}
                            disabled={status !== "draft"}
                            onClick={() => answer(q.id, "yes", 5)}
                          />
                          <AnswerButton
                            label="No"
                            active={r?.response_value === "no"}
                            disabled={status !== "draft"}
                            danger
                            onClick={() => answer(q.id, "no", 0)}
                          />
                          <AnswerButton
                            label="N/A"
                            active={r?.response_value === "not_applicable"}
                            disabled={status !== "draft"}
                            onClick={() => answer(q.id, "not_applicable", 0)}
                          />
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

function AnswerButton({
  label,
  active,
  onClick,
  disabled,
  danger,
}: {
  label: string;
  active?: boolean;
  onClick: () => void;
  disabled?: boolean;
  danger?: boolean;
}) {
  return (
    <button
      disabled={disabled}
      onClick={onClick}
      className={`px-3 py-1.5 rounded-md text-xs font-semibold border transition-colors disabled:opacity-40 disabled:cursor-not-allowed ${
        active
          ? danger
            ? "bg-red-600 text-white border-red-600"
            : "bg-[#1F5A94] text-white border-[#1F5A94]"
          : "bg-white text-slate-600 border-slate-300 hover:border-slate-400"
      }`}
    >
      {label}
    </button>
  );
}

function StatusBadge({ status }: { status: string }) {
  return (
    <span className="text-xs font-semibold uppercase tracking-wide px-3 py-1.5 rounded-full bg-[#EEF3F9] text-[#1F5A94] border border-[#D5DEE9]">
      {STATUS_LABEL[status] ?? status}
    </span>
  );
}
