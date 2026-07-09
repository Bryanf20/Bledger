import { useMemo, useState } from "react";
import { useAuth } from "../../context/AuthContext";
import { hasRole } from "../../components/RoleGuard";
import Banner from "../../components/Banner";
import ToastStack from "../../components/ToastStack";
import ScreenTopbar from "../../components/ScreenTopbar";
import XAFAmount from "../../components/XAFAmount";
import ProductTable from "./ProductTable";
import ProductCard from "./ProductCard";
import ProductFormPanel from "./ProductFormPanel";
import AdjustStockPanel from "./AdjustStockPanel";
import { extractErrorMessage } from "../../api/errors";
import { useCategories, useInventoryProducts, useReactivateProduct } from "../../hooks/useInventory";
import { useToasts } from "../../hooks/useToasts";
import "./InventoryScreen.css";

// UI Design Reference, Screen 3: status filter is a separate
// single-select dimension from the category pill row below it, not
// folded into the same pill group.
const STATUS_FILTERS = [
  { key: "all", label: "All" },
  { key: "low", label: "Low stock" },
  { key: "out", label: "Out of stock" },
];

export default function InventoryScreen() {
  const { user, role } = useAuth();
  const canEdit = hasRole(role, "manager");

  const { data: products, isLoading, isError } = useInventoryProducts();
  const { data: categories } = useCategories();
  const reactivateMutation = useReactivateProduct();

  const [view, setView] = useState("table");
  const [search, setSearch] = useState("");
  const [categoryId, setCategoryId] = useState(null);
  const [statusFilter, setStatusFilter] = useState("all");
  const [showInactive, setShowInactive] = useState(false);

  const [formPanel, setFormPanel] = useState(null); // { mode: "add" } | { mode: "edit", product }
  const [adjustingProduct, setAdjustingProduct] = useState(null);

  // Ephemeral action feedback (add/edit/deactivate/adjust results) --
  // a corner toast stack, not a persistent Banner. Banner is reserved
  // below for the screen-load failure case, which is blocking and
  // should stay on screen until the underlying problem is fixed.
  const { toasts, showToast, dismissToast } = useToasts();

  const visibleProducts = useMemo(() => {
    if (!products) return [];
    const q = search.trim().toLowerCase();
    return products.filter((p) => {
      if (!showInactive && !p.is_active) return false;
      if (categoryId && p.category !== categoryId) return false;
      if (statusFilter === "low" && p.stock_status !== "low") return false;
      if (statusFilter === "out" && p.stock_status !== "out") return false;
      if (q && !p.name.toLowerCase().includes(q)) return false;
      return true;
    });
  }, [products, search, categoryId, statusFilter, showInactive]);

  // Summary stat strip (UI Design Reference, Screen 3 "Components") --
  // active products only, same scope as the stock-status badges.
  const stats = useMemo(() => {
    const active = (products ?? []).filter((p) => p.is_active);
    return {
      totalActive: active.length,
      stockValue: active.reduce((sum, p) => sum + p.stock_level * p.effective_retail_price, 0),
      lowCount: active.filter((p) => p.stock_status === "low").length,
      outCount: active.filter((p) => p.stock_status === "out").length,
    };
  }, [products]);

  function showError(err, fallback) {
    showToast("error", extractErrorMessage(err, fallback));
  }
  function showSuccess(message) {
    showToast("success", message);
  }

  async function handleReactivate(product) {
    try {
      await reactivateMutation.mutateAsync(product.id);
      showSuccess(`${product.name} reactivated.`);
    } catch (err) {
      showError(err, "Couldn't reactivate that product.");
    }
  }

  if (isLoading) {
    return (
      <div className="inv-page">
        <div className="inv-screen">
          <div className="inv-empty-state">Loading inventory…</div>
        </div>
      </div>
    );
  }

  if (isError) {
    return (
      <div className="inv-page">
        <div className="inv-screen">
          {/* Load failure -- persistent Banner, not a toast: the
              screen has no data to show until this is resolved. */}
          <Banner type="error">Couldn&apos;t load inventory. Check your connection.</Banner>
        </div>
      </div>
    );
  }

  return (
    <div className="inv-page">
      <div className="inv-screen">
        <ScreenTopbar
          title="Bledger"
          badge="Inventory"
          meta={
            <>
              <span>
                <span className="screen-sync-dot" />
                Synced
              </span>
              <span>{user?.branch?.branch_name}</span>
            </>
          }
        />

        <div className="inv-body">
          <div className="inv-toolbar">
            <div className="inv-toolbar-row">
              <div className="inv-toolbar-left">
                <input
                  type="text"
                  className="inv-search"
                  placeholder="Search products by name…"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                />
                <div className="inv-status-filters">
                  {STATUS_FILTERS.map((f) => (
                    <div
                      key={f.key}
                      className={`inv-pill${statusFilter === f.key ? " active" : ""}`}
                      onClick={() => setStatusFilter(f.key)}
                    >
                      {f.label}
                    </div>
                  ))}
                </div>
              </div>

              <div className="inv-toolbar-right">
                <div className="inv-view-toggle">
                  <button type="button" className={view === "table" ? "active" : ""} onClick={() => setView("table")} aria-label="Table view" title="Table view">
                    ☰
                  </button>
                  <button type="button" className={view === "card" ? "active" : ""} onClick={() => setView("card")} aria-label="Card view" title="Card view">
                    ⊞
                  </button>
                </div>

                {canEdit && (
                  <button type="button" className="inv-add-btn" onClick={() => setFormPanel({ mode: "add" })}>
                    + Add product
                  </button>
                )}
              </div>
            </div>

            <div className="inv-toolbar-row">
              <div className="inv-cat-pills">
                <div className={`inv-pill${!categoryId ? " active" : ""}`} onClick={() => setCategoryId(null)}>
                  All categories
                </div>
                {(categories ?? []).map((c) => (
                  <div key={c.id} className={`inv-pill${categoryId === c.id ? " active" : ""}`} onClick={() => setCategoryId(c.id)}>
                    {c.name}
                  </div>
                ))}
              </div>

              {canEdit && (
                <label className="inv-inactive-toggle">
                  <input type="checkbox" checked={showInactive} onChange={(e) => setShowInactive(e.target.checked)} />
                  Show deactivated
                </label>
              )}
            </div>
          </div>

          <div className="inv-stats-strip">
            <div className="inv-stat">
              <div className="inv-stat-label">Active products</div>
              <div className="inv-stat-value">{stats.totalActive}</div>
            </div>
            <div className="inv-stat">
              <div className="inv-stat-label">Estimated stock value</div>
              <div className="inv-stat-value"><XAFAmount value={stats.stockValue} /></div>
            </div>
            <div className="inv-stat">
              <div className="inv-stat-label">Low stock</div>
              <div className="inv-stat-value warning">{stats.lowCount}</div>
            </div>
            <div className="inv-stat">
              <div className="inv-stat-label">Out of stock</div>
              <div className="inv-stat-value danger">{stats.outCount}</div>
            </div>
          </div>

          <div className="inv-content">
            {view === "table" ? (
              <ProductTable
                products={visibleProducts}
                canEdit={canEdit}
                onEdit={(product) => setFormPanel({ mode: "edit", product })}
                onAdjust={setAdjustingProduct}
                onReactivate={handleReactivate}
              />
            ) : (
              <div className="inv-card-grid">
                {visibleProducts.length === 0 ? (
                  <div className="inv-empty-state">No products match your search.</div>
                ) : (
                  visibleProducts.map((p) => (
                    <ProductCard
                      key={p.id}
                      product={p}
                      canEdit={canEdit}
                      onEdit={() => setFormPanel({ mode: "edit", product: p })}
                      onAdjust={() => setAdjustingProduct(p)}
                      onReactivate={() => handleReactivate(p)}
                    />
                  ))
                )}
              </div>
            )}
          </div>
        </div>

        <div className="inv-status-bar">
          {canEdit ? (
            <span>{visibleProducts.length} of {products?.length ?? 0} products shown</span>
          ) : (
            <span>View only — contact owner to make changes.</span>
          )}
        </div>
      </div>

      {formPanel && (
        <ProductFormPanel
          mode={formPanel.mode}
          product={formPanel.product}
          categories={categories ?? []}
          onClose={() => setFormPanel(null)}
          onSuccess={(message) => {
            setFormPanel(null);
            showSuccess(message);
          }}
          onError={showError}
        />
      )}

      {adjustingProduct && (
        <AdjustStockPanel
          product={adjustingProduct}
          onClose={() => setAdjustingProduct(null)}
          onSuccess={(message) => {
            setAdjustingProduct(null);
            showSuccess(message);
          }}
          onError={showError}
        />
      )}

      <ToastStack toasts={toasts} onDismiss={dismissToast} />
    </div>
  );
}