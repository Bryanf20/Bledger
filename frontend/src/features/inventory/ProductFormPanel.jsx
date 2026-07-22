import { useState } from "react";
import { useForm } from "react-hook-form";
import { extractErrorMessage } from "../../api/errors";
import {
  useCreateCategory,
  useCreateProduct,
  useDeactivateProduct,
  useReactivateProduct,
  useUpdateProduct,
} from "../../hooks/useInventory";
import "./InventoryScreen.css";

export default function ProductFormPanel({ mode, product, categories, onClose, onSuccess, onError }) {
  const isEdit = mode === "edit";
  const createProductMutation = useCreateProduct();
  const updateProductMutation = useUpdateProduct();
  const createCategoryMutation = useCreateCategory();
  const deactivateMutation = useDeactivateProduct();
  const reactivateMutation = useReactivateProduct();

  const [addingCategory, setAddingCategory] = useState(false);
  const [newCategoryName, setNewCategoryName] = useState("");
  const [categoryError, setCategoryError] = useState(null);
  const [confirmingDeactivate, setConfirmingDeactivate] = useState(false);

  const {
    register,
    handleSubmit,
    watch,
    setValue,
    formState: { errors, isSubmitting },
  } = useForm({
    defaultValues: {
      name: product?.name ?? "",
      description: product?.description ?? "",
      category: product?.category ?? "",
      unit: product?.unit ?? "unit",
      retail_price: product?.retail_price ?? "",
      barcode: product?.barcode ?? "",
      low_stock_threshold: product?.low_stock_threshold ?? 5,
      has_bulk: Boolean(product?.bulk_price && product?.bulk_min_qty),
      bulk_price: product?.bulk_price ?? "",
      bulk_min_qty: product?.bulk_min_qty ?? "",
    },
  });

  const hasBulk = watch("has_bulk");

  async function handleCreateCategory() {
    const name = newCategoryName.trim();
    if (!name) return;
    setCategoryError(null);
    try {
      const category = await createCategoryMutation.mutateAsync({ name });
      setValue("category", category.id);
      setAddingCategory(false);
      setNewCategoryName("");
    } catch (err) {
      setCategoryError(extractErrorMessage(err, "Couldn't create that category."));
    }
  }

  async function onSubmit(values) {
    const payload = {
      name: values.name.trim(),
      description: values.description.trim(),
      category: values.category,
      unit: values.unit.trim() || "unit",
      retail_price: Number(values.retail_price),
      barcode: values.barcode.trim(),
      low_stock_threshold: Number(values.low_stock_threshold),
      bulk_price: values.has_bulk ? Number(values.bulk_price) : null,
      bulk_min_qty: values.has_bulk ? Number(values.bulk_min_qty) : null,
    };

    try {
      if (isEdit) {
        await updateProductMutation.mutateAsync({ id: product.id, payload });
        onSuccess(`${payload.name} updated.`);
      } else {
        await createProductMutation.mutateAsync(payload);
        onSuccess(`${payload.name} added. It starts with 0 stock — use "Adjust stock" to add inventory.`);
      }
    } catch (err) {
      onError(err, isEdit ? "Couldn't save changes." : "Couldn't add that product.");
    }
  }

  async function handleDeactivate() {
    try {
      await deactivateMutation.mutateAsync(product.id);
      onSuccess(`${product.name} deactivated.`);
    } catch (err) {
      onError(err, "Couldn't deactivate that product.");
    }
  }

  async function handleReactivate() {
    try {
      await reactivateMutation.mutateAsync(product.id);
      onSuccess(`${product.name} reactivated.`);
    } catch (err) {
      onError(err, "Couldn't reactivate that product.");
    }
  }

  return (
    <div className="inv-drawer-backdrop" onClick={onClose}>
      <div className="inv-drawer" onClick={(e) => e.stopPropagation()}>
        <div className="inv-drawer-header">
          <span>{isEdit ? "Edit product" : "Add product"}</span>
          <button type="button" className="inv-icon-btn" onClick={onClose}>Close</button>
        </div>

        <form className="inv-form" onSubmit={handleSubmit(onSubmit)}>
          <div className="inv-form-scroll">
            <div>
              <label className="inv-field-label" htmlFor="name">Product name</label>
              <input id="name" className="inv-field-input" {...register("name", { required: "Name is required." })} />
              {errors.name && <div className="inv-field-error">{errors.name.message}</div>}
            </div>

            <div>
              <label className="inv-field-label" htmlFor="description">
                Description <span className="inv-field-hint">(optional)</span>
              </label>
              <textarea
                id="description"
                className="inv-field-input inv-field-textarea"
                rows={3}
                placeholder="Notes, specs, or anything worth remembering about this product…"
                {...register("description")}
              />
            </div>

            <div>
              <label className="inv-field-label" htmlFor="category">Category</label>
              {!addingCategory ? (
                <div className="inv-cat-select-row">
                  <select id="category" className="inv-field-input" {...register("category", { required: "Choose a category." })}>
                    <option value="">Select a category…</option>
                    {categories.map((c) => (
                      <option key={c.id} value={c.id}>{c.name}</option>
                    ))}
                  </select>
                  <button type="button" className="inv-row-btn" onClick={() => setAddingCategory(true)}>+ New</button>
                </div>
              ) : (
                <div className="inv-cat-select-row">
                  <input
                    className="inv-field-input"
                    placeholder="New category name"
                    value={newCategoryName}
                    onChange={(e) => setNewCategoryName(e.target.value)}
                    autoFocus
                  />
                  <button type="button" className="inv-row-btn" onClick={handleCreateCategory} disabled={createCategoryMutation.isPending || !newCategoryName.trim()}>
                    {createCategoryMutation.isPending ? "Adding…" : "Add"}
                  </button>
                  <button type="button" className="inv-row-btn" onClick={() => setAddingCategory(false)}>Cancel</button>
                </div>
              )}
              {categoryError && <div className="inv-field-error">{categoryError}</div>}
              {errors.category && <div className="inv-field-error">{errors.category.message}</div>}
            </div>

            <div>
              <label className="inv-field-label" htmlFor="unit">Unit</label>
              <input id="unit" className="inv-field-input" placeholder="piece, kg, pair…" {...register("unit")} />
            </div>

            <div>
              <label className="inv-field-label" htmlFor="retail_price">Retail price (XAF)</label>
              <input
                id="retail_price"
                type="number"
                min="0"
                className="inv-field-input"
                {...register("retail_price", { required: "Retail price is required.", min: { value: 0, message: "Must be 0 or more." } })}
              />
              {errors.retail_price && <div className="inv-field-error">{errors.retail_price.message}</div>}
            </div>

            <label className="inv-checkbox-row">
              <input type="checkbox" {...register("has_bulk")} />
              This product has a bulk price
            </label>

            {hasBulk && (
              <div className="inv-bulk-row">
                <div>
                  <label className="inv-field-label" htmlFor="bulk_price">Bulk price (XAF)</label>
                  <input id="bulk_price" type="number" min="0" className="inv-field-input" {...register("bulk_price", { required: "Required when bulk pricing is on." })} />
                </div>
                <div>
                  <label className="inv-field-label" htmlFor="bulk_min_qty">Min qty for bulk</label>
                  <input
                    id="bulk_min_qty"
                    type="number"
                    min="2"
                    className="inv-field-input"
                    {...register("bulk_min_qty", { required: "Required when bulk pricing is on.", min: { value: 2, message: "Must be at least 2." } })}
                  />
                </div>
                {(errors.bulk_price || errors.bulk_min_qty) && (
                  <div className="inv-field-error">{errors.bulk_price?.message || errors.bulk_min_qty?.message}</div>
                )}
              </div>
            )}

            <div>
              <label className="inv-field-label" htmlFor="barcode">
                Barcode <span className="inv-field-hint">(optional — scan or type)</span>
              </label>
              <input
                id="barcode"
                className="inv-field-input"
                placeholder="Leave blank for goods with no barcode"
                autoComplete="off"
                {...register("barcode")}
              />
              {errors.barcode && <div className="inv-field-error">{errors.barcode.message}</div>}
            </div>

            <div>
              <label className="inv-field-label" htmlFor="low_stock_threshold">Low stock alert threshold</label>
              <input id="low_stock_threshold" type="number" min="0" className="inv-field-input" {...register("low_stock_threshold")} />
            </div>

            {!isEdit && (
              <div className="inv-info-note">
                New products start with 0 stock. Use &quot;Adjust stock&quot; afterward to record initial inventory.
              </div>
            )}

            {/* Deactivate control lives here per the UI Design Reference
                ("Product edit panel: ... and a Deactivate control (not
                delete)"), not as a row/card action. */}
            {isEdit && (
              <div className="inv-deactivate-block">
                {product.is_active ? (
                  !confirmingDeactivate ? (
                    <button type="button" className="inv-row-btn danger" onClick={() => setConfirmingDeactivate(true)}>
                      Deactivate product
                    </button>
                  ) : (
                    <div className="inv-deactivate-confirm">
                      <span>Deactivate this product? It stays on past receipts and reports.</span>
                      <div className="inv-deactivate-confirm-actions">
                        <button type="button" className="inv-row-btn" onClick={() => setConfirmingDeactivate(false)}>Cancel</button>
                        <button type="button" className="inv-row-btn danger" onClick={handleDeactivate} disabled={deactivateMutation.isPending}>
                          {deactivateMutation.isPending ? "Deactivating…" : "Yes, deactivate"}
                        </button>
                      </div>
                    </div>
                  )
                ) : (
                  <button type="button" className="inv-row-btn" onClick={handleReactivate} disabled={reactivateMutation.isPending}>
                    {reactivateMutation.isPending ? "Reactivating…" : "Reactivate product"}
                  </button>
                )}
              </div>
            )}
          </div>

          <div className="inv-drawer-footer">
            <button type="button" className="inv-row-btn" onClick={onClose}>Cancel</button>
            <button type="submit" className="inv-confirm-btn" disabled={isSubmitting}>
              {isSubmitting ? "Saving…" : isEdit ? "Save changes" : "Add product"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
