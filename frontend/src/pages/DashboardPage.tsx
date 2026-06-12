import { useEffect, useState } from "react";
import {
  Bar,
  BarChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { type DashboardSummary, formatINR, getDashboardSummary } from "../api";

export function DashboardPage() {
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getDashboardSummary()
      .then(setSummary)
      .catch((err: unknown) =>
        setError(err instanceof Error ? err.message : String(err))
      );
  }, []);

  if (error) return <div className="panel error-box">{error}</div>;
  if (!summary) return <div className="panel loading"><div className="spinner" /><span>Loading…</span></div>;

  const { accounts, monthly_spend, net_worth } = summary;
  const otherExpense = Math.max(0, monthly_spend.total_expense - monthly_spend.upi_spend);
  const spendData = [
    { name: "UPI", amount: monthly_spend.upi_spend },
    { name: "Other", amount: otherExpense },
  ];

  return (
    <div className="dashboard">
      <div className="panel net-worth-panel">
        <p className="eyebrow">Net Worth</p>
        <div className="net-worth-value">{formatINR(net_worth.total)}</div>
      </div>

      <section>
        <h2 className="section-heading">Accounts</h2>
        {accounts.length === 0 ? (
          <p className="empty-state">No accounts yet. Import a statement to get started.</p>
        ) : (
          <div className="account-grid">
            {accounts.map((acc) => (
              <div key={acc.id} className="panel account-card">
                <p className="eyebrow">{acc.institution}</p>
                <p className="account-name">{acc.name}</p>
                <p className="account-balance">{formatINR(acc.latest_balance)}</p>
                {acc.as_of_date && (
                  <p className="account-date">as of {acc.as_of_date}</p>
                )}
              </div>
            ))}
          </div>
        )}
      </section>

      <section>
        <h2 className="section-heading">
          Spending — {monthly_spend.month}
        </h2>
        <div className="account-grid">
          <div className="panel account-card">
            <p className="eyebrow">UPI Spend</p>
            <p className="account-balance">{formatINR(monthly_spend.upi_spend)}</p>
          </div>
          <div className="panel account-card">
            <p className="eyebrow">Total Expense</p>
            <p className="account-balance">{formatINR(monthly_spend.total_expense)}</p>
          </div>
        </div>

        {monthly_spend.total_expense > 0 && (
          <div className="panel chart-panel">
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={spendData} barSize={48}>
                <XAxis dataKey="name" axisLine={false} tickLine={false} />
                <YAxis
                  tickFormatter={(v) => `₹${(v / 1000).toFixed(0)}k`}
                  axisLine={false}
                  tickLine={false}
                  width={56}
                />
                <Tooltip formatter={(v) => formatINR(v as number)} />
                <Bar dataKey="amount" fill="#3b6ef8" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
      </section>
    </div>
  );
}
