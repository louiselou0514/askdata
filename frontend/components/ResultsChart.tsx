"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { ChartSuggestion, QueryResult } from "@/lib/api";

interface Props {
  result: QueryResult;
}

export function ResultsChart({ result }: Props) {
  const { chart_suggestion, columns, rows } = result;

  if (chart_suggestion.type === "table" || !chart_suggestion.x || !chart_suggestion.y) {
    return null;
  }

  const xKey = chart_suggestion.x;
  const yKey = chart_suggestion.y;
  const xIdx = columns.indexOf(xKey);
  const yIdx = columns.indexOf(yKey);

  const data = rows.map((row) => ({
    [xKey]: row[xIdx],
    [yKey]: Number(row[yIdx]),
  }));

  const commonProps = {
    data,
    margin: { top: 8, right: 16, left: 0, bottom: 40 },
  };

  const fmtTick = (v: number) => v >= 1000 ? `${(v / 1000).toFixed(v % 1000 === 0 ? 0 : 1)}k` : String(v);
  const fmtTooltip = (v: number) => [v.toLocaleString(), yKey];

  return (
    <div className="w-full">
      <ResponsiveContainer width="100%" height={240}>
        {chart_suggestion.type === "line" ? (
          <LineChart {...commonProps}>
            <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
            <XAxis dataKey={xKey} tick={{ fontSize: 11 }} angle={-30} textAnchor="end" />
            <YAxis tick={{ fontSize: 11 }} tickFormatter={fmtTick} width={48} />
            <Tooltip formatter={fmtTooltip} />
            <Line type="monotone" dataKey={yKey} stroke="#6366f1" strokeWidth={2} dot={false} />
          </LineChart>
        ) : (
          <BarChart {...commonProps}>
            <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
            <XAxis dataKey={xKey} tick={{ fontSize: 11 }} angle={-30} textAnchor="end" />
            <YAxis tick={{ fontSize: 11 }} tickFormatter={fmtTick} width={48} />
            <Tooltip formatter={fmtTooltip} />
            <Bar dataKey={yKey} fill="#6366f1" radius={[4, 4, 0, 0]} />
          </BarChart>
        )}
      </ResponsiveContainer>
    </div>
  );
}
