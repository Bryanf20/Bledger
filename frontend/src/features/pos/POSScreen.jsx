import { useNavigate } from "react-router-dom";
import { useMemo, useState } from "react";
import { useAuth } from "../../context/AuthContext";
import Banner from "../../components/Banner";
import InlineConfirm from "../../components/InlineConfirm";
import ScreenTopbar from "../../components/ScreenTopbar";
import ToastStack from "../../components/ToastStack";
import XAFAmount from "../../components/XAFAmount";
import { useProducts } from "../../hooks/useProducts";
import { useCreateSale } from "../../hooks/useCreateSale";
import { useHeldSales, useHoldSale } from "../../hooks/useHeldSales";
import { useCartStore } from "../../store/cartStore";
import { useToasts } from "../../hooks/useToasts";
import { useBarcodeInput } from "../../hooks/useBarcodeInput";
import ProductGrid from "./ProductGrid";
import Cart from "./Cart";
import PaymentPanel from "./PaymentPanel";
import HeldSalesDrawer from "./HeldSalesDrawer";
import BrokeredItemForm from "./BrokeredItemForm";
import ApprovalPrompt from "./ApprovalPrompt";
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
  const addBrokeredItem = useCartStore((s) => s.addBrokeredItem);
  const restoreFrom = useCartStore((s) => s.restoreFrom);
  const subtotal = items.reduce((sum, i) => sum + i.lineTotal, 0);

  const [search, setSearch] = useState("");
  const [category, setCategory] = useState(null);
  const [view, setView] = useState("grid");
  const [showHeldDrawer, setShowHeldDrawer] = useState(false);
  const [paymentMethod, setPaymentMethod] = useState(null);
  const [momoReference, setMomoReference] = useState("");
  const [momoConfirmed, setMomoConfirmed] = useState(false);
  // Sale-confirmation failures now go through toasts (transient action
  // feedback), not a persistent Banner -- see Banner.jsx/ToastStack.jsx's
  // documented distinction. The isError early-return below (products
  // failed to load at all) is a genuine persistent/blocking state and
  // stays on Banner.
  const { toasts, showToast, dismissToast } = useToasts();

  // Inline confirmation card shown over the right panel -- replaces
  // window.prompt()/window.confirm() so hold/clear match the app's
  // own theme instead of an unstyled OS dialog. `action` is
  // "hold" | "clear" | null; `holdLabel` only used by the hold flow.
  const [action, setAction] = useState(null);
  const [holdLabel, setHoldLabel] = useState("");

  // Scanning is on by default; the topbar toggle lets a cashier turn it
  // off if a misbehaving scanner is interfering.
  const [scanEnabled, setScanEnabled] = useState(true);

  // The out-of-stock product a cashier tapped to sell as sourced
  // (Phase 2 §7B.1); null when the brokered form is closed.
  const [brokeredProduct, setBrokeredProduct] = useState(null);

  // True when the sale is waiting on a manager's price-variance approval
  // (Phase 2 §3.2) — shows the ApprovalPrompt over the right panel.
  const [needsApproval, setNeedsApproval] = useState(false);

  const productsById = useMemo(() => new Map((products ?? []).map((p) => [p.id, p])), [products]);

  // Barcode -> product lookup, client-side (same "fetch all, resolve
  // locally" convention as the rest of POS). Only products that actually
  // carry a barcode are indexed.
  const productsByBarcode = useMemo(() => {
    const map = new Map();
    for (const p of products ?? []) {
      if (p.barcode) map.set(p.barcode, p);
    }
    return map;
  }, [products]);

  function handleScan(code) {
    const product = productsByBarcode.get(code);
    if (!product) {
      showToast("error", `No product found for barcode ${code}.`);
      return;
    }
    if (!product.is_active) {
      showToast("error", `${product.name} is deactivated and can't be sold.`);
      return;
    }
    if (product.stock_level <= 0) {
      showToast("error", `${product.name} is out of stock.`);
      return;
    }
    // Respect the same stock ceiling addItem enforces: warn if the scan
    // would exceed known stock rather than silently no-op'ing.
    const inCart = items.find((i) => i.productId === product.id)?.quantity ?? 0;
    if (inCart + 1 > product.stock_level) {
      showToast("error", `Only ${product.stock_level} of ${product.name} in stock.`);
      return;
    }
    addItem(product);
    showToast("success", `Added ${product.name}.`);
  }

  // Suspend scanning while a modal/confirmation is up, so a stray scan
  // can't fire behind the held-sales drawer or a hold/clear confirm.
  useBarcodeInput({
    onScan: handleScan,
    enabled:
      scanEnabled && !showHeldDrawer && action === null && brokeredProduct === null && !needsApproval,
  });

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

  function saleItemPayload(i) {
    // actual_price is sent for every line (equals catalogue when not
    // negotiated) so the server always has it; brokered lines add their
    // external-source fields.
    const base = { product: i.productId, quantity: i.quantity, actual_price: i.actualPrice };
    return i.isBrokered
      ? { ...base, is_brokered: true, external_cost: i.externalCost, source_note: i.sourceNote }
      : base;
  }

  async function submitSale(approvalToken) {
    const sale = await createSaleMutation.mutateAsync({
      payment_method: paymentMethod,
      ...(isMomo ? { momo_reference: momoReference.trim(), momo_confirmed: momoConfirmed } : {}),
      ...(approvalToken ? { approval_token: approvalToken } : {}),
      items: items.map(saleItemPayload),
    });
    clear();
    resetPaymentState();
    navigate(`/receipt/${sale.id}`);
  }

  async function handleConfirmSale(approvalToken = null) {
    try {
      await submitSale(approvalToken);
    } catch (err) {
      // The server is the authority on whether a negotiated price needs
      // approval — if it asks for a token, open the manager prompt and
      // retry once approved.
      if (err.response?.data?.approval_token && !approvalToken) {
        setNeedsApproval(true);
        return;
      }
      const detail =
        err.response?.data?.items?.[0] ||
        err.response?.data?.approval_token ||
        err.response?.data?.detail ||
        "Could not complete the sale. Check stock and try again.";
      showToast("error", detail);
    }
  }

  async function confirmHoldSale() {
    await holdSaleMutation.mutateAsync({
      label: holdLabel,
      cartData: {
        items: items.map((i) =>
          i.isBrokered
            ? {
                product: i.productId,
                quantity: i.quantity,
                is_brokered: true,
                external_cost: i.externalCost,
                source_note: i.sourceNote,
              }
            : { product: i.productId, quantity: i.quantity },
        ),
      },
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
          <Banner type="error">Couldn&apos;t load products. Check your connection.</Banner>
        </div>
      </div>
    );
  }

  return (
    <div className="pos-page">
      <div className="pos-screen">
        <ScreenTopbar
          title="Bledger"
          badge="Point of sale"
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
                <button
                  type="button"
                  className={`pos-icon-btn${scanEnabled ? " sel" : ""}`}
                  onClick={() => setScanEnabled((v) => !v)}
                  title={
                    scanEnabled
                      ? "Barcode scanning is on — scan any item. Click to turn off."
                      : "Barcode scanning is off. Click to turn on."
                  }
                >
                  ⌗ {scanEnabled ? "scan on" : "scan off"}
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
              <ProductGrid
                products={visibleProducts}
                onSelect={addItem}
                onBrokered={setBrokeredProduct}
                view={view}
              />
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
                onClick={() => handleConfirmSale()}
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
              <InlineConfirm
                title="Hold this sale"
                input={{
                  value: holdLabel,
                  onChange: (e) => setHoldLabel(e.target.value),
                  placeholder: "Label (optional)",
                }}
                onCancel={closeAction}
                onConfirm={confirmHoldSale}
                confirmLabel="Hold sale"
                confirmPendingLabel="Holding…"
                isPending={holdSaleMutation.isPending}
              />
            )}

            {action === "clear" && (
              <InlineConfirm
                title="Clear the current sale?"
                subtitle="This can't be undone."
                onCancel={closeAction}
                onConfirm={confirmClearCart}
                confirmLabel="Clear cart"
                danger
              />
            )}

            {/* Sell-as-sourced form for a tapped out-of-stock product
                (§7B.1). Confined to the right panel like the confirms
                above. On add, the brokered line joins the cart. */}
            {brokeredProduct && (
              <BrokeredItemForm
                product={brokeredProduct}
                onCancel={() => setBrokeredProduct(null)}
                onConfirm={({ quantity, externalCost, sourceNote }) => {
                  addBrokeredItem(brokeredProduct, { quantity, externalCost, sourceNote });
                  setBrokeredProduct(null);
                }}
              />
            )}

            {/* Manager PIN approval for a negotiated price beyond bounds
                (§3.2). On approval, retry the sale with the token. */}
            {needsApproval && (
              <ApprovalPrompt
                purpose="price_variance"
                title="Price approval needed"
                subtitle="A line is priced beyond the allowed range. A manager must approve."
                onCancel={() => setNeedsApproval(false)}
                onApproved={(token) => {
                  setNeedsApproval(false);
                  handleConfirmSale(token);
                }}
              />
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

      <ToastStack toasts={toasts} onDismiss={dismissToast} />
    </div>
  );
}
