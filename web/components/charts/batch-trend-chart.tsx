"use client";

import { useMemo } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import {
  ACCELERATOR_COLORS,
  ACCELERATOR_LABELS,
  AcceleratorSlug,
  BatchTrendRow,
} from "@/lib/types";

export function BatchTrendChart({ rows }: { rows: BatchTrendRow[] }) {
  const data = useMemo(() => {
    const byYear = new Map<number, Record<string, number | string>>();
    for (const r of rows) {
      if (r.founded_year < 2008 || r.founded_year > 2025) continue;
      if (!byYear.has(r.founded_year)) byYear.set(r.founded_year, { year: r.founded_year });
      byYear.get(r.founded_year)![r.slug] = r.n;
    }
    return Array.from(byYear.values()).sort(
      (a, b) => Number(b.year) - Number(a.year) // descending per user request
    );
  }, [rows]);

  const slugs: AcceleratorSlug[] = ["yc", "ef", "spc", "a16z_speedrun"];

  return (
    <ResponsiveContainer width="100%" height={320}>
      <BarChart
        data={data}
        margin={{ top: 8, right: 8, left: 8, bottom: 8 }}
        barCategoryGap="20%"
      >
        <CartesianGrid stroke="#e6e3da" vertical={false} />
        <XAxis
          dataKey="year"
          tick={{ fill: "#4a4945", fontSize: 11 }}
          axisLine={{ stroke: "#e6e3da" }}
          tickLine={false}
        />
        <YAxis
          tick={{ fill: "#4a4945", fontSize: 11 }}
          axisLine={{ stroke: "#e6e3da" }}
          tickLine={false}
          width={36}
        />
        <Tooltip
          cursor={{ fill: "#ece9df88" }}
          contentStyle={{
            background: "#fefdfa",
            border: "1px solid #e6e3da",
            borderRadius: 8,
            fontSize: 12,
          }}
          labelFormatter={(y) => `Founded ${y}`}
        />
        <Legend
          iconType="square"
          wrapperStyle={{ fontSize: 11, paddingTop: 8 }}
          formatter={(v) => ACCELERATOR_LABELS[v as AcceleratorSlug]}
        />
        {slugs.map((s) => (
          <Bar
            key={s}
            dataKey={s}
            stackId="a"
            fill={ACCELERATOR_COLORS[s]}
            isAnimationActive={false}
          />
        ))}
      </BarChart>
    </ResponsiveContainer>
  );
}
