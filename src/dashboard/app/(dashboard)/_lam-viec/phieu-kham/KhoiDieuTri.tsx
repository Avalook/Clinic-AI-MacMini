"use client";

// THẺ CHỈ ĐỊNH ĐIỀU TRỊ — đầu khối 3 "Chỉ định điều trị" của hồ sơ khám (và hồ
// sơ tối giản); lượt Điều trị / Thủ thuật (09/10/2026): ở KHỐI 1, gồm cả thủ
// thuật đã chọn làm tại bàn khám (cờ `ban_kham`), kèm ô tick khi máy chủ mời.
// Không bao giờ vẽ hai nơi cùng lúc (shell chọn chỗ). MỘT thẻ mỗi chỉ định: khung thẻ là `KetQuaChiDinh` (tên, mã, tiền,
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
import { docLT, type LieuTrinhLuot } from "@/lib/lieu-trinh";
import { nhanLoi, type ThanLoi } from "@/lib/loi-api";
import type { ChiDinhVaKetQua } from "@/lib/phieu-kham";
import { MAU_PHIEU_DIEU_TRI } from "@/lib/phieu-ket-qua";
import { useNgheBang } from "../../dung-nghe-bang";
import { OTickTaiCho } from "../OLamTruocThuSau";
import PhieuDieuTri, { type BanDieuTri } from "../PhieuDieuTri";
import PhieuKetQua, { type MauKetQua } from "../PhieuKetQua";
import KetQuaChiDinh, { type PhanKetQua } from "./KetQuaChiDinh";
import { DaiLieuTrinh, DeXuatLieuTrinh, KhungLieuTrinh } from "./LieuTrinhThe";

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

type GoiThe = { the: TheDieuTri[]; chi_doc?: boolean; nhac_tick?: boolean };

export default function KhoiDieuTri({
  visitId,
  choGhi,
  chiDinh,
  ketQua,
  oTick = false,
  goiYTrong = "Chưa có chỉ định điều trị — chọn dịch vụ điều trị ở danh mục bên dưới.",
}: {
  visitId: string;
  choGhi: boolean;
  /** Chỉ định ĐIỀU TRỊ của lượt (`phanChiDinh(...).dieuTri`; khối 1 lượt Điều trị /
   *  Thủ thuật: `.banKham`) — quyết thẻ nào hiện. */
  chiDinh: ChiDinhVaKetQua[];
  /** Thuộc tính khung thẻ chỉ định (Hoàn tác, bắt buộc, tệp…) — shell dựng. */
  ketQua: PhanKetQua;
  /** Khối 1 (09/10/2026): ô "Làm trước – thu sau" ĐẦU khối, chỉ khi máy chủ mời
   *  (`nhac_tick` — chưa thu + chưa tick). Lượt khám thường: ô ở cột phải. */
  oTick?: boolean;
  /** Câu khi chưa có thẻ nào (null = không vẽ). */
  goiYTrong?: string | null;
}) {
  const [the, setThe] = useState<TheDieuTri[] | null>(null);
  const [chiDoc, setChiDoc] = useState(false);
  const [nhacTick, setNhacTick] = useState(false);
  const [dang, setDang] = useState<string | null>(null);
  const [loi, setLoi] = useState<Record<string, string>>({});

  const doc = useCallback(async (): Promise<GoiThe | null> => {
    const r = await fetch(`/api/ho-so-kham?visit_id=${visitId}&xem=dieu-tri`, { cache: "no-store" }).catch(
      () => null,
    );
    return r && r.ok ? ((await r.json().catch(() => null)) as GoiThe | null) : null;
  }, [visitId]);
  const dat = useCallback((d: GoiThe) => {
    setThe(d.the);
    setChiDoc(Boolean(d.chi_doc));
    setNhacTick(Boolean(d.nhac_tick));
  }, []);
  const nap = useCallback(() => {
    void doc().then((d) => {
      if (d) dat(d);
    });
  }, [doc, dat]);

  // Nạp lại khi danh sách chỉ định điều trị đổi (vừa kê / vừa hoàn tác); không
  // có chỉ định điều trị thì khỏi gọi.
  const khoaDs = chiDinh.map((c) => c.service_order_id).join(",");
  useEffect(() => {
    if (!khoaDs) return;
    let huy = false;
    void doc().then((d) => {
      if (!huy && d) dat(d);
    });
    return () => {
      huy = true;
    };
  }, [doc, dat, khoaDs]);
  const theo = useMemo(() => new Map((the ?? []).map((t) => [t.order_id, t] as const)), [the]);
  // Phòng bấm Bắt đầu / Xong, quầy thu tiền, lễ tân check-out → thẻ tự đổi.
  useNgheBang(["service_order", "form_instance", "visit"], nap);

  // LIỆU TRÌNH (08/10/2026): dải trong thẻ + liệu trình chỉ đề xuất từ lượt này.
  // Máy chủ trả số, trạng thái, nút; không có quyền đọc → null, không vẽ gì.
  const [lt, setLt] = useState<LieuTrinhLuot | null>(null);
  const napLT = useCallback(() => {
    void docLT<LieuTrinhLuot>("theo-luot", visitId).then((d) => {
      if (d) setLt(d);
    });
  }, [visitId]);
  useEffect(() => {
    let huy = false;
    void docLT<LieuTrinhLuot>("theo-luot", visitId).then((d) => {
      if (!huy && d) setLt(d);
    });
    return () => {
      huy = true;
    };
  }, [visitId, khoaDs]);
  // Buổi tự gắn / gỡ (trigger), quầy trả trước, người khác điều chỉnh → dải đổi.
  useNgheBang(["lieu_trinh", "lieu_trinh_buoi", "lieu_trinh_lich_su", "lieu_trinh_tra_truoc"], napLT);
  const ltCua = useMemo(() => new Map((lt?.chi_dinh ?? []).map((c) => [c.order_id, c] as const)), [lt]);
  // Liệu trình của lượt KHÔNG gắn với chỉ định nào đang hiện (chỉ đề xuất, hoặc
  // buổi hôm nay đã gỡ) — vẽ riêng dưới thẻ.
  const ltRieng = (lt?.lieu_trinh ?? []).filter(
    (x) => !(lt?.chi_dinh ?? []).some((c) => c.lieu_trinh_id === x.id && chiDinh.some((d) => d.service_order_id === c.order_id)),
  );
  const phanLT = (
    <>
      {ltRieng.map((x) => (
        <KhungLieuTrinh key={x.id} lt={x} choGhi={choGhi} onDoi={napLT} />
      ))}
      {choGhi && lt ? (
        <DeXuatLieuTrinh visitId={visitId} dichVu={lt.dich_vu_de_xuat ?? []} onDoi={napLT} />
      ) : null}
    </>
  );

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
    return (
      <div className="space-y-2">
        {choGhi && goiYTrong ? <p className="text-meta text-ink-muted">{goiYTrong}</p> : null}
        {phanLT}
      </div>
    );
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
    const cdLT = ltCua.get(t.order_id);
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
        {lt && cdLT ? <DaiLieuTrinh visitId={visitId} cd={cdLT} luot={lt} choGhi={choGhi} onDoi={napLT} /> : null}
      </div>
    );
  };

  return (
    <section aria-label="Chỉ định điều trị đã kê" className="space-y-2">
      {/* Câu "chưa thu" của thẻ đi kèm ô tick NGAY ĐÂY — tick xong bấm làm. */}
      {oTick && choGhi && !chiDoc ? <OTickTaiCho visitId={visitId} moi={nhacTick} onDoi={nap} /> : null}
      <KetQuaChiDinh ds={chiDinh} {...ketQua} dieuTri={{ chip, than }} />
      {phanLT}
    </section>
  );
}
