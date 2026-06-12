import { ChevronLeft, ChevronRight } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import {
  Bar, BarChart, CartesianGrid, Cell, LabelList,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { type ExpenseAccount, type ExpensesSummary, formatINR, getExpensesSummary } from "../api";

const INSTITUTION_COLORS: Record<string, string> = {
  HDFC:    "#004C8C",
  SBI:     "#1A6BB5",
  Kotak:   "#ED1C24",
  ICICI:   "#F58220",
  Zerodha: "#387ED1",
  Groww:   "#00D09C",
};
const FALLBACK = ["#7C6AF7", "#C8A96E", "#387ED1", "#2ECC8E"];

function acctColor(institution: string, idx: number) {
  return INSTITUTION_COLORS[institution] ?? FALLBACK[idx % FALLBACK.length];
}

function monthLabel(ym: string) {
  const [y, m] = ym.split("-").map(Number);
  return new Date(y, m - 1, 1).toLocaleString("en-IN", { month: "long", year: "numeric" });
}

function MonthLabel(props: { x?: number; y?: number; payload?: { value: string } }) {
  const { x = 0, y = 0, payload } = props;
  if (!payload) return null;
  const [yr, mo] = payload.value.split("-");
  return <text x={x} y={y + 14} textAnchor="middle" fill="var(--text-3)" fontSize={11}>
    {new Date(+yr, +mo - 1).toLocaleString("en-IN", { month: "short" })}
  </text>;
}

function AccountCard({ acct, idx, threshold, month }: { acct: ExpenseAccount; idx: number; threshold: number; month: string | null }) {
  const [open, setOpen] = useState(false);
  const color = acctColor(acct.institution, idx);

  return (
    <div className="panel" style={{ padding: 0, overflow: "hidden" }}>
      <button
        onClick={() => setOpen(o => !o)}
        style={{
          width: "100%", background: "none", border: "none", cursor: "pointer",
          padding: "16px 20px", display: "flex", alignItems: "center", gap: 12,
          textAlign: "left",
        }}
      >
        <span style={{ width: 10, height: 10, borderRadius: "50%", background: color, flexShrink: 0 }} />
        <div style={{ flex: 1 }}>
          <p style={{ fontSize: 13, fontWeight: 600, color: "var(--text-1)", margin: 0 }}>{acct.account_name}</p>
          <p style={{ fontSize: 11, color: "var(--text-3)", margin: "2px 0 0" }}>
            {acct.transactions.length + acct.random_count} transactions
            {acct.random_count > 0 && ` · ${acct.random_count} random (<₹${threshold.toLocaleString()})`}
          </p>
        </div>
        <p style={{ fontSize: 18, fontWeight: 700, color: "var(--text-1)", margin: 0 }}>
          {formatINR(acct.total)}
        </p>
        <span style={{ color: "var(--text-3)", fontSize: 12, marginLeft: 4 }}>{open ? "▲" : "▼"}</span>
      </button>

      {open && (
        <div style={{ borderTop: "1px solid var(--border)" }}>
          {acct.total === 0 ? (
            <p style={{ padding: "20px 24px", color: "var(--text-3)", fontSize: 13, fontStyle: "italic", margin: 0 }}>
              No expenses for this account{month ? ` in ${monthLabel(month)}` : ""}.
            </p>
          ) : (
            <table className="txn-table">
              <thead>
                <tr>
                  <th>Date</th>
                  <th>Merchant</th>
                  <th style={{ textAlign: "right" }}>Amount</th>
                </tr>
              </thead>
              <tbody>
                {acct.transactions.map(t => (
                  <tr key={t.id}>
                    <td className="mono" style={{ fontSize: 12 }}>{t.date}</td>
                    <td style={{ fontWeight: 500 }}>{t.description}</td>
                    <td className="mono" style={{ textAlign: "right", color: "var(--red)", fontWeight: 600 }}>
                      -{formatINR(t.amount)}
                    </td>
                  </tr>
                ))}
                {acct.random_count > 0 && (
                  <RandomBucket entries={acct.random_transactions} total={acct.random_total} threshold={threshold} />
                )}
              </tbody>
            </table>
          )}
        </div>
      )}
    </div>
  );
}

function RandomBucket({ entries, total, threshold }: {
  entries: { id: string; date: string; description: string; amount: number }[];
  total: number;
  threshold: number;
}) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <tr onClick={() => setOpen(o => !o)} style={{ cursor: "pointer", background: "var(--surface-2)" }}>
        <td className="mono" style={{ fontSize: 12, color: "var(--text-3)" }}>—</td>
        <td style={{ color: "var(--text-3)", fontStyle: "italic" }}>
          Random &lt;₹{threshold.toLocaleString()} · {entries.length} transactions {open ? "▲" : "▼"}
        </td>
        <td className="mono" style={{ textAlign: "right", color: "var(--text-3)", fontWeight: 600 }}>
          -{formatINR(total)}
        </td>
      </tr>
      {open && entries.map(t => (
        <tr key={t.id} style={{ background: "var(--surface)" }}>
          <td className="mono" style={{ fontSize: 11, color: "var(--text-3)", paddingLeft: 32 }}>{t.date}</td>
          <td style={{ fontSize: 12, color: "var(--text-2)", paddingLeft: 32 }}>{t.description}</td>
          <td className="mono" style={{ textAlign: "right", fontSize: 12, color: "var(--text-3)" }}>
            -{formatINR(t.amount)}
          </td>
        </tr>
      ))}
    </>
  );
}

export function ExpensesPage() {
  const [data, setData] = useState<ExpensesSummary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selectedMonth, setSelectedMonth] = useState<string | null>(null);

  useEffect(() => {
    getExpensesSummary().then(d => {
      setData(d);
      // Default to most recent month with any spending
      const months = [...new Set(
        d.accounts.flatMap(a => [...a.transactions, ...a.random_transactions].map(t => t.date.slice(0, 7)))
      )].sort();
      if (months.length > 0) setSelectedMonth(months[months.length - 1]);
    }).catch((e: unknown) => setError(e instanceof Error ? e.message : String(e)));
  }, []);

  // All months that have any transactions
  const availableMonths = useMemo(() => {
    if (!data) return [];
    return [...new Set(
      data.accounts.flatMap(a => [...a.transactions, ...a.random_transactions].map(t => t.date.slice(0, 7)))
    )].sort();
  }, [data]);

  // Filter each account to only transactions in the selected month
  const filteredAccounts = useMemo((): ExpenseAccount[] => {
    if (!data || !selectedMonth) return data?.accounts ?? [];
    return data.accounts.map(acct => {
      const named = acct.transactions.filter(t => t.date.startsWith(selectedMonth));
      const random = acct.random_transactions.filter(t => t.date.startsWith(selectedMonth));
      const namedTotal = named.reduce((s, t) => s + t.amount, 0);
      const randomTotal = random.reduce((s, t) => s + t.amount, 0);
      return {
        ...acct,
        transactions: named,
        random_transactions: random,
        random_count: random.length,
        random_total: randomTotal,
        total: namedTotal + randomTotal,
      };
    }).sort((a, b) => b.total - a.total);
  }, [data, selectedMonth]);

  const filteredTotal = useMemo(
    () => filteredAccounts.reduce((s, a) => s + a.total, 0),
    [filteredAccounts]
  );

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

      {/* Total + per-institution quick stats */}
      <div className="panel" style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "18px 24px" }}>
        <div>
          <p className="eyebrow" style={{ marginBottom: 4 }}>Total Spend</p>
          <p style={{ fontSize: 28, fontWeight: 800, color: "var(--text-1)", margin: 0, letterSpacing: "-0.02em" }}>
            {formatINR(filteredTotal)}
          </p>
        </div>
        <div style={{ display: "flex", gap: 24, flexWrap: "wrap", justifyContent: "flex-end" }}>
          {filteredAccounts.filter(a => a.total > 0).map((acct, i) => (
            <div key={acct.account_id} style={{ textAlign: "right" }}>
              <p style={{ fontSize: 11, color: acctColor(acct.institution, i), fontWeight: 600, margin: "0 0 2px", textTransform: "uppercase", letterSpacing: "0.05em" }}>
                {acct.institution}
              </p>
              <p style={{ fontSize: 15, fontWeight: 700, color: "var(--text-1)", margin: 0 }}>
                {formatINR(acct.total)}
              </p>
            </div>
          ))}
        </div>
      </div>

      {/* Monthly trend — all months, highlights selected */}
      <div className="panel">
        <p className="section-heading" style={{ marginBottom: 16 }}>Monthly Spend</p>
        <ResponsiveContainer width="100%" height={220}>
          <BarChart data={data.trend} barSize={26} margin={{ top: 28, right: 8, bottom: 0, left: 0 }}>
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
              labelFormatter={(l: string) => monthLabel(l)}
            />
            <Bar dataKey="total" radius={[4, 4, 0, 0]}>
              <LabelList
                dataKey="total"
                position="top"
                formatter={(v: number) => v > 0 ? `₹${(v / 1000).toFixed(0)}k` : ""}
                style={{ fill: "var(--text-3)", fontSize: 10, fontWeight: 600 }}
              />
              {data.trend.map((pt, i) => (
                <Cell
                  key={i}
                  fill={pt.month === selectedMonth ? "var(--red)" : pt.total > 0 ? "#6b1c1c" : "var(--surface-3)"}
                  opacity={pt.month === selectedMonth ? 1 : 0.45}
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Per-account cards */}
      <section>
        <p className="section-heading" style={{ marginBottom: 12 }}>By Account</p>
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {filteredAccounts.map((acct, i) => (
            <AccountCard key={acct.account_id} acct={acct} idx={i} threshold={data.random_threshold} month={selectedMonth} />
          ))}
        </div>
      </section>

    </div>
  );
}
