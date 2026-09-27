"use client";

// KHUNG PHẢI CỦA MỘT KHÁCH — dùng CHUNG ở Quản lý khách hàng (CSKH) và Tiếp đón
// (lễ tân). Tuyền 27/09/2026: "khung làm việc của CSKH chưa dễ cho việc ghi chú
// và tự nhắc lịch cho chính mình cho bệnh nhân này … Lễ tân cũng nên có … cần có
// chỗ xem hết mọi thứ của khách đó ở màn của người đó, không miss gì."
//
// Ba khối, một component:
//   1. Ghi chú về khách — sổ chung (ai ghi, lúc nào); người ghi gỡ được dòng
//      của mình → /api/cskh/khach/[id] → `ghi_chu_khach_service.py`.
//   2. Tự nhắc tôi — `TuNhac` sẵn có (→ /api/nhac-viec), cùng khối ở Xem lượt.
//   3. Mọi thứ của khách — lịch sắp tới / đã qua, lượt gần nhất, chỉ định chưa
//      làm, tiền đã trả / còn phải thu, hẹn tái khám bác sĩ đặt. Máy chủ gom và
//      tính (dùng lại hoá đơn của quầy thu); ở đây chỉ vẽ.

import { useCallback, useEffect, useState, type ReactNode } from "react";

import Button from "@/components/ui/Button";
import Chip, { type ChipTone } from "@/components/ui/Chip";
import XacNhanTaiCho from "@/components/ui/XacNhanTaiCho";
import { fmtDate, fmtDayTime } from "@/lib/datetime";

import NutXemLuot from "./NutXemLuot";
import TuNhac from "./TuNhac";

interface GhiChu {
  id: string;
  noi_dung: string;
  tao_luc: string;
  nguoi_ghi: string | null;
  cua_toi: boolean;
}

interface Lich {
  id: string;
  luc: string | null;
  trang_thai: string;
  dich_vu: string | null;
  bac_si: string | null;
  ly_do_huy?: string | null;
}

interface TomTat {
  lich_sap_toi: Lich[];
  lich_da_qua: Lich[];
  luot_gan_nhat: {
    visit_id: string;
    trang_thai: string;
    check_in_luc: string | null;
    kham_xong_luc: string | null;
    dong_luot_luc: string | null;
    dich_vu: string | null;
    bac_si: string | null;
    dang_o: string | null;
  }[];
  chi_dinh_chua_lam: {
    id: string;
    visit_id: string;
    ten: string;
    trang_thai: string;
    phong: string | null;
    luc: string | null;
  }[];
  tien: {
    da_tra: number;
    so_lan_tra: number;
    tra_lan_cuoi: string | null;
    con_phai_thu: number;
  };
  hen_tai_kham: {
    id: string;
    ngay_hen: string | null;
    trang_thai: string;
    ket_qua: string | null;
    bac_si: string | null;
  }[];
  so_ghi_chu: number;
}

// Nhãn hiển thị (không phải luật) cho mã trạng thái máy chủ trả.
const NHAN_LICH: Record<string, [string, ChipTone]> = {
  SCHEDULED: ["Chờ xác nhận", "neutral"],
  CSKH_CONFIRMED: ["Chờ bác sĩ", "neutral"],
  CONFIRMED: ["Đã đặt", "info"],
  CHECKED_IN: ["Đã check-in", "run"],
  COMPLETED: ["Đã khám", "success"],
  CANCELLED: ["Đã huỷ", "neutral"],
  NO_SHOW: ["Không đến", "warning"],
  DOCTOR_DECLINED: ["BS từ chối", "warning"],
};
const NHAN_CHI_DINH: Record<string, string> = {
  authorized: "Chờ xếp phòng",
  assigned: "Đã xếp phòng",
  in_progress: "Đang làm",
};
const NHAN_TAI_KHAM: Record<string, [string, ChipTone]> = {
  CHO_GOI: ["Chờ gọi", "warning"],
  DA_GOI: ["Đã gọi", "success"],
  KHONG_CAN: ["Không cần", "neutral"],
};

const tien = (n: number) => `${n.toLocaleString("vi-VN")} đ`;

function nhanLuot(l: TomTat["luot_gan_nhat"][number]): [string, ChipTone] {
  if (l.trang_thai === "INCOMPLETE") return ["Về giữa chừng", "warning"];
  if (l.dong_luot_luc) return ["Đã về", "neutral"];
  if (l.kham_xong_luc) return ["Khám xong", "success"];
  return [l.dang_o ? `Đang ở ${l.dang_o}` : "Đang trong lượt", "run"];
}

function Khoi({ tieuDe, children }: { tieuDe: string; children: ReactNode }) {
  return (
    <section className="space-y-2 border-t border-hairline pt-3 first:border-t-0 first:pt-0">
      <h3 className="text-label font-semibold uppercase tracking-wide text-ink-muted">
        {tieuDe}
      </h3>
      {children}
    </section>
  );
}

function Trong({ children }: { children: ReactNode }) {
  return <p className="text-meta text-ink-faint">{children}</p>;
}

export default function KhungKhach({ clinicPatientId }: { clinicPatientId: string }) {
  const [ghiChu, setGhiChu] = useState<GhiChu[] | null>(null);
  const [tomTat, setTomTat] = useState<TomTat | null>(null);
  const [loiDoc, setLoiDoc] = useState<string | null>(null);
  const [noiDung, setNoiDung] = useState("");
  const [dang, setDang] = useState(false);
  const [loiGhi, setLoiGhi] = useState<string | null>(null);
  const [goDangHoi, setGoDangHoi] = useState<string | null>(null);

  const duong = `/api/cskh/khach/${clinicPatientId}`;

  const docGhiChu = useCallback(async (): Promise<GhiChu[] | null> => {
    const r = await fetch(`${duong}?xem=ghi-chu`, { cache: "no-store" });
    const d = (await r.json().catch(() => null)) as { items?: GhiChu[] } | null;
    return r.ok ? (d?.items ?? []) : null;
  }, [duong]);

  const docTomTat = useCallback(async (): Promise<TomTat | string> => {
    const r = await fetch(`${duong}?xem=tom-tat`, { cache: "no-store" });
    const d = (await r.json().catch(() => null)) as
      | (TomTat & { message?: string; error?: string })
      | null;
    if (!r.ok || !d) return d?.message ?? d?.error ?? "Không đọc được dữ liệu khách.";
    return d;
  }, [duong]);

  useEffect(() => {
    let huy = false;
    void Promise.all([docGhiChu(), docTomTat()]).then(([g, t]) => {
      if (huy) return;
      if (g) setGhiChu(g);
      if (typeof t === "string") setLoiDoc(t);
      else setTomTat(t);
    });
    return () => {
      huy = true;
    };
  }, [docGhiChu, docTomTat]);

  const gui = async (than: unknown): Promise<boolean> => {
    setDang(true);
    setLoiGhi(null);
    try {
      const r = await fetch(duong, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(than),
      });
      const d = (await r.json().catch(() => null)) as { message?: string; error?: string } | null;
      if (!r.ok) setLoiGhi(d?.message ?? d?.error ?? "Không lưu được.");
      const moi = await docGhiChu();
      if (moi) setGhiChu(moi);
      return r.ok;
    } catch {
      setLoiGhi("Mất kết nối — CHƯA lưu.");
      return false;
    } finally {
      setDang(false);
    }
  };

  return (
    <div
      aria-label="Khung làm việc với khách"
      className="space-y-3 rounded-card border border-line bg-surface p-3 shadow-card"
    >
      <Khoi tieuDe={`Ghi chú về khách${ghiChu && ghiChu.length ? ` (${ghiChu.length})` : ""}`}>
        <textarea
          value={noiDung}
          onChange={(e) => setNoiDung(e.target.value)}
          rows={2}
          maxLength={2000}
          placeholder="Ghi chú cho mọi người cùng thấy (vd: khách dặn chỉ gọi sau 17h)"
          aria-label="Nội dung ghi chú về khách"
          className="w-full rounded-control border border-line bg-surface px-3 py-2 text-body text-ink placeholder:text-ink-faint"
        />
        <div className="flex justify-end">
          <Button
            size="lg"
            variant="soft"
            disabled={dang || noiDung.trim() === ""}
            onClick={() =>
              void gui({ thao_tac: "ghi", noi_dung: noiDung.trim() }).then((ok) => {
                if (ok) setNoiDung("");
              })
            }
          >
            Lưu ghi chú
          </Button>
        </div>
        {loiGhi ? (
          <p role="alert" className="text-meta text-danger">
            {loiGhi}
          </p>
        ) : null}
        {ghiChu === null ? (
          <Trong>Đang tải ghi chú…</Trong>
        ) : ghiChu.length === 0 ? (
          <Trong>Chưa có ghi chú nào.</Trong>
        ) : (
          <ul className="max-h-60 space-y-2 overflow-y-auto overscroll-contain">
            {ghiChu.map((g) => (
              <li key={g.id} className="rounded-control bg-surface-muted px-3 py-2">
                <p className="whitespace-pre-wrap text-body text-ink">{g.noi_dung}</p>
                <div className="mt-1 flex flex-wrap items-center gap-2 text-meta text-ink-muted">
                  <span>
                    {g.nguoi_ghi ?? "—"} · {fmtDayTime(g.tao_luc)}
                  </span>
                  {g.cua_toi && goDangHoi !== g.id ? (
                    <Button size="sm" variant="ghost" disabled={dang} onClick={() => setGoDangHoi(g.id)}>
                      Gỡ
                    </Button>
                  ) : null}
                </div>
                {goDangHoi === g.id ? (
                  <div className="mt-2">
                    <XacNhanTaiCho
                      cau="Gỡ ghi chú này? (vẫn lưu dấu vết ai gỡ)"
                      nhanDongY="Gỡ"
                      dangGui={dang}
                      onThoi={() => setGoDangHoi(null)}
                      onDongY={() =>
                        void gui({ thao_tac: "go", ghi_chu_id: g.id }).then(() =>
                          setGoDangHoi(null),
                        )
                      }
                    />
                  </div>
                ) : null}
              </li>
            ))}
          </ul>
        )}
      </Khoi>

      <Khoi tieuDe="Tự nhắc tôi về khách này">
        <TuNhac clinicPatientId={clinicPatientId} />
      </Khoi>

      <Khoi tieuDe="Mọi thứ của khách">
        {loiDoc ? (
          <p role="alert" className="text-meta text-danger">
            {loiDoc}
          </p>
        ) : !tomTat ? (
          <Trong>Đang tải…</Trong>
        ) : (
          <TomTatKhach t={tomTat} />
        )}
      </Khoi>
    </div>
  );
}

function DongLich({ l }: { l: Lich }) {
  const [nhan, tone] = NHAN_LICH[l.trang_thai] ?? [l.trang_thai, "neutral" as ChipTone];
  return (
    <li className="flex flex-wrap items-center gap-x-2 gap-y-1 text-meta text-ink">
      <span className="tabular-nums font-medium">{l.luc ? fmtDayTime(l.luc) : "—"}</span>
      <span className="min-w-0 flex-1 truncate">
        {l.dich_vu ?? "—"}
        {l.bac_si ? ` · ${l.bac_si}` : ""}
      </span>
      <Chip tone={tone}>{nhan}</Chip>
      {l.ly_do_huy ? (
        <span className="w-full text-ink-muted">Lý do: {l.ly_do_huy}</span>
      ) : null}
    </li>
  );
}

function TomTatKhach({ t }: { t: TomTat }) {
  return (
    <div className="space-y-3 text-meta">
      <div>
        <p className="font-semibold text-ink">Lịch sắp tới</p>
        {t.lich_sap_toi.length === 0 ? (
          <Trong>Không có lịch sắp tới.</Trong>
        ) : (
          <ul className="mt-1 space-y-1">
            {t.lich_sap_toi.map((l) => (
              <DongLich key={l.id} l={l} />
            ))}
          </ul>
        )}
      </div>

      <div>
        <p className="font-semibold text-ink">Lượt khám gần nhất</p>
        {t.luot_gan_nhat.length === 0 ? (
          <Trong>Chưa có lượt khám nào.</Trong>
        ) : (
          <ul className="mt-1 space-y-1">
            {t.luot_gan_nhat.slice(0, 3).map((l) => {
              const [nhan, tone] = nhanLuot(l);
              return (
                <li key={l.visit_id} className="flex flex-wrap items-center gap-x-2 gap-y-1 text-ink">
                  <span className="tabular-nums font-medium">
                    {l.check_in_luc ? fmtDate(l.check_in_luc) : "—"}
                  </span>
                  <span className="min-w-0 flex-1 truncate">
                    {l.dich_vu ?? "—"}
                    {l.bac_si ? ` · ${l.bac_si}` : ""}
                  </span>
                  <Chip tone={tone}>{nhan}</Chip>
                  <NutXemLuot visitId={l.visit_id} nhan="Xem lượt" />
                </li>
              );
            })}
          </ul>
        )}
      </div>

      <div>
        <p className="font-semibold text-ink">Chỉ định chưa làm</p>
        {t.chi_dinh_chua_lam.length === 0 ? (
          <Trong>Không còn chỉ định nào chờ làm.</Trong>
        ) : (
          <ul className="mt-1 space-y-1">
            {t.chi_dinh_chua_lam.map((c) => (
              <li key={c.id} className="flex flex-wrap items-center gap-x-2 gap-y-1 text-ink">
                <span className="min-w-0 flex-1 truncate">{c.ten}</span>
                {c.phong ? <span className="text-ink-muted">{c.phong}</span> : null}
                <Chip tone="warning">{NHAN_CHI_DINH[c.trang_thai] ?? c.trang_thai}</Chip>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div>
        <p className="font-semibold text-ink">Tiền</p>
        <dl className="mt-1 grid grid-cols-[minmax(0,1fr)_auto] gap-x-2 gap-y-1 text-ink">
          <dt className="text-ink-muted">Đã trả ({t.tien.so_lan_tra} lần)</dt>
          <dd className="text-right tabular-nums">{tien(t.tien.da_tra)}</dd>
          <dt className="text-ink-muted">Còn phải thu</dt>
          <dd className="text-right tabular-nums">
            {t.tien.con_phai_thu > 0 ? (
              <Chip tone="warning">{tien(t.tien.con_phai_thu)}</Chip>
            ) : (
              tien(0)
            )}
          </dd>
        </dl>
      </div>

      <div>
        <p className="font-semibold text-ink">Hẹn tái khám (bác sĩ đặt)</p>
        {t.hen_tai_kham.length === 0 ? (
          <Trong>Không có hẹn tái khám.</Trong>
        ) : (
          <ul className="mt-1 space-y-1">
            {t.hen_tai_kham.map((h) => {
              const [nhan, tone] = NHAN_TAI_KHAM[h.trang_thai] ?? [h.trang_thai, "neutral" as ChipTone];
              return (
                <li key={h.id} className="flex flex-wrap items-center gap-x-2 gap-y-1 text-ink">
                  <span className="tabular-nums font-medium">
                    {h.ngay_hen ? fmtDate(h.ngay_hen) : "—"}
                  </span>
                  <span className="min-w-0 flex-1 truncate text-ink-muted">{h.bac_si ?? ""}</span>
                  <Chip tone={tone}>{nhan}</Chip>
                </li>
              );
            })}
          </ul>
        )}
      </div>

      <div>
        <p className="font-semibold text-ink">Lịch đã qua</p>
        {t.lich_da_qua.length === 0 ? (
          <Trong>Chưa có lịch nào đã qua.</Trong>
        ) : (
          <ul className="mt-1 space-y-1">
            {t.lich_da_qua.map((l) => (
              <DongLich key={l.id} l={l} />
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
