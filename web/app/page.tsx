import Link from "next/link";

import { AcceleratorBadge } from "@/components/accelerator-badge";
import { BatchTrendChart } from "@/components/charts/batch-trend-chart";
import { IndustryBar } from "@/components/charts/industry-bar";
import { MetricCard } from "@/components/metric-card";
import { getCompanies, getSummary } from "@/lib/data";
import { fmtInt, fmtNum, fmtUsd } from "@/lib/format";
import { ACCELERATOR_LABELS } from "@/lib/types";

export default async function OverviewPage() {
  const s = await getSummary();
  const companies = await getCompanies();
  const t = s.totals;

  const accMetric = (
    ac: (typeof s.accelerators)[number],
    key: "active_count" | "acquired_count" | "dead_count"
  ) =>
    Math.round((100 * (ac[key] ?? 0)) / Math.max(1, ac.company_count));

  return (
    <div className="max-w-[1400px] mx-auto px-6 py-10">
      {/* Hero */}
      <section className="mb-12">
        <p className="text-[12px] uppercase tracking-[0.2em] text-[var(--color-accent)] mb-4">
          A cross-accelerator atlas
        </p>
        <h1 className="font-serif text-[56px] leading-[1.05] tracking-tight text-[var(--color-ink)] max-w-3xl italic">
          Every company from{" "}
          <span className="not-italic font-serif">YC</span>,{" "}
          <span className="not-italic font-serif">EF</span>,{" "}
          <span className="not-italic font-serif">SPC</span>, and{" "}
          <span className="not-italic font-serif">Speedrun</span>.
          <br />
          Stitched, cleaned, and ready to think with.
        </h1>
        <p className="mt-6 text-[17px] text-[var(--color-ink-3)] max-w-2xl leading-relaxed">
          {fmtInt(t.n_companies)} companies · {fmtInt(t.n_founders)} founders ·{" "}
          {fmtInt(t.n_batches)} batches. Snapshot generated{" "}
          {new Date(s.generated_at).toLocaleString()}.
        </p>
      </section>

      {/* KPI row */}
      <section className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-10">
        <MetricCard label="Companies" value={fmtNum(t.n_companies)} accent />
        <MetricCard
          label="Active"
          value={fmtNum(t.n_active)}
          sub={`${Math.round((100 * t.n_active) / t.n_companies)}% of total`}
        />
        <MetricCard
          label="Acquired"
          value={fmtNum(t.n_acquired)}
          sub={`${Math.round((100 * t.n_acquired) / t.n_companies)}% exited`}
        />
        <MetricCard
          label="Dead"
          value={fmtNum(t.n_dead)}
          sub={`${Math.round((100 * t.n_dead) / t.n_companies)}% mortality`}
        />
      </section>

      {/* Accelerator cards */}
      <section className="mb-12">
        <h2 className="font-serif text-[28px] italic mb-5 tracking-tight">
          The four accelerators
        </h2>
        <div className="grid md:grid-cols-2 xl:grid-cols-4 gap-4">
          {s.accelerators.map((a) => (
            <Link
              key={a.slug}
              href={`/accelerators/${a.slug}`}
              className="card p-5 flex flex-col hover:border-[var(--color-accent)]/40 hover:shadow-sm transition-all"
            >
              <div className="flex justify-between items-start mb-3">
                <div>
                  <div className="font-serif text-[22px] leading-none text-[var(--color-ink)]">
                    {a.name}
                  </div>
                  <div className="text-[11px] uppercase tracking-[0.15em] text-[var(--color-muted)] mt-1">
                    {a.hq_location ?? "—"} · est. {a.founded_year ?? "—"}
                  </div>
                </div>
                <AcceleratorBadge slug={a.slug} />
              </div>
              <p className="text-[13px] text-[var(--color-ink-3)] leading-relaxed line-clamp-3 mb-4 min-h-[54px]">
                {a.description}
              </p>
              <div className="grid grid-cols-4 gap-2 text-center mt-auto">
                <div>
                  <div className="font-serif text-[20px] num-tabular">
                    {fmtNum(a.company_count)}
                  </div>
                  <div className="text-[10px] uppercase tracking-wider text-[var(--color-muted)]">
                    Total
                  </div>
                </div>
                <div>
                  <div className="font-serif text-[20px] num-tabular text-[var(--color-success)]">
                    {accMetric(a, "active_count")}%
                  </div>
                  <div className="text-[10px] uppercase tracking-wider text-[var(--color-muted)]">
                    Active
                  </div>
                </div>
                <div>
                  <div className="font-serif text-[20px] num-tabular text-[var(--color-warning)]">
                    {accMetric(a, "acquired_count")}%
                  </div>
                  <div className="text-[10px] uppercase tracking-wider text-[var(--color-muted)]">
                    Exited
                  </div>
                </div>
                <div>
                  <div className="font-serif text-[20px] num-tabular text-[var(--color-danger)]">
                    {accMetric(a, "dead_count")}%
                  </div>
                  <div className="text-[10px] uppercase tracking-wider text-[var(--color-muted)]">
                    Dead
                  </div>
                </div>
              </div>
            </Link>
          ))}
        </div>
      </section>

      {/* Funding snapshot (high-precision, text-mined) */}
      {s.funding_coverage && s.funding_coverage.some((r) => r.n_matched > 0) && (
        <section className="mb-12 card p-6">
          <div className="flex items-baseline justify-between mb-1 gap-6 flex-wrap">
            <h3 className="font-serif text-[22px] italic tracking-tight">
              Funding mentions
            </h3>
            <p className="text-[11px] text-[var(--color-muted)] max-w-lg">
              Extracted from descriptions with a conservative regex. High
              precision, low recall — treat as a floor, not the truth.
            </p>
          </div>
          <div className="grid md:grid-cols-4 gap-3 mt-4">
            {s.funding_coverage.map((r) => {
              const pct = r.n_total ? (100 * r.n_matched) / r.n_total : 0;
              return (
                <div
                  key={r.slug}
                  className="border hairline rounded-md p-4 bg-[var(--color-cream-2)]/40"
                >
                  <div className="text-[11px] uppercase tracking-[0.14em] text-[var(--color-muted)]">
                    {ACCELERATOR_LABELS[r.slug]}
                  </div>
                  <div className="mt-1 font-serif text-[26px] num-tabular text-[var(--color-ink)]">
                    {r.n_matched}
                    <span className="text-[14px] text-[var(--color-muted)] ml-1">
                      / {r.n_total}
                    </span>
                  </div>
                  <div className="text-[11px] text-[var(--color-ink-3)] num-tabular mt-0.5">
                    {pct.toFixed(1)}% · Σ {fmtUsd(r.sum_usd || null)}
                  </div>
                </div>
              );
            })}
          </div>
        </section>
      )}

      {/* Charts row */}
      <section className="grid lg:grid-cols-[2fr_3fr] gap-6 mb-12">
        <div className="card p-6">
          <h3 className="font-serif text-[22px] italic mb-1 tracking-tight">
            Industry distribution
          </h3>
          <p className="text-[12px] text-[var(--color-muted)] mb-4">
            Unified taxonomy across all four accelerators (normalized labels).
          </p>
          <IndustryBar rows={s.industries} />
        </div>
        <div className="card p-6">
          <h3 className="font-serif text-[22px] italic mb-1 tracking-tight">
            Companies founded per year
          </h3>
          <p className="text-[12px] text-[var(--color-muted)] mb-4">
            Newest cohorts first. Stacked by accelerator.
          </p>
          <BatchTrendChart rows={s.batch_trend} />
        </div>
      </section>

      {/* Traction leaderboards */}
      <TractionSection companies={companies} />
    </div>
  );
}

function TractionSection({ companies }: { companies: Awaited<ReturnType<typeof getCompanies>> }) {
  const withUsers = companies
    .filter((c) => c.traction_users != null)
    .sort((a, b) => (b.traction_users || 0) - (a.traction_users || 0))
    .slice(0, 8);

  const withRevenue = companies
    .filter((c) => c.traction_arr_usd != null || c.traction_mrr_usd != null)
    .sort((a, b) => {
      const aRev = (a.traction_arr_usd || 0) + (a.traction_mrr_usd || 0) * 12;
      const bRev = (b.traction_arr_usd || 0) + (b.traction_mrr_usd || 0) * 12;
      return bRev - aRev;
    })
    .slice(0, 8);

  if (withUsers.length === 0 && withRevenue.length === 0) return null;

  return (
    <section className="mb-12">
      <div className="flex items-baseline justify-between mb-5">
        <h2 className="font-serif text-[28px] italic tracking-tight">
          Traction mentions
        </h2>
        <p className="text-[12px] text-[var(--color-muted)] max-w-md text-right">
          Self-reported metrics extracted from descriptions. Sparse by design —
          only explicit claims captured.
        </p>
      </div>

      <div className="grid lg:grid-cols-2 gap-6">
        {withUsers.length > 0 && (
          <div className="card p-5">
            <h3 className="font-serif text-[18px] italic mb-3">By users</h3>
            <ul className="space-y-2">
              {withUsers.map((c) => (
                <li key={c.id} className="flex justify-between items-center py-1.5 border-b hairline last:border-0">
                  <Link
                    href={`/explorer?batch=${c.batch_slug}`}
                    className="text-[14px] text-[var(--color-ink)] hover:text-[var(--color-accent)] truncate max-w-[200px]"
                  >
                    {c.name}
                  </Link>
                  <span className="num-tabular text-[13px] text-[var(--color-ink-3)]">
                    {fmtNum(c.traction_users || 0)} users
                  </span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {withRevenue.length > 0 && (
          <div className="card p-5">
            <h3 className="font-serif text-[18px] italic mb-3">By revenue (ARR/MRR)</h3>
            <ul className="space-y-2">
              {withRevenue.map((c) => (
                <li key={c.id} className="flex justify-between items-center py-1.5 border-b hairline last:border-0">
                  <Link
                    href={`/explorer?batch=${c.batch_slug}`}
                    className="text-[14px] text-[var(--color-ink)] hover:text-[var(--color-accent)] truncate max-w-[200px]"
                  >
                    {c.name}
                  </Link>
                  <span className="num-tabular text-[13px] text-[var(--color-ink-3)]">
                    {c.traction_arr_usd ? fmtUsd(c.traction_arr_usd) + " ARR" : fmtUsd((c.traction_mrr_usd || 0) * 12) + " ARR eq"}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </section>
  );
}
