import assert from "node:assert/strict";
import test from "node:test";
import {
  clinicalCompletionGate,
  congTuLuu,
  gopCong,
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

// ---- Đợt 3 (27/09/2026): cổng từ trạng thái tự lưu + gộp hai phần ----
const SACH = { dang_luu: false, chua_luu: false, loi: null };
const luuOk = async () => true;
const luuHong = async () => false;

test("congTuLuu: sạch → mở; còn chữ / đang lưu / lỗi → UNSAVED_CHANGES kèm luuNot", async () => {
  assert.equal(congTuLuu(SACH, luuOk).ok, true);
  const chua = congTuLuu({ ...SACH, chua_luu: true }, luuOk, "Đơn thuốc");
  assert.equal(chua.ok, false);
  assert.equal(chua.code, "UNSAVED_CHANGES");
  assert.match(chua.message ?? "", /Đơn thuốc còn nội dung chưa lưu/);
  assert.equal(await chua.luuNot?.(), true);
  assert.equal(congTuLuu({ ...SACH, dang_luu: true }, luuOk).code, "UNSAVED_CHANGES");
  const loi = congTuLuu({ ...SACH, chua_luu: true, loi: "Mất kết nối" }, luuOk);
  assert.match(loi.message ?? "", /chưa lưu được: Mất kết nối/);
});

test("gopCong: null / mở / chưa sẵn sàng thắng / cả hai chưa lưu thì lưu nốt cả hai", async () => {
  const mo = congTuLuu(SACH, luuOk);
  const chuaA = congTuLuu({ ...SACH, chua_luu: true }, luuOk, "A");
  const chuaB = congTuLuu({ ...SACH, chua_luu: true }, luuHong, "B");
  const dangTai = { ok: false, code: "FORM_NOT_READY" as const, message: "Đang tải…" };
  assert.equal(gopCong(null, null), null);
  assert.equal(gopCong(null, mo), mo);
  assert.equal(gopCong(mo, mo)?.ok, true);
  assert.equal(gopCong(mo, chuaA), chuaA);
  assert.equal(gopCong(chuaA, mo), chuaA);
  assert.equal(gopCong(chuaA, dangTai), dangTai);
  assert.equal(gopCong(dangTai, chuaA), dangTai);
  const ca = gopCong(chuaA, chuaB);
  assert.equal(ca?.code, "UNSAVED_CHANGES");
  assert.equal(await ca?.luuNot?.(), false, "một phần lưu hỏng thì cả cổng không mở");
  assert.equal(await gopCong(chuaA, congTuLuu({ ...SACH, chua_luu: true }, luuOk))?.luuNot?.(), true);
});

test("blocks when remote changed", () => {
  const res = clinicalCompletionGate({
    ...BASE_INPUT,
    remoteChanged: true,
  });
  assert.equal(res.ok, false);
  assert.equal(res.code, "REMOTE_CHANGED");
});
