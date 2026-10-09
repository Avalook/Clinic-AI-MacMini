"use client";

// LỊCH SỬ ĐƠN THUỐC của khách cũ + "Bán theo đơn này" từng đơn (09/10/2026).
// Hai chỗ dùng:
//   · khung chọn khách (`KhachMuaThuoc`, CHƯA mở lượt): nút gửi `clinicPatientId`
//     → máy chủ mở/lấy lại lượt + nối đơn + thêm dòng trong MỘT giao dịch;
//   · lượt bán lẻ đang mở (`BanLeThu`): nút gửi `visitId`, có thêm "Gỡ nối đơn".
//
// Máy chủ (`ban_theo_don_service.lich_su_don`) xếp đơn mới → cũ theo trang, tính
// kê / đã mua / còn lại, soạn lời nhắc và nói đơn nào bán được (`ban_duoc`). Ở
// đây chỉ vẽ: đơn đang nối (không có thì đơn mới nhất) mở sẵn, đơn khác thu gọn.
// Lời nhắc chỉ để đọc — không nút nào bị khoá vì nó. "Lịch sử khám" dùng lại
// popup chung (`_lam-viec/LichSuKham`).

import { useEffect, useState } from "react";

import Button from "@/components/ui/Button";
import Chip from "@/components/ui/Chip";

import LichSuKham from "../_lam-viec/LichSuKham";
import { fmtNgay } from "./ban-thuoc";
import { CHAM } from "./DongThuoc";

interface DongDon {
  drug_catalog_id: string | null;
  ten: string;
  ten_bac_si: string | null;
  don_vi: string | null;
  so_ke: string | null;
  da_mua: string;
  dang_ban: string;
  con_lai: string | null;
  vuot: boolean;
}

interface DonCu {
  visit_id: string;
  ngay_kham: string | null;
  bac_si: string | null;
  ngay_hen: string | null;
  da_noi: boolean;
  ban_duoc: boolean;
  dong: DongDon[];
  nhac: string[];
}

interface GoiLichSu {
  don: DonCu[];
  nhac_chung: string[];
  trang: number;
  co_them: boolean;
}

type Doi = (cau: string | null, loi: string | null) => void | Promise<void>;

async function gui(duong: string, than: Record<string, string>) {
  try {
    const r = await fetch(`/api/pharmacy/${duong}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(than),
    });
    const d = (await r.json().catch(() => null)) as {
      message?: string;
      error?: string;
      so_dong_them?: number;
      visit_id?: string;
      bo_qua?: string[];
    } | null;
    if (!r.ok) return { loi: d?.message ?? d?.error ?? `Không ghi được (HTTP ${r.status}).` };
    return { d };
  } catch {
    return { loi: "Mất kết nối — CHƯA ghi được." };
  }
}

async function taiTrang(pid: string, trang: number): Promise<GoiLichSu | null> {
  const q = new URLSearchParams({ clinic_patient_id: pid, trang: String(trang) });
  const r = await fetch(`/api/pharmacy/lich-su-don?${q}`, { cache: "no-store" }).catch(
    () => null,
  );
  return r?.ok ? ((await r.json().catch(() => null)) as GoiLichSu | null) : null;
}

function TheDon({
  don,
  mo,
  onBat,
  visitId,
  clinicPatientId,
  choSua,
  onDoi,
  onMo,
}: {
  don: DonCu;
  mo: boolean;
  onBat: () => void;
  visitId?: string;
  clinicPatientId: string;
  choSua: boolean;
  onDoi: Doi;
  onMo?: (visitId: string) => void;
}) {
  const [dang, setDang] = useState(false);

  const banTheoDon = async () => {
    setDang(true);
    const kq = visitId
      ? await gui("ban-le-theo-don", { visit_id: visitId, don_goc_visit_id: don.visit_id })
      : await gui("ban-le-mo-theo-don", {
          clinic_patient_id: clinicPatientId,
          don_goc_visit_id: don.visit_id,
        });
    setDang(false);
    if (kq.loi) return void (await onDoi(null, kq.loi));
    const so = kq.d?.so_dong_them ?? 0;
    await onDoi(
      [
        so > 0
          ? `Đã thêm ${so} thuốc theo đơn — số điền sẵn là số còn lại, sửa được ở dưới.`
          : "Đã nối đơn — không có thuốc nào cần thêm.",
        ...(kq.d?.bo_qua ?? []),
      ].join(" "),
      null,
    );
    if (!visitId && kq.d?.visit_id) onMo?.(kq.d.visit_id);
  };

  const goNoi = async () => {
    setDang(true);
    const kq = await gui("ban-le-go-don", { visit_id: visitId ?? "" });
    setDang(false);
    if (kq.loi) return void (await onDoi(null, kq.loi));
    await onDoi("Đã gỡ nối đơn. Các dòng thuốc đã thêm vẫn còn — bỏ tick nếu khách không lấy.", null);
  };

  const coVuot = don.dong.some((d) => d.vuot);
  return (
    <li className="px-3 py-2">
      <button
        type="button"
        aria-expanded={mo}
        onClick={onBat}
        className="flex w-full flex-wrap items-center gap-2 text-left"
      >
        <span className="min-w-0 flex-1 text-body font-medium text-ink">
          {[
            don.ngay_kham ? `Khám ${fmtNgay(don.ngay_kham)}` : "Lượt khám",
            don.bac_si ? `BS ${don.bac_si}` : null,
            `${don.dong.length} thuốc`,
          ]
            .filter(Boolean)
            .join(" · ")}
        </span>
        {don.da_noi ? <Chip tone="brand">Đang bán theo đơn</Chip> : null}
        {coVuot ? <Chip tone="warning">Vượt số kê</Chip> : null}
        <span className="text-meta text-ink-muted">{mo ? "Thu gọn" : "Xem"}</span>
      </button>
      {mo ? (
        <div className="mt-2 space-y-2">
          <p className="text-meta text-ink-muted">
            {don.ngay_hen ? `Hẹn tái khám ${fmtNgay(don.ngay_hen)}` : "Không có hẹn tái khám"}
          </p>
          {don.nhac.length > 0 ? (
            <ul role="status" className="space-y-1 rounded-control bg-warning-bg px-3 py-2">
              {don.nhac.map((c) => (
                <li key={c} className="text-meta text-warning">
                  {c}
                </li>
              ))}
            </ul>
          ) : null}
          <ul className="divide-y divide-line rounded-control border border-line">
            {don.dong.map((d) => (
              <li
                key={d.drug_catalog_id ?? d.ten}
                className="flex flex-wrap items-center gap-x-3 gap-y-1 px-3 py-2"
              >
                <span className="min-w-0 flex-1 basis-40">
                  <span className="block text-body text-ink">{d.ten}</span>
                  {d.ten_bac_si ? (
                    <span className="block text-meta text-ink-muted">BS ghi: {d.ten_bac_si}</span>
                  ) : null}
                  {d.drug_catalog_id ? null : (
                    <span className="block text-meta text-ink-muted">Chưa xác định thuốc kho</span>
                  )}
                </span>
                <span className="text-meta tabular-nums text-ink-soft">
                  Kê {d.so_ke ?? "—"} · Đã mua {d.da_mua}
                  {d.dang_ban !== "0" ? ` · Đang bán ${d.dang_ban}` : ""} · Còn{" "}
                  {d.con_lai ?? "—"}
                  {d.don_vi ? ` ${d.don_vi}` : ""}
                </span>
                {d.vuot ? <Chip tone="warning">Vượt số kê</Chip> : null}
              </li>
            ))}
          </ul>
          {choSua && don.da_noi && visitId ? (
            <Button
              type="button"
              className={CHAM}
              size="sm"
              variant="secondary"
              disabled={dang}
              onClick={() => void goNoi()}
            >
              Gỡ nối đơn
            </Button>
          ) : choSua && don.ban_duoc && !(don.da_noi && visitId) ? (
            <Button
              type="button"
              className={CHAM}
              size="sm"
              variant="soft"
              disabled={dang}
              onClick={() => void banTheoDon()}
            >
              {dang ? "Đang thêm…" : "Bán theo đơn này"}
            </Button>
          ) : null}
        </div>
      ) : null}
    </li>
  );
}

export default function LichSuDonThuoc({
  clinicPatientId,
  visitId,
  choSua,
  lanTai = 0,
  onDoi,
  onMo,
}: {
  clinicPatientId: string;
  /** Lượt bán lẻ đang mở; bỏ trống = đang chọn khách, chưa mở lượt. */
  visitId?: string;
  /** Tiền thuốc chưa thu / chưa chờ xác minh — mới nối / gỡ được. */
  choSua: boolean;
  /** Đổi số này = tải lại (màn cha vừa nạp lại lượt). */
  lanTai?: number;
  onDoi: Doi;
  /** Chưa có lượt: máy chủ vừa mở/lấy lại lượt này — màn chọn luôn nó. */
  onMo?: (visitId: string) => void;
}) {
  // undefined = đang tải · null = không đọc được.
  const [goi, setGoi] = useState<GoiLichSu | null | undefined>(undefined);
  const [bat, setBat] = useState<Record<string, boolean>>({});
  const [dangThem, setDangThem] = useState(false);

  useEffect(() => {
    let bo = false;
    void taiTrang(clinicPatientId, 0).then((d) => {
      if (!bo) setGoi(d);
    });
    return () => {
      bo = true;
    };
  }, [clinicPatientId, lanTai]);

  const xemThem = async () => {
    if (!goi) return;
    setDangThem(true);
    const tiep = await taiTrang(clinicPatientId, goi.trang + 1);
    setDangThem(false);
    if (tiep) setGoi({ ...tiep, don: [...goi.don, ...tiep.don] });
  };

  const moSan = goi?.don.find((d) => d.da_noi)?.visit_id ?? goi?.don[0]?.visit_id;
  const taiLai = async (cau: string | null, loi: string | null) => {
    await onDoi(cau, loi);
    if (!loi) setGoi(await taiTrang(clinicPatientId, 0));
  };

  return (
    <section aria-label="Lịch sử đơn thuốc" className="space-y-2 border-b border-line px-4 py-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-body font-semibold text-ink">Lịch sử đơn thuốc</h3>
        <LichSuKham clinicPatientId={clinicPatientId} />
      </div>
      {goi === undefined ? (
        <p className="text-meta text-ink-muted">Đang tải lịch sử đơn thuốc…</p>
      ) : goi === null ? (
        <p role="alert" className="text-meta text-danger">
          Không đọc được lịch sử đơn thuốc.
        </p>
      ) : (
        <>
          {goi.nhac_chung.length > 0 ? (
            <ul role="status" className="space-y-1 rounded-control bg-warning-bg px-3 py-2">
              {goi.nhac_chung.map((c) => (
                <li key={c} className="text-meta text-warning">
                  {c}
                </li>
              ))}
            </ul>
          ) : null}
          {goi.don.length === 0 ? (
            <p className="text-meta text-ink-muted">
              Khách chưa có đơn thuốc nào{visitId ? "." : " — bấm “Mở lượt mua thuốc” để bán lẻ."}
            </p>
          ) : (
            <ul className="divide-y divide-line rounded-control border border-line">
              {goi.don.map((d) => (
                <TheDon
                  key={d.visit_id}
                  don={d}
                  mo={bat[d.visit_id] ?? d.visit_id === moSan}
                  onBat={() =>
                    setBat((b) => ({ ...b, [d.visit_id]: !(b[d.visit_id] ?? d.visit_id === moSan) }))
                  }
                  visitId={visitId}
                  clinicPatientId={clinicPatientId}
                  choSua={choSua}
                  onDoi={taiLai}
                  onMo={onMo}
                />
              ))}
            </ul>
          )}
          {goi.co_them ? (
            <Button
              type="button"
              className={CHAM}
              size="sm"
              variant="ghost"
              disabled={dangThem}
              onClick={() => void xemThem()}
            >
              {dangThem ? "Đang tải…" : "Xem đơn cũ hơn"}
            </Button>
          ) : null}
        </>
      )}
    </section>
  );
}
