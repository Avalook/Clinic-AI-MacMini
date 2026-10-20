# Round 16 — dashboard identity and authorization boundary

Snapshot: pinned main `956ba4f236b1c92f1280d2097018c199e90ce8c7`. This slice follows server-derived staff identity, clinic-session capabilities, UI permission helpers, input validators, service-role confinement, and selected BFF callers. Coverage rows and exact SHA-256/Git blob fingerprints are in `round16_dashboard_auth_boundary.coverage.json`.

The full reads confirm a useful boundary: dashboard identity and capabilities are fetched from FastAPI; `clinic_id` in the dashboard session is a filter hint; service-role access is narrowly isolated to server-side Auth administration; the UI permission helper is not treated as an authorization boundary. Patient create/update routes call the shared name and date validators. Existing boundary tests exercise the relevant wiring.

No new finding was promoted. This slice corroborates existing `SEC-006`: the Auth-admin BFF can report success for an unban even if the follow-up GoTrue operation fails after the backend account state changed. This remains the already-recorded partial-success consistency issue; no duplicate was created. The three selected Node boundary suites passed 22/22 in `RUN-068`. Node emitted `MODULE_TYPELESS_PACKAGE_JSON` reparsing warnings for TS modules; tests still passed, and this is not evidence of a runtime product failure.

Limits: this is a targeted dashboard identity/authorization slice, not a full dashboard review. It did not perform HTTP/browser tests, Auth-provider tests, database/RLS tests, production checks, or a complete role × clinic × patient authorization matrix. SEC-006 still needs a failure-injection test for the GoTrue step and a product decision about partial success/retry semantics. Full source audit remains incomplete.
