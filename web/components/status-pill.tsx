import { cn } from "@/lib/utils";

const STATUS_STYLES: Record<string, string> = {
  Active: "bg-[var(--color-success-soft)] text-[var(--color-success)]",
  Acquired: "bg-[var(--color-warning-soft)] text-[var(--color-warning)]",
  Public: "bg-[#dce6f0] text-[#2b5f8a]",
  Dead: "bg-[var(--color-danger-soft)] text-[var(--color-danger)]",
  Unknown: "bg-[var(--color-cream-3)] text-[var(--color-muted)]",
};

export function StatusPill({ status }: { status: string }) {
  return (
    <span
      className={cn(
        "inline-flex items-center px-2 py-0.5 text-[11px] rounded-full font-medium tracking-wide",
        STATUS_STYLES[status] ?? STATUS_STYLES.Unknown
      )}
    >
      {status}
    </span>
  );
}
