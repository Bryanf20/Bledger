import { useForm } from "react-hook-form";
import { useCreateSupplier, useUpdateSupplier } from "../../hooks/useSuppliers";

// Same "inline side panel, not a modal" convention the UI Design
// Reference establishes for Inventory's Add/Edit-product and
// Adjust-stock panels (transparent backdrop, click-outside-to-close,
// box-shadow/border-left for separation instead of a dimmed overlay).
// The Suppliers screen's own doc section doesn't specify a style for
// "Add supplier" / the detail header's "Edit action", so this reuses
// that already-established global pattern rather than inventing a
// third one -- flagged here since it's a judgment call, not a doc
// requirement.
export default function SupplierFormPanel({ mode, supplier, onClose, onSuccess, onError }) {
  const isEdit = mode === "edit";
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm({
    defaultValues: isEdit
      ? { name: supplier.name, phone: supplier.phone, area: supplier.area, notes: supplier.notes }
      : { name: "", phone: "", area: "", notes: "" },
  });
  const createSupplier = useCreateSupplier();
  const updateSupplier = useUpdateSupplier();
  const isPending = createSupplier.isPending || updateSupplier.isPending;

  async function onSubmit(values) {
    try {
      if (isEdit) {
        await updateSupplier.mutateAsync({ id: supplier.id, payload: values });
        onSuccess(`${values.name} updated.`);
      } else {
        const created = await createSupplier.mutateAsync(values);
        onSuccess(`${values.name} added.`, created.id);
      }
    } catch (err) {
      onError(err, isEdit ? "Couldn't update that supplier." : "Couldn't add that supplier.");
    }
  }

  return (
    <div className="sup-drawer-backdrop" onClick={onClose}>
      <div className="sup-drawer" onClick={(e) => e.stopPropagation()}>
        <div className="sup-drawer-header">
          <span>{isEdit ? `Edit — ${supplier.name}` : "Add supplier"}</span>
          <button type="button" className="sup-icon-btn" onClick={onClose}>Close</button>
        </div>

        <form className="sup-form" onSubmit={handleSubmit(onSubmit)}>
          <div className="sup-form-scroll">
            <div>
              <label className="sup-field-label" htmlFor="name">Name</label>
              <input id="name" className="sup-field-input" {...register("name", { required: "Required." })} />
              {errors.name && <div className="sup-field-error">{errors.name.message}</div>}
            </div>
            <div>
              <label className="sup-field-label" htmlFor="phone">Phone</label>
              <input id="phone" className="sup-field-input" {...register("phone")} />
            </div>
            <div>
              <label className="sup-field-label" htmlFor="area">Area</label>
              <input id="area" className="sup-field-input" {...register("area")} />
            </div>
            <div>
              <label className="sup-field-label" htmlFor="notes">Notes</label>
              <textarea
                id="notes"
                rows={3}
                className="sup-field-input sup-field-textarea"
                {...register("notes")}
              />
            </div>
          </div>

          <div className="sup-drawer-footer">
            <button type="button" className="sup-row-btn" onClick={onClose}>Cancel</button>
            <button type="submit" className="sup-confirm-btn" disabled={isPending}>
              {isPending ? "Saving…" : isEdit ? "Save changes" : "Add supplier"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
