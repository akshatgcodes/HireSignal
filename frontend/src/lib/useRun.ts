import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../api";
import type { Run } from "../types";

/** Starts a scan and polls its run until it finishes, then calls onDone. */
export function useRun(onDone: (run: Run) => void) {
  const [run, setRun] = useState<Run | null>(null);
  const [error, setError] = useState<string | null>(null);
  const timer = useRef<number | undefined>(undefined);
  const done = useRef(onDone);
  done.current = onDone;

  useEffect(() => () => window.clearTimeout(timer.current), []);

  const poll = useCallback((id: number) => {
    api
      .run(id)
      .then((r) => {
        setRun(r);
        if (r.status === "running") timer.current = window.setTimeout(() => poll(id), 1500);
        else done.current(r);
      })
      .catch((e) => setError(e.message));
  }, []);

  const start = useCallback(
    async (begin: () => Promise<{ run_id: number }>) => {
      setError(null);
      setRun({ id: 0, trigger: "manual", status: "running", started_at: new Date().toISOString(), finished_at: null, stats: {} });
      try {
        poll((await begin()).run_id);
      } catch (e) {
        setRun(null);
        setError(e instanceof Error ? e.message : "Scan failed");
      }
    },
    [poll],
  );

  return { run, running: run?.status === "running", error, start };
}
