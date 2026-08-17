"use client";

import Link from "next/link";
import { useActor } from "@/lib/actor";

export function TopBar() {
  const { actor, setActor } = useActor();

  return (
    <header className="border-b border-slate-200 bg-[#0B1F3A]">
      <div className="max-w-6xl mx-auto px-6 py-4 flex items-center justify-between">
        <Link href="/" className="flex items-center gap-3">
          <span className="text-white font-bold text-lg tracking-tight">
            IPAC Governance Systems
          </span>
          <span className="text-[#9fb3cf] text-xs uppercase tracking-widest border border-[#25406b] rounded px-2 py-0.5">
            OPBOH™ · Milestone 1.1
          </span>
        </Link>
        <div className="flex items-center gap-3">
          <label className="text-[#c3cfe0] text-sm">Acting as</label>
          <input
            value={actor}
            onChange={(e) => setActor(e.target.value)}
            className="bg-[#16233A] border border-[#2A3B57] text-white text-sm rounded px-3 py-1.5 w-36 focus:outline-none focus:ring-2 focus:ring-[#6FA8DC]"
            placeholder="name"
          />
        </div>
      </div>
    </header>
  );
}
