"use client";

// CÁC THAO TÁC TẠI CHỖ của menu ⋯ một dòng lịch hẹn (Tuyền bấm thật 29/09/2026:
// "Gọi / ghi chăm sóc", "Huỷ lịch (ghi lý do)" chỉ là link sang /customers — rời
// màn, mở danh sách khách, không làm đúng việc theo tên). Cùng kiểu với Đổi lịch
// tại chỗ: popover neo dòng (<768px thành bottom sheet). ("Mở hồ sơ khách" là
// link sang Danh sách bệnh nhân `?chon=` — Tuyền chốt, không làm ở đây.)
//
//   · HuyLichTaiCho     → PATCH /api/appointments {action:"cancel", ly_do_huy_ma}
//                          (booking_service: bắt buộc mã lý do, "Khác" phải viết).
//   · GhiChamSocTaiCho  → POST /api/cskh/tuong-tac — CÙNG đường + khoá chống ghi
//                          trùng với nút gọi ở Quản lý khách hàng (HanhDongTrangThai).
//   · DoiDichVuKhamTaiCho → GET/POST /api/appointments/doi-dich-vu-kham (V5,
//                          30/09/2026): máy chủ trả danh sách loại khám + đổi được
//                          không, vì sao; đổi sau check-in thì khách được xếp lại
//                          hàng chờ đầu tiên theo loại mới.
//
// CHỈ VẼ. Danh mục lý do huỷ là danh mục chung (lib/ly-do-huy.ts, kiểm chống lệch
// với máy chủ); ai được làm gì do máy chủ quyết.

import { useEffect, useState } from "react";

import Button, { buttonClass } from "@/components/ui/Button";
import ChipChon from "@/components/ui/ChipChon";
import PopoverNeo from "@/components/ui/PopoverNeo";
import { fmtTime, ngayVN } from "@/lib/datetime";
import { doctorName } from "@/lib/doctor-name";
import { nhanLoi } from "@/lib/loi-api";
import { LY_DO_HUY, LY_DO_HUY_THU_TU } from "@/lib/ly-do-huy";
import { dayShort, fmtDayMonth } from "@/lib/roster";

import { dinhDanhThaoTac, khoaThaoTac, xongThaoTac } from "../customers/khoa-mot-lan";
import { ChonDichVuDatLichChip, type NhomDichVuDatLich } from "./ChonDichVuDatLich";

/** Những gì dòng lịch đã có sẵn — không gọi máy chủ chỉ để vẽ đầu hộp. */
export interface LichTaiCho {
  id: string;
  slot_start: string;
  clinic_patient_id: string;
  ten: string;
  sdt: string | null;
  bac_si: string | null;
  dich_vu: string | null;
}

function DauLich({ tieuDe, lich }: { tieuDe: string; lich: LichTaiCho }) {
  const ngay = ngayVN(lich.slot_start);
  return (
    <div className="flex min-w-0 items-center gap-3">
      <span
        aria-hidden
        className="grid size-9 shrink-0 place-items-center rounded-full bg-brand-50 text-emph font-semibold text-brand-700"
      >
        {lich.ten.trim().split(/\s+/).pop()?.charAt(0).toUpperCase() || "?"}
      </span>
      <div className="min-w-0">
        <p className="truncate text-emph font-semibold text-ink">
          {tieuDe} · {lich.ten || "—"}
        </p>
        <p className="truncate text-meta text-ink-muted">
          Lịch: {dayShort(ngay)} {fmtDayMonth(ngay)} · {fmtTime(lich.slot_start)}
          {lich.bac_si ? ` · ${doctorName(lich.bac_si)}` : ""}
          {lich.dich_vu ? ` · ${lich.dich_vu}` : ""}
        </p>
      </div>
    </div>
  );
}

function Loi({ chu }: { chu: string | null }) {
  return chu ? (
    <p role="alert" className="rounded-control bg-danger-bg px-3 py-2 text-meta text-danger">
      {chu}
    </p>
  ) : null;
}

const O_CHU =
  "w-full rounded-control border border-line bg-surface px-3 py-2 text-body text-ink placeholder:text-ink-faint";

/* ───────────────────────────── Huỷ lịch ───────────────────────────── */

export function HuyLichTaiCho({
  lich,
  neo,
  onDong,
  onXong,
}: {
  lich: LichTaiCho;
  neo: HTMLElement | null;
  onDong: () => void;
  onXong: (cau: string) => void;
}) {
  const [ma, setMa] = useState<string | null>(null);
  const [ghi, setGhi] = useState("");
  const [dang, setDang] = useState(false);
  const [loi, setLoi] = useState<string | null>(null);
  const canViet = ma === "KHAC";
  const du = ma !== null && (!canViet || ghi.trim() !== "");

  async function huy() {
    if (!du || dang) return;
    setDang(true);
    setLoi(null);
    const res = await fetch("/api/appointments", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        id: lich.id,
        action: "cancel",
        ly_do_huy_ma: ma,
        cancellation_reason: ghi.trim() || null,
      }),
    }).catch(() => null);
    setDang(false);
    if (!res) {
      setLoi("Mất kết nối — lịch CHƯA huỷ. Thử lại.");
      return;
    }
    if (!res.ok) {
      setLoi(nhanLoi(await res.json().catch(() => null), "Không huỷ được lịch."));
      return;
    }
    onDong();
    onXong(`Đã huỷ lịch của ${lich.ten}.`);
  }

  const chan = (
    <div className="flex flex-col gap-2">
      <Loi chu={loi} />
      <div className="flex flex-wrap items-center justify-end gap-2">
        <Button variant="ghost" size="md" onClick={onDong}>
          Thôi
        </Button>
        <Button variant="danger" size="md" disabled={!du || dang} onClick={() => void huy()}>
          {dang ? "Đang huỷ…" : "Huỷ lịch"}
        </Button>
      </div>
    </div>
  );

  return (
    <PopoverNeo neo={neo} onDong={onDong} dau={<DauLich tieuDe="Huỷ lịch" lich={lich} />} chan={chan}>
      <fieldset className="flex flex-col gap-2">
        <legend className="mb-2 text-body font-semibold text-ink">
          Lý do huỷ
        </legend>
        <div className="flex flex-col gap-1.5">
          {LY_DO_HUY_THU_TU.map((m) => (
            <ChipChon key={m} kieu="mot" ten={`huy-${lich.id}`} chon={ma === m} onDoi={() => setMa(m)}>
              {LY_DO_HUY[m]}
            </ChipChon>
          ))}
        </div>
        <label className="mt-2 block text-meta text-ink-muted" htmlFor={`huy-ghi-${lich.id}`}>
          {canViet ? "Viết rõ lý do (bắt buộc)" : "Ghi thêm (tuỳ chọn)"}
        </label>
        <textarea
          id={`huy-ghi-${lich.id}`}
          rows={2}
          maxLength={1000}
          value={ghi}
          onChange={(e) => setGhi(e.target.value)}
          placeholder="vd: khách đi công tác, hẹn gọi lại tuần sau"
          className={O_CHU}
        />
      </fieldset>
    </PopoverNeo>
  );
}

/* ───────────────────────── Gọi / ghi chăm sóc ───────────────────────── */

/** Kết quả cuộc gọi — cùng bộ nút gọi ở Quản lý khách hàng (HanhDongTrangThai);
 *  mã khớp `KET_QUA_HOP_LE` của máy chủ. */
export const KET_QUA_GOI: [string, string][] = [
  ["DA_LIEN_HE", "Đã liên hệ được"],
  ["CHUA_NGHE_MAY", "Không nghe máy"],
  ["KHONG_LIEN_LAC_DUOC", "Không liên lạc được"],
  ["HEN_GOI_LAI", "Hẹn gọi lại sau"],
];

export function GhiChamSocTaiCho({
  lich,
  neo,
  onDong,
  onXong,
}: {
  lich: LichTaiCho;
  neo: HTMLElement | null;
  onDong: () => void;
  onXong: (cau: string) => void;
}) {
  const [ketQua, setKetQua] = useState<string | null>(null);
  const [noiDung, setNoiDung] = useState("");
  const [dang, setDang] = useState(false);
  const [loi, setLoi] = useState<string | null>(null);

  async function luu() {
    if (!ketQua || dang) return;
    setDang(true);
    setLoi(null);
    // Khoá theo THAO TÁC (bấm đúp / gửi lại sau khi rớt mạng không ghi hai dòng)
    // — cùng cơ chế nút gọi ở Quản lý khách hàng.
    const thaoTac = dinhDanhThaoTac(lich.clinic_patient_id, lich.id, "NHAC_HEN", "menu-lich", ketQua);
    try {
      const res = await fetch("/api/cskh/tuong-tac", {
        method: "POST",
        headers: { "Content-Type": "application/json", "Idempotency-Key": khoaThaoTac(thaoTac) },
        body: JSON.stringify({
          clinic_patient_id: lich.clinic_patient_id,
          appointment_id: lich.id,
          loai: "NHAC_HEN",
          kenh: "GOI",
          ket_qua: ketQua,
          noi_dung: noiDung.trim() || null,
        }),
      });
      if (!res.ok) {
        // 4xx = máy chủ từ chối, chắc chắn chưa ghi → bỏ khoá. 5xx giữ khoá.
        if (res.status >= 400 && res.status < 500) xongThaoTac(thaoTac);
        setLoi(nhanLoi(await res.json().catch(() => null), "Không ghi được."));
        return;
      }
      xongThaoTac(thaoTac);
      onDong();
      onXong(`Đã ghi chăm sóc cho ${lich.ten}.`);
    } catch {
      setLoi("Mất kết nối — chưa chắc đã ghi. Bấm lại (không ghi trùng).");
    } finally {
      setDang(false);
    }
  }

  const chan = (
    <div className="flex flex-col gap-2">
      <Loi chu={loi} />
      <div className="flex flex-wrap items-center justify-end gap-2">
        <Button variant="ghost" size="md" onClick={onDong}>
          Thôi
        </Button>
        <Button variant="primary" size="md" disabled={!ketQua || dang} onClick={() => void luu()}>
          {dang ? "Đang lưu…" : "Lưu chăm sóc"}
        </Button>
      </div>
    </div>
  );

  return (
    <PopoverNeo neo={neo} onDong={onDong} dau={<DauLich tieuDe="Gọi / ghi chăm sóc" lich={lich} />} chan={chan}>
      <div className="flex flex-col gap-3">
        {lich.sdt ? (
          <a href={`tel:${lich.sdt}`} className={`${buttonClass("soft", "lg")} self-start tabular-nums`}>
            Gọi {lich.sdt}
          </a>
        ) : (
          <p className="text-meta text-ink-muted">Khách chưa có số điện thoại.</p>
        )}
        <fieldset className="flex flex-col gap-2">
          <legend className="mb-2 text-body font-semibold text-ink">
            Kết quả cuộc gọi
          </legend>
          <div className="flex flex-wrap gap-1.5">
            {KET_QUA_GOI.map(([m, nhan]) => (
              <ChipChon key={m} kieu="mot" ten={`goi-${lich.id}`} chon={ketQua === m} onDoi={() => setKetQua(m)}>
                {nhan}
              </ChipChon>
            ))}
          </div>
        </fieldset>
        <div>
          <label className="mb-1 block text-meta text-ink-muted" htmlFor={`goi-ghi-${lich.id}`}>
            Ghi chú
          </label>
          <textarea
            id={`goi-ghi-${lich.id}`}
            rows={3}
            maxLength={2000}
            value={noiDung}
            onChange={(e) => setNoiDung(e.target.value)}
            placeholder="vd: khách đang họp, gọi lại sau 17h"
            className={O_CHU}
          />
        </div>
      </div>
    </PopoverNeo>
  );
}

/* ───────────────────────── Đổi dịch vụ khám ───────────────────────── */

interface LuaChonDichVu {
  id: string;
  ten: string;
  hien_tai: boolean;
  /** Chọn là máy chủ từ chối (luật bác sĩ bắt buộc) — câu ở `ghi_chu`. */
  chan: boolean;
  ghi_chu: string | null;
}

interface GoiDoiDichVu {
  da_check_in: boolean;
  dich_vu_hien_tai: { id: string; ten: string | null } | null;
  duoc_doi: boolean;
  ly_do_khong_doi: string | null;
  lua_chon: LuaChonDichVu[];
  /** Cùng danh sách, gom theo nhóm đặt lịch (máy chủ gom). */
  nhom: NhomDichVuDatLich[];
}

export function DoiDichVuKhamTaiCho({
  lich,
  neo,
  onDong,
  onXong,
}: {
  lich: LichTaiCho;
  neo: HTMLElement | null;
  onDong: () => void;
  onXong: (cau: string) => void;
}) {
  const [goi, setGoi] = useState<{ data: GoiDoiDichVu | null; loi: string | null } | null>(null);
  const [chon, setChon] = useState<string | null>(null);
  const [dang, setDang] = useState(false);
  const [loi, setLoi] = useState<string | null>(null);

  useEffect(() => {
    let huy = false;
    const q = new URLSearchParams({ id: lich.id });
    void fetch(`/api/appointments/doi-dich-vu-kham?${q.toString()}`, { cache: "no-store" })
      .then(async (res) => {
        const body = await res.json().catch(() => null);
        if (huy) return;
        setGoi(
          res.ok
            ? { data: body as GoiDoiDichVu, loi: null }
            : { data: null, loi: nhanLoi(body, "Không đọc được danh sách dịch vụ khám.") },
        );
      })
      .catch(() => {
        if (!huy) setGoi({ data: null, loi: "Mất kết nối — thử lại." });
      });
    return () => {
      huy = true;
    };
  }, [lich.id]);

  const data = goi?.data ?? null;
  const muc = data?.lua_chon.find((x) => x.id === chon) ?? null;
  const du = !!data?.duoc_doi && !!muc && !muc.hien_tai && !muc.chan;

  async function doi() {
    if (!du || !muc || dang) return;
    setDang(true);
    setLoi(null);
    const res = await fetch("/api/appointments/doi-dich-vu-kham", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id: lich.id, service_type_id: muc.id }),
    }).catch(() => null);
    setDang(false);
    if (!res) {
      setLoi("Mất kết nối — dịch vụ CHƯA đổi. Thử lại.");
      return;
    }
    const body: unknown = await res.json().catch(() => null);
    if (!res.ok) {
      setLoi(nhanLoi(body as Parameters<typeof nhanLoi>[0], "Không đổi được dịch vụ khám."));
      return;
    }
    const canhBao = (body as { canh_bao?: string[] } | null)?.canh_bao ?? [];
    const nhac = canhBao.length ? ` Lưu ý: ${canhBao.join(" ")}` : "";
    const hang = data?.da_check_in ? " Khách được xếp lại hàng chờ theo dịch vụ mới." : "";
    onDong();
    onXong(`Đã đổi dịch vụ khám của ${lich.ten} sang ${muc.ten}.${hang}${nhac}`);
  }

  const chan = (
    <div className="flex flex-col gap-2">
      <Loi chu={loi} />
      <div className="flex flex-wrap items-center justify-end gap-2">
        <Button variant="ghost" size="md" onClick={onDong}>
          Thôi
        </Button>
        <Button variant="primary" size="md" disabled={!du || dang} onClick={() => void doi()}>
          {dang ? "Đang đổi…" : "Đổi dịch vụ"}
        </Button>
      </div>
    </div>
  );

  return (
    <PopoverNeo neo={neo} onDong={onDong} dau={<DauLich tieuDe="Đổi dịch vụ khám" lich={lich} />} chan={chan}>
      {goi === null ? (
        <p className="text-meta text-ink-muted">Đang tải danh sách dịch vụ khám…</p>
      ) : goi.loi ? (
        <Loi chu={goi.loi} />
      ) : data ? (
        <div className="flex flex-col gap-3">
          {data.ly_do_khong_doi ? (
            <p role="status" className="rounded-control bg-warning-bg px-3 py-2 text-meta text-warning">
              {data.ly_do_khong_doi}
            </p>
          ) : data.da_check_in ? (
            <p className="text-meta text-ink-muted">
              Khách đã check-in — đổi xong, khách được xếp lại hàng chờ theo dịch vụ mới.
            </p>
          ) : null}
          <div className="flex flex-col gap-2">
            <p className="text-body font-semibold text-ink">Dịch vụ khám</p>
            {/* Cùng nhóm với ô chọn lúc đặt lịch (Khám · Điều trị · Khác). */}
            <ChonDichVuDatLichChip
              nhom={data.nhom}
              ten={`dv-${lich.id}`}
              chon={chon}
              onChon={setChon}
              disabled={!data.duoc_doi}
            />
          </div>
        </div>
      ) : null}
    </PopoverNeo>
  );
}
