import { AlertCircle, CheckCircle, Upload } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import {
  type ConfirmResponse,
  type PreviewResponse,
  type SourceDef,
  confirmImport,
  formatINR,
  getSources,
  previewImport,
} from "../api";

type Step = "idle" | "previewing" | "preview" | "confirming" | "done";

export function ImportPage({ onDone }: { onDone: () => void }) {
  const [sources, setSources] = useState<SourceDef[]>([]);
  const [step, setStep] = useState<Step>("idle");
  const [sourceKey, setSourceKey] = useState("");
  const [password, setPassword] = useState("");
  const [preview, setPreview] = useState<PreviewResponse | null>(null);
  const [result, setResult] = useState<ConfirmResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    getSources().then(list => {
      setSources(list);
      if (list.length) setSourceKey(list[0].id);
    });
  }, []);

  const sourceDef = sources.find((s) => s.id === sourceKey) ?? sources[0];

  if (!sources.length) return <div className="panel loading"><div className="spinner" /><span>Loading sources…</span></div>;

  function handleSourceChange(v: string) {
    setSourceKey(v);
    setError(null);
    if (fileRef.current) fileRef.current.value = "";
  }

  async function handlePreview(e: React.FormEvent) {
    e.preventDefault();
    const file = fileRef.current?.files?.[0];
    if (!file) return;
    setError(null);
    setStep("previewing");
    try {
      const data = await previewImport(file, sourceKey, password);
      setPreview(data);
      setStep("preview");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : String(err));
      setStep("idle");
    }
  }

  async function handleConfirm() {
    if (!preview) return;
    const filename = fileRef.current?.files?.[0]?.name ?? "unknown";
    setError(null);
    setStep("confirming");
    try {
      const data = await confirmImport(preview, filename);
      setResult(data);
      setStep("done");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : String(err));
      setStep("preview");
    }
  }

  if (step === "done" && result) {
    return (
      <div className="panel">
        <div className="success-icon">
          <CheckCircle size={40} color="#22c55e" />
        </div>
        <h2>Import complete</h2>
        <p>
          <strong>{result.new_rows}</strong> new rows saved.
          {result.duplicate_rows > 0 && <> {result.duplicate_rows} duplicates skipped.</>}
        </p>
        <button className="btn-primary" style={{ marginTop: 16 }} onClick={onDone}>
          View Dashboard
        </button>
      </div>
    );
  }

  if (step === "preview" && preview) {
    return <PreviewPanel
      preview={preview}
      error={error}
      onConfirm={handleConfirm}
      onCancel={() => { setStep("idle"); setPreview(null); }}
    />;
  }

  return (
    <div className="panel">
      <h2>Import Statement</h2>

      {step === "previewing" || step === "confirming" ? (
        <div className="loading">
          <div className="spinner" />
          <span>{step === "previewing" ? "Reading statement…" : "Saving…"}</span>
        </div>
      ) : (
        <form onSubmit={handlePreview}>
          <div className="field">
            <label>Statement Type</label>
            <select value={sourceKey} onChange={(e) => handleSourceChange(e.target.value)}>
              {sources.map((s) => (
                <option key={s.id} value={s.id}>{s.label}</option>
              ))}
            </select>
          </div>

          <div className="field">
            <label>File ({sourceDef?.accept.toUpperCase().replace(".", "")})</label>
            <input ref={fileRef} type="file" accept={sourceDef?.accept} required />
          </div>

          {sourceDef?.requires_password && (
            <div className="field">
              <label>Password</label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Statement password"
                required
              />
            </div>
          )}

          {error && <div className="error-box">{error}</div>}

          <button className="btn-primary" type="submit">
            <Upload size={16} />
            Preview
          </button>
        </form>
      )}
    </div>
  );
}

function PreviewPanel({
  preview,
  error,
  onConfirm,
  onCancel,
}: {
  preview: PreviewResponse;
  error: string | null;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  const { parsed } = preview;
  const s = parsed.summary;
  const isBroker = parsed.source_kind === "broker_pnl";
  const isCard = parsed.source_kind === "credit_card";

  return (
    <div className="panel">
      <h2>Preview — {parsed.account_name}</h2>
      {parsed.masked_identifier && <p className="eyebrow">{parsed.masked_identifier}</p>}

      <div className="summary-grid">
        <SummaryCard label="Period">
          {parsed.statement_start ?? "—"} → {parsed.statement_end ?? "—"}
        </SummaryCard>
        <SummaryCard label="Rows">{parsed.rows.length}</SummaryCard>

        {isCard && s.total_debits != null && (
          <SummaryCard label="Total Spent">{formatINR(s.total_debits)}</SummaryCard>
        )}
        {isCard && s.total_credits != null && (
          <SummaryCard label="Total Credits">{formatINR(s.total_credits)}</SummaryCard>
        )}

        {!isCard && !isBroker && s.total_withdrawals != null && (
          <SummaryCard label="Withdrawals">{formatINR(s.total_withdrawals)}</SummaryCard>
        )}
        {!isCard && !isBroker && s.total_deposits != null && (
          <SummaryCard label="Deposits">{formatINR(s.total_deposits)}</SummaryCard>
        )}
        {!isCard && !isBroker && s.closing_balance != null && (
          <SummaryCard label="Closing Balance">{formatINR(s.closing_balance)}</SummaryCard>
        )}

        {isBroker && s.realized_pnl != null && (
          <SummaryCard label="Realized P&L">{formatINR(s.realized_pnl)}</SummaryCard>
        )}
        {isBroker && s.unrealized_pnl != null && (
          <SummaryCard label="Unrealized P&L">{formatINR(s.unrealized_pnl)}</SummaryCard>
        )}
        {isBroker && s.total_holdings_value != null && (
          <SummaryCard label="Portfolio Value">{formatINR(s.total_holdings_value)}</SummaryCard>
        )}
        {isBroker && s.current_value != null && (
          <SummaryCard label="Current Value">{formatINR(s.current_value)}</SummaryCard>
        )}
      </div>

      {parsed.warnings.length > 0 && (
        <div className="warning-box">
          <AlertCircle size={16} />
          <ul>
            {parsed.warnings.map((w, i) => <li key={i}>{w}</li>)}
          </ul>
        </div>
      )}

      <div className="table-wrap">
        {isBroker ? (
          <BrokerTable rows={parsed.rows} />
        ) : isCard ? (
          <CardTable rows={parsed.rows} />
        ) : (
          <BankTable rows={parsed.rows} />
        )}
        {parsed.rows.length > 20 && (
          <p className="table-note">Showing 20 of {parsed.rows.length} rows.</p>
        )}
      </div>

      {error && <div className="error-box">{error}</div>}

      <div className="btn-row">
        <button className="btn-secondary" onClick={onCancel}>Cancel</button>
        <button className="btn-primary" onClick={onConfirm}>Confirm Import</button>
      </div>
    </div>
  );
}

function BankTable({ rows }: { rows: unknown[] }) {
  return (
    <table className="txn-table">
      <thead>
        <tr>
          <th>Date</th><th>Description</th><th>Channel</th>
          <th className="num">Withdrawal</th><th className="num">Deposit</th><th className="num">Balance</th>
        </tr>
      </thead>
      <tbody>
        {(rows as Record<string, unknown>[]).slice(0, 20).map((row, i) => (
          <tr key={i}>
            <td className="mono">{String(row.transaction_date)}</td>
            <td className="desc">{String(row.description)}</td>
            <td>{row.payment_channel ? String(row.payment_channel) : "—"}</td>
            <td className="num mono">{row.withdrawal ? formatINR(Number(row.withdrawal)) : ""}</td>
            <td className="num mono">{row.deposit ? formatINR(Number(row.deposit)) : ""}</td>
            <td className="num mono">{row.closing_balance != null ? formatINR(Number(row.closing_balance)) : ""}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function CardTable({ rows }: { rows: unknown[] }) {
  return (
    <table className="txn-table">
      <thead>
        <tr>
          <th>Date</th><th>Description</th><th>Type</th>
          <th className="num">Amount</th><th>Foreign</th>
        </tr>
      </thead>
      <tbody>
        {(rows as Record<string, unknown>[]).slice(0, 20).map((row, i) => (
          <tr key={i}>
            <td className="mono">{String(row.transaction_date)}</td>
            <td className="desc">{String(row.description)}</td>
            <td>
              <span style={{ color: row.entry_type === "credit" ? "var(--green)" : "var(--text-2)" }}>
                {row.is_payment ? "payment" : row.is_refund ? "refund" : String(row.entry_type)}
              </span>
            </td>
            <td className="num mono" style={{ color: row.entry_type === "credit" ? "var(--green)" : "var(--text-1)" }}>
              {row.amount != null ? formatINR(Number(row.amount)) : ""}
            </td>
            <td style={{ color: "var(--text-3)", fontSize: 12 }}>
              {row.foreign_amount ? `${row.foreign_amount} ${row.foreign_currency}` : ""}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function BrokerTable({ rows }: { rows: unknown[] }) {
  const holdings = (rows as Record<string, unknown>[]).filter(
    (r) => r.row_type === "broker_holding"
  );
  return (
    <table className="txn-table">
      <thead>
        <tr>
          <th>Symbol / Fund</th><th>ISIN</th>
          <th className="num">Qty</th><th className="num">Current Value</th>
          <th className="num">Unrealized P&L</th>
        </tr>
      </thead>
      <tbody>
        {holdings.slice(0, 20).map((row, i) => {
          const pnl = Number(row.unrealized_pnl ?? 0);
          return (
            <tr key={i}>
              <td style={{ fontWeight: 600 }}>{String(row.symbol_or_name)}</td>
              <td style={{ color: "var(--text-3)", fontSize: 12 }}>{row.isin ? String(row.isin) : "—"}</td>
              <td className="num mono">{Number(row.quantity).toFixed(3)}</td>
              <td className="num mono">{formatINR(Number(row.current_or_sell_value ?? 0))}</td>
              <td className="num mono" style={{ color: pnl >= 0 ? "var(--green)" : "var(--red)" }}>
                {formatINR(pnl)}
              </td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

function SummaryCard({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="summary-card">
      <span className="summary-label">{label}</span>
      <span className="summary-value">{children}</span>
    </div>
  );
}
