"use client";

import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { AcceleratorBadge } from "@/components/accelerator-badge";
import { ACCELERATOR_LABELS, AcceleratorSlug, Insight } from "@/lib/types";
import { cn } from "@/lib/utils";

export function InsightTabs({ insights }: { insights: Insight[] }) {
  // Infer accelerator slug from the title ("yc: cohort narrative") for routing
  const tabs = insights
    .map((i) => {
      const match = /^([a-z_]+):/.exec(i.title ?? "");
      const slug = (match?.[1] ?? "unknown") as AcceleratorSlug;
      return { slug, insight: i };
    })
    .sort((a, b) =>
      // Newest-cohort-first interpretation: by insight created_at desc
      new Date(b.insight.created_at).getTime() - new Date(a.insight.created_at).getTime()
    );

  const [active, setActive] = useState(tabs[0]?.slug ?? null);
  const current = tabs.find((t) => t.slug === active) ?? tabs[0];

  return (
    <div>
      <div className="flex flex-wrap gap-2 mb-5 border-b hairline pb-4">
        {tabs.map((t) => (
          <button
            key={t.slug}
            onClick={() => setActive(t.slug)}
            className={cn(
              "px-3 py-1.5 text-sm rounded-md transition-colors flex items-center gap-2",
              active === t.slug
                ? "bg-[var(--color-accent-soft)] text-[var(--color-accent)] font-medium"
                : "text-[var(--color-ink-3)] hover:bg-[var(--color-cream-2)]"
            )}
          >
            <AcceleratorBadge slug={t.slug} />
            <span>{ACCELERATOR_LABELS[t.slug]}</span>
          </button>
        ))}
      </div>
      {current && (
        <article className="prose-atlas">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>
            {current.insight.content}
          </ReactMarkdown>
        </article>
      )}
    </div>
  );
}
