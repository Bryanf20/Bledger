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

// Whether a negotiated price falls outside the product's allowed band
// (Phase 2 §3.2). Mirrors apps.sales.services.price_needs_approval,
// including its integer (floor-division) math — but this is only a UX
// hint; the server is the actual gate on POST /sales/.
function priceNeedsApproval(catalogue, actual, floorPct, ceilingPct) {
  if (actual < catalogue) {
    const minAllowed = catalogue - Math.floor((catalogue * floorPct) / 100);
    return actual < minAllowed;
  }
  if (actual > catalogue) {
    const maxAllowed = catalogue + Math.floor((catalogue * ceilingPct) / 100);
    return actual > maxAllowed;
  }
  return false;
}

// Builds a line's price-derived fields shared by normal and brokered
// lines: the resolved catalogue price, the (possibly negotiated) actual
// price, the variance, and whether it needs manager approval. lineTotal
// is left to the caller, which knows the quantity.
function priceFields(product, catalogue, actualPrice, priceEdited) {
  const actual = priceEdited && actualPrice != null ? actualPrice : catalogue;
  const floor = product.effective_discount_floor_pct ?? 0;
  const ceiling = product.effective_surplus_ceiling_pct ?? 0;
  return {
    cataloguePrice: catalogue,
    actualPrice: actual,
    unitPrice: actual, // what the line is charged at
    priceEdited: Boolean(priceEdited),
    variance: actual - catalogue,
    needsApproval: priceNeedsApproval(catalogue, actual, floor, ceiling),
  };
}

function lineFor(product, quantity, actualPrice = null, priceEdited = false) {
  const { unitPrice: catalogue, bulkApplied } = unitPriceFor(product, quantity);
  const pf = priceFields(product, catalogue, actualPrice, priceEdited);
  return {
    productId: product.id,
    name: product.name,
    quantity,
    bulkApplied,
    stockLevel: product.stock_level,
    isBrokered: false,
    ...pf,
    lineTotal: pf.actualPrice * quantity,
  };
}

// A brokered line (Phase 2 §7B.1): the item is sourced externally, so it
// carries no stock ceiling. It sells at the catalogue retail price
// (negotiable, like any line) and records the external cost + source
// note, forwarded on the sale POST as is_brokered / external_cost /
// source_note.
function brokeredLineFor(product, quantity, externalCost, sourceNote, actualPrice = null, priceEdited = false) {
  const catalogue = product.effective_retail_price;
  const pf = priceFields(product, catalogue, actualPrice, priceEdited);
  return {
    productId: product.id,
    name: product.name,
    quantity,
    bulkApplied: false,
    stockLevel: product.stock_level,
    isBrokered: true,
    externalCost,
    sourceNote: sourceNote ?? "",
    ...pf,
    lineTotal: pf.actualPrice * quantity,
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

  // Adds (or replaces) a brokered line for a product, bypassing the
  // stock ceiling — the item isn't in inventory.
  addBrokeredItem: (product, { quantity = 1, externalCost, sourceNote } = {}) => {
    const line = brokeredLineFor(product, quantity, externalCost, sourceNote);
    set((state) => {
      const exists = state.items.some((i) => i.productId === product.id);
      return {
        items: exists
          ? state.items.map((i) => (i.productId === product.id ? line : i))
          : [...state.items, line],
      };
    });
  },

  setQuantity: (productId, quantity, product) => {
    if (quantity <= 0) {
      set((state) => ({ items: state.items.filter((i) => i.productId !== productId) }));
      return;
    }
    const existing = get().items.find((i) => i.productId === productId);
    // Preserve any negotiated price across a quantity change.
    const editedPrice = existing?.priceEdited ? existing.actualPrice : null;
    // A brokered line has no stock ceiling; preserve its external cost
    // and source note when its quantity changes.
    if (existing?.isBrokered) {
      set((state) => ({
        items: state.items.map((i) =>
          i.productId === productId
            ? brokeredLineFor(product, quantity, existing.externalCost, existing.sourceNote, editedPrice, existing.priceEdited)
            : i,
        ),
      }));
      return;
    }
    if (quantity > product.stock_level) return;
    set((state) => ({
      items: state.items.map((i) =>
        i.productId === productId ? lineFor(product, quantity, editedPrice, existing?.priceEdited) : i,
      ),
    }));
  },

  // Sets a negotiated unit price on a line (Phase 2 §3.2). Blank/invalid
  // resets it back to the catalogue price.
  setLinePrice: (productId, actualPrice, product) => {
    const existing = get().items.find((i) => i.productId === productId);
    if (!existing) return;
    const edited = actualPrice != null && actualPrice !== "" && Number(actualPrice) >= 0;
    const price = edited ? Number(actualPrice) : null;
    const build = existing.isBrokered
      ? brokeredLineFor(product, existing.quantity, existing.externalCost, existing.sourceNote, price, edited)
      : lineFor(product, existing.quantity, price, edited);
    set((state) => ({
      items: state.items.map((i) => (i.productId === productId ? build : i)),
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
      .map(({ product: productId, quantity, is_brokered, external_cost, source_note }) => {
        const product = byId.get(productId);
        if (!product) return null;
        return is_brokered
          ? brokeredLineFor(product, quantity, external_cost, source_note)
          : lineFor(product, quantity);
      })
      .filter(Boolean);
    set({ items });
  },

  subtotal: () => get().items.reduce((sum, i) => sum + i.lineTotal, 0),
}));
