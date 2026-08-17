"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { useActor } from "@/lib/actor";
import { api, ApiError, BillOfHealthReportOut } from "@/lib/api";

const RAG_STYLES: Record<string, { bg: string; text: string; border: string }> = {
  green: { bg: "bg-emerald-50", text: "text-emerald-800", border: "border-emerald-300" },
  amber: { bg: "bg-amber-50", text: "text-amber-800", border: "border-amber-300" },
  red: { bg: "bg-red-50", text: "text-red-800", border: "border-red-300" },
};

export default function BillOfHealthPage() {
  const { id } = useParams<{ id: string }>();
  const { actor } = useActor();
  const [report, setReport] = useState<BillOfHealthReportOut | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .getBillOfHealth(actor, id)
      .then(setReport)
      .catch((e) => setError(e instanceof ApiError ? e.message : String(e)));
  }, [actor, id]);

  if (error) return <p className="text-red-600 text-sm">{error}</p>;
  if (!report) return <p className="text-slate-500">Loading…</p>;

  const rag = RAG_STYLES[report.opinion.rag] ?? RAG_STYLES.red;

  return (
    <div className="space-y-6 max-w-3xl">
      <div>
        <p className="text-xs uppercase tracking-wide text-slate-400 mb-1">
          Bill of Health Report
        </p>
        <h1 className="text-2xl font-bold text-[#0B1F3A]">{report.opinion.headline}</h1>
      </div>

      <div className={`border ${rag.border} ${rag.bg} rounded-xl p-6`}>
        <p className={`text-sm font-medium ${rag.text}`}>{report.opinion.narrative}</p>
        <div className="mt-4 flex gap-8 text-sm">
          <Stat label="Assurance Score" value={`${report.score.assurance_score.toFixed(1)} / 100`} />
          <Stat label="Overall Score" value={`${report.score.overall_score.toFixed(1)} / 5`} />
          <Stat
            label="Evidence Sufficiency"
            value={`${(report.score.evidence_sufficiency_factor * 100).toFixed(0)}%`}
          />
          <Stat label="Recorded Decision" value={report.status.replace(/_/g, " ")} />
        </div>
      </div>

      <section className="bg-white border border-slate-200 rounded-xl p-6">
        <h2 className="font-semibold text-[#0B1F3A] mb-3">Domain scores</h2>
        <div className="space-y-2">
          {report.score.domain_results.map((d) => (
            <div key={d.domain_id} className="flex items-center gap-3 text-sm">
              <span className="flex-1 text-slate-700">{d.name}</span>
              {d.critical_failures.length > 0 && (
                <span className="text-[10px] uppercase tracking-wide bg-red-100 text-red-700 px-1.5 py-0.5 rounded">
                  {d.critical_failures.length} critical
                </span>
              )}
              <span
                className={`w-14 text-right font-mono ${
                  d.meets_threshold ? "text-emerald-700" : "text-red-700"
                }`}
              >
                {d.score.toFixed(1)}
              </span>
            </div>
          ))}
        </div>
      </section>

      {report.open_findings.length > 0 && (
        <section className="bg-white border border-slate-200 rounded-xl p-6">
          <h2 className="font-semibold text-[#0B1F3A] mb-3">
            Open findings ({report.open_findings.length})
          </h2>
          <div className="space-y-2">
            {report.open_findings.map((f) => (
              <div
                key={f.id}
                className="border border-slate-200 rounded-lg px-4 py-3 text-sm flex items-start justify-between gap-4"
              >
                <span className="text-slate-700">{f.description}</span>
                <span className="text-[10px] uppercase tracking-wide bg-red-100 text-red-700 px-1.5 py-0.5 rounded shrink-0">
                  {f.severity}
                </span>
              </div>
            ))}
          </div>
        </section>
      )}

      {report.decision_summary && (
        <section className="bg-white border border-slate-200 rounded-xl p-6">
          <h2 className="font-semibold text-[#0B1F3A] mb-2">Decision summary</h2>
          <p className="text-sm text-slate-600">{report.decision_summary}</p>
        </section>
      )}

      <a href={`/opboh/${id}`} className="text-sm text-[#1F5A94] underline">
        ← Back to assessment
      </a>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-slate-500 text-xs">{label}</p>
      <p className="font-semibold text-[#0B1F3A] capitalize">{value}</p>
    </div>
  );
}
