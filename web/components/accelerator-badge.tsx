import { ACCELERATOR_COLORS, ACCELERATOR_LABELS, AcceleratorSlug } from "@/lib/types";
import { cn } from "@/lib/utils";

const SHORT: Record<AcceleratorSlug, string> = {
  yc: "YC",
  ef: "EF",
  spc: "SPC",
  a16z_speedrun: "Speedrun",
};

export function AcceleratorBadge({
  slug,
  full = false,
  className,
}: {
  slug: AcceleratorSlug;
  full?: boolean;
  className?: string;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 px-2 py-0.5 text-[11px] rounded font-medium tracking-wide",
        className
      )}
      style={{
        color: ACCELERATOR_COLORS[slug],
        backgroundColor: `${ACCELERATOR_COLORS[slug]}18`,
        border: `1px solid ${ACCELERATOR_COLORS[slug]}33`,
      }}
      title={ACCELERATOR_LABELS[slug]}
    >
      {full ? ACCELERATOR_LABELS[slug] : SHORT[slug]}
    </span>
  );
}
