"use client";

import {
  ColumnDef,
  SortingState,
  flexRender,
  getCoreRowModel,
  getFilteredRowModel,
  getSortedRowModel,
  useReactTable,
} from "@tanstack/react-table";
import { useVirtualizer } from "@tanstack/react-virtual";
import { ArrowDown, ArrowUp, ChevronDown, ChevronUp, ExternalLink, X } from "lucide-react";
import Link from "next/link";
import { useMemo, useRef, useState } from "react";

import { AcceleratorBadge } from "@/components/accelerator-badge";
import { StatusPill } from "@/components/status-pill";
import { ACCELERATOR_LABELS, AcceleratorSlug, Company } from "@/lib/types";
import { fmtInt, fmtNum, fmtUsd, hostname } from "@/lib/format";
import { cn } from "@/lib/utils";
import { EMPTY_FILTERS, Filters } from "./explorer-shell";

export function CompanyTable({
  data,
  filters,
  setFilters,
  industries,
}: {
  data: Company[];
  filters: Filters;
  setFilters: (f: Filters) => void;
  industries: Array<[string, number]>;
}) {
  const [sorting, setSorting] = useState<SortingState>([
    { id: "founded_year", desc: true },
  ]);
  const [selected, setSelected] = useState<Company | null>(null);

  const filtered = useMemo(() => {
    const q = filters.search.trim().toLowerCase();
    const industriesActive = filters.industries.size > 0;
    return data.filter((c) => {
      if (!filters.accelerators.has(c.accelerator)) return false;
      if (!filters.statuses.has(c.status)) return false;
      if (industriesActive && !filters.industries.has(c.industry)) return false;
      if (filters.yearMin != null && (c.founded_year ?? -Infinity) < filters.yearMin) return false;
      if (filters.yearMax != null && (c.founded_year ?? Infinity) > filters.yearMax) return false;
      if (filters.topOnly && !c.is_top_company) return false;
      if (filters.hiringOnly && !c.is_hiring) return false;
      if (filters.withWebsite && !c.website) return false;
      if (filters.withLinkedIn && !c.linkedin_url) return false;
      if (filters.batchSlug && c.batch_slug !== filters.batchSlug) return false;
      if (filters.serialOnly && !c.has_serial_founder) return false;
      if (q) {
        const hay =
          `${c.name} ${c.one_liner ?? ""} ${c.industry} ${c.all_locations ?? ""} ${hostname(c.website)}`.toLowerCase();
        if (!hay.includes(q)) return false;
      }
      return true;
    });
  }, [data, filters]);

  const columns = useMemo<ColumnDef<Company>[]>(
    () => [
      {
        id: "name",
        header: "Company",
        accessorKey: "name",
        size: 240,
        cell: ({ row }) => (
          <div className="flex flex-col min-w-0">
            <span className="font-medium text-[var(--color-ink)] truncate">
              {row.original.name}
            </span>
            <span className="text-[11px] text-[var(--color-muted)] truncate">
              {row.original.one_liner ?? "—"}
            </span>
          </div>
        ),
      },
      {
        id: "accelerator",
        header: "Accelerator",
        accessorFn: (c) => c.accelerator,
        size: 110,
        cell: ({ row }) => <AcceleratorBadge slug={row.original.accelerator} />,
      },
      {
        id: "batch",
        header: "Batch",
        accessorFn: (c) => c.batch_name ?? `${c.batch_year ?? ""}`,
        size: 120,
        cell: ({ row }) => (
          <span className="text-[12px] text-[var(--color-ink-3)] num-tabular">
            {row.original.batch_name ?? "—"}
          </span>
        ),
        sortingFn: (a, b) => (b.original.batch_year ?? 0) - (a.original.batch_year ?? 0),
      },
      {
        id: "founded_year",
        header: "Founded",
        accessorKey: "founded_year",
        size: 90,
        cell: ({ getValue }) => (
          <span className="num-tabular text-[var(--color-ink-3)]">
            {(getValue() as number | null) ?? "—"}
          </span>
        ),
        sortDescFirst: true,
      },
      {
        id: "industry",
        header: "Industry",
        accessorKey: "industry",
        size: 180,
        cell: ({ getValue }) => (
          <span className="text-[12px] text-[var(--color-ink-2)] truncate block">
            {getValue() as string}
          </span>
        ),
      },
      {
        id: "status",
        header: "Status",
        accessorKey: "status",
        size: 100,
        cell: ({ getValue }) => <StatusPill status={getValue() as string} />,
      },
      {
        id: "funding_tier",
        header: "Stage",
        accessorKey: "funding_tier",
        size: 100,
        cell: ({ getValue }) => {
          const v = getValue() as string | null;
          if (!v) return <span className="text-[var(--color-muted)]">—</span>;
          return (
            <span className="text-[11px] bg-[var(--color-cream-3)] text-[var(--color-ink-3)] px-1.5 py-0.5 rounded">
              {v}
            </span>
          );
        },
      },
      {
        id: "team_size_current",
        header: "Team",
        accessorKey: "team_size_current",
        size: 70,
        cell: ({ getValue }) => (
          <span className="num-tabular text-[var(--color-ink-3)] text-right block">
            {fmtInt(getValue() as number | null)}
          </span>
        ),
      },
      {
        id: "total_funding_usd",
        header: "Funding",
        accessorKey: "total_funding_usd",
        size: 100,
        cell: ({ row }) => {
          const v = row.original.total_funding_usd;
          if (v == null) return <span className="text-[var(--color-muted)]">—</span>;
          return (
            <span
              className="num-tabular text-[var(--color-ink-3)] text-right block"
              title={`Source: ${row.original.total_funding_source ?? "unknown"} · confidence ${
                row.original.total_funding_confidence?.toFixed(2) ?? "n/a"
              }`}
            >
              {fmtUsd(v)}
            </span>
          );
        },
        sortDescFirst: true,
        sortUndefined: "last",
      },
      {
        id: "traction_users",
        header: "Users",
        accessorKey: "traction_users",
        size: 90,
        cell: ({ row }) => {
          const v = row.original.traction_users;
          if (v == null) return <span className="text-[var(--color-muted)]">—</span>;
          return (
            <span
              className="num-tabular text-[var(--color-ink-3)] text-right block text-[11px]"
              title={`Extracted from description · confidence: ${row.original.traction_confidence?.toFixed(2) ?? "n/a"}`}
            >
              {fmtNum(v)}
            </span>
          );
        },
        sortDescFirst: true,
        sortUndefined: "last",
      },
      {
        id: "all_locations",
        header: "Location",
        accessorKey: "all_locations",
        size: 160,
        cell: ({ getValue }) => (
          <span className="text-[12px] text-[var(--color-ink-3)] truncate block">
            {(getValue() as string) ?? "—"}
          </span>
        ),
      },
      {
        id: "website",
        header: "Website",
        accessorKey: "website",
        size: 160,
        enableSorting: false,
        cell: ({ row }) => {
          const url = row.original.website;
          if (!url) return <span className="text-[var(--color-muted)]">—</span>;
          return (
            <a
              href={url}
              target="_blank"
              rel="noreferrer"
              className="flex items-center gap-1 text-[12px] text-[var(--color-accent)] hover:underline truncate"
              onClick={(e) => e.stopPropagation()}
            >
              {hostname(url)}
              <ExternalLink size={11} />
            </a>
          );
        },
      },
    ],
    []
  );

  const table = useReactTable({
    data: filtered,
    columns,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    enableSortingRemoval: false,
  });

  const rows = table.getRowModel().rows;
  const parentRef = useRef<HTMLDivElement>(null);
  const rowVirtualizer = useVirtualizer({
    count: rows.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 52,
    overscan: 18,
  });

  const totalSize = rowVirtualizer.getTotalSize();
  const virtualRows = rowVirtualizer.getVirtualItems();
  const paddingTop = virtualRows.length > 0 ? virtualRows[0].start : 0;
  const paddingBottom =
    virtualRows.length > 0 ? totalSize - virtualRows[virtualRows.length - 1].end : 0;

  const totalColumnsWidth = table.getTotalSize();

  return (
    <div className="grid lg:grid-cols-[260px_1fr] gap-6">
      <FiltersPanel
        filters={filters}
        setFilters={setFilters}
        industries={industries}
      />

      <div>
        <TopBar
          count={filtered.length}
          total={data.length}
          filters={filters}
          setFilters={setFilters}
        />

        <div
          ref={parentRef}
          className="card overflow-auto"
          style={{ height: "calc(100dvh - 260px)", minHeight: 540 }}
        >
          <table
            className="w-full border-collapse"
            style={{ width: totalColumnsWidth }}
          >
            <thead className="sticky top-0 z-10 bg-[var(--color-cream-2)]">
              {table.getHeaderGroups().map((hg) => (
                <tr key={hg.id}>
                  {hg.headers.map((h) => {
                    const sorted = h.column.getIsSorted();
                    return (
                      <th
                        key={h.id}
                        onClick={h.column.getCanSort() ? h.column.getToggleSortingHandler() : undefined}
                        style={{ width: h.getSize() }}
                        className={cn(
                          "text-left text-[11px] uppercase tracking-[0.12em] text-[var(--color-muted)] font-semibold px-3 py-2.5 border-b hairline",
                          h.column.getCanSort() && "cursor-pointer select-none hover:text-[var(--color-ink-2)]"
                        )}
                      >
                        <span className="inline-flex items-center gap-1">
                          {flexRender(h.column.columnDef.header, h.getContext())}
                          {sorted === "asc" && <ArrowUp size={11} />}
                          {sorted === "desc" && <ArrowDown size={11} />}
                        </span>
                      </th>
                    );
                  })}
                </tr>
              ))}
            </thead>
            <tbody>
              {paddingTop > 0 && (
                <tr>
                  <td style={{ height: paddingTop }} colSpan={columns.length} />
                </tr>
              )}
              {virtualRows.map((vr) => {
                const row = rows[vr.index];
                return (
                  <tr
                    key={row.id}
                    onClick={() => setSelected(row.original)}
                    className="cursor-pointer hover:bg-[var(--color-cream-2)]/70 border-b hairline transition-colors"
                    style={{ height: 52 }}
                  >
                    {row.getVisibleCells().map((cell) => (
                      <td
                        key={cell.id}
                        className="px-3 py-2.5 align-middle"
                        style={{ width: cell.column.getSize(), maxWidth: cell.column.getSize() }}
                      >
                        {flexRender(cell.column.columnDef.cell, cell.getContext())}
                      </td>
                    ))}
                  </tr>
                );
              })}
              {paddingBottom > 0 && (
                <tr>
                  <td style={{ height: paddingBottom }} colSpan={columns.length} />
                </tr>
              )}
            </tbody>
          </table>
          {rows.length === 0 && (
            <div className="p-12 text-center text-[var(--color-muted)] text-sm">
              No companies match these filters.
            </div>
          )}
        </div>
      </div>

      {selected && <CompanyDrawer company={selected} onClose={() => setSelected(null)} />}
    </div>
  );
}

function TopBar({
  count,
  total,
  filters,
  setFilters,
}: {
  count: number;
  total: number;
  filters: Filters;
  setFilters: (f: Filters) => void;
}) {
  return (
    <div className="mb-4 space-y-2">
      <div className="flex flex-wrap gap-3 items-center">
        <div className="flex-1 min-w-[240px] relative">
          <input
            type="text"
            placeholder="Search name, description, industry, location, domain…"
            value={filters.search}
            onChange={(e) => setFilters({ ...filters, search: e.target.value })}
            className="w-full px-4 py-2.5 text-sm rounded-lg border hairline bg-white focus:outline-none focus:border-[var(--color-accent)] focus:ring-2 focus:ring-[var(--color-accent)]/20"
          />
          {filters.search && (
            <button
              onClick={() => setFilters({ ...filters, search: "" })}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-[var(--color-muted)] hover:text-[var(--color-ink)]"
            >
              <X size={14} />
            </button>
          )}
        </div>
        <div className="text-[12px] text-[var(--color-muted)] num-tabular">
          Showing <span className="text-[var(--color-ink)] font-semibold">{fmtInt(count)}</span> of {fmtInt(total)}
        </div>
      </div>
      {filters.batchSlug && (
        <div className="flex items-center gap-2">
          <span className="inline-flex items-center gap-2 px-3 py-1 bg-[var(--color-accent-soft)] text-[var(--color-accent)] rounded-full text-xs font-medium">
            Batch: {filters.batchSlug}
            <button
              onClick={() => setFilters({ ...filters, batchSlug: null })}
              className="hover:text-[var(--color-accent-hover)]"
            >
              <X size={12} />
            </button>
          </span>
        </div>
      )}
    </div>
  );
}

function FiltersPanel({
  filters,
  setFilters,
  industries,
}: {
  filters: Filters;
  setFilters: (f: Filters) => void;
  industries: Array<[string, number]>;
}) {
  const [industryOpen, setIndustryOpen] = useState(true);
  const toggleSet = <T,>(set: Set<T>, val: T): Set<T> => {
    const next = new Set(set);
    if (next.has(val)) next.delete(val);
    else next.add(val);
    return next;
  };
  return (
    <aside className="space-y-6">
      <Group label="Accelerators">
        {(["yc", "ef", "spc", "a16z_speedrun"] as AcceleratorSlug[]).map((s) => (
          <CheckItem
            key={s}
            label={ACCELERATOR_LABELS[s]}
            checked={filters.accelerators.has(s)}
            onChange={() =>
              setFilters({ ...filters, accelerators: toggleSet(filters.accelerators, s) })
            }
          />
        ))}
      </Group>

      <Group label="Status">
        {["Active", "Acquired", "Public", "Dead", "Unknown"].map((s) => (
          <CheckItem
            key={s}
            label={s}
            checked={filters.statuses.has(s)}
            onChange={() =>
              setFilters({ ...filters, statuses: toggleSet(filters.statuses, s) })
            }
          />
        ))}
      </Group>

      <Group label="Founded year">
        <div className="flex gap-2 items-center">
          <input
            type="number"
            placeholder="from"
            value={filters.yearMin ?? ""}
            onChange={(e) =>
              setFilters({ ...filters, yearMin: e.target.value ? Number(e.target.value) : null })
            }
            className="w-full px-2 py-1 text-sm rounded border hairline bg-white num-tabular"
          />
          <span className="text-[var(--color-muted)]">–</span>
          <input
            type="number"
            placeholder="to"
            value={filters.yearMax ?? ""}
            onChange={(e) =>
              setFilters({ ...filters, yearMax: e.target.value ? Number(e.target.value) : null })
            }
            className="w-full px-2 py-1 text-sm rounded border hairline bg-white num-tabular"
          />
        </div>
      </Group>

      <Group label="Flags">
        <CheckItem
          label="Top company (YC)"
          checked={filters.topOnly}
          onChange={() => setFilters({ ...filters, topOnly: !filters.topOnly })}
        />
        <CheckItem
          label="Is hiring"
          checked={filters.hiringOnly}
          onChange={() => setFilters({ ...filters, hiringOnly: !filters.hiringOnly })}
        />
        <CheckItem
          label="Has website"
          checked={filters.withWebsite}
          onChange={() => setFilters({ ...filters, withWebsite: !filters.withWebsite })}
        />
        <CheckItem
          label="Has LinkedIn"
          checked={filters.withLinkedIn}
          onChange={() => setFilters({ ...filters, withLinkedIn: !filters.withLinkedIn })}
        />
        <CheckItem
          label="Serial founder"
          checked={filters.serialOnly}
          onChange={() => setFilters({ ...filters, serialOnly: !filters.serialOnly })}
        />
      </Group>

      <Group label="Industry" collapsible open={industryOpen} onToggle={() => setIndustryOpen(!industryOpen)}>
        {industryOpen && (
          <div className="max-h-72 overflow-y-auto pr-1 space-y-0.5">
            {industries.map(([ind, n]) => (
              <CheckItem
                key={ind}
                label={
                  <span className="flex justify-between w-full">
                    <span className="truncate">{ind}</span>
                    <span className="text-[var(--color-muted)] ml-2 num-tabular">{n}</span>
                  </span>
                }
                checked={filters.industries.has(ind)}
                onChange={() =>
                  setFilters({ ...filters, industries: toggleSet(filters.industries, ind) })
                }
              />
            ))}
          </div>
        )}
      </Group>

      <button
        onClick={() => setFilters(EMPTY_FILTERS)}
        className="w-full px-3 py-2 text-[12px] text-[var(--color-accent)] hover:bg-[var(--color-accent-soft)] rounded-md transition-colors text-left"
      >
        Reset filters
      </button>
    </aside>
  );
}

function Group({
  label,
  children,
  collapsible,
  open,
  onToggle,
}: {
  label: string;
  children: React.ReactNode;
  collapsible?: boolean;
  open?: boolean;
  onToggle?: () => void;
}) {
  return (
    <section>
      <button
        onClick={collapsible ? onToggle : undefined}
        className="flex items-center justify-between w-full mb-2 text-[11px] uppercase tracking-[0.15em] text-[var(--color-muted)] font-semibold"
      >
        {label}
        {collapsible && (open ? <ChevronUp size={12} /> : <ChevronDown size={12} />)}
      </button>
      <div className="space-y-1">{children}</div>
    </section>
  );
}

function CheckItem({
  label,
  checked,
  onChange,
}: {
  label: React.ReactNode;
  checked: boolean;
  onChange: () => void;
}) {
  return (
    <label className="flex items-start gap-2 cursor-pointer text-[13px] text-[var(--color-ink-2)] hover:text-[var(--color-ink)] py-0.5">
      <input
        type="checkbox"
        checked={checked}
        onChange={onChange}
        className="mt-0.5 accent-[var(--color-accent)]"
      />
      <span className="flex-1 min-w-0">{label}</span>
    </label>
  );
}

function CompanyDrawer({
  company,
  onClose,
}: {
  company: Company;
  onClose: () => void;
}) {
  return (
    <>
      <div
        onClick={onClose}
        className="fixed inset-0 bg-[var(--color-ink)]/20 backdrop-blur-[2px] z-40"
      />
      <aside className="fixed right-0 top-0 bottom-0 w-full max-w-[540px] bg-[var(--color-cream)] border-l hairline z-50 overflow-y-auto shadow-2xl">
        <div className="sticky top-0 bg-[var(--color-cream)] border-b hairline px-6 py-4 flex items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <AcceleratorBadge slug={company.accelerator} />
              <StatusPill status={company.status} />
              {company.is_top_company ? (
                <span className="text-[10px] uppercase tracking-wider bg-[var(--color-accent-soft)] text-[var(--color-accent)] px-2 py-0.5 rounded">
                  Top company
                </span>
              ) : null}
            </div>
            <h2 className="font-serif text-[28px] italic tracking-tight text-[var(--color-ink)]">
              {company.name}
            </h2>
            {company.one_liner && (
              <p className="text-[14px] text-[var(--color-ink-3)] mt-1">{company.one_liner}</p>
            )}
          </div>
          <button
            onClick={onClose}
            className="p-1 hover:bg-[var(--color-cream-2)] rounded"
            aria-label="Close"
          >
            <X size={18} />
          </button>
        </div>

        <div className="p-6 space-y-6">
          <DrawerSection label="Key data">
            <KV k="Batch" v={company.batch_name ?? "—"} />
            <KV k="Founded" v={company.founded_year?.toString() ?? "—"} />
            <KV k="Industry" v={company.industry} />
            {company.stage && <KV k="Stage" v={company.stage} />}
            {company.all_locations && <KV k="Location" v={company.all_locations} />}
            {company.team_size_current && <KV k="Team size" v={fmtInt(company.team_size_current)} />}
            {company.total_funding_usd != null && (
              <KV
                k="Funding (mentioned)"
                v={`${fmtUsd(company.total_funding_usd)}${
                  company.last_round_type ? ` · ${company.last_round_type}` : ""
                }`}
              />
            )}
            {(company.traction_arr_usd != null || company.traction_mrr_usd != null) && (
              <KV
                k="Revenue (mentioned)"
                v={[
                  company.traction_arr_usd ? `${fmtUsd(company.traction_arr_usd)} ARR` : null,
                  company.traction_mrr_usd ? `${fmtUsd(company.traction_mrr_usd)} MRR` : null,
                ].filter(Boolean).join(" · ")}
              />
            )}
            {company.traction_users != null && (
              <KV k="Users (mentioned)" v={`${fmtNum(company.traction_users)} users`} />
            )}
            {company.traction_customers != null && (
              <KV k="Customers" v={`${fmtNum(company.traction_customers)} customers`} />
            )}
            {company.traction_gmv_usd != null && (
              <KV k="GMV (mentioned)" v={fmtUsd(company.traction_gmv_usd)} />
            )}
            {company.traction_growth_rate != null && (
              <KV k="Growth rate" v={`${company.traction_growth_rate}%`} />
            )}
          </DrawerSection>

          {company.founders.length > 0 && (
            <DrawerSection label={`Founders (${company.founders.length})`}>
              <ul className="space-y-1.5">
                {company.founders.map((f, i) => (
                  <li key={i} className="flex justify-between items-center">
                    <div>
                      <span className="text-[var(--color-ink)]">{f.name}</span>
                      {f.role && (
                        <span className="text-[11px] text-[var(--color-muted)] ml-2 uppercase tracking-wider">
                          {f.role}
                        </span>
                      )}
                    </div>
                    {f.linkedin && (
                      <a
                        href={f.linkedin}
                        target="_blank"
                        rel="noreferrer"
                        className="text-[12px] text-[var(--color-accent)] hover:underline flex items-center gap-1"
                      >
                        LinkedIn <ExternalLink size={10} />
                      </a>
                    )}
                  </li>
                ))}
              </ul>
            </DrawerSection>
          )}

          <DrawerSection label="Links">
            {company.website && <LinkRow label="Website" url={company.website} />}
            {company.linkedin_url && <LinkRow label="LinkedIn" url={company.linkedin_url} />}
            {company.twitter_url && <LinkRow label="Twitter / X" url={company.twitter_url} />}
            {company.source_url && (
              <LinkRow label="Accelerator page" url={company.source_url} />
            )}
          </DrawerSection>

          <DrawerSection label="Provenance">
            <KV
              k="Status source"
              v={company.status_source ?? "—"}
              mono
            />
            <KV
              k="Status confidence"
              v={company.status_confidence != null ? company.status_confidence.toFixed(2) : "—"}
            />
          </DrawerSection>
        </div>
      </aside>
    </>
  );
}

function DrawerSection({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <section>
      <div className="text-[11px] uppercase tracking-[0.15em] text-[var(--color-muted)] mb-2 font-semibold">
        {label}
      </div>
      <div className="space-y-1 text-[14px]">{children}</div>
    </section>
  );
}

function KV({ k, v, mono }: { k: string; v: string; mono?: boolean }) {
  return (
    <div className="flex justify-between gap-4 py-1 border-b hairline last:border-0">
      <span className="text-[12px] text-[var(--color-muted)]">{k}</span>
      <span
        className={cn(
          "text-[13px] text-[var(--color-ink-2)] text-right",
          mono && "font-mono text-[11px]"
        )}
      >
        {v}
      </span>
    </div>
  );
}

function LinkRow({ label, url }: { label: string; url: string }) {
  return (
    <a
      href={url}
      target="_blank"
      rel="noreferrer"
      className="flex items-center justify-between py-1.5 px-2 -mx-2 hover:bg-[var(--color-cream-2)] rounded group"
    >
      <span className="text-[12px] text-[var(--color-muted)]">{label}</span>
      <span className="text-[13px] text-[var(--color-accent)] flex items-center gap-1 truncate max-w-[320px]">
        {hostname(url)} <ExternalLink size={11} />
      </span>
    </a>
  );
}
