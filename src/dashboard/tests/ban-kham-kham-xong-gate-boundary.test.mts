import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const read = (path: string): string =>
  readFileSync(new URL(path, import.meta.url), "utf8");

const banKhamSource = read("../app/(dashboard)/ban-kham/BanKham.tsx");
const clinicalRecordFormSource = read(
  "../app/(dashboard)/tasks/ClinicalRecordForm.tsx",
);
const clinicalCompletionSource = read("../lib/clinical-completion.ts");

test("pure clinical completion helper exports expected types and gate logic", () => {
  assert.match(
    clinicalCompletionSource,
    /export type ClinicalCompletionMode = "HANDOFF" \| "TERMINAL"/,
  );
  assert.match(
    clinicalCompletionSource,
    /export function clinicalCompletionGate\(/,
  );
});

test("ClinicalRecordForm accepts completionMode and notifies gate changes to parent", () => {
  assert.match(
    clinicalRecordFormSource,
    /import\s*\{[^}]*clinicalCompletionGate[^}]*\}\s*from\s*["'][^"']*clinical-completion["']/,
  );
  assert.match(
    clinicalRecordFormSource,
    /completionMode\s*=\s*"TERMINAL"/,
  );
  assert.match(
    clinicalRecordFormSource,
    /onCompletionGateChange\?:\s*\(gate:\s*ClinicalCompletionGate\)\s*=>\s*void/,
  );
  assert.match(
    clinicalRecordFormSource,
    /onCompletionGateChange\?\.\(completionGate\)/,
  );
});

test("BanKham determines HANDOFF vs TERMINAL based on active service orders", () => {
  assert.match(
    banKhamSource,
    /const conChiDinhDangLam\s*=\s*luot\?\.chi_dinh\.some\([\s\S]*?\["authorized",\s*"assigned",\s*"in_progress"\]\.includes\(c\.trang_thai\)/,
  );
  assert.match(
    banKhamSource,
    /const completionMode:\s*ClinicalCompletionMode\s*=\s*conChiDinhDangLam\s*\?\s*"HANDOFF"\s*:\s*"TERMINAL"/,
  );
});

test("BanKham resets completionGate when current queue item changes", () => {
  assert.match(
    banKhamSource,
    /const \[completionGate,\s*setCompletionGate\]\s*=\s*useState<ClinicalCompletionGate \| null>\(null\)/,
  );
  assert.match(
    banKhamSource,
    /useEffect\(\(\)\s*=>\s*\{[\s\S]*?setCompletionGate\(null\);[\s\S]*?\}, \[[^\]]*dong\?\.id[^\]]*\]\)/,
  );
});

test("BanKham enforces gate check and confirm BEFORE calling guiThaoTac('kham-xong')", () => {
  const bamFnIdx = banKhamSource.indexOf("const bam = async");
  assert.ok(bamFnIdx > 0, "bam handler must exist");
  const bamBody = banKhamSource.slice(bamFnIdx, bamFnIdx + 2000);

  const gateCheckIdx = bamBody.indexOf("if (!completionGate)");
  const gateOkCheckIdx = bamBody.indexOf("if (!completionGate.ok)");
  const confirmIdx = bamBody.indexOf("window.confirm(");
  const guiThaoTacIdx = bamBody.indexOf("guiThaoTac(");

  assert.ok(gateCheckIdx > 0, "must check completionGate existence");
  assert.ok(gateOkCheckIdx > gateCheckIdx, "must check completionGate.ok after existence");
  assert.ok(confirmIdx > gateOkCheckIdx, "must confirm after completionGate passes");
  assert.ok(guiThaoTacIdx > confirmIdx, "guiThaoTac must only be called after all gates and confirmation pass");

  // Verify return on failed gate prevents calling guiThaoTac
  const beforeConfirm = bamBody.slice(gateCheckIdx, confirmIdx);
  assert.match(
    beforeConfirm,
    /setLoi\(\{[^}]*cau:\s*completionGate\.message/,
    "must display gate message when gate.ok is false",
  );
});

test("BanKham blocks non-doctor from terminal completion with explicit waiting message", () => {
  assert.match(
    banKhamSource,
    /if\s*\(\s*completionMode\s*===\s*"TERMINAL"\s*&&\s*!laBacSi\s*\)\s*\{[\s\S]*?cau:\s*"Chờ bác sĩ hoàn tất lượt khám\."[\s\S]*?return;/,
  );
  assert.match(
    banKhamSource,
    /!laBacSi\s*&&\s*completionMode\s*===\s*"TERMINAL"[\s\S]*?Chờ bác sĩ hoàn tất lượt khám\./,
  );
});
