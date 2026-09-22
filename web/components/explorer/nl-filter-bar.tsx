"use client";

import { Loader2, Sparkles } from "lucide-react";
import { useState } from "react";

export interface NLFilterResult {
  search?: string;
  accelerators?: string[];
  statuses?: string[];
  industries?: string[];
  yearMin?: number;
  yearMax?: number;
  topOnly?: boolean;
  hiringOnly?: boolean;
  withWebsite?: boolean;
  withLinkedIn?: boolean;
  serialOnly?: boolean;
  rationale?: string;
}

export function NlFilterBar({
  onResult,
  industries,
}: {
  onResult: (r: NLFilterResult) => void;
  industries: string[];
}) {
  const [text, setText] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [rationale, setRationale] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!text.trim() || loading) return;
    setLoading(true);
    setError(null);
    setRationale(null);
    try {
      const res = await fetch("/api/nl-filter", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: text, industries }),
      });
      if (!res.ok) throw new Error(await res.text());
      const data = (await res.json()) as NLFilterResult;
      setRationale(data.rationale ?? null);
      onResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="mb-5">
      <form
        onSubmit={submit}
        className="flex items-stretch gap-2 card p-1.5 bg-white"
      >
        <div className="flex items-center pl-3 text-[var(--color-accent)]">
          <Sparkles size={16} />
        </div>
        <input
          type="text"
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder='Try: "acquired YC AI fintechs from 2019-2022" or "dead EF consumer apps"'
          className="flex-1 bg-transparent px-2 py-2.5 text-sm focus:outline-none"
          disabled={loading}
        />
        <button
          type="submit"
          disabled={loading || !text.trim()}
          className="px-4 py-2 text-sm bg-[var(--color-accent)] hover:bg-[var(--color-accent-hover)] disabled:bg-[var(--color-muted-2)] text-white rounded-md transition-colors font-medium flex items-center gap-2"
        >
          {loading ? <Loader2 size={14} className="animate-spin" /> : null}
          {loading ? "Translating…" : "Filter"}
        </button>
      </form>
      {error && (
        <div className="mt-2 text-[12px] text-[var(--color-danger)]">{error}</div>
      )}
      {rationale && (
        <div className="mt-2 text-[12px] text-[var(--color-muted)] italic">
          {rationale}
        </div>
      )}
    </div>
  );
}
