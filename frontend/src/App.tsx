import { BarChart2, CreditCard, DollarSign, TrendingUp, Upload } from "lucide-react";
import { useState } from "react";
import { createRoot } from "react-dom/client";
import "./styles.css";
import { AccountsPage } from "./pages/AccountsPage";
import { ExpensesPage } from "./pages/ExpensesPage";
import { ImportPage } from "./pages/ImportPage";
import { IncomePage } from "./pages/IncomePage";
import { NetWorthPage } from "./pages/NetWorthPage";

type Page = "networth" | "income" | "expenses" | "accounts" | "import";

const TABS: { id: Page; label: string; Icon: React.ElementType }[] = [
  { id: "networth",  label: "Net Worth", Icon: TrendingUp },
  { id: "income",    label: "Income",    Icon: DollarSign },
  { id: "expenses",  label: "Expenses",  Icon: BarChart2 },
  { id: "accounts",  label: "Accounts",  Icon: CreditCard },
  { id: "import",    label: "Import",    Icon: Upload },
];

function App() {
  const [page, setPage] = useState<Page>("networth");

  return (
    <div className="app">
      {/* ── Desktop top nav ── */}
      <nav className="topnav">
        <span className="nav-brand">Finance</span>
        <div className="nav-links">
          {TABS.filter(t => t.id !== "import").map((t) => (
            <button
              key={t.id}
              className={`nav-link ${page === t.id ? "active" : ""}`}
              onClick={() => setPage(t.id)}
            >
              {t.label}
            </button>
          ))}
        </div>
        <div className="nav-import">
          <button
            className={`nav-link ${page === "import" ? "active" : ""}`}
            onClick={() => setPage("import")}
          >
            Import
          </button>
        </div>
      </nav>

      <main className="page-content">
        {page === "networth" && <NetWorthPage />}
        {page === "income"   && <IncomePage />}
        {page === "expenses" && <ExpensesPage />}
        {page === "accounts" && <AccountsPage />}
        {page === "import"   && <ImportPage onDone={() => setPage("networth")} />}
      </main>

      {/* ── Mobile bottom nav ── */}
      <nav className="bottomnav">
        {TABS.map(({ id, label, Icon }) => (
          <button
            key={id}
            className={`bottomnav-item ${page === id ? "active" : ""}`}
            onClick={() => setPage(id)}
          >
            <Icon size={20} strokeWidth={page === id ? 2.2 : 1.8} />
            <span>{label}</span>
          </button>
        ))}
      </nav>
    </div>
  );
}

createRoot(document.getElementById("root")!).render(<App />);
