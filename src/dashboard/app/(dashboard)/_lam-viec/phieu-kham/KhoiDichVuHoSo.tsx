"use client";

// DỊCH VỤ CỦA LƯỢT ở đầu hồ sơ khám (Tuyền chốt 07/10/2026 — T1, T3, T5):
//   · dịch vụ hiện tại + [Đổi dịch vụ] (bộ chọn 4 nhóm dùng chung) — đã có phiếu
//     / đã thu / đã tick vẫn đổi được; phiếu cũ giữ nguyên, "Phiếu cũ: … [xem]";
//   · lịch sử đổi (ai, lúc, từ → sang) hiện ngay tại đây;
//   · ghi chú CSKH lúc đặt lịch.
// Lượt Điều trị: chỉ định đã sinh sẵn ("Khách đã đặt") nằm ở khối 4 "Điều trị"
// (`KhoiDieuTri.tsx`, Tuyền 07/10 chiều — gộp vào thẻ chỉ định điều trị).
// MÁY CHỦ quyết đổi được không, vì sao (`/api/ho-so-kham`); màn chỉ vẽ.

import { useCallback, useEffect, useState, type ReactNode } from "react";

import Button from "@/components/ui/Button";
import { nhanLoi } from "@/lib/loi-api";
import { INPUT } from "../../form-ui";
import ChonDichVuDatLich, { type NhomDichVuDatLich } from "../ChonDichVuDatLich";

interface GoiHoSo {
  dich_vu: { id: string | null; ten: string | null; nhom: string | null };
  doi_duoc: boolean;
  ly_do_khong_doi: string | null;
  nhom: NhomDichVuDatLich[];
  lich_su_doi: { luc: string | null; ai: string | null; tu: string | null; sang: string | null }[];
  phieu_cu: { form_id: string; ten: string; so_o: number }[];
  ghi_chu_dat: string | null;
}

function gio(iso: string | null): string {
  return iso
    ? new Date(iso).toLocaleString("vi-VN", {
        timeZone: "Asia/Ho_Chi_Minh",
        hour: "2-digit",
        minute: "2-digit",
        day: "2-digit",
        month: "2-digit",
      })
    : "";
}

export default function KhoiDichVuHoSo({
  visitId,
  choGhi,
  onDaDoi,
  vePhieuCu,
}: {
  visitId: string;
  choGhi: boolean;
  /** Đổi xong — shell nạp lại phiếu theo dịch vụ mới + bảng hàng chờ. */
  onDaDoi: () => void;
  /** Phiếu cũ của lượt, chỉ xem (shell dựng). */
  vePhieuCu: (formId: string) => ReactNode;
}) {
  const [goi, setGoi] = useState<GoiHoSo | null>(null);
  const [mo, setMo] = useState(false);
  const [chon, setChon] = useState("");
  const [dang, setDang] = useState(false);
  const [loi, setLoi] = useState<string | null>(null);
  const [xemPhieu, setXemPhieu] = useState<string | null>(null);

  const doc = useCallback(async (): Promise<GoiHoSo | null> => {
    const r = await fetch(`/api/ho-so-kham?visit_id=${visitId}&xem=dich-vu`, { cache: "no-store" }).catch(
      () => null,
    );
    return r && r.ok ? ((await r.json().catch(() => null)) as GoiHoSo | null) : null;
  }, [visitId]);
  const nap = useCallback(() => doc().then(setGoi), [doc]);

  useEffect(() => {
    let huy = false;
    void doc().then((g) => {
      if (!huy) setGoi(g);
    });
    return () => {
      huy = true;
    };
  }, [doc]);

  if (!goi) return null;

  async function doi() {
    if (!chon || dang) return;
    setDang(true);
    setLoi(null);
    const r = await fetch("/api/ho-so-kham", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ thao_tac: "doi-dich-vu", visit_id: visitId, service_type_id: chon }),
    }).catch(() => null);
    setDang(false);
    if (!r) {
      setLoi("Mất kết nối — dịch vụ CHƯA đổi. Thử lại.");
      return;
    }
    if (!r.ok) {
      setLoi(nhanLoi((await r.json().catch(() => null)) as Parameters<typeof nhanLoi>[0], "Không đổi được dịch vụ."));
      return;
    }
    setMo(false);
    setChon("");
    await nap();
    onDaDoi();
  }

  return (
    <section aria-label="Dịch vụ của lượt" className="space-y-2 rounded-card border border-hairline bg-surface p-4">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-meta text-ink-muted">Dịch vụ của lượt</span>
        <b className="text-emph text-ink">{goi.dich_vu.ten ?? "Chưa gán"}</b>
        {choGhi && goi.doi_duoc ? (
          <Button size="sm" variant="ghost" aria-expanded={mo} onClick={() => setMo((x) => !x)}>
            Đổi dịch vụ
          </Button>
        ) : null}
      </div>
      {choGhi && !goi.doi_duoc && goi.ly_do_khong_doi ? (
        <p className="text-meta text-ink-muted">{goi.ly_do_khong_doi}</p>
      ) : null}
      {mo ? (
        <div className="space-y-2 rounded-control bg-surface-sunken p-3">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
            <ChonDichVuDatLich
              nhom={goi.nhom}
              value={chon}
              onChange={(id) => setChon(id)}
              className={INPUT}
              ariaLabel="Dịch vụ mới"
            />
            <div className="flex gap-2">
              <Button variant="primary" disabled={!chon || chon === goi.dich_vu.id || dang} onClick={() => void doi()}>
                {dang ? "Đang đổi…" : "Đổi"}
              </Button>
              <Button variant="ghost" onClick={() => setMo(false)}>
                Thôi
              </Button>
            </div>
          </div>
          <p className="text-meta text-ink-muted">
            Phiếu đang ghi giữ nguyên (thành “phiếu cũ”); đổi ngược lại là mở đúng phiếu ấy. Dịch vụ khám con đã tick
            giữ nguyên.
          </p>
          {loi ? (
            <p role="alert" className="text-meta text-danger">
              {loi}
            </p>
          ) : null}
        </div>
      ) : null}
      {goi.ghi_chu_dat ? <p className="text-body text-ink-soft">Ghi chú lúc đặt: {goi.ghi_chu_dat}</p> : null}
      {goi.phieu_cu.map((p) => (
        <div key={p.form_id} className="space-y-2">
          <p className="flex flex-wrap items-center gap-2 text-body text-ink-soft">
            Phiếu cũ: {p.ten} — đã nhập {p.so_o} ô
            <Button
              size="sm"
              variant="ghost"
              aria-expanded={xemPhieu === p.form_id}
              onClick={() => setXemPhieu((x) => (x === p.form_id ? null : p.form_id))}
            >
              {xemPhieu === p.form_id ? "Ẩn" : "Xem"}
            </Button>
          </p>
          {xemPhieu === p.form_id ? vePhieuCu(p.form_id) : null}
        </div>
      ))}
      {goi.lich_su_doi.length > 0 ? (
        <ul className="space-y-0.5 border-t border-hairline pt-2 text-meta text-ink-muted">
          {goi.lich_su_doi.map((l, i) => (
            <li key={`${l.luc}-${i}`}>
              {gio(l.luc)} · {l.ai ?? "?"} đổi {l.tu ?? "—"} → {l.sang ?? "—"}
            </li>
          ))}
        </ul>
      ) : null}
    </section>
  );
}
