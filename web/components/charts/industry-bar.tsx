"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type { IndustryCount } from "@/lib/types";

const PALETTE = [
  "#cc785c", "#b56a50", "#a05c47", "#8a6b5c", "#7a7563",
  "#637b74", "#5c7a8a", "#4c6d80", "#6b6b8a", "#8a5c6b",
  "#a96f1d", "#a28753", "#6b8a5c", "#4f7a7a", "#5c6b7a",
  "#7a5c9a", "#8a7a5c", "#8a5c5c", "#807e78",
];

export function IndustryBar({
  rows,
  max = 12,
}: {
  rows: IndustryCount[];
  max?: number;
}) {
  const data = rows.slice(0, max);
  return (
    <ResponsiveContainer width="100%" height={Math.max(240, 32 * data.length)}>
      <BarChart
        data={data}
        layout="vertical"
        margin={{ top: 8, right: 24, left: 8, bottom: 8 }}
      >
        <CartesianGrid stroke="#e6e3da" horizontal={false} />
        <XAxis
          type="number"
          tick={{ fill: "#4a4945", fontSize: 11 }}
          axisLine={{ stroke: "#e6e3da" }}
          tickLine={false}
        />
        <YAxis
          type="category"
          dataKey="industry"
          tick={{ fill: "#2b2a27", fontSize: 12 }}
          axisLine={false}
          tickLine={false}
          width={210}
        />
        <Tooltip
          cursor={{ fill: "#ece9df88" }}
          contentStyle={{
            background: "#fefdfa",
            border: "1px solid #e6e3da",
            borderRadius: 8,
            fontSize: 12,
          }}
        />
        <Bar dataKey="n" radius={[0, 3, 3, 0]} isAnimationActive={false}>
          {data.map((_, i) => (
            <Cell key={i} fill={PALETTE[i % PALETTE.length]} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
