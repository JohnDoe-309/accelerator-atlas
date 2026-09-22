import Link from "next/link";
import { notFound } from "next/navigation";
import { ExternalLink } from "lucide-react";

import { AcceleratorBadge } from "@/components/accelerator-badge";
import { IndustryBar } from "@/components/charts/industry-bar";
import { OutcomeMixChart } from "@/components/charts/outcome-mix-chart";
import { MetricCard } from "@/components/metric-card";
import { StatusPill } from "@/components/status-pill";
import { getBatches, getCompanies, getSummary } from "@/lib/data";
import { fmtInt, fmtUsd, hostname } from "@/lib/format";
import { ACCELERATOR_LABELS, AcceleratorSlug } from "@/lib/types";

export async function generateStaticParams() {
  return ["yc", "ef", "spc", "a16z_speedrun"].map((slug) => ({ slug }));
}

export default async function AcceleratorDetailPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug: raw } = await params;
  if (!["yc", "ef", "spc", "a16z_speedrun"].includes(raw)) notFound();
  const slug = raw as AcceleratorSlug;

  const [summary, companies, batches] = await Promise.all([
    getSummary(),
    getCompanies(),
    getBatches(),
  ]);
  const accel = summary.accelerators.find((a) => a.slug === slug);
  if (!accel) notFound();

  const ownCompanies = companies.filter((c) => c.accelerator === slug);
  const ownBatches = batches
    .filter((b) => b.accelerator === slug)
    .sort((a, b) => (b.year ?? 0) - (a.year ?? 0));

  // Industry distribution
  const indMap = new Map<string, number>();
  for (const c of ownCompanies) indMap.set(c.industry, (indMap.get(c.industry) ?? 0) + 1);
  const industries = Array.from(indMap.entries())
    .map(([industry, n]) => ({ industry, n }))
    .sort((a, b) => b.n - a.n);

  // Cohort outcome mix
  const yearMap = new Map<
    number,
    { Active: number; Acquired: number; Public: number; Dead: number; Unknown: number }
  >();
  for (const c of ownCompanies) {
    if (!c.founded_year || c.founded_year < 2008 || c.founded_year > 2025) continue;
    if (!yearMap.has(c.founded_year))
      yearMap.set(c.founded_year, { Active: 0, Acquired: 0, Public: 0, Dead: 0, Unknown: 0 });
    const b = yearMap.get(c.founded_year)!;
    b[(c.status as keyof typeof b) ?? "Unknown"] += 1;
  }
  const yearRows = Array.from(yearMap.entries())
    .map(([year, v]) => ({ label: String(year), ...v }))
    .sort((a, b) => Number(b.label) - Number(a.label));

  // Top performers (acquired / public / top)
  const notable = [...ownCompanies]
    .filter((c) => c.status === "Acquired" || c.status === "Public" || c.is_top_company)
    .sort((a, b) => (b.founded_year ?? 0) - (a.founded_year ?? 0))
    .slice(0, 20);

  const exitRate =
    ((accel.acquired_count + accel.public_count) / Math.max(1, accel.company_count)) * 100;
  const deadRate = (accel.dead_count / Math.max(1, accel.company_count)) * 100;

  return (
    <div className="max-w-[1400px] mx-auto px-6 py-10">
      <header className="mb-10">
        <div className="flex items-center gap-3 mb-3">
          <AcceleratorBadge slug={slug} />
          <span className="text-[11px] uppercase tracking-[0.2em] text-[var(--color-muted)]">
            Accelerator profile
          </span>
        </div>
        <h1 className="font-serif italic text-[56px] leading-[1.05] tracking-tight mb-3">
          {accel.name}
        </h1>
        <p className="text-[16px] text-[var(--color-ink-3)] max-w-3xl leading-relaxed mb-4">
          {accel.description}
        </p>
        <div className="flex items-center gap-6 text-[13px] text-[var(--color-muted)]">
          <span>{accel.hq_location ?? "—"}</span>
          <span>Founded {accel.founded_year ?? "—"}</span>
          {accel.website && (
            <a
              href={accel.website}
              target="_blank"
              rel="noreferrer"
              className="text-[var(--color-accent)] hover:underline flex items-center gap-1"
            >
              {hostname(accel.website)} <ExternalLink size={11} />
            </a>
          )}
        </div>
      </header>

      {/* KPIs */}
      <section className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-10">
        <MetricCard label="Companies" value={fmtInt(accel.company_count)} accent />
        <MetricCard
          label="Exit rate"
          value={`${exitRate.toFixed(1)}%`}
          sub={`${accel.acquired_count} acquired · ${accel.public_count} public`}
        />
        <MetricCard
          label="Mortality"
          value={`${deadRate.toFixed(1)}%`}
          sub={`${fmtInt(accel.dead_count)} dead`}
        />
        <MetricCard
          label="Batches"
          value={fmtInt(ownBatches.length)}
          sub={
            ownBatches.length
              ? `${ownBatches[ownBatches.length - 1]?.year ?? "—"}–${ownBatches[0]?.year ?? "—"}`
              : "—"
          }
        />
      </section>

      {/* Typical check + program details */}
      <section className="card p-6 mb-10">
        <h2 className="font-serif italic text-[22px] tracking-tight mb-4">Program mechanics</h2>
        <dl className="grid md:grid-cols-3 gap-x-8 gap-y-3 text-[14px]">
          <KV
            k="Typical check"
            v={accel.investment_amount_usd ? fmtUsd(accel.investment_amount_usd) : "—"}
          />
          <KV
            k="Typical equity"
            v={accel.investment_equity_pct ? `${accel.investment_equity_pct}%` : "—"}
          />
          <KV k="Terms" v={accel.investment_terms_note ?? "—"} />
          <KV
            k="Program length"
            v={
              accel.program_duration_weeks
                ? `${accel.program_duration_weeks} weeks`
                : "Ongoing / N/A"
            }
          />
          <KV k="Cadence" v={accel.batch_cadence ?? "—"} />
          <KV k="Focus areas" v={accel.focus_areas ?? "—"} />
        </dl>
      </section>

      {/* Charts */}
      <section className="grid lg:grid-cols-[2fr_3fr] gap-6 mb-10">
        <div className="card p-6">
          <h3 className="font-serif text-[22px] italic tracking-tight mb-1">Industries</h3>
          <p className="text-[12px] text-[var(--color-muted)] mb-4">
            Normalized taxonomy. Counts reflect {ACCELERATOR_LABELS[slug]}'s portfolio only.
          </p>
          <IndustryBar rows={industries} />
        </div>
        <div className="card p-6">
          <h3 className="font-serif text-[22px] italic tracking-tight mb-1">Outcome mix by cohort</h3>
          <p className="text-[12px] text-[var(--color-muted)] mb-4">
            Newest cohort first. Stacked by status.
          </p>
          <OutcomeMixChart data={yearRows} height={320} />
        </div>
      </section>

      {/* Batches list */}
      <section className="mb-10">
        <div className="flex justify-between items-baseline mb-4">
          <h2 className="font-serif italic text-[28px] tracking-tight">Batches</h2>
          <Link
            href={`/explorer?accelerator=${slug}`}
            className="text-[13px] text-[var(--color-accent)] hover:underline"
          >
            Open in Explorer →
          </Link>
        </div>
        <div className="card overflow-hidden">
          <table className="w-full">
            <thead className="bg-[var(--color-cream-2)] text-[11px] uppercase tracking-[0.12em] text-[var(--color-muted)]">
              <tr>
                <th className="text-left px-4 py-2.5">Batch</th>
                <th className="text-right px-4 py-2.5">Companies</th>
                <th className="text-right px-4 py-2.5">Active</th>
                <th className="text-right px-4 py-2.5">Acquired</th>
                <th className="text-right px-4 py-2.5">Public</th>
                <th className="text-right px-4 py-2.5">Dead</th>
              </tr>
            </thead>
            <tbody>
              {ownBatches.slice(0, 40).map((b) => (
                <tr key={b.id} className="border-t hairline hover:bg-[var(--color-cream-2)]/50">
                  <td className="px-4 py-2.5 font-medium">{b.name}</td>
                  <td className="px-4 py-2.5 text-right num-tabular">{fmtInt(b.company_count)}</td>
                  <td className="px-4 py-2.5 text-right num-tabular text-[var(--color-success)]">
                    {fmtInt(b.active_count)}
                  </td>
                  <td className="px-4 py-2.5 text-right num-tabular text-[var(--color-warning)]">
                    {fmtInt(b.acquired_count)}
                  </td>
                  <td className="px-4 py-2.5 text-right num-tabular text-[#2b5f8a]">
                    {fmtInt(b.public_count)}
                  </td>
                  <td className="px-4 py-2.5 text-right num-tabular text-[var(--color-danger)]">
                    {fmtInt(b.dead_count)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {ownBatches.length > 40 && (
            <div className="px-4 py-2 text-[12px] text-[var(--color-muted)] bg-[var(--color-cream-2)]/30 text-center">
              Showing latest 40 of {ownBatches.length}. Full list in the Batches page.
            </div>
          )}
        </div>
      </section>

      {/* Notable companies */}
      <section>
        <h2 className="font-serif italic text-[28px] tracking-tight mb-4">
          Notable companies
        </h2>
        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-3">
          {notable.map((c) => (
            <div key={c.id} className="card p-4">
              <div className="flex justify-between items-start mb-2">
                <div className="font-medium text-[var(--color-ink)]">{c.name}</div>
                <StatusPill status={c.status} />
              </div>
              <p className="text-[12px] text-[var(--color-ink-3)] line-clamp-2 mb-2 min-h-[30px]">
                {c.one_liner ?? "—"}
              </p>
              <div className="flex justify-between items-center text-[11px] text-[var(--color-muted)]">
                <span>{c.industry}</span>
                <span className="num-tabular">{c.founded_year ?? "—"}</span>
              </div>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}

function KV({ k, v }: { k: string; v: string }) {
  return (
    <div className="flex justify-between items-baseline gap-3 border-b hairline pb-2">
      <dt className="text-[12px] uppercase tracking-[0.12em] text-[var(--color-muted)]">{k}</dt>
      <dd className="text-[var(--color-ink-2)] text-right">{v}</dd>
    </div>
  );
}
