import { BatchesTable } from "@/components/batches/batches-table";
import { getBatches } from "@/lib/data";
import { fmtInt } from "@/lib/format";

export default async function BatchesPage() {
  const batches = await getBatches();
  const totalCompanies = batches.reduce((s, b) => s + b.company_count, 0);
  const totalAcquired = batches.reduce((s, b) => s + b.acquired_count, 0);
  const totalDead = batches.reduce((s, b) => s + b.dead_count, 0);

  return (
    <div className="max-w-[1400px] mx-auto px-6 py-10">
      <header className="mb-8">
        <p className="text-[12px] uppercase tracking-[0.2em] text-[var(--color-accent)] mb-2">
          Batches
        </p>
        <h1 className="font-serif italic text-[44px] tracking-tight leading-[1.05] mb-3">
          {batches.length} cohorts, descending.
        </h1>
        <p className="text-[15px] text-[var(--color-ink-3)] max-w-2xl">
          Every batch we have data on — {fmtInt(totalCompanies)} companies in
          total, {fmtInt(totalAcquired)} acquired, {fmtInt(totalDead)} dead.
          Click a batch name to open the Explorer filtered to that cohort.
        </p>
      </header>

      <BatchesTable batches={batches} />
    </div>
  );
}
