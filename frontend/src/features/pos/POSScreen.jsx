import { useNavigate } from "react-router-dom";
import { useMemo, useState } from "react";
import { useAuth } from "../../context/AuthContext";
import ThemeToggle from "../../components/ThemeToggle";
import UserMenu from "../../components/UserMenu";
import XAFAmount from "../../components/XAFAmount";
import { useProducts } from "../../hooks/useProducts";
import { useCreateSale } from "../../hooks/useCreateSale";
import { useHeldSales, useHoldSale } from "../../hooks/useHeldSales";
import { useCartStore } from "../../store/cartStore";
import ProductGrid from "./ProductGrid";
import Cart from "./Cart";
import PaymentPanel from "./PaymentPanel";
import HeldSalesDrawer from "./HeldSalesDrawer";
import "./POSScreen.css";

export default function POSScreen() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const { data: products, isLoading, isError } = useProducts();
  const { data: heldSales } = useHeldSales();
  const createSaleMutation = useCreateSale();
  const holdSaleMutation = useHoldSale();

  const items = useCartStore((s) => s.items);
  const clear = useCartStore((s) => s.clear);
  const addItem = useCartStore((s) => s.addItem);
  const restoreFrom = useCartStore((s) => s.restoreFrom);
  const subtotal = items.reduce((sum, i) => sum + i.lineTotal, 0);

  const [search, setSearch] = useState("");
  const [category, setCategory] = useState(null);
  const [view, setView] = useState("grid");
  const [showHeldDrawer, setShowHeldDrawer] = useState(false);
  const [paymentMethod, setPaymentMethod] = useState(null);
  const [momoReference, setMomoReference] = useState("");
  const [momoConfirmed, setMomoConfirmed] = useState(false);
  const [banner, setBanner] = useState(null);

  // Inline confirmation card shown over the right panel -- replaces
  // window.prompt()/window.confirm() so hold/clear match the app's
  // own theme instead of an unstyled OS dialog. `action` is
  // "hold" | "clear" | null; `holdLabel` only used by the hold flow.
  const [action, setAction] = useState(null);
  const [holdLabel, setHoldLabel] = useState("");

  const productsById = useMemo(() => new Map((products ?? []).map((p) => [p.id, p])), [products]);

  const categories = useMemo(() => {
    const seen = new Map();
    for (const p of products ?? []) {
      if (p.category && !seen.has(p.category)) seen.set(p.category, p.category_name);
    }
    return Array.from(seen, ([id, name]) => ({ id, name }));
  }, [products]);

  const visibleProducts = useMemo(() => {
    return (products ?? []).filter((p) => {
      if (category && p.category !== category) return false;
      if (search && !p.name.toLowerCase().includes(search.toLowerCase())) return false;
      return true;
    });
  }, [products, search, category]);

  const isMomo = paymentMethod === "mtn_momo" || paymentMethod === "orange_money";
  const canConfirm = items.length > 0 && paymentMethod && (!isMomo || (momoReference.trim() && momoConfirmed));

  function resetPaymentState() {
    setPaymentMethod(null);
    setMomoReference("");
    setMomoConfirmed(false);
  }

  function closeAction() {
    setAction(null);
    setHoldLabel("");
  }

  async function handleConfirmSale() {
    setBanner(null);
    try {
      const sale = await createSaleMutation.mutateAsync({
        payment_method: paymentMethod,
        ...(isMomo ? { momo_reference: momoReference.trim(), momo_confirmed: momoConfirmed } : {}),
        items: items.map((i) => ({ product: i.productId, quantity: i.quantity })),
      });
      clear();
      resetPaymentState();
      navigate(`/receipt/${sale.id}`);
    } catch (err) {
      const detail =
        err.response?.data?.items?.[0] ||
        err.response?.data?.detail ||
        "Could not complete the sale. Check stock and try again.";
      setBanner({ type: "error", message: detail });
    }
  }

  async function confirmHoldSale() {
    await holdSaleMutation.mutateAsync({
      label: holdLabel,
      cartData: { items: items.map((i) => ({ product: i.productId, quantity: i.quantity })) },
    });
    clear();
    resetPaymentState();
    closeAction();
  }

  function confirmClearCart() {
    clear();
    resetPaymentState();
    closeAction();
  }

  function handleRestore(cartData) {
    restoreFrom(cartData, products ?? []);
    setShowHeldDrawer(false);
  }

  if (isLoading) {
    return (
      <div className="pos-page">
        <div className="pos-screen">
          <div className="pos-empty-state">Loading products…</div>
        </div>
      </div>
    );
  }
  if (isError) {
    return (
      <div className="pos-page">
        <div className="pos-screen">
          <div className="pos-error-banner">Couldn&apos;t load products. Check your connection.</div>
        </div>
      </div>
    );
  }

  return (
    <div className="pos-page">
      <div className="pos-screen">
        <div className="pos-topbar">
          <div className="pos-topbar-left">
            <span className="pos-topbar-title">Bledger</span>
            <span className="pos-topbar-badge">Point of sale</span>
          </div>
          <div className="pos-topbar-meta">
            <span>
              <span className="pos-sync-dot" />
              Synced
            </span>
            <span>{user?.branch?.branch_name}</span>
            <ThemeToggle />
            <UserMenu />
          </div>
        </div>

        {banner && (
          <div className={banner.type === "error" ? "pos-error-banner" : "pos-success-banner"} role="alert">
            {banner.message}
          </div>
        )}

        <div className="pos-body">
          <div className="pos-left-panel">
            <div className="pos-left-header">
              <div className="pos-search-row">
                <input
                  type="text"
                  placeholder="Search products by name…"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                />
                <button type="button" className="pos-icon-btn" disabled title="Phase 2">
                  ⌗  barcode
                </button>
                <button type="button" className="pos-icon-btn pos-held-btn" onClick={() => setShowHeldDrawer(true)}>
                  ⏸ {heldSales?.length ?? 0} held
                </button>
                <div className="pos-view-toggle">
                  <button
                    type="button"
                    className={view === "grid" ? "active" : ""}
                    onClick={() => setView("grid")}
                    aria-label="Grid view"
                    title="Grid view"
                  >
                    ⊞
                  </button>
                  <button
                    type="button"
                    className={view === "list" ? "active" : ""}
                    onClick={() => setView("list")}
                    aria-label="List view"
                    title="List view"
                  >
                    ☰
                  </button>
                </div>
              </div>

              <div className="pos-cat-pills">
                <div className={`pos-pill${!category ? " active" : ""}`} onClick={() => setCategory(null)}>
                  All
                </div>
                {categories.map((c) => (
                  <div
                    key={c.id}
                    className={`pos-pill${category === c.id ? " active" : ""}`}
                    onClick={() => setCategory(c.id)}
                  >
                    {c.name}
                  </div>
                ))}
              </div>
            </div>

            <div className="pos-prod-scroll">
              <ProductGrid products={visibleProducts} onSelect={addItem} view={view} />
            </div>
          </div>

          <div className="pos-right-panel">
            <div className="pos-cart-scroll">
              <Cart productsById={productsById} />
            </div>

            <div className="pos-right-footer">
              <div className="pos-total-row">
                <span>Subtotal</span>
                <XAFAmount value={subtotal} />
              </div>
              <div className="pos-total-row">
                <span>Tax (0%)</span>
                <XAFAmount value={0} />
              </div>
              <hr className="pos-divider" />
              <div className="pos-grand-row">
                <span>Total</span>
                <XAFAmount value={subtotal} />
              </div>

              <PaymentPanel
                method={paymentMethod}
                onMethodChange={setPaymentMethod}
                momoReference={momoReference}
                onMomoReferenceChange={setMomoReference}
                momoConfirmed={momoConfirmed}
                onMomoConfirmedChange={setMomoConfirmed}
              />

              <div className="pos-footer-actions">
                <button
                  type="button"
                  className="pos-icon-btn pos-hold-sale-btn"
                  disabled={!items.length}
                  onClick={() => setAction("hold")}
                >
                  ⏸ Hold this sale
                </button>
                <button
                  type="button"
                  className="pos-icon-btn pos-clear-btn"
                  disabled={!items.length}
                  onClick={() => setAction("clear")}
                >
                  🗑 Clear cart
                </button>
              </div>

              <button
                type="button"
                className="pos-confirm-btn"
                disabled={!canConfirm || createSaleMutation.isPending}
                onClick={handleConfirmSale}
              >
                {createSaleMutation.isPending ? "Completing…" : "Confirm sale"}
              </button>
            </div>

            {/* Inline confirmation overlay -- confined to the right
                panel (its parent has position:relative), not a
                viewport-wide modal, per design intent: it should read
                as "this panel is asking you something," not a global
                interrupt. */}
            {action === "hold" && (
              <div className="pos-inline-confirm-backdrop">
                <div className="pos-inline-confirm">
                  <p className="pos-inline-confirm-title">Hold this sale</p>
                  <input
                    type="text"
                    className="pos-inline-confirm-input"
                    placeholder="Label (optional)"
                    value={holdLabel}
                    onChange={(e) => setHoldLabel(e.target.value)}
                    autoFocus
                  />
                  <div className="pos-inline-confirm-actions">
                    <button type="button" className="pos-icon-btn" onClick={closeAction}>
                      Cancel
                    </button>
                    <button
                      type="button"
                      className="pos-confirm-btn pos-inline-confirm-btn"
                      onClick={confirmHoldSale}
                      disabled={holdSaleMutation.isPending}
                    >
                      {holdSaleMutation.isPending ? "Holding…" : "Hold sale"}
                    </button>
                  </div>
                </div>
              </div>
            )}

            {action === "clear" && (
              <div className="pos-inline-confirm-backdrop">
                <div className="pos-inline-confirm">
                  <p className="pos-inline-confirm-title">Clear the current sale?</p>
                  <p className="pos-inline-confirm-sub">This can&apos;t be undone.</p>
                  <div className="pos-inline-confirm-actions">
                    <button type="button" className="pos-icon-btn" onClick={closeAction}>
                      Cancel
                    </button>
                    <button
                      type="button"
                      className="pos-inline-confirm-btn pos-inline-confirm-btn-danger"
                      onClick={confirmClearCart}
                    >
                      Clear cart
                    </button>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>

        <div className="pos-status-bar">
          <span>Ready</span>
          <span className="pos-badge">Stock: OK</span>
        </div>
      </div>

      {showHeldDrawer && (
        <HeldSalesDrawer
          productsById={productsById}
          onRestore={handleRestore}
          onClose={() => setShowHeldDrawer(false)}
        />
      )}
    </div>
  );
}
