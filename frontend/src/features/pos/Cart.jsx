import { useCartStore } from "../../store/cartStore";

export default function Cart({ productsById }) {
  const items = useCartStore((s) => s.items);
  const setQuantity = useCartStore((s) => s.setQuantity);
  const removeItem = useCartStore((s) => s.removeItem);

  return (
    <div>
      <div className="pos-cart-header">
        <span>🛒 Current sale</span>
        <span className="pos-cart-count">
          {items.length} item{items.length === 1 ? "" : "s"}
        </span>
      </div>

      {items.length === 0 ? (
        <div className="pos-empty-state">Cart is empty — tap a product to add it.</div>
      ) : (
        items.map((item) => {
          const product = productsById.get(item.productId);
          return (
            <div className="pos-cart-row" key={item.productId}>
              <div className="pos-cart-name">
                {item.name}
                {item.bulkApplied && <span className="pos-prod-bulk"> · bulk</span>}
                {item.isBrokered && <span className="pos-brokered-tag"> · sourced</span>}
              </div>
              <div className="pos-qty-ctrl">
                <button
                  type="button"
                  className="pos-qty-btn"
                  onClick={() => setQuantity(item.productId, item.quantity - 1, product)}
                >
                  −
                </button>
                <div className="pos-qty-num">{item.quantity}</div>
                <button
                  type="button"
                  className="pos-qty-btn"
                  onClick={() => setQuantity(item.productId, item.quantity + 1, product)}
                  disabled={!item.isBrokered && item.quantity >= item.stockLevel}
                >
                  +
                </button>
              </div>
              <div className="pos-cart-price">
                {new Intl.NumberFormat("en-US").format(item.lineTotal)} XAF
              </div>
              <button
                type="button"
                className="pos-qty-btn"
                aria-label={`Remove ${item.name}`}
                onClick={() => removeItem(item.productId)}
              >
                ×
              </button>
            </div>
          );
        })
      )}
    </div>
  );
}
