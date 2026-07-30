import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const registrySource = readFileSync(
  new URL("../lib/form-schemas/index.ts", import.meta.url),
  "utf8",
);
const obstetricsSource = readFileSync(
  new URL("../lib/form-schemas/sk.ts", import.meta.url),
  "utf8",
);

test("an inferred form without a doctor-approved source is quarantined", () => {
  assert.equal(
    /\bNK:\s*nkSchema\b/.test(registrySource),
    false,
    "NK was assembled from another service and must stay unavailable until signed off",
  );
});

test("no exposed section advertises itself as pending doctor review", () => {
  assert.equal(
    obstetricsSource.includes(
      'title: "Khám thai (khung tối thiểu) — //TODO-BS-REVIEW"',
    ),
    false,
  );
});
