"use client";

// KHỐI 4 "ĐIỀU TRỊ" của hồ sơ khám (Tuyền chốt 07/10/2026 chiều): danh sách CHỈ
// ĐỊNH ĐIỀU TRỊ của lượt — mỗi chỉ định một thẻ:
//   · PHIẾU ĐIỀU TRỊ = phiếu KẾT QUẢ của chính chỉ định ấy (mẫu PHIEU_DIEU_TRI:
//     "Cảm nhận", "Vấn đề sau điều trị") — CÙNG `PhieuKetQua` / `form_instance` mà
//     phòng dịch vụ mở: bàn khám ghi dở thì phòng ghi tiếp, không điền lại. Tự lưu
//     + revision chống ghi đè do engine phiếu kết quả lo.
//   · trạng thái (chưa làm / đang làm ở P. X / đang làm tại bàn khám / xong) +
//     nhãn "Khách đã đặt" (lượt đặt lịch Điều trị);
//   · [Làm tại bàn khám] → [Xong] (giờ thật), hoàn tác từng bước. Điền phiếu KHÔNG
//     tính là đã làm.
// MÁY CHỦ quyết nút nào hiện, vì sao không làm được (cửa tiền — `lam_duoc`,
// `ly_do_khong_lam`); màn chỉ vẽ và gửi lệnh (`/api/ho-so-kham`).

import { useCallback, useEffect, useState } from "react";

import Button from "@/components/ui/Button";
import Chip, { type ChipTone } from "@/components/ui/Chip";
import { fmtTime } from "@/lib/datetime";
import { nhanLoi, type ThanLoi } from "@/lib/loi-api";
import { useNgheBang } from "../../dung-nghe-bang";
import PhieuKetQua, { type MauKetQua } from "../PhieuKetQua";

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

export default function KhoiDieuTri({ visitId, choGhi }: { visitId: string; choGhi: boolean }) {
  const [the, setThe] = useState<TheDieuTri[] | null>(null);
  const [dang, setDang] = useState<string | null>(null);
  const [loi, setLoi] = useState<Record<string, string>>({});
  // Phiếu điều trị MỞ sẵn trong thẻ (gập được) — nó là nửa của thẻ.
  const [anPhieu, setAnPhieu] = useState<Record<string, boolean>>({});

  const doc = useCallback(async (): Promise<TheDieuTri[] | null> => {
    const r = await fetch(`/api/ho-so-kham?visit_id=${visitId}&xem=dieu-tri`, { cache: "no-store" }).catch(
      () => null,
    );
    const d = r && r.ok ? ((await r.json().catch(() => null)) as { the: TheDieuTri[] } | null) : null;
    return d?.the ?? null;
  }, [visitId]);
  const nap = useCallback(() => {
    void doc().then((t) => {
      if (t) setThe(t);
    });
  }, [doc]);

  useEffect(() => {
    let huy = false;
    void doc().then((t) => {
      if (!huy) setThe(t ?? []);
    });
    return () => {
      huy = true;
    };
  }, [doc]);
  // Phòng bấm Bắt đầu / Xong, quầy thu tiền → thẻ tự đổi.
  useNgheBang(["service_order", "form_instance"], nap);

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

  if (the === null) return <p className="text-body text-ink-muted">Đang mở khối Điều trị…</p>;
  if (the.length === 0) {
    return (
      <section aria-label="Điều trị" className="rounded-card border border-hairline bg-surface p-4">
        <p className="text-body text-ink-muted">Chưa có chỉ định điều trị — kê ở khối Chỉ định điều trị.</p>
      </section>
    );
  }

  return (
    <section aria-label="Điều trị" className="space-y-3">
      {the.map((t) => {
        const ban = dang === t.order_id;
        const moi = loi[t.order_id];
        const mo = !anPhieu[t.order_id];
        return (
          <article key={t.order_id} className="space-y-2 rounded-card border border-hairline bg-surface p-4">
            <div className="flex flex-wrap items-center gap-2">
              <b className="min-w-0 text-emph text-ink">{t.ten}</b>
              {t.da_dat ? <Chip tone="brand">Khách đã đặt</Chip> : null}
              <Chip tone={TONE[t.trang_thai]}>
                {t.nhan}
                {t.phong && t.trang_thai !== "DANG_LAM_BAN_KHAM" ? ` · ${t.phong}` : ""}
              </Chip>
              <Chip tone={t.da_thu ? "success" : "warning"}>{t.da_thu ? "Đã thu" : "Chưa thu"}</Chip>
            </div>
            {t.bat_dau_luc ? (
              <p className="text-meta text-ink-muted">
                {t.nguoi_lam ?? "?"} · bắt đầu {fmtTime(t.bat_dau_luc)}
                {t.xong_luc ? ` · xong ${fmtTime(t.xong_luc)}` : ""}
              </p>
            ) : null}
            {choGhi ? (
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
                <Button
                  size="sm"
                  variant="ghost"
                  aria-expanded={mo}
                  onClick={() => setAnPhieu((x) => ({ ...x, [t.order_id]: mo }))}
                >
                  {mo ? "Gập phiếu điều trị" : "Mở phiếu điều trị"}
                </Button>
              </div>
            ) : null}
            {choGhi && t.ly_do_khong_lam ? <p className="text-meta text-ink-muted">{t.ly_do_khong_lam}</p> : null}
            {moi ? (
              <p role="alert" className="text-meta text-danger">
                {moi}
              </p>
            ) : null}
            {choGhi && mo ? (
              <div className="border-t border-hairline pt-3">
                <PhieuKetQua serviceOrderId={t.order_id} mau={t.mau} mauMacDinh={t.mau_chon_san} onHoanTat={nap} />
              </div>
            ) : null}
          </article>
        );
      })}
    </section>
  );
}
