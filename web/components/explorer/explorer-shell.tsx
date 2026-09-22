"use client";

import { useSearchParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import { CompanyTable } from "./company-table";
import { NLFilterResult, NlFilterBar } from "./nl-filter-bar";
import { AcceleratorSlug, Company } from "@/lib/types";

export interface Filters {
  search: string;
  accelerators: Set<AcceleratorSlug>;
  statuses: Set<string>;
  industries: Set<string>;
  yearMin: number | null;
  yearMax: number | null;
  topOnly: boolean;
  hiringOnly: boolean;
  withWebsite: boolean;
  withLinkedIn: boolean;
  batchSlug: string | null;
  serialOnly: boolean;
}

export const EMPTY_FILTERS: Filters = {
  search: "",
  accelerators: new Set<AcceleratorSlug>(["yc", "ef", "spc", "a16z_speedrun"]),
  statuses: new Set(["Active", "Acquired", "Public", "Dead", "Unknown"]),
  industries: new Set(),
  yearMin: null,
  yearMax: null,
  topOnly: false,
  hiringOnly: false,
  withWebsite: false,
  withLinkedIn: false,
  batchSlug: null,
  serialOnly: false,
};

export function ExplorerShell({ data }: { data: Company[] }) {
  const sp = useSearchParams();
  const industries = useMemo(() => {
    const m = new Map<string, number>();
    for (const c of data) m.set(c.industry, (m.get(c.industry) ?? 0) + 1);
    return Array.from(m.entries()).sort((a, b) => b[1] - a[1]);
  }, [data]);

  const [filters, setFilters] = useState<Filters>(EMPTY_FILTERS);

  // Initialize from URL (?accelerator=yc, ?batch=winter-2024, ?q=foo)
  useEffect(() => {
    const acc = sp.get("accelerator");
    const batch = sp.get("batch");
    const q = sp.get("q");
    if (!acc && !batch && !q) return;
    setFilters((prev) => ({
      ...prev,
      accelerators: acc
        ? new Set<AcceleratorSlug>([acc as AcceleratorSlug])
        : prev.accelerators,
      batchSlug: batch ?? prev.batchSlug,
      search: q ?? prev.search,
    }));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function applyNL(r: NLFilterResult) {
    const next: Filters = { ...EMPTY_FILTERS };
    if (r.search != null) next.search = r.search;
    if (r.accelerators?.length)
      next.accelerators = new Set(r.accelerators as AcceleratorSlug[]);
    if (r.statuses?.length) next.statuses = new Set(r.statuses);
    if (r.industries?.length) next.industries = new Set(r.industries);
    if (r.yearMin != null) next.yearMin = r.yearMin;
    if (r.yearMax != null) next.yearMax = r.yearMax;
    if (r.topOnly) next.topOnly = true;
    if (r.hiringOnly) next.hiringOnly = true;
    if (r.withWebsite) next.withWebsite = true;
    if (r.withLinkedIn) next.withLinkedIn = true;
    if (r.serialOnly) next.serialOnly = true;
    setFilters(next);
  }

  return (
    <>
      <NlFilterBar
        onResult={applyNL}
        industries={industries.map((i) => i[0])}
      />
      <CompanyTable
        data={data}
        filters={filters}
        setFilters={setFilters}
        industries={industries}
      />
    </>
  );
}
