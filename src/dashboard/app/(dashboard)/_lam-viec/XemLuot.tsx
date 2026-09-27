"use client";

// XEM LẠI MỘT LƯỢT KHÁM — batch pilot 18/09/2026 (Pack B).
//
// MỘT component cho mọi vai: điều dưỡng xem số vừa đo, bác sĩ/thư ký xem lượt đã
// khám, trưởng ca xem dòng thời gian từng chỉ định, lễ tân xem hành trình, thu
// ngân xem giao dịch, nhà thuốc xem cấp thuốc. Chỉ đọc. Vai nào thấy mục nào là
// MÁY CHỦ quyết (`xem_luot_service.muc_duoc_xem`) — màn chỉ vẽ mục có trong dữ
// liệu trả về, không tự lọc theo tên vai.

import { X } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import Button from "@/components/ui/Button";

import { docBang, gioVn } from "./api";
import DoiPhong from "./DoiPhong";
import TuNhac from "./TuNhac";
import NutInPhieu from "@/components/ui/NutInPhieu";
import SoLuot from "@/components/ui/SoLuot";

interface Moc {
  viec: string;
  luc: string | null;
  ai: string | null;
}
interface DichVu {
  id: string;
  dich_vu: string;
  trang_thai: string;
  phong: string | null;
  /** Đổi phòng ngay tại đây (23/09/2026) — máy chủ vẫn tự kiểm quyền + tiền. */
  phong_id?: string | null;
  routing_revision?: number | null;
  doi_phong_duoc?: boolean;
  so_tep: number;
  ly_do_khong_lam: string | null;
  ket_qua_ghi: string | null;
  /** Ghi chú khi bấm Xong / Đã lấy mẫu — phòng, điều dưỡng, đối tác (24/09). */
  ghi_chu?: string[];
  moc: Moc[];
}
interface SinhHieu {
  luc: string | null;
  nguoi_do: string | null;
  tam_thu: number | null;
  tam_truong: number | null;
  mach: number | null;
  nhiet_do: number | null;
  can_nang: number | null;
  chieu_cao: number | null;
  nhip_tho: number | null;
  spo2: number | null;
  bmi: number | null;
  muc_do_dau: number | null;
}
interface DuLieuXem {
  visit_id: string;
  khach: {
    id: string;
    ten: string;
    ma: string | null;
    so_booking?: number | null;
    so_tiep_don?: number | null;
  };
  /** Người xem đọc được hồ sơ khám → hiện [In phiếu khám] (cùng luật trang in). */
  in_phieu?: boolean;
  hanh_chinh: {
    check_in_luc: string | null;
    trang_thai_luot: string;
    dich_vu_kham: string | null;
    bac_si: string | null;
    da_do_sinh_hieu: boolean;
    /** "lượt trước" khi số đo của lượt khác cùng buổi (máy chủ trả). */
    sinh_hieu_nguon?: string | null;
    kham_xong_luc: string | null;
    dang_o: string | null;
    da_thu_dich_vu: boolean;
    da_thu_thuoc: boolean;
    dong_luot_luc: string | null;
    lich_tiep_theo: string | null;
  };
  dich_vu: DichVu[];
  su_kien: Moc[];
  /** Sổ sự kiện nghiệp vụ (nhóm 3, 24/09/2026) — projection dòng thời gian. */
  dong_thoi_gian?: { luc: string | null; nhan: string; ai: string | null }[];
  lich_su: { visit_id: string; luc: string | null; dich_vu: string | null; bac_si: string | null }[];
  sinh_hieu?: { luot_nay: SinhHieu[]; luot_truoc: SinhHieu[] };
  lam_sang?: {
    ky: { da_ky: boolean; luc: string | null; nguoi_ky: string | null };
    phien: { loai: string; vong: number; trang_thai: string; bac_si: string | null; bat_dau: string | null; xong: string | null; nguoi_bam_bat_dau: string | null }[];
    benh_an: {
      ly_do: string | null;
      chan_doan: Record<string, unknown> | null;
      ke_hoach: Record<string, unknown> | null;
      revision: number | null;
      co_don_nhap_cho_duyet: boolean;
    };
    phieu: { ma: string; nguoi_tao: string | null; nguoi_sua_cuoi: string | null; sua_luc: string | null } | null;
    vong_doc: { vong: number; dich_vu: string; can: string; yeu_cau: string; nguoi_quyet: string | null; ly_do: string | null }[];
    theo_doi: { trang_thai: string; ly_do: string; han: string | null; chu: string | null; dich_vu: string | null }[];
  };
  tai_chinh?: { id: string; loai: string; trang_thai: string; so_tien: number | null; luc: string | null; nguoi_thu: string | null; huy_luc: string | null; nguoi_huy: string | null; ly_do_huy: string | null }[];
  thuoc?: {
    thuoc: string;
    so_luong: number | string | null;
    don_vi: string | null;
    cach_dung: string | null;
    da_cap: number | null;
    trang_thai_cap: string | null;
    nguoi_cap: string | null;
    cap_luc: string | null;
    // CP6: dòng đã được bác sĩ đính chính — lịch sử, không còn trong đơn.
    da_dinh_chinh?: boolean;
    dinh_chinh_luc?: string | null;
    ly_do_dinh_chinh?: string | null;
  }[];
}

const TRANG_THAI_DV: Record<string, string> = {
  draft: "Nháp chờ bác sĩ duyệt",
  authorized: "Chờ xếp phòng",
  assigned: "Đã xếp phòng",
  in_progress: "Đang làm",
  performed: "Đã làm",
  not_performed: "Không làm được",
  cancelled: "Đã huỷ",
  khach_khong_lam: "Khách không làm",
};
const THANH_TOAN: Record<string, string> = { PAID: "Đã thu", VOIDED: "Đã huỷ" };
const THEO_DOI: Record<string, string> = {
  OPEN: "đang theo dõi",
  DONE: "đã xong",
  CANCELLED: "đã huỷ",
};
const YEU_CAU: Record<string, string> = {
  open: "đang chờ",
  // Chỉ định không làm được / khách không chọn — bác sĩ miễn hoặc chuyển theo dõi.
  needs_decision: "bác sĩ cần quyết",
  satisfied: "đạt",
  waived: "bác sĩ miễn",
  follow_up: "chuyển theo dõi",
};

function ngayGio(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return Number.isNaN(d.getTime())
    ? "—"
    : d.toLocaleString("vi-VN", { timeZone: "Asia/Ho_Chi_Minh", dateStyle: "short", timeStyle: "short" });
}
function tien(n: number | null): string {
  return n === null ? "—" : `${n.toLocaleString("vi-VN")} đ`;
}
function chu(v: unknown): string {
  if (v === null || v === undefined) return "";
  if (Array.isArray(v)) return v.map(chu).filter(Boolean).join(", ");
  if (typeof v === "object") return Object.values(v as Record<string, unknown>).map(chu).filter(Boolean).join(" · ");
  return String(v);
}

function Muc({ tieuDe, children }: { tieuDe: string; children: React.ReactNode }) {
  return (
    <section className="border-t border-line pt-3">
      <h3 className="mb-2 text-sm font-semibold text-ink">{tieuDe}</h3>
      {children}
    </section>
  );
}

function DongSinhHieu({ s }: { s: SinhHieu }) {
  return (
    <li className="text-xs text-ink-soft">
      <b className="text-ink">
        HA {s.tam_thu ?? "—"}/{s.tam_truong ?? "—"}
      </b>{" "}
      · Mạch {s.mach ?? "—"} · Nhiệt {s.nhiet_do ?? "—"} · Nhịp thở {s.nhip_tho ?? "—"} · SpO₂{" "}
      {s.spo2 ?? "—"} · Cân {s.can_nang ?? "—"} · Cao {s.chieu_cao ?? "—"} · BMI {s.bmi ?? "—"}
      {s.muc_do_dau !== null ? ` · Đau ${s.muc_do_dau}` : ""}
      <span className="text-ink-muted">
        {" "}
        — {s.nguoi_do ?? "?"}, {ngayGio(s.luc)}
      </span>
    </li>
  );
}

export default function XemLuot({
  visitId,
  onDong,
}: {
  visitId: string;
  onDong: () => void;
}) {
  const [dangXem, setDangXem] = useState(visitId);
  // Kết quả gắn với MÃ lượt đã hỏi — đổi lượt thì bản cũ tự thành "đang tải",
  // không cần xoá state đồng bộ trong effect.
  const [kq, setKq] = useState<{ id: string; dl?: DuLieuXem; loi?: string } | null>(null);
  const [lanNap, setLanNap] = useState(0);
  const dongRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    let huy = false;
    void docBang<DuLieuXem>("xem-luot", { luot: dangXem }).then((r) => {
      if (huy) return;
      setKq(r.ok ? { id: dangXem, dl: r.data } : { id: dangXem, loi: r.loi });
    });
    return () => {
      huy = true;
    };
  }, [dangXem, lanNap]);

  useEffect(() => {
    dongRef.current?.focus();
    const esc = (e: KeyboardEvent) => {
      if (e.key === "Escape") onDong();
    };
    window.addEventListener("keydown", esc);
    return () => window.removeEventListener("keydown", esc);
  }, [onDong]);

  const dl = kq?.id === dangXem ? (kq.dl ?? null) : null;
  const loi = kq?.id === dangXem ? (kq.loi ?? null) : null;
  const hc = dl?.hanh_chinh;
  const ls = dl?.lam_sang;

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-ink/40 p-0 sm:p-4"
      onClick={onDong}
      role="presentation"
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="xem-luot-tieu-de"
        className="min-h-full w-full max-w-3xl bg-surface p-4 shadow-panel sm:my-8 sm:min-h-0 sm:rounded-card sm:p-5"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-3 flex items-start justify-between gap-2">
          <div className="min-w-0">
            <h2 id="xem-luot-tieu-de" className="text-base font-semibold text-ink">
              Xem lại lượt khám{dl ? ` — ${dl.khach.ten}` : ""}
            </h2>
            <p className="flex flex-wrap items-center gap-1.5 text-xs text-ink-muted">
              <SoLuot booking={dl?.khach.so_booking} checkin={dl?.khach.so_tiep_don} />
              {dl?.khach.ma ? `${dl.khach.ma} · ` : ""}Chỉ xem — không sửa được ở đây.
            </p>
          </div>
          {/* IN PHIẾU Ở MỌI KHÂU (Tuyền 27/09/2026): Xem lượt mở được từ tiếp
              đón, đo sinh hiệu, bàn khám, phòng dịch vụ, quầy thu, nhà thuốc,
              hành trình, trưởng ca — nên nút in đặt ở ĐÂY là có ở mọi khâu. */}
          {dl?.in_phieu ? (
            <NutInPhieu href={`/print/phieu-kham/${visitId}`} size="md">
              In phiếu khám
            </NutInPhieu>
          ) : null}
          <button
            ref={dongRef}
            type="button"
            onClick={onDong}
            aria-label="Đóng"
            className="shrink-0 rounded-control p-1 text-ink-muted hover:bg-surface-sunken"
          >
            <X className="size-5" aria-hidden="true" />
          </button>
        </div>

        {dangXem !== visitId ? (
          <Button size="sm" variant="ghost" className="mb-2" onClick={() => setDangXem(visitId)}>
            ← Về lượt đang xem
          </Button>
        ) : null}

        {!dl ? (
          <p className={`text-sm ${loi ? "text-danger" : "text-ink-muted"}`} role={loi ? "alert" : undefined}>
            {loi ?? "Đang tải…"}
          </p>
        ) : (
          <div className="grid gap-3">
            {hc ? (
              <Muc tieuDe="Hành trình">
                <dl className="grid grid-cols-2 gap-x-3 gap-y-1 text-xs sm:grid-cols-3">
                  <Truong nhan="Check-in" gia={ngayGio(hc.check_in_luc)} />
                  <Truong nhan="Loại khám" gia={hc.dich_vu_kham ?? "—"} />
                  <Truong nhan="Bác sĩ" gia={hc.bac_si ?? "—"} />
                  <Truong
                    nhan="Sinh hiệu"
                    gia={
                      hc.da_do_sinh_hieu
                        ? `Đã đo${hc.sinh_hieu_nguon ? ` (${hc.sinh_hieu_nguon})` : ""}`
                        : "Chưa đo"
                    }
                  />
                  <Truong nhan="Khám xong" gia={ngayGio(hc.kham_xong_luc)} />
                  <Truong nhan="Đang ở" gia={hc.dong_luot_luc ? "Đã về" : (hc.dang_o ?? "—")} />
                  <Truong nhan="Thu dịch vụ" gia={hc.da_thu_dich_vu ? "Đã thu" : "Chưa thu"} />
                  <Truong nhan="Thu thuốc" gia={hc.da_thu_thuoc ? "Đã thu" : "—"} />
                  <Truong nhan="Đóng lượt" gia={ngayGio(hc.dong_luot_luc)} />
                  <Truong nhan="Lịch tiếp theo" gia={ngayGio(hc.lich_tiep_theo)} />
                </dl>
              </Muc>
            ) : null}

            {dl.sinh_hieu ? (
              <Muc tieuDe="Sinh hiệu">
                {dl.sinh_hieu.luot_nay.length === 0 ? (
                  <p className="text-xs text-ink-muted">Lượt này chưa đo.</p>
                ) : (
                  <ul className="grid gap-1">
                    {dl.sinh_hieu.luot_nay.map((s, i) => (
                      <DongSinhHieu key={`n${i}`} s={s} />
                    ))}
                  </ul>
                )}
                {dl.sinh_hieu.luot_truoc.length > 0 ? (
                  <details className="mt-2">
                    <summary className="cursor-pointer text-xs font-semibold text-ink-soft">
                      Các lần đo ở lượt trước ({dl.sinh_hieu.luot_truoc.length})
                    </summary>
                    <ul className="mt-1 grid gap-1">
                      {dl.sinh_hieu.luot_truoc.map((s, i) => (
                        <DongSinhHieu key={`t${i}`} s={s} />
                      ))}
                    </ul>
                  </details>
                ) : null}
              </Muc>
            ) : null}

            {ls ? (
              <Muc tieuDe="Khám & bệnh án">
                <p className="text-xs text-ink-soft">
                  {ls.ky.da_ky
                    ? `Đã hoàn tất · ${ls.ky.nguoi_ky ?? "?"} · ${ngayGio(ls.ky.luc)}`
                    : "Chưa hoàn tất khám"}
                  {ls.benh_an.revision ? ` · bản ${ls.benh_an.revision}` : ""}
                  {ls.benh_an.co_don_nhap_cho_duyet ? " · có đơn thuốc thư ký nhập chờ bác sĩ duyệt" : ""}
                </p>
                {ls.phien.length > 0 ? (
                  <ul className="mt-1 grid gap-0.5 text-xs text-ink-soft">
                    {ls.phien.map((p) => (
                      <li key={p.vong}>
                        {p.loai === "PRIMARY" ? "Khám" : `Đọc kết quả (vòng ${p.vong})`}: {p.bac_si ?? "—"} ·{" "}
                        {ngayGio(p.bat_dau)} → {ngayGio(p.xong)}
                        {p.nguoi_bam_bat_dau && p.nguoi_bam_bat_dau !== p.bac_si
                          ? ` · ${p.nguoi_bam_bat_dau} bấm bắt đầu`
                          : ""}
                      </li>
                    ))}
                  </ul>
                ) : null}
                {ls.phieu ? (
                  <p className="mt-1 text-xs text-ink-soft">
                    Phiếu {ls.phieu.ma}: {ls.phieu.nguoi_tao ?? "?"} nhập
                    {ls.phieu.nguoi_sua_cuoi && ls.phieu.nguoi_sua_cuoi !== ls.phieu.nguoi_tao
                      ? ` · ${ls.phieu.nguoi_sua_cuoi} sửa cuối`
                      : ""}{" "}
                    · {ngayGio(ls.phieu.sua_luc)}
                  </p>
                ) : null}
                <dl className="mt-2 grid gap-1 text-xs">
                  <Truong nhan="Lý do khám" gia={ls.benh_an.ly_do ?? "—"} dai />
                  <Truong nhan="Chẩn đoán" gia={chu(ls.benh_an.chan_doan) || "—"} dai />
                  <Truong nhan="Xử trí / lời dặn / tái khám" gia={chu(ls.benh_an.ke_hoach) || "—"} dai />
                </dl>
                {ls.vong_doc.length > 0 ? (
                  <ul className="mt-2 grid gap-0.5 text-xs text-ink-soft">
                    {ls.vong_doc.map((v, i) => (
                      <li key={i}>
                        Vòng {v.vong} · {v.dich_vu} ({v.can === "VALID_RESULT" ? "cần kết quả" : "cần làm"}):{" "}
                        {YEU_CAU[v.yeu_cau] ?? v.yeu_cau}
                        {v.nguoi_quyet ? ` — ${v.nguoi_quyet}: ${v.ly_do ?? ""}` : ""}
                      </li>
                    ))}
                  </ul>
                ) : null}
                {ls.theo_doi.length > 0 ? (
                  <ul className="mt-2 grid gap-0.5 text-xs text-ink-soft">
                    {ls.theo_doi.map((t, i) => (
                      <li key={i}>
                        Theo dõi{t.dich_vu ? ` ${t.dich_vu}` : ""}: {t.ly_do} · {t.chu ?? "—"} · hạn{" "}
                        {ngayGio(t.han)} · {THEO_DOI[t.trang_thai] ?? t.trang_thai}
                      </li>
                    ))}
                  </ul>
                ) : null}
              </Muc>
            ) : null}

            <Muc tieuDe="Chỉ định & dịch vụ">
              {/* Chỉ định khách BỎ ở quầy không nằm trong danh sách việc — chỉ
                  một dòng ghi lại cho khỏi mất dấu (24/09/2026). */}
              {dl.dich_vu.some((d) => d.trang_thai === "khach_khong_lam") ? (
                <p className="mb-2 text-xs text-ink-muted">
                  Khách không làm:{" "}
                  {dl.dich_vu
                    .filter((d) => d.trang_thai === "khach_khong_lam")
                    .map((d) => d.dich_vu)
                    .join(", ")}
                </p>
              ) : null}
              {dl.dich_vu.every((d) => d.trang_thai === "khach_khong_lam") ? (
                <p className="text-xs text-ink-muted">Không có chỉ định.</p>
              ) : (
                <ul className="grid gap-2">
                  {dl.dich_vu.filter((d) => d.trang_thai !== "khach_khong_lam").map((d) => (
                    <li key={d.id} className="rounded-control bg-surface-muted px-3 py-2">
                      <p className="text-sm font-medium text-ink">
                        {d.dich_vu}{" "}
                        <span className="text-xs font-normal text-ink-muted">
                          · {TRANG_THAI_DV[d.trang_thai] ?? d.trang_thai}
                          {d.phong ? ` · ${d.phong}` : ""}
                          {d.so_tep ? ` · ${d.so_tep} tệp kết quả` : ""}
                        </span>
                      </p>
                      {d.ly_do_khong_lam ? (
                        <p className="text-xs text-warning">Lý do không làm: {d.ly_do_khong_lam}</p>
                      ) : null}
                      {d.ket_qua_ghi ? <p className="text-xs text-ink">Kết quả: {d.ket_qua_ghi}</p> : null}
                      {(d.ghi_chu ?? []).map((g) => (
                        <p key={g} className="whitespace-pre-wrap text-xs text-ink-soft">
                          Ghi chú: {g}
                        </p>
                      ))}
                      {d.doi_phong_duoc ? (
                        <DoiPhong
                          orderId={d.id}
                          phongHienTaiId={d.phong_id ?? null}
                          routingRevision={d.routing_revision ?? null}
                          choDoi
                          onDaDoi={() => setLanNap((n) => n + 1)}
                        />
                      ) : null}
                      <ol className="mt-1 grid gap-0.5 text-xs text-ink-soft">
                        {d.moc.map((m, i) => (
                          <li key={i}>
                            {gioVn(m.luc)} · {m.viec}
                            {m.ai ? ` — ${m.ai}` : ""}
                          </li>
                        ))}
                      </ol>
                    </li>
                  ))}
                </ul>
              )}
            </Muc>

            {dl.thuoc ? (
              <Muc tieuDe="Đơn thuốc & cấp thuốc">
                {dl.thuoc.length === 0 ? (
                  <p className="text-xs text-ink-muted">Không có đơn thuốc.</p>
                ) : (
                  <ul className="grid gap-1 text-xs text-ink-soft">
                    {dl.thuoc.map((t, i) => (
                      <li key={i} className={t.da_dinh_chinh ? "text-ink-muted" : undefined}>
                        <b className={t.da_dinh_chinh ? "line-through" : "text-ink"}>{t.thuoc}</b> ·{" "}
                        {t.so_luong ?? "—"} {t.don_vi ?? ""} · {t.cach_dung ?? ""} · đã cấp {t.da_cap ?? 0}
                        {t.nguoi_cap ? ` — ${t.nguoi_cap}, ${ngayGio(t.cap_luc)}` : ""}
                        {t.da_dinh_chinh
                          ? ` · bác sĩ đã đính chính ${ngayGio(t.dinh_chinh_luc ?? null)}: ${t.ly_do_dinh_chinh ?? ""}`
                          : ""}
                      </li>
                    ))}
                  </ul>
                )}
              </Muc>
            ) : null}

            {dl.tai_chinh ? (
              <Muc tieuDe="Thanh toán">
                {dl.tai_chinh.length === 0 ? (
                  <p className="text-xs text-ink-muted">Chưa có giao dịch.</p>
                ) : (
                  <ul className="grid gap-1 text-xs text-ink-soft">
                    {dl.tai_chinh.map((t) => (
                      <li key={t.id}>
                        <b className="text-ink">{t.loai === "thuoc" ? "Thuốc" : "Dịch vụ"}</b> · {tien(t.so_tien)} ·{" "}
                        {THANH_TOAN[t.trang_thai] ?? t.trang_thai} · {t.nguoi_thu ?? "—"}, {ngayGio(t.luc)}
                        {t.huy_luc
                          ? ` · ĐÃ HUỶ ${ngayGio(t.huy_luc)} — ${t.nguoi_huy ?? ""}: ${t.ly_do_huy ?? ""}`
                          : ""}
                      </li>
                    ))}
                  </ul>
                )}
              </Muc>
            ) : null}

            <Muc tieuDe="Tự nhắc tôi về khách này">
              <TuNhac clinicPatientId={dl.khach.id} visitId={dl.visit_id} />
            </Muc>

            <Muc tieuDe="Hành trình (sự kiện)">
              {!dl.dong_thoi_gian || dl.dong_thoi_gian.length === 0 ? (
                <p className="text-xs text-ink-muted">Chưa có sự kiện nào.</p>
              ) : (
                <ol className="grid gap-0.5 text-xs text-ink-soft">
                  {dl.dong_thoi_gian.map((e, i) => (
                    <li key={i}>
                      {ngayGio(e.luc)} · {e.nhan}
                      {e.ai ? ` — ${e.ai}` : ""}
                    </li>
                  ))}
                </ol>
              )}
            </Muc>

            <Muc tieuDe="Dòng thời gian thao tác">
              {dl.su_kien.length === 0 ? (
                <p className="text-xs text-ink-muted">Chưa có thao tác nào được ghi.</p>
              ) : (
                <ol className="grid gap-0.5 text-xs text-ink-soft">
                  {dl.su_kien.map((e, i) => (
                    <li key={i}>
                      {ngayGio(e.luc)} · {e.viec}
                      {e.ai ? ` — ${e.ai}` : ""}
                    </li>
                  ))}
                </ol>
              )}
            </Muc>

            {dl.lich_su.length > 0 ? (
              <Muc tieuDe="Các lượt trước">
                <ul className="grid gap-1">
                  {dl.lich_su.map((l) => (
                    <li key={l.visit_id}>
                      <button
                        type="button"
                        className="text-left text-xs text-brand-700 underline-offset-2 hover:underline"
                        onClick={() => setDangXem(l.visit_id)}
                      >
                        {ngayGio(l.luc)} · {l.dich_vu ?? "—"} · {l.bac_si ?? "—"}
                      </button>
                    </li>
                  ))}
                </ul>
              </Muc>
            ) : null}
          </div>
        )}
      </div>
    </div>
  );
}

function Truong({ nhan, gia, dai = false }: { nhan: string; gia: string; dai?: boolean }) {
  return (
    <div className={dai ? "col-span-full" : undefined}>
      <dt className="text-ink-faint">{nhan}</dt>
      <dd className="font-medium text-ink">{gia}</dd>
    </div>
  );
}
