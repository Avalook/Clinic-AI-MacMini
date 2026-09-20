import assert from "node:assert/strict";
import test from "node:test";
import {
  clinicalCompletionGate,
  type ClinicalCompletionInput,
} from "./clinical-completion.ts";

const BASE_INPUT: ClinicalCompletionInput = {
  mode: "TERMINAL",
  hasData: true,
  loading: false,
  saving: false,
  remoteChanged: false,
  dirty: false,
  hasPrescriptionDraft: false,
  diagnosis: "Viêm họng cấp",
  advice: "Uống nhiều nước ấm",
};

test("handoff blocks unsaved typing", () => {
  const res = clinicalCompletionGate({
    ...BASE_INPUT,
    mode: "HANDOFF",
    dirty: true,
  });
  assert.equal(res.ok, false);
  assert.equal(res.code, "UNSAVED_CHANGES");
  assert.match(res.message ?? "", /chưa lưu/);
});

test("handoff does not require final diagnosis", () => {
  const res = clinicalCompletionGate({
    ...BASE_INPUT,
    mode: "HANDOFF",
    dirty: false,
    diagnosis: "",
    advice: "",
    hasPrescriptionDraft: true,
  });
  assert.equal(res.ok, true);
  assert.equal(res.code, null);
  assert.equal(res.message, null);
});

test("terminal blocks pending prescription draft", () => {
  const res = clinicalCompletionGate({
    ...BASE_INPUT,
    mode: "TERMINAL",
    hasPrescriptionDraft: true,
  });
  assert.equal(res.ok, false);
  assert.equal(res.code, "PRESCRIPTION_DRAFT_PENDING");
  assert.match(res.message ?? "", /thư ký nhập chờ bác sĩ duyệt/);
});

test("terminal allows clean saved chart without diagnosis or advice when not enforced", () => {
  const res = clinicalCompletionGate({
    ...BASE_INPUT,
    mode: "TERMINAL",
    diagnosis: "",
    advice: "",
  });
  assert.equal(res.ok, true);
  assert.equal(res.code, null);
  assert.equal(res.message, null);
});

test("terminal allows clean saved chart", () => {
  const res = clinicalCompletionGate({
    ...BASE_INPUT,
    mode: "TERMINAL",
  });
  assert.equal(res.ok, true);
  assert.equal(res.code, null);
  assert.equal(res.message, null);
});

test("blocks when loading, saving, or no data", () => {
  assert.equal(
    clinicalCompletionGate({ ...BASE_INPUT, loading: true }).code,
    "FORM_NOT_READY",
  );
  assert.equal(
    clinicalCompletionGate({ ...BASE_INPUT, saving: true }).code,
    "FORM_NOT_READY",
  );
  assert.equal(
    clinicalCompletionGate({ ...BASE_INPUT, hasData: false }).code,
    "FORM_NOT_READY",
  );
});

test("blocks when remote changed", () => {
  const res = clinicalCompletionGate({
    ...BASE_INPUT,
    remoteChanged: true,
  });
  assert.equal(res.ok, false);
  assert.equal(res.code, "REMOTE_CHANGED");
});
