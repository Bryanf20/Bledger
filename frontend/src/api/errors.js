// DRF's default error shape for serializer.validate() raising
// ValidationError without a field key is { "non_field_errors": [...] }.
// Field-specific errors come back as { "<field>": [...] }. This helper
// normalizes either shape (plus network failures) into one string for
// display, without assuming which shape a given endpoint uses.
export function extractErrorMessage(error, fallback = "Something went wrong. Please try again.") {
  if (!error?.response) {
    return "Can't reach the server. Check your connection and try again.";
  }

  const data = error.response.data;
  if (!data) return fallback;

  if (typeof data === "string") return data;
  if (data.detail) return data.detail;
  if (Array.isArray(data.non_field_errors) && data.non_field_errors.length) {
    return data.non_field_errors[0];
  }

  // Field-specific errors: take the first field's first message.
  const firstKey = Object.keys(data)[0];
  if (firstKey && Array.isArray(data[firstKey]) && data[firstKey].length) {
    return data[firstKey][0];
  }

  return fallback;
}
