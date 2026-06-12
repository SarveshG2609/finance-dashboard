import { ChevronLeft, ChevronRight } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import {
  Bar, BarChart, CartesianGrid, Cell,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { type IncomeSummary, formatINR, getIncomeSummary } from "../api";

function MonthLabel(props: { x?: number; y?: number; payload?: { value: string } }) {
  const { x = 0, y = 0, payload } = props;
  if (!payload) return null;
  const [yr, mo] = payload.value.split("-");
  const label = new Date(+yr, +mo - 1).toLocaleString("en-IN", { month: "short" });
  return <text x={x} y={y + 14} textAnchor="middle" fill="var(--text-3)" fontSize={11}>{label}</text>;
}

function monthLabel(ym: string) {
  const [y, m] = ym.split("-").map(Number);
  return new Date(y, m - 1, 1).toLocaleString("en-IN", { month: "long", year: "numeric" });
}

const CATEGORY_ORDER = ["job_business", "stcg", "interest", "unrealized_ltcg", "misc"];

export function IncomePage() {
  const [data, setData] = useState<IncomeSummary | null>(null);
  const [error, setError] = useState<string | null>(null);
  // Selected month for the breakdown (null = show all-time totals)
  const [selectedMonth, setSelectedMonth] = useState<string | null>(null);

  useEffect(() => {
    getIncomeSummary()
      .then(d => {
        setData(d);
        // Default to most recent month that has entries
        const months = [...new Set(d.entries.map(e => e.date.slice(0, 7)))].sort();
        if (months.length > 0) setSelectedMonth(months[months.length - 1]);
      })
      .catch((e: unknown) => setError(e instanceof Error ? e.message : String(e)));
  }, []);

  // All unique months that have transactional income entries (not unrealized LTCG)
  const availableMonths = useMemo(() => {
    if (!data) return [];
    return [...new Set(
      data.entries
        .filter(e => e.category !== "unrealized_ltcg")
        .map(e => e.date.slice(0, 7))
    )].sort();
  }, [data]);

  // Entries and totals for the selected month only
  const filteredEntries = useMemo(() => {
    if (!data || !selectedMonth) return data?.entries ?? [];
    return data.entries.filter(e => e.date.startsWith(selectedMonth));
  }, [data, selectedMonth]);

  const filteredByCategory = useMemo(() => {
    if (!data) return {};
    const totals: Record<string, number> = { ...Object.fromEntries(CATEGORY_ORDER.map(k => [k, 0])) };
    for (const e of filteredEntries) {
      if (e.category !== "unrealized_ltcg") {
        totals[e.category] = (totals[e.category] ?? 0) + e.amount;
      }
    }
    // Unrealized LTCG is a portfolio snapshot — not month-specific
    totals["unrealized_ltcg"] = data.by_category["unrealized_ltcg"] ?? 0;
    return totals;
  }, [data, filteredEntries]);

  function shiftMonth(delta: number) {
    if (!selectedMonth || availableMonths.length === 0) return;
    const idx = availableMonths.indexOf(selectedMonth);
    const next = availableMonths[idx + delta];
    if (next) setSelectedMonth(next);
  }

  const canGoPrev = selectedMonth ? availableMonths.indexOf(selectedMonth) > 0 : false;
  const canGoNext = selectedMonth ? availableMonths.indexOf(selectedMonth) < availableMonths.length - 1 : false;

  if (error) return <div className="panel error-box">{error}</div>;
  if (!data) return <div className="panel loading"><div className="spinner" /><span>Loading…</span></div>;

  return (
    <div className="dashboard">

      {/* Month navigation */}
      <div className="panel" style={{ padding: "14px 20px", display: "flex", alignItems: "center", gap: 12 }}>
        <button className="month-nav-btn" onClick={() => shiftMonth(-1)} disabled={!canGoPrev}>
          <ChevronLeft size={16} />
        </button>
        <span style={{ flex: 1, textAlign: "center", fontWeight: 600, fontSize: 15, color: "var(--text-1)" }}>
          {selectedMonth ? monthLabel(selectedMonth) : "All time"}
        </span>
        <button className="month-nav-btn" onClick={() => shiftMonth(1)} disabled={!canGoNext}>
          <ChevronRight size={16} />
        </button>
      </div>

      {/* Stat cards — filtered totals for selected month */}
      <div style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
        {CATEGORY_ORDER.map(cat => {
          const amt = filteredByCategory[cat] ?? 0;
          const color = data.category_colors[cat] ?? "var(--accent)";
          const isUnrealized = cat === "unrealized_ltcg";
          const positive = amt >= 0;
          return (
            <div key={cat} className="panel" style={{ flex: 1, minWidth: 170 }}>
              <p className="eyebrow" style={{ marginBottom: 6 }}>{data.category_labels[cat]}</p>
              <p style={{
                fontSize: 24, fontWeight: 800, margin: 0, letterSpacing: "-0.02em",
                color: isUnrealized ? (positive ? color : "var(--red)") : color,
              }}>
                {!positive && "-"}{formatINR(Math.abs(amt))}
              </p>
              {isUnrealized && (
                <p style={{ fontSize: 10, color: "var(--text-3)", marginTop: 4 }}>
                  {positive ? "Unrealized gain" : "Unrealized loss"} · current portfolio
                </p>
              )}
            </div>
          );
        })}
      </div>

      {/* Monthly trend (all months, highlights selected) */}
      <div className="panel">
        <p className="section-heading" style={{ marginBottom: 16 }}>Monthly Inflows</p>
        <ResponsiveContainer width="100%" height={200}>
          <BarChart data={data.trend} barSize={26}>
            <CartesianGrid vertical={false} stroke="var(--border)" />
            <XAxis dataKey="month" tick={MonthLabel} axisLine={false} tickLine={false} />
            <YAxis
              tickFormatter={(v: number) => `₹${(v / 1000).toFixed(0)}k`}
              axisLine={false} tickLine={false}
              tick={{ fill: "var(--text-3)", fontSize: 11 }} width={48}
            />
            <Tooltip
              formatter={(v: number) => formatINR(v)}
              contentStyle={{ background: "var(--surface-2)", border: "1px solid var(--border)", borderRadius: 8, fontSize: 12 }}
              labelFormatter={(l: string) => {
                const [yr, mo] = l.split("-");
                return new Date(+yr, +mo - 1).toLocaleString("en-IN", { month: "long", year: "numeric" });
              }}
            />
            <Bar dataKey="total" radius={[4, 4, 0, 0]}>
              {data.trend.map((pt, i) => (
                <Cell
                  key={i}
                  fill={pt.month === selectedMonth
                    ? "var(--green)"
                    : pt.total > 0 ? "var(--green-dim, #1a4a30)" : "var(--surface-3)"}
                  opacity={pt.month === selectedMonth ? 1 : 0.45}
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Transaction list for selected month */}
      <section>
        <p className="section-heading" style={{ marginBottom: 12 }}>
          Transactions{selectedMonth ? ` — ${monthLabel(selectedMonth)}` : ""}
        </p>
        <div className="panel" style={{ padding: 0, overflow: "hidden" }}>
          <table className="txn-table">
            <thead>
              <tr>
                <th>Date</th>
                <th>From</th>
                <th>Category</th>
                <th style={{ textAlign: "right" }}>Amount</th>
              </tr>
            </thead>
            <tbody>
              {filteredEntries.map(e => {
                const color = data.category_colors[e.category] ?? "var(--text-3)";
                return (
                  <tr key={e.id}>
                    <td className="mono" style={{ fontSize: 12 }}>{e.date}</td>
                    <td style={{ fontWeight: 500 }}>{e.entity}</td>
                    <td>
                      <span style={{
                        fontSize: 10, fontWeight: 700, padding: "2px 8px", borderRadius: 8,
                        background: `${color}22`, color,
                        textTransform: "uppercase", letterSpacing: "0.05em",
                      }}>
                        {data.category_labels[e.category] ?? e.category}
                      </span>
                    </td>
                    <td className="mono" style={{ textAlign: "right", color: "var(--green)", fontWeight: 600 }}>
                      +{formatINR(e.amount)}
                    </td>
                  </tr>
                );
              })}
              {filteredEntries.length === 0 && (
                <tr><td colSpan={4} style={{ textAlign: "center", color: "var(--text-3)", padding: 24 }}>
                  No qualifying income for {selectedMonth ? monthLabel(selectedMonth) : "this period"}.
                </td></tr>
              )}
            </tbody>
          </table>
        </div>
      </section>

    </div>
  );
}
