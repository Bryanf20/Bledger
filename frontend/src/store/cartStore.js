import { create } from "zustand";

// Bulk pricing (design doc B.1): applies automatically once cart
// quantity for a product meets its bulk_min_qty. Mirrors
// apps.sales.services.resolve_unit_price() for display only -- the
// server recomputes on POST /sales/ and is the actual source of truth
// for what gets charged.
function unitPriceFor(product, quantity) {
  const bulkEligible =
    product.effective_bulk_price != null &&
    product.bulk_min_qty != null &&
    quantity >= product.bulk_min_qty;
  return {
    unitPrice: bulkEligible ? product.effective_bulk_price : product.effective_retail_price,
    bulkApplied: bulkEligible,
  };
}

function lineFor(product, quantity) {
  const { unitPrice, bulkApplied } = unitPriceFor(product, quantity);
  return {
    productId: product.id,
    name: product.name,
    quantity,
    unitPrice,
    bulkApplied,
    lineTotal: unitPrice * quantity,
    stockLevel: product.stock_level,
  };
}

export const useCartStore = create((set, get) => ({
  items: [],

  addItem: (product) => {
    const existing = get().items.find((i) => i.productId === product.id);
    const nextQty = (existing?.quantity ?? 0) + 1;
    if (nextQty > product.stock_level) return; // never exceed known stock client-side
    const line = lineFor(product, nextQty);
    set((state) => ({
      items: existing
        ? state.items.map((i) => (i.productId === product.id ? line : i))
        : [...state.items, line],
    }));
  },

  setQuantity: (productId, quantity, product) => {
    if (quantity <= 0) {
      set((state) => ({ items: state.items.filter((i) => i.productId !== productId) }));
      return;
    }
    if (quantity > product.stock_level) return;
    set((state) => ({
      items: state.items.map((i) => (i.productId === productId ? lineFor(product, quantity) : i)),
    }));
  },

  removeItem: (productId) =>
    set((state) => ({ items: state.items.filter((i) => i.productId !== productId) })),

  clear: () => set({ items: [] }),

  // Rebuilds cart lines from a restored held sale's cart_data
  // ({ items: [{ product, quantity }] }) against the currently fetched
  // product list, so prices/names/stock reflect the live catalogue
  // rather than whatever was true when the sale was held.
  restoreFrom: (cartData, products) => {
    const byId = new Map(products.map((p) => [p.id, p]));
    const items = (cartData?.items ?? [])
      .map(({ product: productId, quantity }) => {
        const product = byId.get(productId);
        return product ? lineFor(product, quantity) : null;
      })
      .filter(Boolean);
    set({ items });
  },

  subtotal: () => get().items.reduce((sum, i) => sum + i.lineTotal, 0),
}));
