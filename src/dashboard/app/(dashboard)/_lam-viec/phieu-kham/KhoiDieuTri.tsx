"use client";

// THẺ CHỈ ĐỊNH ĐIỀU TRỊ — đầu khối 3 "Chỉ định điều trị" của hồ sơ khám (và hồ
// sơ tối giản). MỘT thẻ mỗi chỉ định: khung thẻ là `KetQuaChiDinh` (tên, mã, tiền,
// bắt buộc, Hoàn tác chỉ định, Ảnh · tệp — như mọi chỉ định), phần điều trị vẽ ở
// đây qua `dieuTri={{ chip, than }}`. Danh sách lấy theo cờ `dieu_tri` máy chủ
// (`phanChiDinh`) — một định nghĩa, không dò theo danh mục thủ thuật, nên một chỉ
// định không bao giờ ra hai thẻ.
//   · PHIẾU ĐIỀU TRỊ = phiếu KẾT QUẢ của chính chỉ định ấy (mẫu PHIEU_DIEU_TRI:
//     "Cảm nhận", "Vấn đề sau điều trị") — CÙNG component `PhieuDieuTri` và CÙNG
//     `form_instance` mà phòng dịch vụ mở: bàn khám ghi dở thì phòng ghi tiếp,
//     không điền lại. Gọn (sau bấm thử staging 07/10): không tiêu đề "Phiếu kết
//     quả · …", mỗi ô một nhãn, không "Hoàn tất phiếu", không gập/mở.
//   · trạng thái (chưa làm / đang làm ở P. X / đang làm tại bàn khám / xong) +
//     nhãn "Khách đã đặt" (lượt đặt lịch Điều trị);
//   · [Làm tại bàn khám] → [Xong] (giờ thật), hoàn tác từng bước. Điền phiếu KHÔNG
//     tính là đã làm.
// MÁY CHỦ quyết nút nào hiện, vì sao không làm được (cửa tiền — `lam_duoc`,
// `ly_do_khong_lam`), lượt đã check-out thì chỉ đọc (`chi_doc`); màn chỉ vẽ và
// gửi lệnh (`/api/ho-so-kham`).

import { useCallback, useEffect, useMemo, useState } from "react";

import Button from "@/components/ui/Button";
import Chip, { type ChipTone } from "@/components/ui/Chip";
import { fmtTime } from "@/lib/datetime";
import { nhanLoi, type ThanLoi } from "@/lib/loi-api";
import type { ChiDinhVaKetQua } from "@/lib/phieu-kham";
import { MAU_PHIEU_DIEU_TRI } from "@/lib/phieu-ket-qua";
import { useNgheBang } from "../../dung-nghe-bang";
import PhieuDieuTri, { type BanDieuTri } from "../PhieuDieuTri";
import PhieuKetQua, { type MauKetQua } from "../PhieuKetQua";
import KetQuaChiDinh, { type PhanKetQua } from "./KetQuaChiDinh";

export interface TheDieuTri {
  order_id: string;
  ten: string;
  da_dat: boolean;
  trang_thai: "CHUA_LAM" | "DANG_LAM_PHONG" | "DANG_LAM_BAN_KHAM" | "XONG" | "KHONG_LAM" | "DUNG";
  nhan: string;
  phong: string | null;
  nguoi_lam: string | null;
  bat_dau_luc: string | null;
  xong_luc: string | null;
  attempt_id: string | null;
  execution_revision: number;
  da_thu: boolean;
  lam_duoc: boolean;
  ly_do_khong_lam: string | null;
  xong_duoc: boolean;
  huy_lam_duoc: boolean;
  hoan_tac_xong_duoc: boolean;
  mau: MauKetQua[];
  mau_chon_san: string | null;
  phieu: (BanDieuTri & { phieu_id: string; form_id: string }) | null;
}

const TONE: Record<TheDieuTri["trang_thai"], ChipTone> = {
  CHUA_LAM: "neutral",
  DANG_LAM_PHONG: "run",
  DANG_LAM_BAN_KHAM: "run",
  XONG: "success",
  KHONG_LAM: "warning",
  DUNG: "warning",
};

type Lenh = "lam" | "xong" | "huy-lam" | "hoan-tac-xong";

function khoaGui(): string {
  return `ban-kham-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
}

export default function KhoiDieuTri({
  visitId,
  choGhi,
  chiDinh,
  ketQua,
}: {
  visitId: string;
  choGhi: boolean;
  /** Chỉ định ĐIỀU TRỊ của lượt (`phanChiDinh(...).dieuTri`) — quyết thẻ nào hiện. */
  chiDinh: ChiDinhVaKetQua[];
  /** Thuộc tính khung thẻ chỉ định (Hoàn tác, bắt buộc, tệp…) — shell dựng. */
  ketQua: PhanKetQua;
}) {
  const [the, setThe] = useState<TheDieuTri[] | null>(null);
  const [chiDoc, setChiDoc] = useState(false);
  const [dang, setDang] = useState<string | null>(null);
  const [loi, setLoi] = useState<Record<string, string>>({});

  const doc = useCallback(async (): Promise<{ the: TheDieuTri[]; chi_doc?: boolean } | null> => {
    const r = await fetch(`/api/ho-so-kham?visit_id=${visitId}&xem=dieu-tri`, { cache: "no-store" }).catch(
      () => null,
    );
    return r && r.ok
      ? ((await r.json().catch(() => null)) as { the: TheDieuTri[]; chi_doc?: boolean } | null)
      : null;
  }, [visitId]);
  const nap = useCallback(() => {
    void doc().then((d) => {
      if (!d) return;
      setThe(d.the);
      setChiDoc(Boolean(d.chi_doc));
    });
  }, [doc]);

  // Nạp lại khi danh sách chỉ định điều trị đổi (vừa kê / vừa hoàn tác); không
  // có chỉ định điều trị thì khỏi gọi.
  const khoaDs = chiDinh.map((c) => c.service_order_id).join(",");
  useEffect(() => {
    if (!khoaDs) return;
    let huy = false;
    void doc().then((d) => {
      if (huy || !d) return;
      setThe(d.the);
      setChiDoc(Boolean(d.chi_doc));
    });
    return () => {
      huy = true;
    };
  }, [doc, khoaDs]);
  const theo = useMemo(() => new Map((the ?? []).map((t) => [t.order_id, t] as const)), [the]);
  // Phòng bấm Bắt đầu / Xong, quầy thu tiền, lễ tân check-out → thẻ tự đổi.
  useNgheBang(["service_order", "form_instance", "visit"], nap);

  async function bam(t: TheDieuTri, lenh: Lenh) {
    if (dang) return;
    setDang(t.order_id);
    setLoi((x) => ({ ...x, [t.order_id]: "" }));
    const r = await fetch("/api/ho-so-kham", {
      method: "POST",
      headers: { "Content-Type": "application/json", "Idempotency-Key": khoaGui() },
      body: JSON.stringify({
        thao_tac: "ban-kham",
        visit_id: visitId,
        order_id: t.order_id,
        lenh,
        expected_execution_revision: t.execution_revision,
        attempt_id: t.attempt_id,
      }),
    }).catch(() => null);
    setDang(null);
    if (!r) {
      setLoi((x) => ({ ...x, [t.order_id]: "Mất kết nối — chưa ghi. Thử lại." }));
      return;
    }
    if (!r.ok) {
      const d = (await r.json().catch(() => null)) as ThanLoi | null;
      setLoi((x) => ({ ...x, [t.order_id]: nhanLoi(d, "Không làm được thao tác này.") }));
    }
    nap();
  }

  // Không có chỉ định điều trị: không vẽ vùng thẻ — chỉ một dòng gợi ý khi ghi được.
  if (chiDinh.length === 0) {
    return choGhi ? (
      <p className="text-meta text-ink-muted">
        Chưa có chỉ định điều trị — chọn dịch vụ điều trị ở danh mục bên dưới.
      </p>
    ) : null;
  }

  // Ghi được phiếu: người có quyền ghi hồ sơ, lượt chưa check-out (máy chủ nói).
  const ghiPhieu = choGhi && !chiDoc;

  // Chip trạng thái điều trị (chính xác hơn trục một chiều: đang làm ở phòng nào /
  // tại bàn khám). Chưa nạp xong thẻ → null, khung thẻ giữ chip một trục.
  const chip = (d: ChiDinhVaKetQua) => {
    const t = theo.get(d.service_order_id);
    if (!t) return null;
    return (
      <>
        {t.da_dat ? <Chip tone="brand">Khách đã đặt</Chip> : null}
        <Chip tone={TONE[t.trang_thai]}>
          {t.nhan}
          {t.phong && t.trang_thai !== "DANG_LAM_BAN_KHAM" ? ` · ${t.phong}` : ""}
        </Chip>
        <Chip tone={t.da_thu ? "success" : "warning"}>{t.da_thu ? "Đã thu" : "Chưa thu"}</Chip>
      </>
    );
  };

  const than = (d: ChiDinhVaKetQua) => {
    const t = theo.get(d.service_order_id);
    if (!t) return null;
    const ban = dang === t.order_id;
    const moi = loi[t.order_id];
    const coNut = t.lam_duoc || t.xong_duoc || t.huy_lam_duoc || t.hoan_tac_xong_duoc;
    return (
      <div className="space-y-3">
        {t.bat_dau_luc ? (
          <p className="text-meta text-ink-muted">
            {t.nguoi_lam ?? "?"} · bắt đầu {fmtTime(t.bat_dau_luc)}
            {t.xong_luc ? ` · xong ${fmtTime(t.xong_luc)}` : ""}
          </p>
        ) : null}
        {choGhi && coNut ? (
          <div className="flex flex-wrap items-center gap-2">
            {t.lam_duoc ? (
              <Button size="sm" variant="primary" disabled={ban} onClick={() => void bam(t, "lam")}>
                Làm tại bàn khám
              </Button>
            ) : null}
            {t.xong_duoc ? (
              <Button size="sm" variant="primary" disabled={ban} onClick={() => void bam(t, "xong")}>
                Xong
              </Button>
            ) : null}
            {t.huy_lam_duoc ? (
              <Button size="sm" variant="ghost" disabled={ban} onClick={() => void bam(t, "huy-lam")}>
                Hoàn tác bắt đầu
              </Button>
            ) : null}
            {t.hoan_tac_xong_duoc ? (
              <Button size="sm" variant="ghost" disabled={ban} onClick={() => void bam(t, "hoan-tac-xong")}>
                Hoàn tác Xong
              </Button>
            ) : null}
          </div>
        ) : null}
        {choGhi && t.ly_do_khong_lam ? <p className="text-meta text-ink-muted">{t.ly_do_khong_lam}</p> : null}
        {moi ? (
          <p role="alert" className="text-meta text-danger">
            {moi}
          </p>
        ) : null}
        {t.mau_chon_san === MAU_PHIEU_DIEU_TRI || !ghiPhieu ? (
          <PhieuDieuTri serviceOrderId={t.order_id} choGhi={ghiPhieu} banDoc={t.phieu} />
        ) : (
          // Dịch vụ điều trị mà quản lý gắn mẫu khác: phiếu kết quả chung.
          <PhieuKetQua serviceOrderId={t.order_id} mau={t.mau} mauMacDinh={t.mau_chon_san} onHoanTat={nap} />
        )}
      </div>
    );
  };

  return (
    <section aria-label="Chỉ định điều trị đã kê">
      <KetQuaChiDinh ds={chiDinh} {...ketQua} dieuTri={{ chip, than }} />
    </section>
  );
}
