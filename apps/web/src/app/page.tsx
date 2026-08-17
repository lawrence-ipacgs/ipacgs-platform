"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useActor } from "@/lib/actor";
import { api, Organisation, ProjectSummary, ApiError } from "@/lib/api";
import { addRecentAssessment, getRecentAssessments, RecentAssessment } from "@/lib/recent";

export default function HomePage() {
  const { actor } = useActor();
  const router = useRouter();
  const [orgs, setOrgs] = useState<Organisation[]>([]);
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [recent, setRecent] = useState<RecentAssessment[]>([]);
  const [newOrgName, setNewOrgName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    // Syncing from localStorage (an external system), same reasoning
    // lib/actor.tsx documents; the two fetches below are the standard
    // fetch-on-mount pattern this demo's tight timeline didn't warrant
    // restructuring around a data-fetching library for.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setRecent(getRecentAssessments());
    api.listOrganisations(actor).then(setOrgs).catch(() => {});
    api.listProjects(actor).then(setProjects).catch(() => {});
  }, [actor]);

  async function startAssessment(org: Organisation) {
    setError(null);
    setBusy(true);
    try {
      const assessment = await api.createAssessment(actor, org.id);
      addRecentAssessment({
        id: assessment.id,
        organisationName: org.legal_name,
        createdAt: new Date().toISOString(),
      });
      router.push(`/opboh/${assessment.id}`);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Something went wrong.");
    } finally {
      setBusy(false);
    }
  }

  async function createOrgAndStart() {
    if (!newOrgName.trim()) return;
    setError(null);
    setBusy(true);
    try {
      const org = await api.createOrganisation(actor, newOrgName.trim());
      setOrgs((prev) => [...prev, org]);
      setNewOrgName("");
      await startAssessment(org);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not create organisation.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-10">
      <section>
        <h1 className="text-2xl font-bold text-[#0B1F3A]">Command Centre</h1>
        <p className="text-slate-500 mt-1 max-w-2xl">
          Live against the real API — the 37-domain / 222-question OPBOH catalogue,
          the seven-stage UACOC intake pipeline, and the real scoring/decision
          engine built this milestone. Nothing on this page is mocked data.
        </p>
      </section>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-800 text-sm rounded-lg px-4 py-3">
          {error}
        </div>
      )}

      <section className="bg-white border border-slate-200 rounded-xl p-6">
        <h2 className="font-semibold text-[#0B1F3A] mb-1">Start a new OPBOH assessment</h2>
        <p className="text-sm text-slate-500 mb-4">
          Runs the real 37-domain, 222-question catalogue seeded from KMI&rsquo;s
          controlled work-package register.
        </p>
        <div className="flex flex-wrap gap-3">
          {orgs.map((org) => (
            <button
              key={org.id}
              disabled={busy}
              onClick={() => startAssessment(org)}
              className="px-4 py-2 rounded-lg bg-[#1F5A94] text-white text-sm font-medium hover:bg-[#164572] disabled:opacity-50"
            >
              New assessment · {org.legal_name}
            </button>
          ))}
        </div>
        <div className="mt-4 flex gap-2">
          <input
            value={newOrgName}
            onChange={(e) => setNewOrgName(e.target.value)}
            placeholder="Or register a new organisation…"
            className="flex-1 border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#1F5A94]"
          />
          <button
            disabled={busy || !newOrgName.trim()}
            onClick={createOrgAndStart}
            className="px-4 py-2 rounded-lg border border-[#1F5A94] text-[#1F5A94] text-sm font-medium hover:bg-[#F4F7FA] disabled:opacity-50"
          >
            Register &amp; start
          </button>
        </div>
      </section>

      {recent.length > 0 && (
        <section>
          <h2 className="font-semibold text-[#0B1F3A] mb-3">Recent assessments</h2>
          <div className="grid gap-2">
            {recent.map((r) => (
              <a
                key={r.id}
                href={`/opboh/${r.id}`}
                className="bg-white border border-slate-200 rounded-lg px-4 py-3 text-sm hover:border-[#1F5A94] transition-colors flex justify-between"
              >
                <span className="font-medium text-slate-800">{r.organisationName}</span>
                <span className="text-slate-400">{r.id.slice(0, 8)}</span>
              </a>
            ))}
          </div>
        </section>
      )}

      <section>
        <h2 className="font-semibold text-[#0B1F3A] mb-3">
          Project pipeline — UACOC Intake &amp; Screening
        </h2>
        {projects.length === 0 ? (
          <p className="text-sm text-slate-500">
            No projects yet — the seven-stage intake pipeline (Submission →
            Onboarding) is seeded and ready.{" "}
            <Link href="/projects/new" className="text-[#1F5A94] underline">
              Start one
            </Link>
            .
          </p>
        ) : (
          <div className="grid gap-2">
            {projects.map((p) => (
              <a
                key={p.id}
                href={`/projects/${p.id}`}
                className="bg-white border border-slate-200 rounded-lg px-4 py-3 text-sm hover:border-[#1F5A94] transition-colors flex items-center justify-between"
              >
                <span className="font-medium text-slate-800">{p.name}</span>
                <span className="text-slate-500">{p.current_stage_name}</span>
                <RagBadge rag={p.rag_status} />
              </a>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

export function RagBadge({ rag }: { rag: string }) {
  const styles: Record<string, string> = {
    green: "bg-emerald-100 text-emerald-800",
    amber: "bg-amber-100 text-amber-800",
    red: "bg-red-100 text-red-800",
    grey: "bg-slate-100 text-slate-600",
  };
  return (
    <span
      className={`text-xs font-semibold uppercase tracking-wide px-2 py-1 rounded ${
        styles[rag] ?? styles.grey
      }`}
    >
      {rag}
    </span>
  );
}
