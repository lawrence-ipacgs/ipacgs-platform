"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useActor } from "@/lib/actor";
import { api, ApiError, Organisation } from "@/lib/api";

export default function NewProjectPage() {
  const { actor } = useActor();
  const router = useRouter();
  const [orgs, setOrgs] = useState<Organisation[]>([]);
  const [name, setName] = useState("");
  const [orgId, setOrgId] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.listOrganisations(actor).then((list) => {
      setOrgs(list);
      if (list[0]) setOrgId(list[0].id);
    });
  }, [actor]);

  async function create() {
    if (!name.trim() || !orgId) return;
    setBusy(true);
    setError(null);
    try {
      const project = await api.createProject(actor, orgId, name.trim());
      router.push(`/projects/${project.id}`);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not create project.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="max-w-lg space-y-5">
      <div>
        <p className="text-xs uppercase tracking-wide text-slate-400 mb-1">New Project</p>
        <h1 className="text-2xl font-bold text-[#0B1F3A]">
          Start UACOC Intake &amp; Screening
        </h1>
        <p className="text-sm text-slate-500 mt-1">
          Enters the project at the first of the seven real stages seeded from UACOC&rsquo;s
          own Project Intake Full Process Map — Project Submission.
        </p>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-800 text-sm rounded-lg px-4 py-3">
          {error}
        </div>
      )}

      <div className="bg-white border border-slate-200 rounded-xl p-6 space-y-4">
        <div>
          <label className="text-sm font-medium text-slate-700 block mb-1">Project name</label>
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm"
            placeholder="e.g. Mankweng Mixed-Use Development"
          />
        </div>
        <div>
          <label className="text-sm font-medium text-slate-700 block mb-1">Organisation</label>
          <select
            value={orgId}
            onChange={(e) => setOrgId(e.target.value)}
            className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm"
          >
            {orgs.map((o) => (
              <option key={o.id} value={o.id}>
                {o.legal_name}
              </option>
            ))}
          </select>
        </div>
        <button
          disabled={busy || !name.trim()}
          onClick={create}
          className="w-full px-4 py-2 rounded-lg bg-[#1F5A94] text-white text-sm font-medium hover:bg-[#164572] disabled:opacity-50"
        >
          Create project
        </button>
      </div>
    </div>
  );
}
