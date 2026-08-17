"use client";

import { createContext, useContext, useEffect, useState } from "react";

// Stands in for a real signed-in identity — this platform's real auth is
// Entra ID (core/security.py), which has no app registration yet
// (infra/scripts/create-app-registrations.sh is still a pending manual
// step). Every name typed here becomes a real actor on real audit
// events/segregation-of-duties checks via the X-Dev-User header — see
// lib/api.ts.

const STORAGE_KEY = "ipacgs-demo-actor";

const ActorContext = createContext<{
  actor: string;
  setActor: (a: string) => void;
}>({ actor: "alice", setActor: () => {} });

export function ActorProvider({ children }: { children: React.ReactNode }) {
  const [actor, setActorState] = useState("alice");

  useEffect(() => {
    // Reading localStorage (an external system) is exactly what this rule
    // wants synced via an effect; the flagged part is just that the sync
    // target is local state, not a ref or DOM node.
    const stored = window.localStorage.getItem(STORAGE_KEY);
    // eslint-disable-next-line react-hooks/set-state-in-effect
    if (stored) setActorState(stored);
  }, []);

  function setActor(a: string) {
    setActorState(a);
    window.localStorage.setItem(STORAGE_KEY, a);
  }

  return (
    <ActorContext.Provider value={{ actor, setActor }}>{children}</ActorContext.Provider>
  );
}

export function useActor() {
  return useContext(ActorContext);
}
