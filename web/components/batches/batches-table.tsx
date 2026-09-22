"use client";

import { useMemo, useState } from "react";
import { X } from "lucide-react";

import { AcceleratorBadge } from "@/components/accelerator-badge";
import { ACCELERATOR_LABELS, AcceleratorSlug, Batch } from "@/lib/types";
import { fmtInt } from "@/lib/format";
import { cn } from "@/lib/utils";

type SortKey = "year" | "companies" | "acquired_rate" | "dead_rate";

export function BatchesTable({ batches }: { batches: Batch[] }) {
  const [sort, setSort] = useState<SortKey>("year");
  const [accelerators, setAccelerators] = useState<Set<AcceleratorSlug>>(
    new Set<AcceleratorSlug>(["yc", "ef", "spc", "a16z_speedrun"])
  );
  const [search, setSearch] = useState("");

  const rows = useMemo(() => {
    const filtered = batches.filter(
      (b) =>
        accelerators.has(b.accelerator) &&
        (!search.trim() ||
          b.name.toLowerCase().includes(search.toLowerCase()) ||
          b.accelerator.toLowerCase().includes(search.toLowerCase()))
    );
    const annotated = filtered.map((b) => ({
      ...b,
      acquired_rate: b.company_count > 0 ? (100 * b.acquired_count) / b.company_count : 0,
      dead_rate: b.company_count > 0 ? (100 * b.dead_count) / b.company_count : 0,
    }));
    annotated.sort((a, b) => {
      if (sort === "year") {
        const ay = a.year ?? 0,
          by = b.year ?? 0;
        if (by !== ay) return by - ay;
        return (b.season ?? "").localeCompare(a.season ?? "");
      }
      if (sort === "companies") return b.company_count - a.company_count;
      if (sort === "acquired_rate") return b.acquired_rate - a.acquired_rate;
      if (sort === "dead_rate") return a.dead_rate - b.dead_rate;
      return 0;
    });
    return annotated;
  }, [batches, sort, accelerators, search]);

  const toggle = (s: AcceleratorSlug) => {
    const next = new Set(accelerators);
    if (next.has(s)) next.delete(s);
    else next.add(s);
    setAccelerators(next);
  };

  return (
    <div>
      <div className="flex flex-wrap gap-4 items-center mb-4">
        <div className="flex-1 min-w-[240px] relative">
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search batch names…"
            className="w-full px-4 py-2.5 text-sm rounded-lg border hairline bg-white focus:outline-none focus:border-[var(--color-accent)] focus:ring-2 focus:ring-[var(--color-accent)]/20"
          />
          {search && (
            <button
              onClick={() => setSearch("")}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-[var(--color-muted)] hover:text-[var(--color-ink)]"
            >
              <X size={14} />
            </button>
          )}
        </div>
        <div className="flex gap-2">
          {(["yc", "ef", "spc", "a16z_speedrun"] as AcceleratorSlug[]).map((s) => (
            <button
              key={s}
              onClick={() => toggle(s)}
              className={cn(
                "px-2 py-1 text-xs rounded transition-opacity",
                accelerators.has(s) ? "opacity-100" : "opacity-30"
              )}
            >
              <AcceleratorBadge slug={s} />
            </button>
          ))}
        </div>
        <div className="text-[12px] text-[var(--color-muted)] num-tabular">
          Showing <span className="text-[var(--color-ink)] font-semibold">{fmtInt(rows.length)}</span>{" "}
          of {fmtInt(batches.length)} batches
        </div>
      </div>

      <div className="card overflow-hidden">
        <table className="w-full">
          <thead className="bg-[var(--color-cream-2)] text-[11px] uppercase tracking-[0.12em] text-[var(--color-muted)]">
            <tr>
              <th className="text-left px-4 py-3 font-semibold">Accelerator</th>
              <SortableTh label="Batch" onClick={() => setSort("year")} active={sort === "year"} align="left" />
              <SortableTh label="Companies" onClick={() => setSort("companies")} active={sort === "companies"} align="right" />
              <th className="text-right px-4 py-3 font-semibold">Active</th>
              <SortableTh label="Acquired %" onClick={() => setSort("acquired_rate")} active={sort === "acquired_rate"} align="right" />
              <SortableTh label="Dead %" onClick={() => setSort("dead_rate")} active={sort === "dead_rate"} align="right" />
            </tr>
          </thead>
          <tbody>
            {rows.map((b) => (
              <tr key={b.id} className="border-t hairline hover:bg-[var(--color-cream-2)]/50 transition-colors">
                <td className="px-4 py-3">
                  <AcceleratorBadge slug={b.accelerator} />
                </td>
                <td className="px-4 py-3">
                  <a
                    href={`/explorer?batch=${encodeURIComponent(b.slug)}&accelerator=${b.accelerator}`}
                    className="font-medium text-[var(--color-ink)] hover:text-[var(--color-accent)]"
                  >
                    {b.name}
                  </a>
                  <div className="text-[11px] text-[var(--color-muted)]">
                    {ACCELERATOR_LABELS[b.accelerator]}
                  </div>
                </td>
                <td className="px-4 py-3 text-right num-tabular font-medium">
                  {fmtInt(b.company_count)}
                </td>
                <td className="px-4 py-3 text-right num-tabular text-[var(--color-success)]">
                  {fmtInt(b.active_count)}
                </td>
                <td className="px-4 py-3 text-right num-tabular text-[var(--color-warning)]">
                  {b.acquired_rate.toFixed(1)}%
                </td>
                <td className="px-4 py-3 text-right num-tabular text-[var(--color-danger)]">
                  {b.dead_rate.toFixed(1)}%
                </td>
              </tr>
            ))}
            {rows.length === 0 && (
              <tr>
                <td colSpan={6} className="px-4 py-12 text-center text-[var(--color-muted)]">
                  No batches match.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function SortableTh({
  label,
  onClick,
  active,
  align = "left",
}: {
  label: string;
  onClick: () => void;
  active: boolean;
  align?: "left" | "right";
}) {
  return (
    <th
      onClick={onClick}
      className={cn(
        "px-4 py-3 font-semibold cursor-pointer select-none",
        active ? "text-[var(--color-ink)]" : "hover:text-[var(--color-ink-3)]",
        align === "right" ? "text-right" : "text-left"
      )}
    >
      {label}
      {active && <span className="ml-1 text-[var(--color-accent)]">↓</span>}
    </th>
  );
}
