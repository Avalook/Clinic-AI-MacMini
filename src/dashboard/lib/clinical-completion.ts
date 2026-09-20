export type ClinicalCompletionMode = "HANDOFF" | "TERMINAL";

export type ClinicalCompletionCode =
  | "FORM_NOT_READY"
  | "REMOTE_CHANGED"
  | "UNSAVED_CHANGES"
  | "PRESCRIPTION_DRAFT_PENDING"
  | "DIAGNOSIS_REQUIRED"
  | "ADVICE_REQUIRED";

export interface ClinicalCompletionGate {
  ok: boolean;
  code: ClinicalCompletionCode | null;
  message: string | null;
}

export interface ClinicalCompletionInput {
  mode: ClinicalCompletionMode;
  hasData: boolean;
  loading: boolean;
  saving: boolean;
  remoteChanged: boolean;
  dirty: boolean;
  hasPrescriptionDraft: boolean;
  diagnosis: string;
  advice: string;
}

export function clinicalCompletionGate(
  input: ClinicalCompletionInput,
): ClinicalCompletionGate {
  if (!input.hasData || input.loading || input.saving) {
    return {
      ok: false,
      code: "FORM_NOT_READY",
      message: "Hồ sơ đang tải hoặc đang lưu. Chờ hoàn tất rồi bấm Khám xong.",
    };
  }

  if (input.remoteChanged) {
    return {
      ok: false,
      code: "REMOTE_CHANGED",
      message:
        "Hồ sơ vừa được người khác cập nhật. Tải và đối chiếu bản mới trước khi Khám xong.",
    };
  }

  if (input.dirty) {
    return {
      ok: false,
      code: "UNSAVED_CHANGES",
      message: "Bạn còn nội dung chưa lưu. Lưu hồ sơ trước khi Khám xong.",
    };
  }

  // Bàn giao khách sang phòng dịch vụ chưa phải kết thúc lâm sàng.
  if (input.mode === "HANDOFF") {
    return { ok: true, code: null, message: null };
  }

  if (input.hasPrescriptionDraft) {
    return {
      ok: false,
      code: "PRESCRIPTION_DRAFT_PENDING",
      message:
        "Còn đơn thuốc thư ký nhập chờ bác sĩ duyệt; chưa thể kết thúc lượt khám.",
    };
  }

  // Ghi chú: DIAGNOSIS_REQUIRED / ADVICE_REQUIRED tạm thời chưa kích hoạt làm hard gate bắt buộc
  // theo yêu cầu: nguồn chưa chốt loi_dan/chan_doan là field bắt buộc khi terminal.
  // Giữ lại type và helper nếu cần kích hoạt sau.

  return { ok: true, code: null, message: null };
}
