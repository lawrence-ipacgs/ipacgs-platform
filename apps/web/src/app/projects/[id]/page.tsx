"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { useActor } from "@/lib/actor";
import { api, ApiError, ChecklistItem, Project, Stage } from "@/lib/api";
import { RagBadge } from "@/app/page";

export default function ProjectPage() {
  const { id } = useParams<{ id: string }>();
  const { actor } = useActor();

  const [project, setProject] = useState<Project | null>(null);
  const [stage, setStage] = useState<Stage | null>(null);
  const [items, setItems] = useState<ChecklistItem[]>([]);
  const [rag, setRag] = useState<string | null>(null);
  const [outcome, setOutcome] = useState("proceed");
  const [conditions, setConditions] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const load = useCallback(async () => {
    const p = await api.getProject(actor, id);
    setProject(p);
    const stages = await api.listStages(actor);
    setStage(stages.find((s) => s.id === p.current_stage_id) ?? null);
    const checklist = await api.getStageChecklist(actor, id);
    setItems(checklist);
    const ragStatus = await api.getProjectRag(actor, id);
    setRag(ragStatus.status);
  }, [actor, id]);

  useEffect(() => {
    // Standard fetch-on-mount error handling, same reasoning
    // app/page.tsx documents.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    load().catch((e) => setError(e instanceof ApiError ? e.message : String(e)));
  }, [load]);

  async function respond(itemId: string, value: "yes" | "no" | "not_applicable") {
    try {
      await api.respondToChecklistItem(actor, id, itemId, { response_value: value });
      await load();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not save response.");
    }
  }

  async function recordDecision() {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      await api.recordStageDecision(actor, id, { outcome, conditions: conditions || undefined });
      setNotice(`Decision recorded: ${outcome.replace(/_/g, " ")}.`);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not record decision.");
    } finally {
      setBusy(false);
    }
  }

  async function advance() {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      await api.advanceStage(actor, id);
      setNotice("Stage advanced.");
      await load();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not advance — check the decision above.");
    } finally {
      setBusy(false);
    }
  }

  if (!project) return <p className="text-slate-500">{error ?? "Loading…"}</p>;

  const answered = items.filter((i) => i.response_value).length;

  return (
    <div className="space-y-6 max-w-3xl">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-xs uppercase tracking-wide text-slate-400 mb-1">
            UACOC Intake &amp; Screening
          </p>
          <h1 className="text-2xl font-bold text-[#0B1F3A]">{project.name}</h1>
        </div>
        {rag && <RagBadge rag={rag} />}
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-800 text-sm rounded-lg px-4 py-3">
          {error}
        </div>
      )}
      {notice && (
        <div className="bg-emerald-50 border border-emerald-200 text-emerald-800 text-sm rounded-lg px-4 py-3">
          {notice}
        </div>
      )}

      <div className="bg-white border border-slate-200 rounded-xl p-6">
        <p className="text-xs uppercase tracking-wide text-[#1F5A94] font-semibold mb-1">
          {stage?.code}
        </p>
        <h2 className="text-lg font-bold text-[#0B1F3A]">{stage?.name}</h2>
        <p className="text-sm text-slate-500 mt-1">{stage?.description}</p>
      </div>

      <div className="bg-white border border-slate-200 rounded-xl p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-semibold text-[#0B1F3A]">
            Real exit criteria — sourced from UACOC&rsquo;s own process map
          </h3>
          <span className="text-sm text-slate-400">
            {answered}/{items.length} answered
          </span>
        </div>
        <div className="divide-y divide-slate-100">
          {items.map((item) => (
            <div key={item.item_id} className="py-3 flex items-center justify-between gap-4">
              <span className="text-sm text-slate-700">{item.criterion}</span>
              <div className="flex gap-1.5 shrink-0">
                <AnswerButton
                  label="Yes"
                  active={item.response_value === "yes"}
                  onClick={() => respond(item.item_id, "yes")}
                />
                <AnswerButton
                  label="No"
                  active={item.response_value === "no"}
                  danger
                  onClick={() => respond(item.item_id, "no")}
                />
                <AnswerButton
                  label="N/A"
                  active={item.response_value === "not_applicable"}
                  onClick={() => respond(item.item_id, "not_applicable")}
                />
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="bg-white border border-slate-200 rounded-xl p-6 space-y-4">
        <h3 className="font-semibold text-[#0B1F3A]">Stage decision</h3>
        <div className="flex flex-wrap gap-3 items-center">
          <select
            value={outcome}
            onChange={(e) => setOutcome(e.target.value)}
            className="border border-slate-300 rounded-lg px-3 py-2 text-sm"
          >
            <option value="proceed">Proceed</option>
            <option value="proceed_with_conditions">Proceed with Conditions</option>
            <option value="return_for_information">Return for Information</option>
            <option value="require_due_diligence">Require Due Diligence</option>
            <option value="escalate_for_specialist_review">Escalate for Specialist Review</option>
            <option value="hold_pending">Hold / Pending</option>
            <option value="decline">Decline</option>
          </select>
          <input
            value={conditions}
            onChange={(e) => setConditions(e.target.value)}
            placeholder="Conditions (optional)"
            className="flex-1 min-w-48 border border-slate-300 rounded-lg px-3 py-2 text-sm"
          />
          <button
            disabled={busy || answered < items.length}
            onClick={recordDecision}
            className="px-4 py-2 rounded-lg bg-[#1F5A94] text-white text-sm font-medium hover:bg-[#164572] disabled:opacity-50"
          >
            Record decision
          </button>
        </div>
        <button
          disabled={busy}
          onClick={advance}
          className="px-4 py-2 rounded-lg bg-[#0B1F3A] text-white text-sm font-medium hover:bg-[#132c52] disabled:opacity-50"
        >
          Advance to next stage
        </button>
      </div>
    </div>
  );
}

function AnswerButton({
  label,
  active,
  onClick,
  danger,
}: {
  label: string;
  active?: boolean;
  onClick: () => void;
  danger?: boolean;
}) {
  return (
    <button
      onClick={onClick}
      className={`px-3 py-1.5 rounded-md text-xs font-semibold border transition-colors ${
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
