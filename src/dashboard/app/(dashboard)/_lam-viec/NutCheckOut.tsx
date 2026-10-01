"use client";

// NÚT CHECK-OUT DÙNG CHUNG (27/09/2026, đợt 3 — góp ý phòng khám A8: "check
// out của BN hiện đang hiển thị tại bước nào?" + quầy hay quên).
//
// Trước đây check-out CHỈ có ở màn riêng `/reception/checkout`, nên khách đã
// xong mà lễ tân không mở màn ấy thì lượt treo mãi. Nút này gắn ngay chỗ người
// ta đang nhìn khách: tab Đã check-in (Tiếp đón), dòng khách ở Hành trình, và
// sau "Đã nhận đủ" ở quầy thu.
//
// MỘT LỆNH, MÁY CHỦ QUYẾT: cùng `GET/POST /api/reception/checkout` với màn
// check-out (→ `checkout_service.readiness` / `close`). Màn không tự suy "đóng
// được chưa":
//   1. bấm → hỏi máy chủ lượt này còn vướng gì;
//   2. dải xác nhận tại chỗ (`XacNhanTaiCho`, không `window.confirm`) — còn việc
//      dở thì liệt kê đúng danh sách máy chủ trả + ô lý do. Lý do TUỲ CHỌN theo
//      luật máy chủ (24/09/2026): để trống thì máy chủ tự ghi kèm việc còn dở;
//   3. gửi lệnh đóng.
//
// Check-out ≠ Hoàn tất khám: Hoàn tất khám là mốc của bác sĩ (Bàn khám), check-
// out là mốc khách rời phòng khám. Nút này không đụng phiếu khám.
//
// Chỉ hiện khi tài khoản có quyền đóng lượt (`useCheckOutDuoc` — lego 1 Tiếp
// đón khách), không hỏi vai.
//
// CÒN NỢ (01/10/2026): máy chủ trả `no_khi_ve`; còn nợ chưa ghi thì nút
// "Check-out" khoá, khối `KhoanNoKhiVe` cho Thu ngay / Ghi nợ (kèm lý do) —
// máy chủ cũng chặn, khoá ở đây chỉ để khỏi bấm vào câu từ chối.

import { useState } from "react";

import Button, { type ButtonSize, type ButtonVariant } from "@/components/ui/Button";
import XacNhanTaiCho from "@/components/ui/XacNhanTaiCho";
import { loiDocDuoc } from "@/lib/loi-doc-duoc";

import { INPUT } from "../form-ui";
import { useCheckOutDuoc } from "../QuyenContext";
import KhoanNoKhiVe, { coNo, type NoKhiVe } from "./KhoanNoKhiVe";

interface VuongMac {
  type: string;
  message: string;
  /** Vướng cứng — không vượt bằng lý do (còn nợ). */
  chan?: boolean;
}

/** Hình dạng `GET /api/v1/reception/checkout/{visit_id}` (phần màn cần). */
interface SanSang {
  ok?: boolean;
  already_closed?: boolean;
  blockers?: VuongMac[];
  no_khi_ve?: NoKhiVe | null;
}

type Buoc = "nghi" | "dang_hoi" | "hoi" | "dang_gui" | "xong";

export default function NutCheckOut({
  visitId,
  ten,
  onXong,
  size = "sm",
  variant = "secondary",
}: {
  visitId: string;
  /** Tên khách để câu hỏi nói rõ đang cho AI về. */
  ten?: string | null;
  /** Gọi sau khi máy chủ đã đóng lượt (hoặc lượt đã đóng từ trước). */
  onXong?: () => void;
  size?: ButtonSize;
  variant?: ButtonVariant;
}) {
  const duoc = useCheckOutDuoc();
  const [buoc, setBuoc] = useState<Buoc>("nghi");
  const [vuong, setVuong] = useState<VuongMac[]>([]);
  const [no, setNo] = useState<NoKhiVe | null>(null);
  const [lyDo, setLyDo] = useState("");
  const [loi, setLoi] = useState<string | null>(null);
  const [bao, setBao] = useState<string | null>(null);

  if (!duoc) return null;

  const tenKhach = ten?.trim() || "khách này";

  async function hoi() {
    setLoi(null);
    setBuoc("dang_hoi");
    try {
      const r = await fetch(
        `/api/reception/checkout?visit_id=${encodeURIComponent(visitId)}`,
        { cache: "no-store" },
      );
      const d = (await r.json().catch(() => null)) as SanSang | null;
      // `ok:false` = proxy không nhận được câu trả lời (máy chủ im / từ chối).
      if (!r.ok || !d || d.ok === false) {
        setLoi(loiDocDuoc(d, "Không đọc được lượt này còn vướng gì — thử lại."));
        setBuoc("nghi");
        return;
      }
      if (d.already_closed) {
        setBao("Lượt này đã check-out trước đó.");
        setBuoc("xong");
        onXong?.();
        return;
      }
      // Vướng "còn nợ" vẽ ở khối nợ, không lặp trong danh sách việc dở.
      setVuong((d.blockers ?? []).filter((b) => !b.chan));
      setNo(d.no_khi_ve ?? null);
      setLyDo("");
      setBuoc("hoi");
    } catch {
      setLoi("Mất kết nối — chưa check-out.");
      setBuoc("nghi");
    }
  }

  async function gui() {
    setLoi(null);
    setBuoc("dang_gui");
    try {
      const r = await fetch("/api/reception/checkout", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          visit_id: visitId,
          override_reason: lyDo.trim() || null,
          incomplete: false,
          incomplete_reason: null,
        }),
      });
      const d = (await r.json().catch(() => null)) as
        | { ok?: boolean; already_closed?: boolean }
        | null;
      if (!r.ok || !d?.ok) {
        setLoi(loiDocDuoc(d, `Không check-out được (HTTP ${r.status}).`));
        setBuoc("hoi");
        return;
      }
      setBao(
        d.already_closed
          ? "Lượt này đã check-out trước đó."
          : `Đã check-out ${tenKhach}.`,
      );
      setBuoc("xong");
      onXong?.();
    } catch {
      setLoi("Mất kết nối — chưa check-out.");
      setBuoc("hoi");
    }
  }

  if (buoc === "xong") {
    return (
      <p role="status" className="text-meta text-success">
        {bao}
      </p>
    );
  }

  const chanNo = !!no?.chan;
  const cau = chanNo
    ? `${tenKhach} còn nợ — thu ngay hoặc ghi nợ rồi mới check-out được.`
    : vuong.length > 0
      ? `${tenKhach} còn ${vuong.length} việc chưa xong — vẫn check-out?`
      : `Check-out ${tenKhach}? Khách rời hàng chờ, lượt khám đóng lại.`;

  const dangHoiLai = buoc === "hoi" || buoc === "dang_gui";

  return (
    // Chỉ chiếm trọn dòng khi dải xác nhận / câu lỗi đang mở — lúc nghỉ nó là
    // một nút đứng cạnh các nút khác của dòng khách.
    <div className={`flex flex-col items-start gap-1 ${dangHoiLai || loi ? "w-full" : ""}`}>
      {dangHoiLai ? (
        <XacNhanTaiCho
          cau={cau}
          nhanDongY="Check-out"
          dangGui={buoc === "dang_gui"}
          choDongY={!chanNo}
          onDongY={() => void gui()}
          onThoi={() => {
            setLoi(null);
            setBuoc("nghi");
          }}
        >
          {coNo(no) || vuong.length > 0 ? (
            <div className="space-y-2">
              {coNo(no) ? (
                <KhoanNoKhiVe visitId={visitId} no={no} onDoi={() => void hoi()} />
              ) : null}
              {vuong.length > 0 ? (
                <>
                  <ul className="list-disc pl-5 text-meta text-warning">
                    {vuong.map((v, i) => (
                      <li key={`${v.type}-${i}`}>{v.message}</li>
                    ))}
                  </ul>
                  <label className="block text-meta text-ink-muted">
                    Lý do cho khách về (không bắt buộc — để trống thì máy ghi kèm
                    danh sách việc còn dở)
                    <input
                      value={lyDo}
                      onChange={(e) => setLyDo(e.target.value)}
                      maxLength={500}
                      className={`${INPUT} mt-1`}
                    />
                  </label>
                </>
              ) : null}
            </div>
          ) : null}
        </XacNhanTaiCho>
      ) : (
        <Button
          size={size}
          variant={variant}
          disabled={buoc === "dang_hoi"}
          onClick={() => void hoi()}
        >
          {buoc === "dang_hoi" ? "Đang kiểm…" : "Check-out"}
        </Button>
      )}
      {loi ? (
        <p role="alert" className="text-meta text-danger">
          {loi}
        </p>
      ) : null}
    </div>
  );
}
