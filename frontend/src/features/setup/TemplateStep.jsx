import { useState } from "react";
import { useTemplates } from "../../hooks/useTemplates";

// Matches 07_setup_wizard.html's step 2 markup: a 2x2 template grid
// with one active card, and a preview box listing the products that
// template will load. Templates now come from GET /setup/templates/
// (live counts/previews read from the real fixture files server-side)
// rather than a hardcoded client-side list.
export default function TemplateStep({ defaultTemplateKey, onBack, onContinue }) {
  const { data: templates, isLoading, isError } = useTemplates();

  const [templateKey, setTemplateKey] = useState(defaultTemplateKey ?? undefined);
  const [skipped, setSkipped] = useState(defaultTemplateKey === null);

  // Default to the first template once the list arrives, if nothing's
  // been chosen yet (e.g. first time through this step).
  if (!isLoading && templates?.length && templateKey === undefined && !skipped) {
    setTemplateKey(templates[0].key);
  }

  const selected = templates?.find((t) => t.key === templateKey);

  function selectTemplate(key) {
    setSkipped(false);
    setTemplateKey(key);
  }

  function handleContinue() {
    onContinue(skipped ? null : templateKey);
  }

  if (isLoading) {
    return <div className="wiz-step-sub">Loading product templates…</div>;
  }

  if (isError || !templates?.length) {
    return (
      <div>
        <div className="wiz-error-banner" role="alert">
          Couldn&apos;t load product templates. You can skip this step and add products
          manually after setup.
        </div>
        <div className="wiz-nav">
          <button type="button" className="wiz-btn" onClick={onBack}>
            Back
          </button>
          <button type="button" className="wiz-btn primary" onClick={() => onContinue(null)}>
            Continue without a template
          </button>
        </div>
      </div>
    );
  }

  return (
    <div>
      <div className="wiz-step-title">Start with a product template</div>
      <div className="wiz-step-sub">
        Pick the template closest to your business. You can remove products you don&apos;t
        stock and add your own after setup.
      </div>

      <div className="wiz-template-grid">
        {templates.map((tpl) => (
          <button
            key={tpl.key}
            type="button"
            className={`wiz-tpl-card${!skipped && templateKey === tpl.key ? " active" : ""}`}
            onClick={() => selectTemplate(tpl.key)}
            aria-pressed={!skipped && templateKey === tpl.key}
          >
            <div className="wiz-tpl-icon">{tpl.icon}</div>
            <div className="wiz-tpl-name">{tpl.name}</div>
            <div className="wiz-tpl-desc">{tpl.description}</div>
            <div className="wiz-tpl-count">{tpl.product_count} products pre-loaded</div>
          </button>
        ))}
      </div>

      {skipped ? (
        <div className="wiz-info-banner">
          No template will be loaded. You can add products from Inventory after setup.
        </div>
      ) : (
        selected && (
          <div className="wiz-preview-box">
            <div className="wiz-preview-title">Products that will be loaded ({selected.product_count})</div>
            {selected.preview_products.map((name) => (
              <span key={name} className="wiz-preview-pill">
                {name}
              </span>
            ))}
          </div>
        )
      )}

      <button type="button" className="wiz-skip-template-link" onClick={() => setSkipped((s) => !s)}>
        {skipped ? "Actually, load a template" : "Skip — I'll add products myself"}
      </button>

      <div className="wiz-nav">
        <button type="button" className="wiz-btn" onClick={onBack}>
          Back
        </button>
        <button type="button" className="wiz-btn primary" onClick={handleContinue}>
          Continue
        </button>
      </div>
    </div>
  );
}
