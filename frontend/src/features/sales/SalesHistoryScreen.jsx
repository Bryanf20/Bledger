import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../../context/AuthContext";
import Banner from "../../components/Banner";
import ScreenTopbar from "../../components/ScreenTopbar";
import { useSalesHistory } from "../../hooks/useSalesHistory";
import SalesTable from "./SalesTable";
import SalesCard from "./SalesCard";
import "./SalesHistoryScreen.css";

// Sales History is new this session -- not one of the 7 screens in
// the UI Design Reference. Filter/toolbar shape is patterned after
// Inventory's toolbar+pills+view-toggle; the table itself is closer
// to Suppliers' purchase history table. See project instructions for
// the full deviation note.

const STATUS_FILTERS = [
  { key: "all", label: "All" },
  { key: "completed", label: "Completed" },
  { key: "voided", label: "Voided" },
];

const PAYMENT_FILTERS = [
  { key: "all", label: "All" },
  { key: "cash", label: "Cash" },
  { key: "mtn_momo", label: "MTN MoMo" },
  { key: "orange_money", label: "Orange Money" },
  { key: "other", label: "Other" },
];

const PAGE_SIZE = 25; // matches apps.core.pagination.StandardResultsSetPagination

export default function SalesHistoryScreen() {
  const { user, role } = useAuth();
  const navigate = useNavigate();
  // Cashiers only ever see their own sales (server-enforced) -- the
  // Cashier column would just repeat their own name on every row.
  const showCashierColumn = role !== "cashier";

  const [view, setView] = useState("table");
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [paymentFilter, setPaymentFilter] = useState("all");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [page, setPage] = useState(1);

  // Debounce free-text search before it hits the backend -- low-
  // bandwidth optimisation (design doc Section 14). This is also why
  // this screen filters server-side at all, unlike POS/Inventory's
  // fetch-everything-then-filter-client-side approach: those
  // catalogues are tens to low hundreds of rows, sales history over
  // real time isn't bounded the same way.
  useEffect(() => {
    const t = setTimeout(() => setDebouncedSearch(search.trim()), 300);
    return () => clearTimeout(t);
  }, [search]);

  // Any filter change invalidates whatever page we were on.
  useEffect(() => {
    setPage(1);
  }, [debouncedSearch, statusFilter, paymentFilter, dateFrom, dateTo]);

  const filters = useMemo(
    () => ({
      page,
      search: debouncedSearch || undefined,
      status: statusFilter === "all" ? undefined : statusFilter,
      paymentMethod: paymentFilter === "all" ? undefined : paymentFilter,
      dateFrom: dateFrom || undefined,
      dateTo: dateTo || undefined,
    }),
    [page, debouncedSearch, statusFilter, paymentFilter, dateFrom, dateTo],
  );

  const { data, isLoading, isError } = useSalesHistory(filters);
  const sales = data?.results ?? [];
  const totalCount = data?.count ?? 0;
  const totalPages = Math.max(1, Math.ceil(totalCount / PAGE_SIZE));

  const hasActiveFilters =
    Boolean(search) || statusFilter !== "all" || paymentFilter !== "all" || Boolean(dateFrom) || Boolean(dateTo);

  function clearFilters() {
    setSearch("");
    setStatusFilter("all");
    setPaymentFilter("all");
    setDateFrom("");
    setDateTo("");
  }

  function openSale(id) {
    // Void lives on the existing Receipt screen -- this screen never
    // duplicates that logic, it just navigates there.
    navigate(`/receipt/${id}`);
  }

  if (isError) {
    return (
      <div className="sh-page">
        <div className="sh-screen">
          <Banner type="error">Couldn&apos;t load sales history. Check your connection.</Banner>
        </div>
      </div>
    );
  }

  return (
    <div className="sh-page">
      <div className="sh-screen">
        <ScreenTopbar
          title="Bledger"
          badge="Sales history"
          meta={
            <>
              <span>{user?.branch?.branch_name}</span>
            </>
          }
        />

        <div className="sh-body">
          <div className="sh-toolbar">
            <div className="sh-toolbar-row">
              <div className="sh-toolbar-left">
                <input
                  type="text"
                  className="sh-search"
                  placeholder="Search by sale reference…"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                />
                <div className="sh-pills">
                  {STATUS_FILTERS.map((f) => (
                    <div
                      key={f.key}
                      className={`sh-pill${statusFilter === f.key ? " active" : ""}`}
                      onClick={() => setStatusFilter(f.key)}
                    >
                      {f.label}
                    </div>
                  ))}
                </div>
              </div>

              <div className="sh-view-toggle">
                <button
                  type="button"
                  className={view === "table" ? "active" : ""}
                  onClick={() => setView("table")}
                  aria-label="Table view"
                  title="Table view"
                >
                  ☰
                </button>
                <button
                  type="button"
                  className={view === "card" ? "active" : ""}
                  onClick={() => setView("card")}
                  aria-label="Card view"
                  title="Card view"
                >
                  ⊞
                </button>
              </div>
            </div>

            <div className="sh-toolbar-row">
              <div className="sh-date-range">
                <label className="sh-date-label">
                  From
                  <input type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} />
                </label>
                <label className="sh-date-label">
                  To
                  <input type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} />
                </label>
              </div>

              <div className="sh-pills">
                {PAYMENT_FILTERS.map((f) => (
                  <div
                    key={f.key}
                    className={`sh-pill${paymentFilter === f.key ? " active" : ""}`}
                    onClick={() => setPaymentFilter(f.key)}
                  >
                    {f.label}
                  </div>
                ))}
              </div>

              {hasActiveFilters && (
                <button type="button" className="sh-clear-btn" onClick={clearFilters}>
                  Clear filters
                </button>
              )}
            </div>
          </div>

          <div className="sh-content">
            {isLoading ? (
              <div className="sh-empty-state">Loading sales…</div>
            ) : sales.length === 0 ? (
              <div className="sh-empty-state">No sales match your filters.</div>
            ) : view === "table" ? (
              <SalesTable sales={sales} showCashier={showCashierColumn} onOpen={openSale} />
            ) : (
              <div className="sh-card-grid">
                {sales.map((sale) => (
                  <SalesCard key={sale.id} sale={sale} showCashier={showCashierColumn} onOpen={openSale} />
                ))}
              </div>
            )}
          </div>

          <div className="sh-status-bar">
            <span>
              {totalCount === 0 ? "No matching sales" : `Showing ${sales.length} of ${totalCount} matching sales`}
            </span>
            <div className="sh-pager">
              <button type="button" disabled={!data?.previous} onClick={() => setPage((p) => Math.max(1, p - 1))}>
                ← Prev
              </button>
              <span>
                Page {page} of {totalPages}
              </span>
              <button type="button" disabled={!data?.next} onClick={() => setPage((p) => p + 1)}>
                Next →
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
