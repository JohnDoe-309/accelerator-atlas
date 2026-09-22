import { ExternalLink } from "lucide-react";

import { AcceleratorBadge } from "@/components/accelerator-badge";
import { StatusPill } from "@/components/status-pill";
import { getSerialFounders, getSummary } from "@/lib/data";
import { fmtInt } from "@/lib/format";

export default async function FoundersPage() {
  const [founders, summary] = await Promise.all([getSerialFounders(), getSummary()]);

  return (
    <div className="max-w-[1200px] mx-auto px-6 py-10">
      <header className="mb-8">
        <p className="text-[12px] uppercase tracking-[0.2em] text-[var(--color-accent)] mb-2">
          Founders
        </p>
        <h1 className="font-serif italic text-[44px] tracking-tight leading-[1.05] mb-3">
          Serial founders across the atlas.
        </h1>
        <p className="text-[15px] text-[var(--color-ink-3)] max-w-2xl">
          {fmtInt(summary.totals.n_founders)} founders across {fmtInt(summary.totals.n_companies)}{" "}
          companies.{" "}
          {!summary.sample && (
            <>
              Of those, <strong className="text-[var(--color-ink)]">{founders.length}</strong>{" "}
              appear in at least two distinct companies — either serial founders, same person on
              multiple ventures, or duplicate registrations we haven't deduped yet.
            </>
          )}
        </p>
        <p className="text-[12px] text-[var(--color-muted)] mt-3 italic">
          Matched by normalized name — expect occasional false positives. Click through to
          LinkedIn for a quick sanity check.
        </p>
      </header>

      {founders.length === 0 && (
        <div className="card p-12 text-center text-[var(--color-muted)]">
          {summary.sample
            ? "Founder-level data (names, roles, LinkedIn) is not included in the public sample."
            : "No serial founders detected yet."}
        </div>
      )}

      <div className="space-y-3">
        {founders.map((f, i) => (
          <div key={f.key} className="card p-5">
            <div className="flex items-start justify-between gap-4 mb-3">
              <div>
                <div className="flex items-center gap-3 mb-1">
                  <span className="font-serif text-[13px] italic text-[var(--color-muted)] num-tabular">
                    #{(i + 1).toString().padStart(2, "0")}
                  </span>
                  <h3 className="font-serif text-[24px] italic tracking-tight">
                    {f.display_name}
                  </h3>
                </div>
                {f.aliases.length > 1 && (
                  <div className="text-[11px] text-[var(--color-muted)]">
                    Also: {f.aliases.slice(1).join(", ")}
                  </div>
                )}
              </div>
              <div className="text-right">
                <div className="font-serif text-[20px] num-tabular">
                  {f.company_count}×
                </div>
                <div className="text-[10px] uppercase tracking-wider text-[var(--color-muted)]">
                  companies
                </div>
              </div>
            </div>
            <div className="flex gap-1 mb-3">
              {f.accelerators.map((s) => (
                <AcceleratorBadge key={s} slug={s} />
              ))}
            </div>
            <ul className="space-y-1.5 text-[13px]">
              {f.companies.map((co, j) => (
                <li
                  key={j}
                  className="flex items-center justify-between gap-2 py-1.5 px-2 -mx-2 rounded hover:bg-[var(--color-cream-2)]/60"
                >
                  <div className="flex items-center gap-2 min-w-0">
                    <AcceleratorBadge slug={co.accelerator} />
                    <span className="font-medium text-[var(--color-ink)] truncate">
                      {co.name}
                    </span>
                    {co.role && (
                      <span className="text-[10px] uppercase tracking-wider text-[var(--color-muted)]">
                        {co.role}
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-3 flex-shrink-0">
                    <StatusPill status={co.status} />
                    {co.linkedin && (
                      <a
                        href={co.linkedin}
                        target="_blank"
                        rel="noreferrer"
                        className="text-[11px] text-[var(--color-accent)] hover:underline flex items-center gap-1"
                      >
                        LinkedIn <ExternalLink size={10} />
                      </a>
                    )}
                  </div>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </div>
  );
}
