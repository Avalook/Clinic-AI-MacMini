/** Marker retained in audit JSON when a sensitive value has been removed. */
const REDACTED = "[REDACTED]";

/**
 * Sensitive keys accepted by current dashboard routes and common aliases used by
 * integrations. Comparisons ignore case, underscores and punctuation so a new
 * caller cannot accidentally bypass redaction with a spelling variant.
 */
const SENSITIVE_KEYS = new Set([
  "accesstoken",
  "address",
  "authorization",
  "dateofbirth",
  "dob",
  "email",
  "ethnicity",
  "fullname",
  "gender",
  "guardianname",
  "guardianphone",
  "homeaddress",
  "identitynumber",
  "mobile",
  "nationalid",
  "nationalidnumber",
  "nationality",
  "note",
  "notes",
  "occupation",
  "passportnumber",
  "patientname",
  "patientobjection",
  "password",
  "phone",
  "phonenumber",
  "phoneprimary",
  "phonesecondary",
  "reason",
  "refreshtoken",
  "secret",
  "telephone",
  "token",
]);

function normalizedKey(key: string): string {
  return key.toLowerCase().replace(/[^a-z0-9]/g, "");
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

/**
 * Return an immutable, recursively redacted copy suitable for event_log audit
 * payloads and metadata. Dates are retained as values; patient identifiers and
 * operational state remain available for investigation without duplicating PII.
 */
export function redactAuditData<T>(value: T): T {
  if (Array.isArray(value)) {
    return value.map((item) => redactAuditData(item)) as T;
  }

  if (!isRecord(value) || value instanceof Date) {
    return value;
  }

  return Object.fromEntries(
    Object.entries(value).map(([key, item]) => [
      key,
      SENSITIVE_KEYS.has(normalizedKey(key)) ? REDACTED : redactAuditData(item),
    ]),
  ) as T;
}
