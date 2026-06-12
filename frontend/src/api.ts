// In production the frontend and backend are on different Railway domains.
// Set VITE_API_URL to the backend service URL (e.g. https://api-xxx.railway.app).
// In local dev this is empty and the Vite proxy forwards /imports, /dashboard etc.
const API_BASE = (import.meta.env.VITE_API_URL ?? "").replace(/\/$/, "");
function api(path: string): string { return `${API_BASE}${path}`; }

// ── Import Sources ────────────────────────────────────────────────────────────

export interface SourceDef {
  id: string;
  label: string;
  requires_password: boolean;
  accept: string;
}

export async function getSources(): Promise<SourceDef[]> {
  const res = await fetch(api("/imports/sources"));
  if (!res.ok) throw new Error("Failed to load import sources");
  return res.json();
}

export interface TransactionRow {
  transaction_date: string;
  description: string;
  withdrawal?: number;
  deposit?: number;
  closing_balance?: number | null;
  payment_channel?: string | null;
  classification?: string | null;
  reference?: string | null;
  amount?: number;
  entry_type?: string;
}

export interface ParsedStatement {
  source_kind: string;
  institution: string;
  account_name: string;
  masked_identifier: string | null;
  statement_start: string | null;
  statement_end: string | null;
  summary: Record<string, number | null>;
  rows: TransactionRow[];
  warnings: string[];
}

export interface PreviewResponse {
  file_sha256: string;
  source: string;
  parsed: ParsedStatement;
}

export interface ConfirmResponse {
  batch_id: string;
  new_rows: number;
  duplicate_rows: number;
  status: string;
}

export interface AccountBalance {
  id: string;
  name: string;
  institution: string;
  latest_balance: number;
  as_of_date: string | null;
}

export interface DashboardSummary {
  accounts: AccountBalance[];
  monthly_spend: {
    month: string;
    upi_spend: number;
    total_expense: number;
  };
  net_worth: {
    bank_total: number;
    total: number;
  };
}

export async function previewImport(
  file: File,
  source: string,
  password: string
): Promise<PreviewResponse> {
  const form = new FormData();
  form.append("file", file);
  form.append("source", source);
  if (password) form.append("password", password);

  const res = await fetch(api("/imports/preview"), { method: "POST", body: form });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail ?? "Preview failed");
  }
  return res.json();
}

export async function confirmImport(
  preview: PreviewResponse,
  originalFilename: string
): Promise<ConfirmResponse> {
  const res = await fetch(api("/imports/confirm"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      file_sha256: preview.file_sha256,
      original_filename: originalFilename,
      parsed: preview.parsed,
    }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail ?? "Confirm failed");
  }
  return res.json();
}

export async function getDashboardSummary(): Promise<DashboardSummary> {
  const res = await fetch(api("/dashboard/summary"));
  if (!res.ok) throw new Error("Failed to load dashboard");
  return res.json();
}

// ── Net Worth ────────────────────────────────────────────────────────────────

export interface BankAccountSnapshot {
  name: string;
  balance: number;
  as_of: string;
}

export interface NetWorthBreakdown {
  bank_balance: number;
  bank_accounts: BankAccountSnapshot[];
  equity: number;
  mutual_funds: number;
  manual_assets: number;
  liabilities: number;
  total: number;
  is_imputed: boolean;
}

export interface NetWorthTrendPoint {
  month: string;
  total: number;
  bank: number;
  bank_accounts: BankAccountSnapshot[];
  investments: number;
  equity: number;
  mutual_funds: number;
  is_imputed: boolean;
  manual: number;
}

export interface NetWorthSummary {
  current: NetWorthBreakdown;
  trend: NetWorthTrendPoint[];
}

export interface ManualAssetEntry {
  id: string;
  name: string;
  kind: "asset" | "liability";
  value: number;
  date: string;
  notes: string | null;
  is_recurring?: boolean;
}

export async function getNetWorth(): Promise<NetWorthSummary> {
  const res = await fetch(api("/dashboard/networth"));
  if (!res.ok) throw new Error("Failed to load net worth");
  return res.json();
}

export async function getManualAssets(): Promise<ManualAssetEntry[]> {
  const res = await fetch(api("/manual-assets"));
  if (!res.ok) throw new Error("Failed to load manual assets");
  return res.json();
}

export async function getEffectiveAssets(month: string): Promise<ManualAssetEntry[]> {
  const res = await fetch(api(`/manual-assets/effective?month=${month}`));
  if (!res.ok) throw new Error("Failed to load assets for month");
  return res.json();
}

type AssetBody = { name: string; kind: string; value: number; date: string; notes?: string };

export async function createManualAsset(body: AssetBody): Promise<{ id: string }> {
  const res = await fetch(api("/manual-assets"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail ?? "Failed to save");
  }
  return res.json();
}

export async function updateManualAsset(id: string, body: AssetBody): Promise<void> {
  const res = await fetch(api(`/manual-assets/${id}`), {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail ?? "Failed to update");
  }
}

export async function deleteManualAsset(id: string): Promise<void> {
  const res = await fetch(api(`/manual-assets/${id}`), { method: "DELETE" });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail ?? "Failed to delete");
  }
}

// ── Accounts Overview ────────────────────────────────────────────────────────

export interface BankAccountInfo {
  id: string;
  name: string;
  institution: string;
  masked_identifier: string | null;
  latest_balance: number | null;
  last_txn_date: string | null;
  statement_start: string | null;
  txn_count: number;
}

export interface CreditCardInfo {
  id: string;
  name: string;
  institution: string;
  masked_identifier: string | null;
  statement_date: string | null;
  billing_start: string | null;
  billing_end: string | null;
  last_spend: number;
  txn_count: number;
}

export interface BrokerAccountInfo {
  id: string;
  name: string;
  institution: string;
  masked_identifier: string | null;
  portfolio_value: number;
  unrealized_pnl: number;
  as_of_date: string | null;
  holdings_count: number;
}

export interface ManualAssetInfo {
  id: string;
  name: string;
  kind: "asset" | "liability";
  value: number;
  date: string;
  notes: string | null;
}

export interface AccountsOverview {
  banks: BankAccountInfo[];
  credit_cards: CreditCardInfo[];
  brokers: BrokerAccountInfo[];
  manual_assets: ManualAssetInfo[];
}

export async function getAccountsOverview(): Promise<AccountsOverview> {
  const res = await fetch(api("/accounts/overview"));
  if (!res.ok) throw new Error("Failed to load accounts");
  return res.json();
}

// ── Income ───────────────────────────────────────────────────────────────────

export interface IncomeEntry {
  id: string;
  date: string;
  amount: number;
  entity: string;
  category: string;
  source: string;
}

export interface IncomeSummary {
  total_realized: number;
  unrealized_ltcg: number;
  by_category: Record<string, number>;
  trend: { month: string; total: number }[];
  entries: IncomeEntry[];
  category_labels: Record<string, string>;
  category_colors: Record<string, string>;
}

export async function getIncomeSummary(): Promise<IncomeSummary> {
  const res = await fetch(api("/dashboard/income"));
  if (!res.ok) throw new Error("Failed to load income");
  return res.json();
}

// ── Expenses ─────────────────────────────────────────────────────────────────

export interface ExpenseEntry {
  id: string;
  date: string;
  amount: number;
  description: string;
  account_id: string;
  account_name: string;
  institution: string;
}

export interface ExpenseAccount {
  account_id: string;
  account_name: string;
  institution: string;
  total: number;
  transactions: ExpenseEntry[];
  random_total: number;
  random_count: number;
  random_transactions: ExpenseEntry[];
}

export interface ExpensesSummary {
  total_spend: number;
  accounts: ExpenseAccount[];
  trend: { month: string; total: number }[];
  random_threshold: number;
}

export async function getExpensesSummary(): Promise<ExpensesSummary> {
  const res = await fetch(api("/dashboard/expenses"));
  if (!res.ok) throw new Error("Failed to load expenses");
  return res.json();
}

export interface DataFlag {
  account_id: string;
  account_name: string;
  institution: string;
  account_type: string;
  last_date: string | null;
  days_since: number | null;
}

export async function getDataFlags(): Promise<DataFlag[]> {
  const res = await fetch(api("/dashboard/data-flags"));
  if (!res.ok) throw new Error("Failed to load data flags");
  return res.json();
}

export const formatINR = (n: number) =>
  new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 0,
  }).format(n);
