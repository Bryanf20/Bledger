import apiClient from "./client";

// Verified against backend/apps/auth_users/{views,serializers}.py and
// backend/apps/inventory/{serializers,services}.py in project
// knowledge:
//
//   GET  /setup/templates/     -> [{ key, name, description, icon,
//     category_count, product_count, preview_products }]  (AllowAny --
//     new endpoint added this session, see ProductTemplateListView.
//     Replaces the hardcoded templateOptions.js this same session
//     originally shipped with; that file should be deleted.)
//   POST /setup/               -> { token, user }  (SetupSerializer --
//     combines wizard step 1 "Business" and step 3 "Account" fields
//     into ONE call: business_name, branch_name, address, phone,
//     receipt_footer, owner_name, username, password, pin. 409 if a
//     Branch with setup_complete=True already exists.)
//   POST /setup/load-template/ -> { template, categories_created,
//     products_created }  (owner-only, IsOwner -- but the token from
//     submitSetup() below is already stored and attached by the
//     request interceptor by the time this is called, so no extra
//     auth wiring is needed here.)

export async function fetchTemplates() {
  const { data } = await apiClient.get("/setup/templates/");
  return data; // ProductTemplate[]
}

export async function submitSetup(payload) {
  const { data } = await apiClient.post("/setup/", payload);
  return data; // { token, user }
}

export async function loadTemplate(templateKey) {
  const { data } = await apiClient.post("/setup/load-template/", {
    template_key: templateKey,
  });
  return data; // { template, categories_created, products_created }
}
