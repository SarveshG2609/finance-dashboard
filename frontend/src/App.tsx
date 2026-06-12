import { useState } from "react";
import { createRoot } from "react-dom/client";
import "./styles.css";
import { AccountsPage } from "./pages/AccountsPage";
import { ExpensesPage } from "./pages/ExpensesPage";
import { ImportPage } from "./pages/ImportPage";
import { IncomePage } from "./pages/IncomePage";
import { NetWorthPage } from "./pages/NetWorthPage";

type Page = "networth" | "income" | "expenses" | "accounts" | "import";

const MAIN_TABS: { id: Page; label: string }[] = [
  { id: "networth", label: "Net Worth" },
  { id: "income", label: "Income" },
  { id: "expenses", label: "Expenses" },
  { id: "accounts", label: "Accounts" },
];

function App() {
  const [page, setPage] = useState<Page>("networth");

  return (
    <div className="app">
      <nav className="topnav">
        <span className="nav-brand">Finance</span>
        <div className="nav-links">
          {MAIN_TABS.map((t) => (
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
        {page === "income" && <IncomePage />}
        {page === "expenses" && <ExpensesPage />}
        {page === "accounts" && <AccountsPage />}
        {page === "import" && <ImportPage onDone={() => setPage("networth")} />}
      </main>
    </div>
  );
}

createRoot(document.getElementById("root")!).render(<App />);
