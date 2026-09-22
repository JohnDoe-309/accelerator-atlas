import { AcceleratorBadge } from "@/components/accelerator-badge";
import { getCoverage, getSummary } from "@/lib/data";
import { ACCELERATOR_LABELS, AcceleratorSlug } from "@/lib/types";
import { cn } from "@/lib/utils";

export default async function DataQualityPage() {
  const [coverage, summary] = await Promise.all([getCoverage(), getSummary()]);

  const accelerators: AcceleratorSlug[] = ["yc", "ef", "spc", "a16z_speedrun"];
  const fields = Array.from(new Set(coverage.map((r) => r.field)));

  // Build a matrix: [field][accelerator] -> pct
  const matrix = new Map<string, Record<AcceleratorSlug, { pct: number; have: number; total: number }>>();
  for (const f of fields) {
    const row = {} as Record<AcceleratorSlug, { pct: number; have: number; total: number }>;
    for (const a of accelerators) {
      const hit = coverage.find((c) => c.field === f && c.accelerator === a);
      row[a] = hit ? { pct: hit.pct, have: hit.have, total: hit.total } : { pct: 0, have: 0, total: 0 };
    }
    matrix.set(f, row);
  }

  const totals = summary.totals;

  return (
    <div className="max-w-[1400px] mx-auto px-6 py-10">
      <header className="mb-8">
        <p className="text-[12px] uppercase tracking-[0.2em] text-[var(--color-accent)] mb-2">
          Data quality
        </p>
        <h1 className="font-serif italic text-[44px] tracking-tight leading-[1.05] mb-3">
          Field coverage, honestly stated.
        </h1>
        <p className="text-[15px] text-[var(--color-ink-3)] max-w-2xl">
          For each core field, what fraction of companies have a non-empty
          value? Useful for catching silent regressions in the scraper layer.
          {" "}Red means &lt;50%, amber 50–89%, green 90+%.
        </p>
      </header>

      <div className="card overflow-hidden">
        <table className="w-full">
          <thead className="bg-[var(--color-cream-2)] text-[11px] uppercase tracking-[0.12em] text-[var(--color-muted)]">
            <tr>
              <th className="text-left px-4 py-3">Field</th>
              {accelerators.map((a) => (
                <th key={a} className="text-right px-4 py-3">
                  <div className="flex items-center justify-end gap-2">
                    <AcceleratorBadge slug={a} />
                    <span className="text-[var(--color-muted)] num-tabular">
                      n={totals && summary.accelerators.find((x) => x.slug === a)?.company_count}
                    </span>
                  </div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {fields.map((f) => {
              const row = matrix.get(f)!;
              return (
                <tr key={f} className="border-t hairline">
                  <td className="px-4 py-3 font-medium text-[var(--color-ink-2)]">
                    <code className="font-mono text-[12px] bg-[var(--color-cream-2)] px-1.5 py-0.5 rounded">
                      {f}
                    </code>
                  </td>
                  {accelerators.map((a) => {
                    const cell = row[a];
                    const color =
                      cell.pct >= 90
                        ? "text-[var(--color-success)] bg-[var(--color-success-soft)]"
                        : cell.pct >= 50
                        ? "text-[var(--color-warning)] bg-[var(--color-warning-soft)]"
                        : "text-[var(--color-danger)] bg-[var(--color-danger-soft)]";
                    return (
                      <td key={a} className="px-4 py-3 text-right">
                        <div className="inline-flex items-center gap-2">
                          <span className="num-tabular text-[12px] text-[var(--color-muted)]">
                            {cell.have}/{cell.total}
                          </span>
                          <span
                            className={cn(
                              "inline-block px-2 py-0.5 rounded font-semibold num-tabular text-[12px] w-14 text-center",
                              color
                            )}
                          >
                            {cell.pct.toFixed(0)}%
                          </span>
                        </div>
                      </td>
                    );
                  })}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <section className="mt-10 grid md:grid-cols-3 gap-4">
        {summary.accelerators.map((a) => (
          <div key={a.slug} className="card p-5">
            <div className="flex justify-between items-center mb-3">
              <div className="font-serif italic text-[22px] tracking-tight">
                {a.name}
              </div>
              <AcceleratorBadge slug={a.slug} />
            </div>
            <dl className="space-y-1 text-[13px]">
              <Row k="Companies" v={a.company_count.toLocaleString()} />
              <Row k="HQ" v={a.hq_location ?? "—"} />
              <Row k="Founded" v={a.founded_year?.toString() ?? "—"} />
              <Row
                k="Typical check"
                v={
                  a.investment_amount_usd
                    ? `$${Math.round(a.investment_amount_usd).toLocaleString()}`
                    : "—"
                }
              />
              <Row k="Equity" v={a.investment_equity_pct ? `${a.investment_equity_pct}%` : "—"} />
              <Row k="Cadence" v={a.batch_cadence ?? "—"} />
            </dl>
          </div>
        ))}
      </section>
    </div>
  );
}

function Row({ k, v }: { k: string; v: string }) {
  return (
    <div className="flex justify-between border-b hairline py-1.5 last:border-0">
      <dt className="text-[12px] text-[var(--color-muted)]">{k}</dt>
      <dd className="text-[var(--color-ink-2)] text-right">{v}</dd>
    </div>
  );
}
