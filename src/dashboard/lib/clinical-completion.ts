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
  /**
   * Đợt 3 (27/09/2026): còn chữ chưa lưu thì nút Hoàn tất KHÔNG bắt người dùng
   * đợi rồi bấm lại — nó gọi hàm này để lưu nốt, true = đã lưu hết, bấm tiếp.
   * Chỉ có ở `UNSAVED_CHANGES` của màn tự lưu (`lib/use-tu-luu`).
   */
  luuNot?: () => Promise<boolean>;
}

const CONG_MO: ClinicalCompletionGate = { ok: true, code: null, message: null };

/**
 * Cổng Hoàn tất từ trạng thái tự lưu của một màn. Còn chữ chưa lưu / đang lưu
 * / lưu lỗi → UNSAVED_CHANGES kèm `luuNot` để nút tự lưu nốt.
 */
export function congTuLuu(
  tt: { dang_luu: boolean; chua_luu: boolean; loi: string | null },
  luuNot: () => Promise<boolean>,
  ten = "Phiếu",
): ClinicalCompletionGate {
  if (!tt.dang_luu && !tt.chua_luu && !tt.loi) return CONG_MO;
  return {
    ok: false,
    code: "UNSAVED_CHANGES",
    message: tt.loi ? `${ten} chưa lưu được: ${tt.loi}` : `${ten} còn nội dung chưa lưu.`,
    luuNot,
  };
}

/**
 * Gộp cổng của HAI phần cùng một màn (ô tư vấn + mục B ở Bàn tư vấn). Phần
 * nào chưa sẵn sàng mà không lưu nốt được (đang tải…) thì thắng; hai phần cùng
 * còn chữ chưa lưu thì lưu nốt cả hai.
 */
export function gopCong(
  a: ClinicalCompletionGate | null,
  b: ClinicalCompletionGate | null,
): ClinicalCompletionGate | null {
  if (!a || !b) return a ?? b;
  if (a.ok && b.ok) return CONG_MO;
  if (a.ok) return b;
  if (b.ok) return a;
  if (!a.luuNot) return a;
  if (!b.luuNot) return b;
  const la = a.luuNot;
  const lb = b.luuNot;
  return {
    ok: false,
    code: "UNSAVED_CHANGES",
    message: a.message ?? b.message,
    luuNot: async () => {
      const [x, y] = await Promise.all([la(), lb()]);
      return x && y;
    },
  };
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
      message: "Hồ sơ đang tải hoặc đang lưu. Chờ lưu xong rồi bấm Hoàn tất.",
    };
  }

  if (input.remoteChanged) {
    return {
      ok: false,
      code: "REMOTE_CHANGED",
      message:
        "Hồ sơ vừa được người khác cập nhật. Tải và đối chiếu bản mới trước khi Hoàn tất.",
    };
  }

  if (input.dirty) {
    return {
      ok: false,
      code: "UNSAVED_CHANGES",
      message: "Bạn còn nội dung chưa lưu. Lưu hồ sơ trước khi Hoàn tất.",
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
