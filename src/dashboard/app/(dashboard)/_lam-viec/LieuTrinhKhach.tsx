"use client";

// LIỆU TRÌNH CỦA KHÁCH — một dòng mỗi liệu trình, dùng CHUNG ở CSKH
// `/nhac-tai-kham` (tab Liệu trình) và khung khách `/customers` (08/10/2026,
// docs/KE-HOACH-LIEU-TRINH.md — luồng CSKH).
//
// Nút theo trạng thái máy chủ trả:
//   Đề xuất  → [Đăng ký] (1 buổi / cả lộ trình N buổi / số khác) · [Không đăng ký]
//   Đang làm → [Dừng] (lý do)       ·   Đã dừng → [Mở lại]
//   mọi trạng thái trừ Đã dừng → [Đặt lịch buổi kế] (bộ đặt lịch sẵn có của màn
//   cha, khoá đúng loại khám Điều trị của dịch vụ)
// Mỗi lệnh xong → thông báo kèm [Hoàn tác] (lệnh hoàn tác của máy chủ — lần sửa
// mới nhất). Tiền KHÔNG thu ở đây (Q3: thu ở quầy khi khách có mặt).
//
// Màn chỉ vẽ + gửi lệnh: quyền (crm.manage | booking.create), bản cũ (409),
// bấm hai lần (khoá theo revision) — máy chủ quyết. Không luật nghiệp vụ ở đây.

import { useCallback, useEffect, useState } from "react";
import { History } from "lucide-react";

import Button from "@/components/ui/Button";
import Chip, { type ChipTone } from "@/components/ui/Chip";
import ChipChon from "@/components/ui/ChipChon";
import NutHoanTac, { type DuLieuHoanTac, type KetQuaHoanTac } from "@/components/ui/NutHoanTac";
import OSo from "@/components/ui/OSo";
import ThongBaoHoanTac, { type ThongBao } from "@/components/ui/ThongBaoHoanTac";
import XacNhanTaiCho from "@/components/ui/XacNhanTaiCho";
import { fmtDate, fmtDayTime } from "@/lib/datetime";
import {
  docSoBuoiDangKy,
  NHAN_HANH_DONG_LT,
  NHAN_TRANG_THAI_LT,
  nhanTienDo,
  type DongLichSuLieuTrinh,
  type LieuTrinh,
  type TrangThaiLieuTrinh,
} from "@/lib/lieu-trinh-cskh";
import { tienVn } from "@/lib/phieu-kham";

import { useNgheBang } from "../dung-nghe-bang";

const TONE: Record<TrangThaiLieuTrinh, ChipTone> = {
  DE_XUAT: "warning",
  DANG_LAM: "run",
  XONG: "success",
  DUNG: "neutral",
};

type KetQua = { ok: true } | { ok: false; loi: string };

async function guiLenh(id: string, than: Record<string, unknown>): Promise<KetQua> {
  try {
    const r = await fetch(`/api/cskh/lieu-trinh/${id}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(than),
    });
    if (r.ok) return { ok: true };
    const d = (await r.json().catch(() => null)) as { message?: string; error?: string } | null;
    return { ok: false, loi: d?.message ?? d?.error ?? `Không ghi được (HTTP ${r.status}).` };
  } catch {
    return { ok: false, loi: "Mất kết nối — CHƯA ghi, bấm lại." };
  }
}

async function docLichSu(id: string): Promise<{ revision: number; dong: DongLichSuLieuTrinh[] } | string> {
  try {
    const r = await fetch(`/api/cskh/lieu-trinh/${id}`, { cache: "no-store" });
    const d = (await r.json().catch(() => null)) as
      | { revision?: number; dong?: DongLichSuLieuTrinh[]; message?: string }
      | null;
    if (!r.ok || !d) return d?.message ?? "Không đọc được lịch sử sửa.";
    return { revision: d.revision ?? 0, dong: d.dong ?? [] };
  } catch {
    return "Mất kết nối — không đọc được lịch sử sửa.";
  }
}

/** Lệnh hoàn tác: lần sửa MỚI NHẤT người bấm (máy chủ đánh dấu `hoan_tac_duoc`). */
export function hoanTacLieuTrinh(id: string): (d: DuLieuHoanTac) => Promise<KetQuaHoanTac> {
  return async () => {
    const ls = await docLichSu(id);
    if (typeof ls === "string") return { ok: false, loi: ls };
    const dong = ls.dong.find((x) => x.loai === "SUA" && x.hoan_tac_duoc);
    if (!dong) return { ok: false, loi: "Không còn lần sửa nào hoàn tác được." };
    return guiLenh(id, {
      thao_tac: "hoan-tac",
      lich_su_id: dong.id,
      expected_revision: ls.revision,
      idempotency_key: `lt-${id}-hoan-tac-${dong.id}-r${ls.revision}`,
    });
  };
}

function nhanDongLichSu(d: DongLichSuLieuTrinh): string {
  if (d.loai === "GAN") return `Gắn buổi ${d.buoi_so ?? "?"}`;
  if (d.loai === "GO") return `Gỡ buổi ${d.buoi_so ?? "?"}`;
  return NHAN_HANH_DONG_LT[d.hanh_dong ?? ""] ?? d.hanh_dong ?? "Sửa";
}

function LichSuSua({ id, onDaHoanTac }: { id: string; onDaHoanTac: () => void }) {
  const [mo, setMo] = useState(false);
  const [ls, setLs] = useState<DongLichSuLieuTrinh[] | string | null>(null);
  const nap = () => {
    setLs(null);
    void docLichSu(id).then((kq) => setLs(typeof kq === "string" ? kq : kq.dong));
  };
  return (
    <div className="w-full">
      <Button
        size="sm"
        variant="ghost"
        aria-expanded={mo}
        onClick={() => {
          if (!mo) nap();
          setMo(!mo);
        }}
      >
        <History className="size-3.5" aria-hidden="true" />
        Lịch sử sửa
      </Button>
      {!mo ? null : ls === null ? (
        <p className="text-meta text-ink-faint">Đang tải…</p>
      ) : typeof ls === "string" ? (
        <p role="alert" className="text-meta text-danger">
          {ls}
        </p>
      ) : ls.length === 0 ? (
        <p className="text-meta text-ink-faint">Chưa có lần sửa nào.</p>
      ) : (
        <ul className="mt-1 space-y-1 border-l border-hairline pl-3">
          {ls.map((d) => (
            <li key={`${d.loai}-${d.id}`} className="flex flex-wrap items-center gap-x-2 gap-y-1 text-meta text-ink">
              <span className="font-medium">{nhanDongLichSu(d)}</span>
              <span className="text-ink-muted">
                {d.boi ?? "hệ thống"} · {d.luc ? fmtDayTime(d.luc) : "—"}
              </span>
              {d.hoan_tac_duoc ? (
                <NutHoanTac
                  goi={hoanTacLieuTrinh(id)}
                  moTa="Rút lại lần sửa này"
                  onXong={() => {
                    nap();
                    onDaHoanTac();
                  }}
                />
              ) : null}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

type Mo = null | "dang-ky" | "dung";

export function DongLieuTrinh({
  lt,
  coQuyen,
  hienKhach = false,
  kemLichSu = false,
  onDatLich,
  onDaDoi,
  onBao,
}: {
  lt: LieuTrinh;
  /** Máy chủ nói người này đăng ký / dừng / mở lại được (crm.manage | booking.create). */
  coQuyen: boolean;
  /** Dòng ở danh sách CSKH: hiện tên + mã + số khách. */
  hienKhach?: boolean;
  /** Khung khách: mở rộng "Lịch sử sửa". */
  kemLichSu?: boolean;
  /** Mở bộ đặt lịch sẵn có của màn cha (khoá loại khám Điều trị của dịch vụ). */
  onDatLich?: (lt: LieuTrinh) => void;
  onDaDoi: () => void;
  onBao: (tb: ThongBao) => void;
}) {
  const [mo, setMo] = useState<Mo>(null);
  const [soChon, setSoChon] = useState<string>(String(lt.so_buoi));
  const [lyDo, setLyDo] = useState("");
  const [dang, setDang] = useState(false);
  const [loi, setLoi] = useState<string | null>(null);

  const soDangKy = docSoBuoiDangKy(soChon);
  const lam = async (than: Record<string, unknown>, cau: string) => {
    setDang(true);
    setLoi(null);
    const kq = await guiLenh(lt.id, { expected_revision: lt.revision, ...than });
    setDang(false);
    if (!kq.ok) {
      setLoi(kq.loi);
      onDaDoi();
      return;
    }
    setMo(null);
    onBao({ cau, goi: hoanTacLieuTrinh(lt.id) });
    onDaDoi();
  };
  const ten = `${lt.service_name}${lt.ten_khach ? ` — ${lt.ten_khach}` : ""}`;

  return (
    <li className="space-y-1.5 rounded-control border border-line bg-surface px-3 py-2">
      <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
        {hienKhach ? (
          <span className="min-w-0 text-body font-semibold text-ink">
            {lt.ten_khach ?? "—"}
            {lt.ma_khach ? <span className="font-normal text-ink-muted"> · {lt.ma_khach}</span> : null}
            {lt.sdt ? <span className="font-normal text-ink-muted"> · {lt.sdt}</span> : null}
          </span>
        ) : null}
        <span className={`min-w-0 flex-1 text-body ${hienKhach ? "text-ink-soft" : "font-semibold text-ink"}`}>
          {lt.service_name}
        </span>
        <Chip tone={TONE[lt.trang_thai]}>{NHAN_TRANG_THAI_LT[lt.trang_thai]}</Chip>
      </div>
      <p className="text-meta tabular-nums text-ink">
        {nhanTienDo(lt)} · đã trả {lt.da_tra} · còn lại {lt.con_lai} buổi
        {lt.tien_con_lai > 0 ? ` · còn phải trả ${tienVn(lt.tien_con_lai)}` : ""}
      </p>
      <p className="text-meta text-ink-muted">
        Đề xuất bởi {lt.de_xuat_boi ?? "—"}
        {lt.tao_luc ? ` · ${fmtDayTime(lt.tao_luc)}` : ""}
        {lt.dang_ky_luc ? ` · đăng ký ${fmtDate(lt.dang_ky_luc)}${lt.dang_ky_boi ? ` (${lt.dang_ky_boi})` : ""}` : ""}
        {` · lần cuối ${lt.lan_cuoi ? fmtDate(lt.lan_cuoi) : "chưa làm buổi nào"}`}
        {lt.lich_hen_sap_toi ? ` · có lịch ${fmtDayTime(lt.lich_hen_sap_toi)}` : ""}
      </p>
      {lt.ghi_chu_lo_trinh ? (
        <p className="whitespace-pre-wrap text-meta text-ink-soft">Lộ trình: {lt.ghi_chu_lo_trinh}</p>
      ) : null}
      {lt.trang_thai === "DUNG" && lt.ly_do_dung ? (
        <p className="text-meta text-ink-muted">Lý do dừng: {lt.ly_do_dung}</p>
      ) : null}

      <div className="flex flex-wrap items-center gap-2">
        {coQuyen && lt.trang_thai === "DE_XUAT" && mo === null ? (
          <Button size="sm" variant="primary" disabled={dang} onClick={() => setMo("dang-ky")}>
            Đăng ký
          </Button>
        ) : null}
        {onDatLich && lt.trang_thai !== "DUNG" ? (
          <Button
            size="sm"
            variant="secondary"
            disabled={!lt.service_type_id}
            title={lt.service_type_id ? undefined : "Dịch vụ chưa có loại khám nhóm Điều trị — sửa ở Danh mục"}
            onClick={() => onDatLich(lt)}
          >
            Đặt lịch buổi kế
          </Button>
        ) : null}
        {coQuyen && (lt.trang_thai === "DE_XUAT" || lt.trang_thai === "DANG_LAM") && mo === null ? (
          <Button size="sm" variant="ghost" disabled={dang} onClick={() => setMo("dung")}>
            {lt.trang_thai === "DE_XUAT" ? "Không đăng ký" : "Dừng"}
          </Button>
        ) : null}
        {coQuyen && lt.trang_thai === "DUNG" ? (
          <Button
            size="sm"
            variant="secondary"
            disabled={dang}
            onClick={() =>
              void lam(
                { thao_tac: "mo-lai", idempotency_key: `lt-${lt.id}-mo-lai-r${lt.revision}` },
                `Đã mở lại liệu trình ${ten}`,
              )
            }
          >
            Mở lại
          </Button>
        ) : null}
      </div>

      {mo === "dang-ky" ? (
        <XacNhanTaiCho
          cau={`Khách đăng ký liệu trình ${lt.service_name}? Tiền thu ở quầy khi khách đến.`}
          nhanDongY={soDangKy ? `Đăng ký ${soDangKy} buổi` : "Đăng ký"}
          choDongY={soDangKy !== null}
          dangGui={dang}
          onThoi={() => setMo(null)}
          onDongY={() =>
            void lam(
              {
                thao_tac: "dang-ky",
                so_buoi: soDangKy,
                idempotency_key: `lt-${lt.id}-dang-ky-${soDangKy}-r${lt.revision}`,
              },
              `Đã đăng ký ${soDangKy} buổi ${ten}`,
            )
          }
        >
          <div role="radiogroup" aria-label="Số buổi đăng ký" className="flex flex-wrap items-center gap-2">
            <ChipChon kieu="mot" ten={`so-buoi-${lt.id}`} chon={soChon === "1"} onDoi={() => setSoChon("1")}>
              1 buổi
            </ChipChon>
            {lt.so_buoi > 1 ? (
              <ChipChon
                kieu="mot"
                ten={`so-buoi-${lt.id}`}
                chon={soChon === String(lt.so_buoi)}
                onDoi={() => setSoChon(String(lt.so_buoi))}
              >
                Cả lộ trình {lt.so_buoi} buổi
              </ChipChon>
            ) : null}
            <label className="flex items-center gap-1.5 text-meta text-ink-muted">
              Số khác
              <OSo nguyen value={soChon} onChange={setSoChon} donVi="buổi" aria-label="Số buổi khác" />
            </label>
          </div>
        </XacNhanTaiCho>
      ) : null}

      {mo === "dung" ? (
        <XacNhanTaiCho
          cau={
            lt.trang_thai === "DE_XUAT"
              ? "Khách không đăng ký liệu trình này? (mở lại được)"
              : `Dừng liệu trình?${lt.con_tra_truoc > 0 ? ` Khách còn ${lt.con_tra_truoc} buổi đã trả — hoàn tiền ở quầy.` : ""} (mở lại được)`
          }
          nhanDongY={lt.trang_thai === "DE_XUAT" ? "Không đăng ký" : "Dừng"}
          dangGui={dang}
          onThoi={() => setMo(null)}
          onDongY={() =>
            void lam(
              {
                thao_tac: "dung",
                ly_do: lyDo.trim() || (lt.trang_thai === "DE_XUAT" ? "Khách không đăng ký" : null),
                idempotency_key: `lt-${lt.id}-dung-r${lt.revision}`,
              },
              lt.trang_thai === "DE_XUAT" ? `Đã ghi khách không đăng ký ${ten}` : `Đã dừng liệu trình ${ten}`,
            )
          }
        >
          <input
            value={lyDo}
            onChange={(e) => setLyDo(e.target.value)}
            maxLength={500}
            placeholder="Lý do (không bắt buộc) — vd khách bận, đổi ý"
            aria-label="Lý do dừng"
            className="w-full rounded-control border border-line bg-surface px-3 py-2 text-body text-ink placeholder:text-ink-faint"
          />
        </XacNhanTaiCho>
      ) : null}

      {loi ? (
        <p role="alert" className="text-meta text-danger">
          {loi}
        </p>
      ) : null}
      {kemLichSu ? <LichSuSua id={lt.id} onDaHoanTac={onDaDoi} /> : null}
    </li>
  );
}

/** Khối "Liệu trình" của khung khách: MỌI liệu trình của một khách
 *  (`GET /lieu-trinh/theo-khach`), nút theo cờ quyền máy chủ trả. */
export function LieuTrinhCuaKhach({
  clinicPatientId,
  onDatLich,
}: {
  clinicPatientId: string;
  onDatLich?: (lt: LieuTrinh) => void;
}) {
  const [ds, setDs] = useState<LieuTrinh[] | string | null>(null);
  const [coQuyen, setCoQuyen] = useState(false);
  const [lan, setLan] = useState(0);
  const [thongBao, setThongBao] = useState<ThongBao | null>(null);
  const dongThongBao = useCallback(() => setThongBao(null), []);
  const napLai = useCallback(() => setLan((n) => n + 1), []);
  useNgheBang(["lieu_trinh", "lieu_trinh_buoi", "lieu_trinh_tra_truoc"], napLai);

  useEffect(() => {
    let huy = false;
    void (async () => {
      try {
        const r = await fetch(`/api/cskh/lieu-trinh?khach=${clinicPatientId}`, { cache: "no-store" });
        const d = (await r.json().catch(() => null)) as
          | { lieu_trinh?: LieuTrinh[]; quyen_cskh?: boolean; message?: string; error?: string }
          | null;
        if (huy) return;
        if (r.status === 403) {
          setDs("Tài khoản này không xem được liệu trình.");
          return;
        }
        if (!r.ok || !d) {
          setDs(d?.message ?? d?.error ?? "Không đọc được liệu trình của khách.");
          return;
        }
        setDs(d.lieu_trinh ?? []);
        setCoQuyen(d.quyen_cskh === true);
      } catch {
        if (!huy) setDs("Mất kết nối — không đọc được liệu trình của khách.");
      }
    })();
    return () => {
      huy = true;
    };
  }, [clinicPatientId, lan]);

  return (
    <>
      <ThongBaoHoanTac thongBao={thongBao} onDong={dongThongBao} onHoanTacXong={napLai} />
      {ds === null ? (
        <p className="text-meta text-ink-faint">Đang tải…</p>
      ) : typeof ds === "string" ? (
        <p role="alert" className="text-meta text-danger">
          {ds}
        </p>
      ) : ds.length === 0 ? (
        <p className="text-meta text-ink-faint">Khách chưa có liệu trình nào.</p>
      ) : (
        <ul className="space-y-2">
          {ds.map((lt) => (
            <DongLieuTrinh
              key={`${lt.id}-${lt.revision}`}
              lt={lt}
              coQuyen={coQuyen}
              kemLichSu
              onDatLich={onDatLich}
              onDaDoi={napLai}
              onBao={setThongBao}
            />
          ))}
        </ul>
      )}
    </>
  );
}
