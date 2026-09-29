"use client";

// HÀNH TRÌNH KHÁCH — MỘT khung cho mọi màn (Tuyền chốt 29/09/2026, bản mẫu
// demo-di-phong/hanh-trinh.html).
//
//   · `DongHanhTrinhGon`   — mỗi khách một dòng: "Đang ở / Đang chờ / Đã về" +
//                            TÊN PHÒNG + chip giờ + thanh đoạn màu + x/y dịch vụ.
//   · `KhungHanhTrinh`     — khung đầy đủ: ĐANG Ở + TIẾP THEO, dòng thời gian dọc,
//                            dịch vụ song song mỗi chỉ định một thẻ.
//   · `PopupHanhTrinhKhach`— khung đầy đủ trong hộp thoại (trang chủ, Hành trình,
//                            Bàn khám).
//   · `HanhTrinhKhachTuTai`— dòng gọn + [Xem kỹ] mở khung ngay tại chỗ (Xem lượt).
//
// CHỈ VẼ. Máy chủ quyết khách đang ở đâu, bước nào xong / đang / chờ, giờ từng
// mốc (`GET /api/v1/luot-kham/visits/{id}/hanh-trinh-khach`, mọi thành viên nội
// bộ). Ở đây chỉ đổi thời điểm thành số phút theo đồng hồ (`lib/hanh-trinh-khach`).
//
// Màu (token sẵn có): xanh lá = xong · xanh dương = đang làm · cam = đang chờ ·
// tím = chờ kết quả đối tác (không giữ khách) · xám = chưa tới.

import { X } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";

import Button from "@/components/ui/Button";
import Chip from "@/components/ui/Chip";
import { doctorName } from "@/lib/doctor-name";
import {
  chipGon,
  demThe,
  dongDoSinhHieu,
  dongLanLam,
  dongPhuGon,
  ghiChuKham,
  gio,
  nhanThe,
  noiGon,
  phut,
  thoiGian,
  type BuocHanhTrinh,
  type DongLichSuPhong,
  type HanhTrinhGon,
  type HanhTrinhKhach,
  type TheDichVu,
  type TrangThaiBuoc,
  type TrangThaiThe,
} from "@/lib/hanh-trinh-khach";
import { khoang } from "@/lib/hanh-trinh";

import { useNgheBang } from "../dung-nghe-bang";
import { docBang } from "./api";

const BANG_NGHE = [
  "luot_dong_thoi_gian",
  "queue_entry",
  "service_order",
  "payment",
  "visit",
  "consultation",
] as const;

const MAU_DOAN: Record<TrangThaiBuoc, string> = {
  xong: "bg-success",
  dang: "bg-status-in-progress",
  cho: "bg-warning",
  doi_tac: "bg-status-dang-o",
  chua: "bg-surface-sunken",
  khong: "bg-surface-sunken",
};

/** Thanh đoạn màu — mỗi bước / mỗi dịch vụ một đoạn. */
export function ThanhDoan({ doan }: { doan: TrangThaiBuoc[] }) {
  if (doan.length === 0) return null;
  return (
    <div className="mt-1.5 flex gap-1" aria-hidden="true">
      {doan.map((d, i) => (
        <span key={i} className={`h-1.5 flex-1 rounded-chip ${MAU_DOAN[d]}`} />
      ))}
    </div>
  );
}

/** Đồng hồ vẽ lại mỗi 30 giây — "chờ 12′" phải nhích theo phút. */
export function useBayGio(): number {
  const [bayGio, setBayGio] = useState(() => Date.now());
  useEffect(() => {
    const t = setInterval(() => setBayGio(Date.now()), 30_000);
    return () => clearInterval(t);
  }, []);
  return bayGio;
}

/** Dòng gọn: "Đang ở  Phòng siêu âm 1  [đang làm từ 10:58 · 6′]" + thanh + dòng phụ. */
export function DongHanhTrinhGon({ gon, bayGio }: { gon: HanhTrinhGon; bayGio: number }) {
  const chip = chipGon(gon, bayGio);
  const phu = dongPhuGon(gon);
  return (
    <div className="min-w-0">
      <p className="flex flex-wrap items-center gap-x-2 gap-y-1">
        <span className="text-meta text-ink-muted">{gon.nhan}</span>
        <span className="text-emph font-semibold text-ink">{noiGon(gon)}</span>
        {chip ? (
          <Chip tone={chip.tone} className="tabular-nums">
            {chip.nhan}
          </Chip>
        ) : null}
      </p>
      <ThanhDoan doan={gon.doan} />
      {phu ? <p className="mt-1 text-meta text-ink-muted">{phu}</p> : null}
    </div>
  );
}

const CHAM: Record<TrangThaiBuoc, string> = {
  xong: "border-success bg-success",
  dang: "border-status-in-progress bg-status-in-progress ring-4 ring-status-in-progress-bg",
  cho: "border-warning bg-surface",
  doi_tac: "border-status-dang-o bg-status-dang-o",
  chua: "border-line bg-surface",
  khong: "border-line bg-surface-sunken",
};

const VIEN_THE: Record<TrangThaiThe, string> = {
  XONG: "border-l-success",
  DANG_LAM: "border-l-status-in-progress bg-status-in-progress-bg/30",
  CHO_LAM: "border-l-warning",
  CHO_THU: "border-l-warning",
  DOI_TAC: "border-l-status-dang-o",
  BO: "border-l-line",
};

const CHU_THE: Record<TrangThaiThe, string> = {
  XONG: "text-success",
  DANG_LAM: "text-status-in-progress",
  CHO_LAM: "text-warning",
  CHO_THU: "text-warning",
  DOI_TAC: "text-status-dang-o",
  BO: "text-ink-muted",
};

function TheDv({
  t,
  bayGio,
  dung,
  lichSu,
}: {
  t: TheDichVu;
  bayGio: number;
  dung: boolean;
  lichSu?: DongLichSuPhong[];
}) {
  // LÀM LẠI (29/09/2026): mỗi lần một dòng đủ vào / bắt đầu / xong — lần 1 vẫn
  // giữ; khi ấy giờ gộp của thẻ không in nữa (đã nằm trong dòng lần mới nhất).
  const cacLan = t.lan ?? [];
  const gioThe = cacLan.length > 1 ? "" : thoiGian(t, bayGio, dung);
  return (
    <div className={`rounded-card border border-l-4 border-hairline bg-surface p-3 ${VIEN_THE[t.trang_thai]}`}>
      <p className="flex flex-wrap items-center gap-2 text-emph font-semibold text-ink">
        {t.noi}
        {(t.so_lan ?? 1) >= 2 ? <Chip tone="warning">{`Làm lại · lần ${t.so_lan}`}</Chip> : null}
      </p>
      <p className="text-meta text-ink-soft">{t.ten}</p>
      <p className={`mt-2 flex items-center gap-1.5 text-body font-semibold tabular-nums ${CHU_THE[t.trang_thai]}`}>
        {t.trang_thai === "DANG_LAM" && !dung ? (
          <span className="size-2 rounded-full bg-current animate-pulse motion-reduce:animate-none" aria-hidden="true" />
        ) : null}
        {nhanThe(t, bayGio, dung)}
      </p>
      {gioThe ? <p className="mt-0.5 text-meta tabular-nums text-ink-muted">{gioThe}</p> : null}
      {cacLan.length > 1 ? (
        <ul className="mt-1 space-y-0.5 text-meta tabular-nums text-ink-muted">
          {cacLan.map((l) => (
            <li key={l.so}>{dongLanLam(l, bayGio, dung)}</li>
          ))}
        </ul>
      ) : null}
      {t.trang_thai === "DOI_TAC" ? (
        <p className="mt-0.5 text-meta text-ink-muted">
          {t.lay_mau ? `lấy mẫu ${gio(t.lay_mau)} · ` : ""}không giữ khách
        </p>
      ) : null}
      {lichSu && lichSu.length > 0 ? (
        // Lịch sử xếp / đổi phòng (Tuyền 29/09/2026): giờ · ai · A → B · lý do.
        <ul className="mt-2 space-y-0.5 border-t border-hairline pt-1.5" aria-label="Lịch sử xếp phòng">
          {lichSu.map((l, i) => (
            <li key={i} className="text-meta text-ink-muted">
              <span className="tabular-nums">{gio(l.luc)}</span> · {l.cau}
              {l.ai ? ` (${l.ai})` : ""}
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}

function tenAi(b: BuocHanhTrinh): string | null {
  if (!b.ai) return null;
  return b.ma === "KHAM" || b.ma === "DOC_KQ" ? `BS ${doctorName(b.ai)}` : b.ai;
}

function Buoc({
  b,
  cuoi,
  bayGio,
  dung,
  lichSu,
}: {
  b: BuocHanhTrinh;
  cuoi: boolean;
  bayGio: number;
  dung: boolean;
  lichSu?: Record<string, DongLichSuPhong[]>;
}) {
  const chuaToi = b.trang_thai === "chua" || b.trang_thai === "khong";
  // BƯỚC CHƯA XẢY RA (29/09/2026): chữ giữ chỗ xám "dự kiến", KHÔNG giờ.
  const duKien = b.du_kien === true;
  const meta = [
    b.ma === "LAM_DV" ? null : b.noi ? (b.noi_du_kien && !duKien ? `${b.noi} (dự kiến)` : b.noi) : null,
    tenAi(b),
    duKien ? null : b.trang_thai === "khong" ? "không làm" : thoiGian(b, bayGio, dung) || null,
  ].filter(Boolean);
  const ghi = b.ma === "KHAM" ? ghiChuKham(b) : b.ghi_chu;
  // Sinh hiệu đo lại — dòng RIÊNG, không gộp vào thời gian làm.
  const doLai = b.ma === "SINH_HIEU" ? dongDoSinhHieu(b) : "";
  return (
    <li className="flex gap-3">
      <div className="flex flex-col items-center" aria-hidden="true">
        <span className={`mt-1 size-3.5 shrink-0 rounded-full border-2 ${CHAM[b.trang_thai]}`} />
        {!cuoi ? (
          <span className={`mt-1 w-0.5 flex-1 ${b.trang_thai === "xong" ? "bg-success-bg" : "bg-hairline"}`} />
        ) : null}
      </div>
      <div className="min-w-0 flex-1 pb-4">
        <p className={`flex flex-wrap items-center gap-2 ${chuaToi ? "text-body font-medium text-ink-muted" : "text-emph font-semibold text-ink"}`}>
          {b.ten}
          {b.dich_vu && b.dich_vu.length > 0 ? <Chip tone="run">{demThe(b.dich_vu)}</Chip> : null}
          {duKien ? <Chip tone="neutral">dự kiến</Chip> : null}
        </p>
        {meta.length > 0 ? (
          <p className="text-meta tabular-nums text-ink-muted">{meta.join(" · ")}</p>
        ) : null}
        {doLai ? <p className="mt-0.5 text-meta tabular-nums text-ink-muted">{doLai}</p> : null}
        {ghi ? (
          <p className={`mt-1 text-meta ${duKien ? "text-ink-muted" : "text-ink-soft"}`}>{ghi}</p>
        ) : null}
        {b.dich_vu && b.dich_vu.length > 0 ? (
          <div className="mt-2 grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
            {b.dich_vu.map((t, i) => (
              <TheDv
                key={t.id ?? i}
                t={t}
                bayGio={bayGio}
                dung={dung}
                lichSu={t.id ? lichSu?.[t.id] : undefined}
              />
            ))}
          </div>
        ) : null}
      </div>
    </li>
  );
}

/** Khung đầy đủ: đầu ĐANG Ở + TIẾP THEO, dưới là dòng thời gian dọc. */
export function KhungHanhTrinh({ ht, bayGio }: { ht: HanhTrinhKhach; bayGio: number }) {
  const o = ht.gon;
  const dung = o.xong_buoi || o.trang_thai === "BO_VE";
  const p = dung ? null : phut(o.tu_luc, bayGio);
  const phu =
    o.trang_thai === "DANG_O"
      ? [o.tu_luc ? `đang làm từ ${gio(o.tu_luc)}` : "đang làm", p != null ? khoang(p) : null]
      : o.trang_thai === "DANG_CHO" || o.trang_thai === "DANG_GOI"
        ? [
            o.trang_thai === "DANG_GOI" ? "đang gọi vào" : null,
            p != null ? `chờ ${khoang(p)}` : null,
            o.stt != null ? `STT ${o.stt}` : null,
          ]
        : o.trang_thai === "DA_VE"
          ? [o.tu_luc ? `check-out ${gio(o.tu_luc)}` : null, "xong buổi"]
          : [];
  return (
    <div className="overflow-hidden rounded-card border border-hairline bg-surface">
      <div className="flex flex-wrap justify-between gap-4 bg-brand-600 p-4 text-white">
        <div className="min-w-0">
          <p className="text-label font-semibold uppercase tracking-wide text-brand-100">{o.nhan}</p>
          <p className="text-title font-semibold">{noiGon(o)}</p>
          {phu.filter(Boolean).length > 0 ? (
            <p className="mt-0.5 flex items-center gap-1.5 text-body tabular-nums">
              {o.trang_thai === "DANG_O" ? (
                <span className="size-2 rounded-full bg-current animate-pulse motion-reduce:animate-none" aria-hidden="true" />
              ) : null}
              {phu.filter(Boolean).join(" · ")}
            </p>
          ) : null}
        </div>
        {ht.tiep_theo.length > 0 ? (
          <div className="min-w-56 rounded-control bg-white/10 px-3 py-2">
            <p className="text-label font-semibold uppercase tracking-wide text-brand-100">Tiếp theo</p>
            <ul className="mt-0.5 space-y-0.5">
              {ht.tiep_theo.map((t, i) => (
                <li key={i} className="text-body">
                  <span className="font-semibold">{t.noi}</span>{" "}
                  <span className="text-meta text-brand-50">
                    {[
                      t.stt != null ? `STT ${t.stt}` : null,
                      t.so_nguoi_cho != null ? `chờ ${t.so_nguoi_cho} người` : null,
                      t.ghi_chu,
                      t.du_kien ? "dự kiến" : null,
                    ]
                      .filter(Boolean)
                      .join(" · ")}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        ) : null}
      </div>
      <ol className="p-4 pb-0" aria-label="Dòng thời gian hành trình">
        {ht.buoc.map((b, i) => (
          <Buoc
            key={b.ma}
            b={b}
            cuoi={i === ht.buoc.length - 1}
            bayGio={bayGio}
            dung={dung}
            lichSu={ht.lich_su_phong}
          />
        ))}
      </ol>
      <p className="border-t border-hairline px-4 py-2 text-meta text-ink-muted">
        Xanh lá = xong · xanh dương = đang làm · cam = đang chờ · tím = chờ kết quả đối tác
        (không giữ khách) · xám = chưa tới.
      </p>
    </div>
  );
}

/** Đọc khung đầy đủ của một lượt + nạp lại khi có tin bảng đổi (dòng SSE chung). */
function useHanhTrinhKhach(visitId: string) {
  const [kq, setKq] = useState<{ id: string; ht?: HanhTrinhKhach; loi?: string } | null>(null);
  const [lanNap, setLanNap] = useState(0);
  useEffect(() => {
    let huy = false;
    void docBang<HanhTrinhKhach>("hanh-trinh-khach", { luot: visitId }).then((r) => {
      if (huy) return;
      setKq(r.ok ? { id: visitId, ht: r.data } : { id: visitId, loi: r.loi });
    });
    return () => {
      huy = true;
    };
  }, [visitId, lanNap]);
  const napLai = useCallback(() => setLanNap((n) => n + 1), []);
  useNgheBang(BANG_NGHE, napLai);
  const dung = kq?.id === visitId;
  return { ht: dung ? (kq?.ht ?? null) : null, loi: dung ? (kq?.loi ?? null) : null };
}

/** Khung đầy đủ trong hộp thoại. */
export function PopupHanhTrinhKhach({
  visitId,
  ten,
  onDong,
}: {
  visitId: string;
  ten?: string | null;
  onDong: () => void;
}) {
  const { ht, loi } = useHanhTrinhKhach(visitId);
  const bayGio = useBayGio();
  const dongRef = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    dongRef.current?.focus();
    const esc = (e: KeyboardEvent) => {
      if (e.key === "Escape") onDong();
    };
    window.addEventListener("keydown", esc);
    return () => window.removeEventListener("keydown", esc);
  }, [onDong]);
  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-ink/40 p-0 sm:p-4"
      onClick={onDong}
      role="presentation"
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="hanh-trinh-khach-tieu-de"
        className="min-h-full w-full max-w-3xl bg-surface-muted p-4 shadow-panel sm:my-8 sm:min-h-0 sm:rounded-card"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-3 flex items-start justify-between gap-2">
          <h2 id="hanh-trinh-khach-tieu-de" className="text-title font-semibold text-ink">
            Hành trình khách{ten ? ` — ${ten}` : ""}
          </h2>
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
        {ht ? (
          <KhungHanhTrinh ht={ht} bayGio={bayGio} />
        ) : (
          <p className={`text-body ${loi ? "text-danger" : "text-ink-muted"}`} role={loi ? "alert" : undefined}>
            {loi ?? "Đang tải…"}
          </p>
        )}
      </div>
    </div>
  );
}

/** Nút [Xem hành trình ›] tự giữ popup — gắn vào dòng nào cũng được. */
export function NutXemHanhTrinh({
  visitId,
  ten,
  nhan = "Xem hành trình ›",
}: {
  visitId: string;
  ten?: string | null;
  nhan?: string;
}) {
  const [mo, setMo] = useState(false);
  return (
    <>
      <Button size="sm" variant="soft" onClick={() => setMo(true)}>
        {nhan}
      </Button>
      {mo ? <PopupHanhTrinhKhach visitId={visitId} ten={ten} onDong={() => setMo(false)} /> : null}
    </>
  );
}

/** Dòng gọn + [Xem kỹ] mở khung đầy đủ ngay tại chỗ — dùng trong Xem lượt. */
export function HanhTrinhKhachTuTai({ visitId }: { visitId: string }) {
  const { ht, loi } = useHanhTrinhKhach(visitId);
  const bayGio = useBayGio();
  const [moRong, setMoRong] = useState(false);
  if (!ht) {
    return loi ? (
      <p className="text-meta text-danger" role="alert">
        {loi}
      </p>
    ) : null;
  }
  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <DongHanhTrinhGon gon={ht.gon} bayGio={bayGio} />
        <Button size="sm" variant="soft" aria-expanded={moRong} onClick={() => setMoRong((v) => !v)}>
          {moRong ? "Thu gọn" : "Xem kỹ ›"}
        </Button>
      </div>
      {moRong ? <KhungHanhTrinh ht={ht} bayGio={bayGio} /> : null}
    </div>
  );
}
