import { ChevronLeft, ChevronRight, Pencil, RefreshCw, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  type ManualAssetEntry,
  type NetWorthSummary,
  type NetWorthTrendPoint,
  createManualAsset,
  deleteManualAsset,
  formatINR,
  getEffectiveAssets,
  getNetWorth,
  updateManualAsset,
} from "../api";

function todayMonth() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
}

function monthLabel(ym: string) {
  const [y, m] = ym.split("-").map(Number);
  return new Date(y, m - 1, 1).toLocaleString("en-IN", { month: "long", year: "numeric" });
}

function shiftMonth(ym: string, delta: number): string {
  const [y, m] = ym.split("-").map(Number);
  const d = new Date(y, m - 1 + delta, 1);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
}

export function NetWorthPage() {
  const [summary, setSummary] = useState<NetWorthSummary | null>(null);
  const [selectedMonth, setSelectedMonth] = useState(todayMonth());
  const [effectiveAssets, setEffectiveAssets] = useState<ManualAssetEntry[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [showAddForm, setShowAddForm] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);

  async function loadSummary() {
    try {
      const nw = await getNetWorth();
      setSummary(nw);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  async function loadEffective(month: string) {
    try {
      const ea = await getEffectiveAssets(month);
      setEffectiveAssets(ea);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  useEffect(() => { loadSummary(); }, []);
  useEffect(() => { loadEffective(selectedMonth); }, [selectedMonth]);

  async function handleDelete(id: string, name: string) {
    if (!window.confirm(`Delete "${name}"? This removes it from all months.`)) return;
    await deleteManualAsset(id);
    loadSummary();
    loadEffective(selectedMonth);
  }

  function handleMonthChange(delta: number) {
    setSelectedMonth((m) => shiftMonth(m, delta));
    setShowAddForm(false);
    setEditingId(null);
  }

  if (error) return <div className="panel error-box">{error}</div>;
  if (!summary) return <div className="panel loading"><div className="spinner" /><span>Loading…</span></div>;

  const { current, trend } = summary;
  const monthSnapshot = trend.find(t => t.month === selectedMonth) ?? null;
  const prevMonth = trend.length >= 2 ? trend[trend.length - 2] : null;
  const delta = prevMonth && prevMonth.total > 0
    ? ((current.total - prevMonth.total) / prevMonth.total) * 100
    : null;

  const assetCards = [
    { label: "Bank Balance",  value: current.bank_balance,  color: "#6366F1" },
    { label: "Mutual Funds",  value: current.mutual_funds,  color: "#8B5CF6" },
    { label: "Gold ETF",      value: current.gold_etf,      color: "#C8A96E" },
    { label: "Silver ETF",    value: current.silver_etf,    color: "#94A3B8" },
    { label: "Stocks",        value: current.stocks,        color: "#2ECC8E" },
    { label: "Other Assets",  value: current.manual_assets, color: "#0EA5E9" },
    { label: "Liabilities",   value: -current.liabilities,  color: "#E05C5C" },
  ].filter((c) => c.value !== 0);

  const isCurrentMonth = selectedMonth === todayMonth();

  return (
    <div className="dashboard">

      {/* Hero */}
      <div className="panel net-worth-panel">
        <p className="eyebrow">Total Net Worth</p>
        <div className="nw-headline">
          <span className="net-worth-value">{formatINR(current.total)}</span>
          {delta !== null && (
            <span className={`delta-badge ${delta >= 0 ? "up" : "down"}`}>
              {delta >= 0 ? "▲" : "▼"} {Math.abs(delta).toFixed(1)}% vs last month
            </span>
          )}
        </div>
      </div>

      {/* Asset distribution */}
      {assetCards.length > 0 && (
        <section>
          <p className="section-heading">Asset Breakdown</p>
          <div className="asset-grid">
            {assetCards.map((c) => (
              <div key={c.label} className="panel asset-card">
                <div className="asset-dot" style={{ background: c.color }} />
                <p className="eyebrow">{c.label}</p>
                <p className="asset-value" style={{ color: c.value < 0 ? "var(--red)" : "var(--text-1)" }}>
                  {formatINR(Math.abs(c.value))}
                </p>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* 12-month trend */}
      <section>
        <p className="section-heading">12-Month Trend</p>
        <div className="panel chart-panel">
          <ResponsiveContainer width="100%" height={240}>
            <LineChart data={trend} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
              <XAxis
                dataKey="month"
                tickFormatter={(v: string) => v.slice(5)}
                axisLine={false} tickLine={false}
                tick={{ fill: "var(--text-3)", fontSize: 11 }}
              />
              <YAxis
                tickFormatter={(v: number) =>
                  v >= 100000 ? `₹${(v / 100000).toFixed(0)}L` : `₹${(v / 1000).toFixed(0)}K`
                }
                axisLine={false} tickLine={false} width={52}
                tick={{ fill: "var(--text-3)", fontSize: 11 }}
              />
              <Tooltip
                contentStyle={{ background: "var(--surface-2)", border: "1px solid var(--border-2)", borderRadius: 8, color: "var(--text-1)" }}
                formatter={(v: number, name: string) => [formatINR(v), name]}
                labelFormatter={(l: string) => `Month: ${l}`}
              />
              <Line dataKey="total" name="Net Worth" stroke="#7C6AF7" strokeWidth={2} dot={false} activeDot={{ r: 4, fill: "#7C6AF7" }} />
              <Line dataKey="bank" name="Bank" stroke="#2ECC8E" strokeWidth={1.5} dot={false} strokeDasharray="4 2" />
              <Line dataKey="investments" name="Investments" stroke="#C8A96E" strokeWidth={1.5} dot={false} strokeDasharray="4 2" />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </section>

      {/* Manual assets with month picker */}
      <section>
        <div className="section-header-row">
          <p className="section-heading">Assets &amp; Liabilities</p>
          {isCurrentMonth && (
            <button className="btn-secondary" onClick={() => { setShowAddForm((s) => !s); setEditingId(null); }}>
              {showAddForm ? "Cancel" : "+ Add"}
            </button>
          )}
        </div>

        {/* Month navigation */}
        <div className="month-nav">
          <button className="month-nav-btn" onClick={() => handleMonthChange(-1)}>
            <ChevronLeft size={16} />
          </button>
          <span className="month-nav-label">{monthLabel(selectedMonth)}</span>
          <button
            className="month-nav-btn"
            onClick={() => handleMonthChange(1)}
            disabled={isCurrentMonth}
          >
            <ChevronRight size={16} />
          </button>
        </div>

        {/* Per-month breakdown — simple list */}
        {monthSnapshot && monthSnapshot.total > 0 && (
          <div className="panel" style={{ padding: 0, overflow: "hidden", marginBottom: 16 }}>
            <BreakdownList snap={monthSnapshot} selectedMonth={selectedMonth} />
          </div>
        )}

        {showAddForm && isCurrentMonth && (
          <AssetForm
            defaultMonth={selectedMonth}
            onSaved={() => { setShowAddForm(false); loadSummary(); loadEffective(selectedMonth); }}
            onCancel={() => setShowAddForm(false)}
          />
        )}

        {effectiveAssets.length === 0 && !showAddForm && isCurrentMonth ? (
          <p className="empty-state" style={{ fontSize: 12, color: "var(--text-3)" }}>
            No manual entries for this month. Use + Add to record things like PPF, jewellery, unlisted shares.
          </p>
        ) : effectiveAssets.length > 0 ? (
          <div className="panel" style={{ padding: 0, overflow: "hidden" }}>
            <table className="txn-table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Type</th>
                  <th className="num">Value</th>
                  <th>Since</th>
                  <th style={{ width: 80 }} />
                </tr>
              </thead>
              <tbody>
                {effectiveAssets.map((a) =>
                  editingId === a.id ? (
                    <tr key={a.id}>
                      <td colSpan={5} style={{ padding: 0 }}>
                        <AssetForm
                          initial={a}
                          defaultMonth={selectedMonth}
                          onSaved={() => { setEditingId(null); loadSummary(); loadEffective(selectedMonth); }}
                          onCancel={() => setEditingId(null)}
                          inline
                        />
                      </td>
                    </tr>
                  ) : (
                    <tr key={a.id}>
                      <td style={{ fontWeight: 600 }}>
                        {a.name}
                        {a.is_recurring && (
                          <span className="recurring-badge" title="Carrying forward from previous month">
                            <RefreshCw size={10} /> recurring
                          </span>
                        )}
                      </td>
                      <td><span className={`kind-badge ${a.kind}`}>{a.kind}</span></td>
                      <td className="num mono" style={{ color: a.kind === "asset" ? "var(--gold)" : "var(--red)" }}>
                        {formatINR(a.value)}
                      </td>
                      <td className="mono" style={{ color: "var(--text-3)", fontSize: 12 }}>{a.date}</td>
                      <td>
                        <div style={{ display: "flex", gap: 4, justifyContent: "flex-end" }}>
                          <button className="btn-icon" onClick={() => { setEditingId(a.id); setShowAddForm(false); }} title="Edit">
                            <Pencil size={14} />
                          </button>
                          <button className="btn-icon danger" onClick={() => handleDelete(a.id, a.name)} title="Delete">
                            <Trash2 size={14} />
                          </button>
                        </div>
                      </td>
                    </tr>
                  )
                )}
              </tbody>
            </table>
          </div>
        ) : null}
      </section>
    </div>
  );
}

// ── Simple breakdown list for a selected month ────────────────────────────

function fmtDate(iso: string) {
  const d = new Date(iso);
  return d.toLocaleDateString("en-IN", { day: "numeric", month: "short" });
}

function BreakdownRow({
  label, value, color, indent = false, note,
}: {
  label: string; value: number; color?: string; indent?: boolean; note?: string;
}) {
  if (value === 0 && indent) return null;
  return (
    <div style={{
      display: "flex", alignItems: "baseline", justifyContent: "space-between",
      padding: indent ? "6px 20px 6px 36px" : "10px 20px",
      borderBottom: "1px solid var(--border)",
      background: indent ? "var(--surface)" : undefined,
    }}>
      <span style={{ fontSize: indent ? 12 : 13, color: indent ? "var(--text-2)" : "var(--text-1)", fontWeight: indent ? 400 : 600 }}>
        {label}
        {note && <span style={{ fontSize: 10, color: "var(--text-3)", marginLeft: 8 }}>{note}</span>}
      </span>
      <span style={{ fontSize: indent ? 13 : 14, fontWeight: 700, color: color ?? (indent ? "var(--text-2)" : "var(--text-1)"), fontFamily: "monospace" }}>
        {formatINR(value)}
      </span>
    </div>
  );
}

function BreakdownList({ snap, selectedMonth }: { snap: NetWorthTrendPoint; selectedMonth: string }) {
  const monthYM = selectedMonth; // "YYYY-MM"

  return (
    <div>
      {/* Bank */}
      <BreakdownRow label="Bank Balance" value={snap.bank} color="#6366F1" />
      {snap.bank_accounts.map(a => {
        const stale = !a.as_of.startsWith(monthYM);
        return (
          <BreakdownRow
            key={a.name}
            label={a.name}
            value={a.balance}
            indent
            note={stale ? `as of ${fmtDate(a.as_of)} — no newer statement` : `as of ${fmtDate(a.as_of)}`}
          />
        );
      })}

      {/* Investments */}
      {snap.investments > 0 && (
        <>
          <BreakdownRow label="Investments" value={snap.investments} color="#C8A96E" />
          {snap.mutual_funds > 0 && <BreakdownRow label="Mutual Funds" value={snap.mutual_funds} indent />}
          {snap.stocks > 0 && <BreakdownRow label="Stocks" value={snap.stocks} indent />}
          {snap.gold_etf > 0 && <BreakdownRow label="Gold ETF" value={snap.gold_etf} indent />}
          {snap.silver_etf > 0 && <BreakdownRow label="Silver ETF" value={snap.silver_etf} indent />}
        </>
      )}

      {/* Manual */}
      {snap.manual !== 0 && (
        <BreakdownRow label="Manual Assets (net)" value={snap.manual} color={snap.manual >= 0 ? "#0EA5E9" : "var(--red)"} />
      )}

      {/* Total */}
      <div style={{
        display: "flex", alignItems: "baseline", justifyContent: "space-between",
        padding: "12px 20px",
        borderTop: "2px solid var(--border-2)",
        background: "var(--surface-2)",
      }}>
        <span style={{ fontSize: 13, fontWeight: 700, color: "var(--text-1)" }}>Net Worth</span>
        <span style={{ fontSize: 16, fontWeight: 800, color: "#7C6AF7", fontFamily: "monospace" }}>
          {formatINR(snap.total)}
        </span>
      </div>
    </div>
  );
}

function AssetForm({
  initial,
  defaultMonth,
  onSaved,
  onCancel,
  inline = false,
}: {
  initial?: ManualAssetEntry;
  defaultMonth: string;
  onSaved: () => void;
  onCancel: () => void;
  inline?: boolean;
}) {
  const defaultDate = initial?.date ?? `${defaultMonth}-01`;
  const [name, setName] = useState(initial?.name ?? "");
  const [kind, setKind] = useState(initial?.kind ?? "asset");
  const [value, setValue] = useState(String(initial?.value ?? ""));
  const [date, setDate] = useState(defaultDate);
  const [notes, setNotes] = useState(initial?.notes ?? "");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError(null);
    const body = { name, kind, value: parseFloat(value), date, notes: notes || undefined };
    try {
      if (initial) {
        await updateManualAsset(initial.id, body);
      } else {
        await createManualAsset(body);
      }
      onSaved();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : String(err));
      setSaving(false);
    }
  }

  const wrapClass = inline ? "add-asset-form" : "panel add-asset-form";
  const wrapStyle = inline
    ? { padding: "16px", borderTop: "1px solid var(--border)" }
    : { marginBottom: 14 };

  return (
    <form className={wrapClass} style={wrapStyle} onSubmit={handleSubmit}>
      <div className="form-row">
        <div className="field">
          <label>Name</label>
          <input type="text" value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Unlisted Shares" required />
        </div>
        <div className="field" style={{ maxWidth: 130 }}>
          <label>Type</label>
          <select value={kind} onChange={(e) => setKind(e.target.value)}>
            <option value="asset">Asset</option>
            <option value="liability">Liability</option>
          </select>
        </div>
        <div className="field" style={{ maxWidth: 150 }}>
          <label>Value (₹)</label>
          <input type="number" value={value} onChange={(e) => setValue(e.target.value)} placeholder="0" min="0" step="1" required />
        </div>
        <div className="field" style={{ maxWidth: 160 }}>
          <label>As of Date</label>
          <input type="date" value={date} onChange={(e) => setDate(e.target.value)} required />
        </div>
        <div className="field" style={{ flex: 2 }}>
          <label>Notes</label>
          <input type="text" value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="Optional" />
        </div>
      </div>
      {!initial && (
        <p style={{ fontSize: 12, color: "var(--text-3)", marginBottom: 12 }}>
          This asset will automatically appear in all future months.
        </p>
      )}
      {error && <div className="error-box">{error}</div>}
      <div style={{ display: "flex", gap: 8 }}>
        <button className="btn-primary" type="submit" disabled={saving}>
          {saving ? "Saving…" : initial ? "Update" : "Save"}
        </button>
        <button className="btn-secondary" type="button" onClick={onCancel}>Cancel</button>
      </div>
    </form>
  );
}
