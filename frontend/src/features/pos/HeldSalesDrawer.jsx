import XAFAmount from "../../components/XAFAmount";
import { useDiscardHeldSale, useHeldSales, useRestoreHeldSale } from "../../hooks/useHeldSales";

export default function HeldSalesDrawer({ productsById, onRestore, onClose }) {
  const { data: heldSales, isLoading } = useHeldSales();
  const restoreMutation = useRestoreHeldSale();
  const discardMutation = useDiscardHeldSale();

  function cartTotal(cartData) {
    return (cartData?.items ?? []).reduce((sum, { product: id, quantity }) => {
      const product = productsById.get(id);
      if (!product) return sum;
      const bulkEligible =
        product.effective_bulk_price != null && product.bulk_min_qty != null && quantity >= product.bulk_min_qty;
      const unitPrice = bulkEligible ? product.effective_bulk_price : product.effective_retail_price;
      return sum + unitPrice * quantity;
    }, 0);
  }

  async function handleRestore(id) {
    const cartData = await restoreMutation.mutateAsync(id);
    onRestore(cartData);
  }

  return (
    <div className="pos-drawer-backdrop" onClick={onClose}>
      <div className="pos-drawer" onClick={(e) => e.stopPropagation()}>
        <div className="pos-cart-header">
          <span>⏸ Held sales</span>
          <button type="button" className="pos-icon-btn" onClick={onClose}>
            Close
          </button>
        </div>

        {isLoading && <div className="pos-empty-state">Loading…</div>}
        {!isLoading && !heldSales?.length && <div className="pos-empty-state">No sales on hold.</div>}

        {heldSales?.map((held) => (
          <div className="pos-cart-row pos-drawer-row" key={held.id}>
            <div className="pos-cart-name">
              {held.label || "Untitled hold"}
              <div className="pos-drawer-row-time">
                {new Date(held.held_at).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })}
              </div>
            </div>
            <div className="pos-cart-price">
              <XAFAmount value={cartTotal(held.cart_data)} />
            </div>
            <div className="pos-drawer-row-actions">
              <button type="button" className="pos-icon-btn" onClick={() => handleRestore(held.id)}>
                Restore
              </button>
              <button type="button" className="pos-icon-btn" onClick={() => discardMutation.mutate(held.id)}>
                Discard
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
