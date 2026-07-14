import { useMemo, useState } from "react";
import { useAuth } from "../../context/AuthContext";
import Banner from "../../components/Banner";
import ToastStack from "../../components/ToastStack";
import ScreenTopbar from "../../components/ScreenTopbar";
import SupplierList from "./SupplierList";
import SupplierDetail from "./SupplierDetail";
import SupplierFormPanel from "./SupplierFormPanel";
import { extractErrorMessage } from "../../api/errors";
import { usePurchases, useSuppliers } from "../../hooks/useSuppliers";
import { useToasts } from "../../hooks/useToasts";
import "./SuppliersScreen.css";

// Manager/owner-only per apps/suppliers/views.py's IsManagerOrOwner
// gate on the whole app -- App.jsx wraps this route in a RoleGuard
// (minimumRole="manager") rather than this screen having its own
// cashier-visible fallback state, unlike Inventory. Per the UI Design
// Reference's "Role-based visibility" global pattern: "Supplier/
// Purchase screens entirely (cashiers don't see them)".
export default function SuppliersScreen() {
  const { user } = useAuth();
  const { data: suppliers, isLoading: suppliersLoading, isError: suppliersError } = useSuppliers();
  const { data: purchases, isLoading: purchasesLoading, isError: purchasesError } = usePurchases();

  const [search, setSearch] = useState("");
  const [selectedId, setSelectedId] = useState(null);
  const [formPanel, setFormPanel] = useState(null); // { mode: "add" } | { mode: "edit", supplier }

  const { toasts, showToast, dismissToast } = useToasts();
  const showSuccess = (message) => showToast("success", message);
  const showError = (err, fallback) => showToast("error", extractErrorMessage(err, fallback));

  const visibleSuppliers = useMemo(() => {
    if (!suppliers) return [];
    const q = search.trim().toLowerCase();
    if (!q) return suppliers;
    return suppliers.filter((s) => s.name.toLowerCase().includes(q));
  }, [suppliers, search]);

  // Defaults to the first supplier in the (unfiltered) list once it
  // loads, so the detail panel isn't blank on first visit -- matches
  // 04_suppliers.html's mockup, which shows "Eto'o Supplies" already
  // selected. Search filtering the LEFT list doesn't clear this
  // selection; it only changes what's visible to pick from.
  const selectedSupplier = useMemo(() => {
    if (!suppliers?.length) return null;
    return suppliers.find((s) => s.id === selectedId) ?? suppliers[0];
  }, [suppliers, selectedId]);

  const supplierPurchases = useMemo(() => {
    if (!purchases || !selectedSupplier) return [];
    return purchases
      .filter((p) => p.supplier === selectedSupplier.id)
      .sort((a, b) => (a.purchase_date < b.purchase_date ? 1 : -1));
  }, [purchases, selectedSupplier]);

  const isLoading = suppliersLoading || purchasesLoading;
  const isError = suppliersError || purchasesError;

  return (
    <div className="sup-page">
      <div className="sup-screen">
        <ScreenTopbar
          title="Bledger — Suppliers & purchases"
          meta={
            <span>
              👤 {user?.name} · {user?.branch?.branch_name}
            </span>
          }
        />

        {isError && (
          <Banner type="error">Couldn&apos;t load suppliers. Check your connection and try again.</Banner>
        )}

        {!isError && (
          /* `show-detail` drives the <720px one-panel-at-a-time flow
             (see SuppliersScreen.css's media query): an EXPLICIT
             selection (selectedId set) switches to the detail panel;
             the detail header's back button clears it to return to the
             list. Desktop is unaffected -- both panels always render,
             and selectedSupplier still falls back to the first
             supplier when nothing is explicitly selected. */
          <div className={`sup-body${selectedId !== null ? " show-detail" : ""}`}>
            <SupplierList
              suppliers={visibleSuppliers}
              search={search}
              onSearchChange={setSearch}
              selectedId={selectedSupplier?.id ?? null}
              onSelect={setSelectedId}
              onAddSupplier={() => setFormPanel({ mode: "add" })}
              isLoading={isLoading}
            />

            <SupplierDetail
              supplier={selectedSupplier}
              purchases={supplierPurchases}
              isLoading={isLoading}
              onEditSupplier={() => setFormPanel({ mode: "edit", supplier: selectedSupplier })}
              onBack={() => setSelectedId(null)}
              onSuccess={showSuccess}
              onError={showError}
            />
          </div>
        )}
      </div>

      {formPanel && (
        <SupplierFormPanel
          mode={formPanel.mode}
          supplier={formPanel.supplier}
          onClose={() => setFormPanel(null)}
          onSuccess={(message, newSupplierId) => {
            setFormPanel(null);
            showSuccess(message);
            if (newSupplierId) setSelectedId(newSupplierId);
          }}
          onError={showError}
        />
      )}

      <ToastStack toasts={toasts} onDismiss={dismissToast} />
    </div>
  );
}
