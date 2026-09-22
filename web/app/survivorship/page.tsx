import Link from "next/link";

import { AcceleratorBadge } from "@/components/accelerator-badge";
import { OutcomeMixChart } from "@/components/charts/outcome-mix-chart";
import { StatusPill } from "@/components/status-pill";
import { getBatches, getCompanies } from "@/lib/data";
import { fmtInt } from "@/lib/format";
import { Company } from "@/lib/types";

export default async function SurvivorshipPage() {
  const [batches, companies] = await Promise.all([getBatches(), getCompanies()]);

  // Cohort-year outcome mix across all accelerators
  const yearMap = new Map<
    number,
    { Active: number; Acquired: number; Public: number; Dead: number; Unknown: number }
  >();
  for (const c of companies) {
    if (!c.founded_year || c.founded_year < 2008 || c.founded_year > 2025) continue;
    if (!yearMap.has(c.founded_year))
      yearMap.set(c.founded_year, { Active: 0, Acquired: 0, Public: 0, Dead: 0, Unknown: 0 });
    const bucket = yearMap.get(c.founded_year)!;
    bucket[(c.status as keyof typeof bucket) ?? "Unknown"] =
      (bucket[(c.status as keyof typeof bucket) ?? "Unknown"] ?? 0) + 1;
  }
  const yearRows = Array.from(yearMap.entries())
    .map(([year, v]) => ({ label: String(year), ...v }))
    .sort((a, b) => Number(b.label) - Number(a.label)); // newest first per request

  const topAcquired = [...companies]
    .filter((c) => c.status === "Acquired")
    .sort((a, b) => (b.founded_year ?? 0) - (a.founded_year ?? 0))
    .slice(0, 30);
  const topPublic = [...companies]
    .filter((c) => c.status === "Public")
    .sort((a, b) => (b.founded_year ?? 0) - (a.founded_year ?? 0));
  const topCompanies = [...companies]
    .filter((c) => c.is_top_company)
    .sort((a, b) => (b.founded_year ?? 0) - (a.founded_year ?? 0))
    .slice(0, 30);

  const topBatches = [...batches]
    .sort((a, b) => {
      const ay = a.year ?? 0,
        by = b.year ?? 0;
      if (ay !== by) return by - ay;
      return (b.season ?? "").localeCompare(a.season ?? "");
    })
    .slice(0, 24);

  return (
    <div className="max-w-[1400px] mx-auto px-6 py-8">
      <header className="mb-8">
        <p className="text-[12px] uppercase tracking-[0.2em] text-[var(--color-accent)] mb-2">
          Survivorship
        </p>
        <h1 className="font-serif italic text-[44px] tracking-tight leading-[1.05] mb-2">
          What lives, what dies, what exits.
        </h1>
        <p className="text-[15px] text-[var(--color-ink-3)] max-w-2xl">
          Outcome mix by founded year (newest first). Every status label is
          sourced from primary data + a liveness probe — see the Data Quality
          page for confidence breakdowns.
        </p>
      </header>

      <section className="card p-6 mb-10">
        <div className="flex items-baseline justify-between mb-4">
          <div>
            <h2 className="font-serif text-[24px] italic tracking-tight">
              Cohort outcome mix
            </h2>
            <p className="text-[12px] text-[var(--color-muted)]">
              Absolute counts per founded year, stacked by status
            </p>
          </div>
        </div>
        <OutcomeMixChart data={yearRows} />
      </section>

      <section className="mb-10">
        <h2 className="font-serif text-[24px] italic tracking-tight mb-4">
          Latest batches
        </h2>
        <div className="card overflow-hidden">
          <table className="w-full">
            <thead className="bg-[var(--color-cream-2)] text-[11px] uppercase tracking-[0.12em] text-[var(--color-muted)]">
              <tr>
                <th className="text-left px-4 py-2.5">Accelerator</th>
                <th className="text-left px-4 py-2.5">Batch</th>
                <th className="text-right px-4 py-2.5">Companies</th>
                <th className="text-right px-4 py-2.5">Active</th>
                <th className="text-right px-4 py-2.5">Acquired</th>
                <th className="text-right px-4 py-2.5">Dead</th>
                <th className="text-right px-4 py-2.5">Dead %</th>
              </tr>
            </thead>
            <tbody>
              {topBatches.map((b) => {
                const deadPct =
                  b.company_count > 0
                    ? Math.round((100 * b.dead_count) / b.company_count)
                    : 0;
                return (
                  <tr key={b.id} className="border-t hairline hover:bg-[var(--color-cream-2)]/50">
                    <td className="px-4 py-2.5">
                      <AcceleratorBadge slug={b.accelerator} />
                    </td>
                    <td className="px-4 py-2.5 font-medium">{b.name}</td>
                    <td className="px-4 py-2.5 text-right num-tabular">{fmtInt(b.company_count)}</td>
                    <td className="px-4 py-2.5 text-right num-tabular text-[var(--color-success)]">
                      {fmtInt(b.active_count)}
                    </td>
                    <td className="px-4 py-2.5 text-right num-tabular text-[var(--color-warning)]">
                      {fmtInt(b.acquired_count)}
                    </td>
                    <td className="px-4 py-2.5 text-right num-tabular text-[var(--color-danger)]">
                      {fmtInt(b.dead_count)}
                    </td>
                    <td className="px-4 py-2.5 text-right num-tabular text-[var(--color-muted)]">
                      {deadPct}%
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </section>

      <section className="grid lg:grid-cols-3 gap-6">
        <CompanyList title="Top acquired (recent)" items={topAcquired} />
        <CompanyList title="Went public" items={topPublic} />
        <CompanyList title="YC Top Companies" items={topCompanies} />
      </section>
    </div>
  );
}

function CompanyList({ title, items }: { title: string; items: Company[] }) {
  return (
    <div className="card p-5">
      <h3 className="font-serif text-[20px] italic tracking-tight mb-3">{title}</h3>
      <ul className="space-y-2 max-h-[520px] overflow-y-auto pr-1">
        {items.length === 0 && (
          <li className="text-[12px] text-[var(--color-muted)]">None</li>
        )}
        {items.map((c) => (
          <li
            key={c.id}
            className="flex items-center justify-between gap-2 py-1.5 border-b hairline last:border-0"
          >
            <div className="min-w-0">
              <div className="flex items-center gap-1.5">
                <AcceleratorBadge slug={c.accelerator} />
                <Link
                  href={`/explorer?q=${encodeURIComponent(c.name)}`}
                  className="font-medium text-[14px] text-[var(--color-ink)] hover:text-[var(--color-accent)] truncate"
                >
                  {c.name}
                </Link>
              </div>
              <div className="text-[11px] text-[var(--color-muted)] truncate">
                {c.industry} · {c.founded_year ?? "—"}
              </div>
            </div>
            <StatusPill status={c.status} />
          </li>
        ))}
      </ul>
    </div>
  );
}
