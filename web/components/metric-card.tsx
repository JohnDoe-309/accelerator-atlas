import { cn } from "@/lib/utils";

interface Props {
  label: string;
  value: string | number;
  sub?: string;
  accent?: boolean;
  className?: string;
}

export function MetricCard({ label, value, sub, accent, className }: Props) {
  return (
    <div
      className={cn(
        "card px-5 py-4 flex flex-col gap-1",
        accent && "bg-[var(--color-accent-soft)] border-[var(--color-accent)]/30",
        className
      )}
    >
      <div className="text-[11px] uppercase tracking-[0.15em] text-[var(--color-muted)]">
        {label}
      </div>
      <div className="font-serif text-[34px] leading-none text-[var(--color-ink)] num-tabular">
        {value}
      </div>
      {sub ? (
        <div className="text-xs text-[var(--color-ink-3)] mt-1">{sub}</div>
      ) : null}
    </div>
  );
}
