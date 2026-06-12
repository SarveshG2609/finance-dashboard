import { useEffect, useState } from "react";
import {
  type AccountsOverview,
  formatINR,
  getAccountsOverview,
} from "../api";

type SyncStatus = "fresh" | "aging" | "stale";

function syncStatus(dateStr: string | null): SyncStatus {
  if (!dateStr) return "stale";
  const days = Math.floor((Date.now() - new Date(dateStr).getTime()) / 86_400_000);
  if (days <= 30) return "fresh";
  if (days <= 60) return "aging";
  return "stale";
}

function daysAgo(dateStr: string | null): string {
  if (!dateStr) return "Never";
  const days = Math.floor((Date.now() - new Date(dateStr).getTime()) / 86_400_000);
  if (days === 0) return "Today";
  if (days === 1) return "Yesterday";
  return `${days}d ago`;
}

const STATUS_COLOR: Record<SyncStatus, string> = {
  fresh:  "var(--green)",
  aging:  "var(--gold)",
  stale:  "var(--red)",
};

const STATUS_BG: Record<SyncStatus, string> = {
  fresh:  "var(--green-dim)",
  aging:  "var(--gold-dim)",
  stale:  "var(--red-dim)",
};

const TYPE_LABEL: Record<string, string> = {
  bank:        "Bank",
  credit_card: "Credit Card",
  broker:      "Broker",
  manual:      "Manual",
};

interface Row {
  id: string;
  institution: string;
  name: string;
  type: string;
  lastSyncDate: string | null;   // the date we care about
  syncDetail: string;            // human-readable context
}

function buildRows(data: AccountsOverview): Row[] {
  const rows: Row[] = [];

  for (const b of data.banks) {
    rows.push({
      id: b.id,
      institution: b.institution,
      name: b.name,
      type: "bank",
      lastSyncDate: b.last_txn_date,
      syncDetail: b.masked_identifier ?? "",
    });
  }

  for (const c of data.credit_cards) {
    rows.push({
      id: c.id,
      institution: c.institution,
      name: c.name,
      type: "credit_card",
      lastSyncDate: c.billing_end,
      syncDetail: c.masked_identifier ?? "",
    });
  }

  for (const br of data.brokers) {
    rows.push({
      id: br.id,
      institution: br.institution,
      name: br.name,
      type: "broker",
      lastSyncDate: br.as_of_date,
      syncDetail: `${br.holdings_count} holdings`,
    });
  }

  for (const m of data.manual_assets) {
    rows.push({
      id: m.id,
      institution: "Manual",
      name: m.name,
      type: "manual",
      lastSyncDate: m.date,
      syncDetail: `${m.kind} · ${formatINR(m.value)}`,
    });
  }

  return rows;
}

function SyncSection({ title, rows, empty }: { title: string; rows: Row[]; empty: string }) {
  return (
    <section>
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 12 }}>
        <p className="section-heading" style={{ margin: 0 }}>{title}</p>
        <span style={{
          fontSize: 11, fontWeight: 700, padding: "2px 8px", borderRadius: 10,
          background: "var(--surface-3)", color: "var(--text-3)",
        }}>{rows.length}</span>
      </div>
      {rows.length === 0 ? (
        <p className="empty-state">{empty}</p>
      ) : (
        <div className="panel" style={{ padding: 0, overflow: "hidden" }}>
          <table className="txn-table">
            <thead>
              <tr>
                <th>Account</th>
                <th>Details</th>
                <th>Last Synced</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {rows.map(row => {
                const status = syncStatus(row.lastSyncDate);
                const dotColor = INSTITUTION_COLORS[row.institution] ?? "var(--accent)";
                return (
                  <tr key={row.id}>
                    <td>
                      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                        <span style={{
                          display: "inline-block", width: 8, height: 8,
                          borderRadius: "50%", background: dotColor, flexShrink: 0,
                        }} />
                        <div>
                          <div style={{ fontWeight: 600, fontSize: 13, color: "var(--text-1)" }}>{row.name}</div>
                          <div style={{ fontSize: 11, color: "var(--text-3)", marginTop: 1 }}>{row.institution}</div>
                        </div>
                      </div>
                    </td>
                    <td style={{ color: "var(--text-3)", fontSize: 12 }}>{row.syncDetail}</td>
                    <td className="mono" style={{ fontSize: 13 }}>{row.lastSyncDate ?? "—"}</td>
                    <td>
                      <span style={{
                        fontSize: 10, fontWeight: 700, padding: "3px 10px", borderRadius: 10,
                        background: STATUS_BG[status], color: STATUS_COLOR[status],
                        textTransform: "uppercase", letterSpacing: "0.05em",
                      }}>
                        {status === "fresh" ? daysAgo(row.lastSyncDate) : status === "aging" ? "Aging" : "Stale"}
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

const INSTITUTION_COLORS: Record<string, string> = {
  HDFC:    "#004C8C",
  SBI:     "#1A6BB5",
  Kotak:   "#ED1C24",
  ICICI:   "#F58220",
  Zerodha: "#387ED1",
  Groww:   "#00D09C",
  Manual:  "var(--text-3)",
};

export function AccountsPage() {
  const [data, setData] = useState<AccountsOverview | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getAccountsOverview()
      .then(setData)
      .catch((e: unknown) => setError(e instanceof Error ? e.message : String(e)));
  }, []);

  if (error) return <div className="panel error-box">{error}</div>;
  if (!data) return <div className="panel loading"><div className="spinner" /><span>Loading…</span></div>;

  const rows = buildRows(data);
  const total = rows.length;
  const staleCount = rows.filter(r => syncStatus(r.lastSyncDate) === "stale").length;

  return (
    <div className="dashboard">

      {/* Header */}
      <div className="panel" style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "18px 24px" }}>
        <div>
          <p className="eyebrow" style={{ marginBottom: 4 }}>Tracked Accounts</p>
          <p style={{ fontSize: 28, fontWeight: 800, color: "var(--text-1)", margin: 0, letterSpacing: "-0.02em" }}>
            {total}
          </p>
        </div>
        {staleCount > 0 && (
          <div style={{ background: "var(--red-dim)", border: "1px solid rgba(224,92,92,0.25)", borderRadius: 8, padding: "8px 14px", textAlign: "right" }}>
            <p style={{ fontSize: 11, fontWeight: 700, color: "var(--red)", textTransform: "uppercase", letterSpacing: "0.07em", margin: "0 0 2px" }}>
              Needs Update
            </p>
            <p style={{ fontSize: 18, fontWeight: 700, color: "var(--red)", margin: 0 }}>{staleCount}</p>
          </div>
        )}
      </div>

      {/* Sections */}
      <SyncSection
        title="Banks"
        rows={rows.filter(r => r.type === "bank")}
        empty="No bank statements imported yet."
      />
      <SyncSection
        title="Cards"
        rows={rows.filter(r => r.type === "credit_card")}
        empty="No credit card statements imported yet."
      />
      <SyncSection
        title="Demat &amp; Brokers"
        rows={rows.filter(r => r.type === "broker")}
        empty="No broker statements imported yet."
      />
      <SyncSection
        title="Others"
        rows={rows.filter(r => r.type === "manual")}
        empty="No manual entries added yet. Add them from the Net Worth tab."
      />

    </div>
  );
}
