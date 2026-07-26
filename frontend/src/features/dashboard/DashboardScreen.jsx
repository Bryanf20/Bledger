import { useState } from "react";
import { useAuth } from "../../context/AuthContext";
import { hasRole } from "../../components/roles";
import Banner from "../../components/Banner";
import ToastStack from "../../components/ToastStack";
import ScreenTopbar from "../../components/ScreenTopbar";
import KPIStrip from "./KPIStrip";
import SalesChart from "./SalesChart";
import TopProductsTable from "./TopProductsTable";
import PaymentBreakdownCard from "./PaymentBreakdownCard";
import StockAlertsCard from "./StockAlertsCard";
import RecentSalesList from "./RecentSalesList";
import ProfitCards from "./ProfitCards";
import { extractErrorMessage } from "../../api/errors";
import { fetchSalesReport } from "../../api/dashboard";
import { downloadBlob } from "../../utils/downloadBlob";
import { useToasts } from "../../hooks/useToasts";
import {
  useDashboardSummary,
  usePaymentBreakdown,
  useRecentSales,
  useSalesChart,
  useStockAlerts,
  useTopProducts,
} from "../../hooks/useDashboard";
import "./DashboardScreen.css";

const PERIODS = [
  { key: "today", label: "Today" },
  { key: "week", label: "This week" },
  { key: "month", label: "This month" },
];

function todayLabel() {
  return new Date().toLocaleDateString(undefined, {
    weekday: "long",
    year: "numeric",
    month: "long",
    day: "numeric",
  });
}

// Role-aware single screen, same pattern InventoryScreen established
// (not the RoleGuard-route-wrapper pattern Suppliers uses) -- per the
// UI Design Reference: "Manager+ only, except the stock alerts card
// which cashiers can also see." A cashier landing on /dashboard still
// gets the real screen, just with every widget but Stock Alerts
// replaced by a view-only notice, mirroring Inventory's "same screen,
// edit controls hidden, replaced by a notice" convention rather than
// bouncing them away entirely (which is why App.jsx does NOT wrap
// this route in RoleGuard the way it wraps /suppliers).
export default function DashboardScreen() {
  const { user, role } = useAuth();
  const [period, setPeriod] = useState("today");
  const [isExporting, setIsExporting] = useState(false);
  const { toasts, showToast, dismissToast } = useToasts();

  const canViewFull = hasRole(role, "manager");

  const { data: alerts, isLoading: alertsLoading, isError: alertsError } = useStockAlerts();

  const { data: summary, isLoading: summaryLoading } = useDashboardSummary(period);
  const { data: chartData, isLoading: chartLoading } = useSalesChart(period);
  const { data: topProducts, isLoading: topProductsLoading } = useTopProducts(period, 5);
  const { data: paymentData, isLoading: paymentLoading } = usePaymentBreakdown(period);
  const { data: salesData, isLoading: salesLoading } = useRecentSales();

  async function handleExport(exportFormat) {
    setIsExporting(true);
    try {
      const blob = await fetchSalesReport(period, exportFormat);
      const ext = exportFormat === "pdf" ? "pdf" : "csv";
      downloadBlob(blob, `sales-report-${period}.${ext}`);
    } catch (err) {
      showToast(
        "error",
        err.response?.status === 503
          ? "PDF export isn't available on this install yet (missing PDF dependency)."
          : extractErrorMessage(err, "Couldn't export the report."),
      );
    } finally {
      setIsExporting(false);
    }
  }

  return (
    <div className="dash-page">
      <div className="dash-screen">
        <ScreenTopbar
          title="Bledger"
          badge="Dashboard"
          meta={
            <>
              <span>{user?.branch?.branch_name}</span>
            </>
          }
        />

        {!canViewFull ? (
          // Cashier view: Stock Alerts only, no restock shortcut (see
          // StockAlertsCard's header comment -- /suppliers is
          // Manager+-gated so the link would be a dead end).
          <div className="dash-body dash-body-cashier">
            <Banner type="success">
              Showing stock alerts only. The full dashboard (revenue, sales chart, reports) requires manager or
              owner access.
            </Banner>
            {alertsError ? (
              <Banner type="error">Couldn&apos;t load stock alerts. Check your connection.</Banner>
            ) : (
              <StockAlertsCard alerts={alerts} isLoading={alertsLoading} showRestockLink={false} />
            )}
          </div>
        ) : (
          <div className="dash-body">
            <div className="dash-toolbar">
              <div className="dash-period-toggle">
                {PERIODS.map((p) => (
                  <div
                    key={p.key}
                    className={`dash-period-pill${period === p.key ? " active" : ""}`}
                    onClick={() => setPeriod(p.key)}
                  >
                    {p.label}
                  </div>
                ))}
              </div>
              <div className="dash-toolbar-date">{todayLabel()}</div>
              <div className="dash-toolbar-export">
                <button
                  type="button"
                  className="dash-export-btn"
                  onClick={() => handleExport("csv")}
                  disabled={isExporting}
                >
                  ⬇ CSV
                </button>
                <button
                  type="button"
                  className="dash-export-btn"
                  onClick={() => handleExport("pdf")}
                  disabled={isExporting}
                >
                  ⬇ PDF
                </button>
              </div>
            </div>

            <KPIStrip summary={summary} period={period} isLoading={summaryLoading} />

            <div className="dash-columns">
              <div className="dash-main-col">
                <div className="dash-main-scroll">
                  <SalesChart data={chartData} isLoading={chartLoading} />
                  <ProfitCards period={period} />
                  <TopProductsTable products={topProducts} isLoading={topProductsLoading} />
                </div>
              </div>

              <div className="dash-side-col">
                <div className="dash-side-scroll">
                  <PaymentBreakdownCard data={paymentData} isLoading={paymentLoading} />
                  {alertsError ? (
                    <Banner type="error">Couldn&apos;t load stock alerts.</Banner>
                  ) : (
                    <StockAlertsCard alerts={alerts} isLoading={alertsLoading} />
                  )}
                  <RecentSalesList sales={salesData?.results} isLoading={salesLoading} />
                </div>
              </div>
            </div>
          </div>
        )}
      </div>

      <ToastStack toasts={toasts} onDismiss={dismissToast} />
    </div>
  );
}
