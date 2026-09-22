import Link from "next/link";

import { getInsights, getSummary } from "@/lib/data";
import { fmtInt, fmtUsd } from "@/lib/format";

export const metadata = {
  title: "About · Accelerator Atlas",
  description:
    "Methodology, data sources, and honest caveats for the Accelerator Atlas.",
};

export default async function AboutPage() {
  const s = await getSummary();
  const { budget } = await getInsights();
  const t = s.totals;

  return (
    <div className="max-w-[840px] mx-auto px-6 py-12">
      <p className="text-[12px] uppercase tracking-[0.2em] text-[var(--color-accent)] mb-4">
        About the project
      </p>
      <h1 className="font-serif text-[44px] leading-[1.05] tracking-tight italic text-[var(--color-ink)]">
        How this atlas was built, and what&rsquo;s actually in it.
      </h1>
      <p className="text-[15px] text-[var(--color-ink-3)] leading-relaxed mt-6">
        Accelerator Atlas is a personal research tool. It stitches together{" "}
        <strong>{fmtInt(t.n_companies)}</strong> companies across four programs,
        normalizes their industries, probes their websites for liveness, and
        layers on a small set of Grok-generated narratives — within a
        self-imposed <strong>$50 API budget</strong>. Everything below is built
        out of open data sources and a few thoughtful bits of glue; nothing here
        is scraped behind paywalls.
      </p>

      <Section title="Data sources">
        <ul className="space-y-3 text-[15px] text-[var(--color-ink-2)]">
          <li>
            <strong>Y Combinator</strong> — the public{" "}
            <Code>yc-oss/api</Code> GitHub mirror (updated weekly). Gave us
            batches, industries, statuses, launched_at, team size, and the{" "}
            <em>is_top_company</em> flag essentially for free.
          </li>
          <li>
            <strong>a16z Speedrun</strong> — their own website&rsquo;s REST
            endpoint (<Code>speedrun-be.a16z.com/api/companies</Code>)
            returns the full company list in one call, including descriptions
            and logos. No scraping required.
          </li>
          <li>
            <strong>South Park Commons</strong> — parsed from their public
            companies page via Firecrawl. Status labels (Acquired / Public) are
            inferred from slug suffixes and stage text.
          </li>
          <li>
            <strong>Entrepreneur First</strong> — their WordPress{" "}
            <Code>admin-ajax.php</Code> endpoint (discovered by reading the
            minified front-end JS) yields the full 490-company list plus
            founders, LinkedIn handles, and long descriptions.
          </li>
        </ul>
      </Section>

      <Section title="Enrichment pipeline">
        <ol className="space-y-3 text-[15px] text-[var(--color-ink-2)] list-decimal pl-5 marker:text-[var(--color-muted)]">
          <li>
            <strong>Liveness probe.</strong> A TLS-fingerprinted HTTP probe
            (via <Code>curl_cffi</Code>, impersonating Chrome) hits each
            company&rsquo;s domain and classifies dead / parked / active.
            Cloudflare and Vercel walls are handled; unreachable domains stay
            labelled &ldquo;Active&rdquo; with low confidence rather than being
            wrongly marked dead.
          </li>
          <li>
            <strong>Industry retagging.</strong> YC&rsquo;s granular{" "}
            <Code>tags</Code> are deterministically re-classified into a
            single 19-category taxonomy (<em>AI &amp; ML Infrastructure</em>,{" "}
            <em>Fintech</em>, etc.) so the four programs can be compared
            apples-to-apples.
          </li>
          <li>
            <strong>Funding text mining.</strong> Descriptions are scanned for
            funding-specific phrases (&ldquo;raised $X&rdquo;, &ldquo;Series A
            of $X&rdquo;, etc.) with a hand-written set of disqualifiers for
            market-size, revenue, valuation, and customer claims. Captured
            amounts are labelled <em>regex:description</em> with a confidence
            score. This is high-precision but low-recall — it&rsquo;s a floor.
          </li>
          <li>
            <strong>Serial founder detection.</strong> Founder names are
            normalised and cross-referenced across all four accelerators to
            surface people who&rsquo;ve been through more than one.
          </li>
          <li>
            <strong>Grok synthesis.</strong> Three passes on xAI&rsquo;s
            grok-4-fast models: industry label normalization, a white-space
            narrative, and one short essay per accelerator cohort. Every call
            is budget-tracked and cached by SHA-256 hash of its input.
          </li>
        </ol>
      </Section>

      <Section title="Known caveats">
        <ul className="space-y-3 text-[15px] text-[var(--color-ink-2)]">
          <li>
            <strong>Funding data is deliberately sparse.</strong> Only{" "}
            {fmtInt(
              (s.funding_coverage ?? []).reduce((sum, r) => sum + r.n_matched, 0)
            )}{" "}
            companies have an extracted amount. A proper Crunchbase or
            PitchBook mirror would dwarf this; out of scope for a $50 personal
            project.
          </li>
          <li>
            <strong>Status labels are imperfect.</strong> Active just means
            &ldquo;the domain responded and didn&rsquo;t look parked.&rdquo;{" "}
            Companies can be zombies for years behind a live marketing page.
          </li>
          <li>
            <strong>Team size is only for YC and Speedrun.</strong> SPC and EF
            don&rsquo;t publish headcount. Rather than fake an estimate, the
            field is left blank for those programs.
          </li>
          <li>
            <strong>Descriptions are self-reported.</strong> Anything the
            company says about itself should be read as marketing; the atlas
            reflects their framing, not necessarily reality.
          </li>
        </ul>
      </Section>

      <Section title="Budget">
        <div className="grid grid-cols-3 gap-4 text-[14px]">
          <Stat
            label="Cap"
            value={fmtUsd(budget.cap_usd)}
            sub="self-imposed"
          />
          <Stat
            label="Spent"
            value={fmtUsd(budget.spent_usd)}
            sub={`${budget.calls} calls`}
          />
          <Stat
            label="Remaining"
            value={fmtUsd(budget.remaining_usd)}
            sub={`${Math.round((100 * budget.remaining_usd) / budget.cap_usd)}% left`}
          />
        </div>
        <p className="text-[12px] text-[var(--color-muted)] mt-3">
          Every Grok call is logged to a local <Code>grok_usage</Code> table
          with token counts, USD cost, and an input hash. Cached hits are
          replayed for free, so re-running a synthesis job is a no-op unless
          the inputs actually change.
        </p>
      </Section>

      <Section title="Reproducibility">
        <p className="text-[14px] text-[var(--color-ink-2)] leading-relaxed">
          Data lives in a single SQLite file (<Code>data/accelerators.db</Code>).
          The Next.js app only reads static JSON produced by{" "}
          <Code>uv run python -m accelerator_atlas.export.to_json</Code>. A
          full refresh is <Code>make refresh-all</Code>: scrape, enrich, retag,
          find serial founders, export. Everything is stateless on the server;
          the Vercel deployment is just the static snapshot plus one serverless
          route (<Code>/api/nl-filter</Code>) that forwards to Grok.
        </p>
      </Section>

      <p className="text-[13px] text-[var(--color-muted)] mt-16 pt-6 border-t hairline">
        Snapshot generated{" "}
        <span className="num-tabular">
          {new Date(s.generated_at).toLocaleString()}
        </span>
        . Personal research — no warranties, expressed or implied.{" "}
        <Link
          href="/data-quality"
          className="text-[var(--color-accent)] hover:underline"
        >
          Field-level coverage →
        </Link>
      </p>
    </div>
  );
}

function Section({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="mt-10">
      <h2 className="font-serif text-[24px] italic tracking-tight text-[var(--color-ink)] mb-3">
        {title}
      </h2>
      {children}
    </section>
  );
}

function Stat({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="border hairline rounded-md p-4 bg-[var(--color-cream-2)]/40">
      <div className="text-[11px] uppercase tracking-[0.14em] text-[var(--color-muted)]">
        {label}
      </div>
      <div className="font-serif text-[26px] num-tabular text-[var(--color-ink)] mt-1">
        {value}
      </div>
      {sub && (
        <div className="text-[11px] text-[var(--color-ink-3)] num-tabular mt-0.5">
          {sub}
        </div>
      )}
    </div>
  );
}

function Code({ children }: { children: React.ReactNode }) {
  return (
    <code className="font-mono text-[12px] text-[var(--color-accent)] bg-[var(--color-accent-soft)] px-1.5 py-0.5 rounded">
      {children}
    </code>
  );
}
