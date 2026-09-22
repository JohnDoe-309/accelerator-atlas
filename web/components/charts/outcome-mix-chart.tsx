"use client";

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

import { STATUS_COLORS } from "@/lib/types";

interface Row {
  label: string;
  Active: number;
  Acquired: number;
  Public: number;
  Dead: number;
  Unknown?: number;
}

export function OutcomeMixChart({
  data,
  mode = "count",
  height = 420,
}: {
  data: Row[];
  mode?: "count" | "percent";
  height?: number;
}) {
  const keys = ["Active", "Acquired", "Public", "Dead", "Unknown"] as const;
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} margin={{ top: 8, right: 12, left: 4, bottom: 8 }}>
        <CartesianGrid stroke="#e6e3da" vertical={false} />
        <XAxis
          dataKey="label"
          tick={{ fill: "#4a4945", fontSize: 11 }}
          axisLine={{ stroke: "#e6e3da" }}
          tickLine={false}
          interval={0}
        />
        <YAxis
          tick={{ fill: "#4a4945", fontSize: 11 }}
          axisLine={{ stroke: "#e6e3da" }}
          tickLine={false}
          width={36}
          tickFormatter={(v) => (mode === "percent" ? `${v}%` : v)}
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
        <Legend iconType="square" wrapperStyle={{ fontSize: 11, paddingTop: 8 }} />
        {keys.map((k) => (
          <Bar
            key={k}
            dataKey={k}
            stackId="a"
            fill={STATUS_COLORS[k] ?? "#807e78"}
            isAnimationActive={false}
          />
        ))}
      </BarChart>
    </ResponsiveContainer>
  );
}
