import { Suspense } from "react";

import { ExplorerShell } from "@/components/explorer/explorer-shell";
import { getCompanies } from "@/lib/data";
import { fmtInt } from "@/lib/format";

export default async function ExplorerPage() {
  const companies = await getCompanies();
  return (
    <div className="max-w-[1400px] mx-auto px-6 py-8">
      <header className="mb-6">
        <p className="text-[12px] uppercase tracking-[0.2em] text-[var(--color-accent)] mb-2">
          Explorer
        </p>
        <h1 className="font-serif italic text-[44px] tracking-tight leading-[1.05] mb-2">
          {fmtInt(companies.length)} companies, one table.
        </h1>
        <p className="text-[15px] text-[var(--color-ink-3)] max-w-2xl">
          Sorted newest-cohort-first by default. Click any row for a detail
          drawer with founders, links, and provenance. Filters are on the left;
          use the natural-language bar to translate English into filters via
          Grok.
        </p>
      </header>

      <Suspense
        fallback={
          <div className="card p-8 text-center text-[var(--color-muted)] text-sm">
            Loading explorer…
          </div>
        }
      >
        <ExplorerShell data={companies} />
      </Suspense>
    </div>
  );
}
