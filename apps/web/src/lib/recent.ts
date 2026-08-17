// Client-side convenience only — there's no "list assessments" endpoint in
// the real API yet (a real, separate gap; not added here to keep this
// session's scope to what the demo actually needs). Recently-created
// assessment IDs are remembered locally so the demo can jump back into one
// without re-creating it every time.

const KEY = "ipacgs-demo-recent-assessments";

export interface RecentAssessment {
  id: string;
  organisationName: string;
  createdAt: string;
}

export function getRecentAssessments(): RecentAssessment[] {
  if (typeof window === "undefined") return [];
  try {
    return JSON.parse(window.localStorage.getItem(KEY) ?? "[]");
  } catch {
    return [];
  }
}

export function addRecentAssessment(entry: RecentAssessment) {
  const existing = getRecentAssessments().filter((e) => e.id !== entry.id);
  const updated = [entry, ...existing].slice(0, 10);
  window.localStorage.setItem(KEY, JSON.stringify(updated));
}
