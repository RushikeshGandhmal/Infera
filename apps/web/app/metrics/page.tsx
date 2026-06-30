"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

type Totals = {
  requests: number;
  error_rate: number;
  p50_ms: number;
  p95_ms: number;
  p99_ms: number;
  avg_ttft_ms: number;
  total_tokens: number;
  total_cost_usd: number;
};

type TimePoint = { t: string; requests: number; errors: number; p95_ms: number };
type ProviderRow = {
  provider: string;
  requests: number;
  p95_ms: number;
  errors: number;
  tokens: number;
  cost_usd: number;
};
type ModelRow = {
  model: string;
  requests: number;
  p95_ms: number;
  errors: number;
  tokens: number;
};

type Summary = {
  window: string;
  error?: string;
  totals: Totals;
  timeseries: TimePoint[];
  by_provider: ProviderRow[];
  by_model: ModelRow[];
};

const WINDOWS: { id: string; label: string }[] = [
  { id: "1h", label: "Last hour" },
  { id: "24h", label: "Last 24h" },
  { id: "7d", label: "Last 7 days" },
];

function fmt(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}k`;
  return `${n}`;
}

function StatCard({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="rounded-xl border border-neutral-800 bg-neutral-900/60 p-4">
      <div className="text-xs font-medium uppercase tracking-wide text-neutral-500">{label}</div>
      <div className="mt-1 text-2xl font-semibold text-neutral-100">{value}</div>
      {hint ? <div className="mt-0.5 text-xs text-neutral-500">{hint}</div> : null}
    </div>
  );
}

function Throughput({ points }: { points: TimePoint[] }) {
  if (points.length === 0) {
    return <div className="py-8 text-center text-sm text-neutral-500">No data in this window yet.</div>;
  }
  const max = Math.max(...points.map((p) => p.requests), 1);
  return (
    <div className="flex h-32 items-end gap-1">
      {points.map((p) => {
        const h = Math.round((p.requests / max) * 100);
        const errH = p.requests > 0 ? Math.round((p.errors / p.requests) * h) : 0;
        return (
          <div
            key={p.t}
            className="group relative flex-1"
            title={`${new Date(p.t).toLocaleString()}\n${p.requests} requests, ${p.errors} errors, p95 ${p.p95_ms}ms`}
          >
            <div className="flex flex-col justify-end" style={{ height: "128px" }}>
              <div className="w-full rounded-t bg-emerald-500/70" style={{ height: `${h}%` }}>
                <div className="w-full rounded-t bg-red-500/80" style={{ height: `${errH}%` }} />
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}

export default function MetricsPage() {
  const [window, setWindow] = useState("24h");
  const [data, setData] = useState<Summary | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/metrics/summary?window=${window}`);
      setData(await res.json());
    } catch {
      setData(null);
    } finally {
      setLoading(false);
    }
  }, [window]);

  useEffect(() => {
    setLoading(true);
    load();
    const id = setInterval(load, 10_000); // live refresh
    return () => clearInterval(id);
  }, [load]);

  const t = data?.totals;

  return (
    <div className="mx-auto max-w-6xl px-6 py-8">
      <header className="mb-6 flex items-center justify-between">
        <div>
          <div className="flex items-center gap-3">
            <Link href="/" className="text-sm text-neutral-400 hover:text-neutral-200">
              ← Chat
            </Link>
            <h1 className="text-xl font-semibold text-neutral-100">Inference Metrics</h1>
          </div>
          <p className="mt-1 text-sm text-neutral-500">Live view of latency, throughput, and errors.</p>
        </div>
        <div className="flex gap-1 rounded-lg border border-neutral-800 bg-neutral-900 p-1">
          {WINDOWS.map((w) => (
            <button
              key={w.id}
              onClick={() => setWindow(w.id)}
              className={`rounded-md px-3 py-1 text-sm transition ${
                window === w.id ? "bg-neutral-700 text-neutral-100" : "text-neutral-400 hover:text-neutral-200"
              }`}
            >
              {w.label}
            </button>
          ))}
        </div>
      </header>

      {data?.error ? (
        <div className="mb-4 rounded-lg border border-amber-800/50 bg-amber-950/30 px-4 py-3 text-sm text-amber-300">
          Metrics store unreachable — showing empty data. ({data.error})
        </div>
      ) : null}

      {loading && !data ? (
        <div className="py-16 text-center text-neutral-500">Loading…</div>
      ) : (
        <>
          <section className="grid grid-cols-2 gap-3 md:grid-cols-4">
            <StatCard label="Requests" value={fmt(t?.requests ?? 0)} />
            <StatCard label="Error rate" value={`${t?.error_rate ?? 0}%`} />
            <StatCard label="p95 latency" value={`${t?.p95_ms ?? 0}ms`} hint={`p50 ${t?.p50_ms ?? 0} · p99 ${t?.p99_ms ?? 0}`} />
            <StatCard label="Avg TTFT" value={`${t?.avg_ttft_ms ?? 0}ms`} />
            <StatCard label="Tokens" value={fmt(t?.total_tokens ?? 0)} />
            <StatCard label="Cost" value={`$${(t?.total_cost_usd ?? 0).toFixed(4)}`} />
          </section>

          <section className="mt-6 rounded-xl border border-neutral-800 bg-neutral-900/60 p-5">
            <div className="mb-3 flex items-center justify-between">
              <h2 className="text-sm font-semibold text-neutral-200">Throughput</h2>
              <div className="flex items-center gap-3 text-xs text-neutral-500">
                <span className="flex items-center gap-1">
                  <span className="inline-block h-2 w-2 rounded-sm bg-emerald-500/70" /> requests
                </span>
                <span className="flex items-center gap-1">
                  <span className="inline-block h-2 w-2 rounded-sm bg-red-500/80" /> errors
                </span>
              </div>
            </div>
            <Throughput points={data?.timeseries ?? []} />
          </section>

          <div className="mt-6 grid gap-6 md:grid-cols-2">
            <section className="rounded-xl border border-neutral-800 bg-neutral-900/60 p-5">
              <h2 className="mb-3 text-sm font-semibold text-neutral-200">By Provider</h2>
              <Table
                head={["Provider", "Reqs", "p95", "Err", "Tokens", "Cost"]}
                rows={(data?.by_provider ?? []).map((r) => [
                  r.provider,
                  fmt(r.requests),
                  `${r.p95_ms}ms`,
                  `${r.errors}`,
                  fmt(r.tokens),
                  `$${r.cost_usd.toFixed(4)}`,
                ])}
              />
            </section>
            <section className="rounded-xl border border-neutral-800 bg-neutral-900/60 p-5">
              <h2 className="mb-3 text-sm font-semibold text-neutral-200">By Model</h2>
              <Table
                head={["Model", "Reqs", "p95", "Err", "Tokens"]}
                rows={(data?.by_model ?? []).map((r) => [
                  r.model,
                  fmt(r.requests),
                  `${r.p95_ms}ms`,
                  `${r.errors}`,
                  fmt(r.tokens),
                ])}
              />
            </section>
          </div>
        </>
      )}
    </div>
  );
}

function Table({ head, rows }: { head: string[]; rows: string[][] }) {
  if (rows.length === 0) {
    return <div className="py-6 text-center text-sm text-neutral-500">No data yet.</div>;
  }
  return (
    <table className="w-full text-sm">
      <thead>
        <tr className="border-b border-neutral-800 text-left text-xs uppercase tracking-wide text-neutral-500">
          {head.map((h, i) => (
            <th key={h} className={`pb-2 font-medium ${i === 0 ? "" : "text-right"}`}>
              {h}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {rows.map((row, ri) => (
          <tr key={ri} className="border-b border-neutral-800/50 last:border-0">
            {row.map((cell, ci) => (
              <td
                key={ci}
                className={`py-2 ${ci === 0 ? "font-medium text-neutral-200" : "text-right text-neutral-400"}`}
              >
                {cell}
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}
