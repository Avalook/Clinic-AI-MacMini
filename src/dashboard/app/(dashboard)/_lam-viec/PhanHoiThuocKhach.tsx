"use client";

// PHẢN HỒI SAU DÙNG THUỐC (10/10/2026) — khối trong khung khách (Quản lý khách
// hàng). Khách: "CSKH ghi phản hồi sau dùng thuốc vào bước chăm sóc khách như
// đang làm … bác sĩ mở hồ sơ là thấy, cần tư vấn thêm thì CSKH đặt lịch khám".
//
// Chọn lượt có đơn (mặc định lượt gần nhất) → ghi nội dung → dòng sổ chăm sóc
// `tuong_tac_cskh` loại PHAN_HOI_THUOC. Người ghi gỡ được dòng của mình (ẩn, còn
// dấu vết). [Đặt lịch khám] mở bộ đặt lịch SẴN CÓ của màn cha. Luật (lượt nào
// có đơn, ai gỡ được) ở `phan_hoi_thuoc_service.py`; ở đây chỉ vẽ.

import { useCallback, useEffect, useState } from "react";

import Button from "@/components/ui/Button";
import ChipChon from "@/components/ui/ChipChon";
import OChon from "@/components/ui/OChon";
import XacNhanTaiCho from "@/components/ui/XacNhanTaiCho";
import { fmtDate, fmtDayTime } from "@/lib/datetime";

import { useNgheBang } from "../dung-nghe-bang";

export interface PhanHoiThuoc {
  id: string;
  visit_id: string;
  noi_dung: string | null;
  kenh: string;
  luc: string | null;
  /** Ngày của lượt có đơn mà phản hồi nói tới. */
  luot_luc: string | null;
  nguoi_ghi: string | null;
  cua_toi: boolean;
}

interface LuotCoDon {
  visit_id: string;
  luc: string | null;
  bac_si: string | null;
  thuoc: string | null;
}

// Nhãn hiển thị (không phải luật) cho mã kênh máy chủ trả.
const NHAN_KENH: Record<string, string> = {
  GOI: "Gọi điện",
  ZALO: "Zalo",
  TRUC_TIEP: "Trực tiếp",
  SMS: "SMS",
};
const KENH_CHON = ["GOI", "ZALO", "TRUC_TIEP"] as const;

/** Một dòng phản hồi — dùng chung với màn bác sĩ (chỉ đọc). */
export function DongPhanHoiThuoc({ p }: { p: PhanHoiThuoc }) {
  return (
    <>
      <p className="whitespace-pre-wrap text-body text-ink">{p.noi_dung ?? "—"}</p>
      <p className="mt-1 text-meta text-ink-muted">
        Đơn ngày {p.luot_luc ? fmtDate(p.luot_luc) : "—"} · {NHAN_KENH[p.kenh] ?? p.kenh}
        {" · "}
        {p.nguoi_ghi ?? "—"} · {p.luc ? fmtDayTime(p.luc) : "—"}
      </p>
    </>
  );
}

export default function PhanHoiThuocKhach({
  clinicPatientId,
  onDatLichKham,
}: {
  clinicPatientId: string;
  /** Có = hiện [Đặt lịch khám] — màn cha mở bộ đặt lịch sẵn có. */
  onDatLichKham?: () => void;
}) {
  const [data, setData] = useState<{ luot_co_don: LuotCoDon[]; items: PhanHoiThuoc[] } | null>(
    null,
  );
  const [loiDoc, setLoiDoc] = useState<string | null>(null);
  const [luot, setLuot] = useState("");
  const [kenh, setKenh] = useState<string>("GOI");
  const [noiDung, setNoiDung] = useState("");
  const [dang, setDang] = useState(false);
  const [loiGhi, setLoiGhi] = useState<string | null>(null);
  const [goDangHoi, setGoDangHoi] = useState<string | null>(null);

  const duong = `/api/cskh/khach/${clinicPatientId}`;

  const [lan, setLan] = useState(0);
  const napLai = useCallback(() => setLan((n) => n + 1), []);
  // Người khác ghi / gỡ ở màn khác → khối này tự cập nhật (NOTIFY sẵn có).
  useNgheBang(["tuong_tac_cskh"], napLai);

  useEffect(() => {
    let huy = false;
    void (async () => {
      try {
        const r = await fetch(`${duong}?xem=phan-hoi-thuoc`, { cache: "no-store" });
        const d = (await r.json().catch(() => null)) as
          | { luot_co_don?: LuotCoDon[]; items?: PhanHoiThuoc[]; message?: string }
          | null;
        if (huy) return;
        if (!r.ok) {
          setLoiDoc(d?.message ?? "Không đọc được phản hồi thuốc.");
          return;
        }
        setLoiDoc(null);
        setData({ luot_co_don: d?.luot_co_don ?? [], items: d?.items ?? [] });
      } catch {
        if (!huy) setLoiDoc("Mất kết nối — không đọc được phản hồi thuốc.");
      }
    })();
    return () => {
      huy = true;
    };
  }, [duong, lan]);

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
      napLai();
      return r.ok;
    } catch {
      setLoiGhi("Mất kết nối — CHƯA lưu.");
      return false;
    } finally {
      setDang(false);
    }
  };

  if (loiDoc && !data) {
    return (
      <p role="alert" className="text-meta text-danger">
        {loiDoc}
      </p>
    );
  }
  if (!data) return <p className="text-meta text-ink-faint">Đang tải…</p>;

  const coDon = data.luot_co_don.length > 0;
  const luotChon = luot || data.luot_co_don[0]?.visit_id || "";

  return (
    <div className="space-y-2">
      {coDon ? (
        <>
          <OChon
            value={luotChon}
            onChange={(e) => setLuot(e.target.value)}
            aria-label="Lượt có đơn thuốc"
            className="w-full"
          >
            {data.luot_co_don.map((l) => (
              <option key={l.visit_id} value={l.visit_id}>
                {l.luc ? fmtDate(l.luc) : "—"}
                {l.bac_si ? ` · ${l.bac_si}` : ""}
                {l.thuoc ? ` · ${l.thuoc}` : ""}
              </option>
            ))}
          </OChon>
          <div className="flex flex-wrap gap-1.5">
            {KENH_CHON.map((k) => (
              <ChipChon
                key={k}
                kieu="mot"
                ten={`kenh-phan-hoi-${clinicPatientId}`}
                chon={kenh === k}
                onDoi={() => setKenh(k)}
              >
                {NHAN_KENH[k]}
              </ChipChon>
            ))}
          </div>
          <textarea
            value={noiDung}
            onChange={(e) => setNoiDung(e.target.value)}
            rows={2}
            maxLength={2000}
            placeholder="Khách dùng thuốc thấy thế nào (bắt buộc)"
            aria-label="Nội dung phản hồi sau dùng thuốc"
            className="w-full rounded-control border border-line bg-surface px-3 py-2 text-body text-ink placeholder:text-ink-faint"
          />
          <div className="flex flex-wrap justify-end gap-2">
            {onDatLichKham ? (
              <Button size="lg" variant="secondary" onClick={onDatLichKham}>
                Đặt lịch khám
              </Button>
            ) : null}
            <Button
              size="lg"
              variant="soft"
              disabled={dang || noiDung.trim() === ""}
              onClick={() =>
                void gui({
                  thao_tac: "phan-hoi-thuoc",
                  visit_id: luotChon || null,
                  kenh,
                  noi_dung: noiDung.trim(),
                }).then((ok) => {
                  if (ok) setNoiDung("");
                })
              }
            >
              Lưu phản hồi
            </Button>
          </div>
        </>
      ) : (
        <p className="text-meta text-ink-faint">Khách chưa có lượt khám nào có đơn thuốc.</p>
      )}
      {loiGhi ? (
        <p role="alert" className="text-meta text-danger">
          {loiGhi}
        </p>
      ) : null}
      {data.items.length === 0 ? (
        coDon ? <p className="text-meta text-ink-faint">Chưa có phản hồi nào.</p> : null
      ) : (
        <ul className="max-h-60 space-y-2 overflow-y-auto overscroll-contain">
          {data.items.map((p) => (
            <li key={p.id} className="rounded-control bg-surface-muted px-3 py-2">
              <DongPhanHoiThuoc p={p} />
              {p.cua_toi && goDangHoi !== p.id ? (
                <Button size="sm" variant="ghost" disabled={dang} onClick={() => setGoDangHoi(p.id)}>
                  Gỡ
                </Button>
              ) : null}
              {goDangHoi === p.id ? (
                <div className="mt-2">
                  <XacNhanTaiCho
                    cau="Gỡ phản hồi này? (vẫn lưu dấu vết ai gỡ)"
                    nhanDongY="Gỡ"
                    dangGui={dang}
                    onThoi={() => setGoDangHoi(null)}
                    onDongY={() =>
                      void gui({ thao_tac: "go-phan-hoi-thuoc", phan_hoi_id: p.id }).then(() =>
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
    </div>
  );
}
