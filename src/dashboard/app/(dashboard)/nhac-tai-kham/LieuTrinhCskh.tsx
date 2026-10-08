"use client";

// TAB "LIỆU TRÌNH" CỦA CSKH (08/10/2026, docs/KE-HOACH-LIEU-TRINH.md — luồng CSKH).
//
// Ba danh sách máy chủ lọc (`GET /lieu-trinh/cskh`), MỘT KHÁCH MỘT DÒNG mỗi
// liệu trình:
//   0. Sắp hết lộ trình (08/10/2026, ĐẦU tab) — còn ≤ 1 buổi, hoặc đã dùng hết
//      buổi trả trước; chip lý do máy chủ tính; [Đã xử lý] ẩn tới mốc sau.
//   1. Đề xuất chưa đăng ký — bác sĩ đề xuất, khách chưa nhận.
//   2. Đang dở, quá X ngày chưa quay lại — không còn buổi đang chờ làm.
// Mặc định máy chủ bỏ khách đã có lịch hẹn sắp tới (đã đặt thì khỏi gọi) — trừ
// "Sắp hết" (có lịch buổi cuối vẫn cần gọi tư vấn thêm buổi).
// Danh sách này CHỈ ở màn CSKH + khung khách — không sinh dòng ở phòng / hàng
// chờ / Hành trình / TV (phạm vi hiển thị đã chốt).

import { useCallback, useEffect, useState, type ReactNode } from "react";

import ChipLoc from "@/components/ui/ChipLoc";
import ThongBaoHoanTac, { type ThongBao } from "@/components/ui/ThongBaoHoanTac";
import { QUA_NGAY_CHON, QUA_NGAY_MAC_DINH, type LieuTrinh, type LoaiDsCskh } from "@/lib/lieu-trinh-cskh";

import DatLichBuoiKe, { type MucChon } from "../_lam-viec/DatLichBuoiKe";
import { DongLieuTrinh } from "../_lam-viec/LieuTrinhKhach";
import { useNgheBang } from "../dung-nghe-bang";

type Doc = LieuTrinh[] | string | null;

async function docDs(loai: LoaiDsCskh, quaNgay: number): Promise<LieuTrinh[] | string> {
  const q = new URLSearchParams({ loai });
  if (loai === "dang_do") q.set("qua_ngay", String(quaNgay));
  try {
    const r = await fetch(`/api/cskh/lieu-trinh?${q.toString()}`, { cache: "no-store" });
    const d = (await r.json().catch(() => null)) as
      | { lieu_trinh?: LieuTrinh[]; message?: string; error?: string }
      | null;
    if (r.status === 403) return "Tài khoản này không có quyền xem liệu trình của CSKH.";
    if (!r.ok || !d) return d?.message ?? d?.error ?? "Không đọc được danh sách liệu trình.";
    return d.lieu_trinh ?? [];
  } catch {
    return "Mất kết nối — không đọc được danh sách liệu trình.";
  }
}

function Nhom({
  tieuDe,
  moTa,
  ds,
  trong,
  dauNhom,
  onDatLich,
  onDaDoi,
  onBao,
}: {
  tieuDe: string;
  moTa: string;
  ds: Doc;
  trong: string;
  dauNhom?: ReactNode;
  onDatLich: (lt: LieuTrinh) => void;
  onDaDoi: () => void;
  onBao: (tb: ThongBao) => void;
}) {
  return (
    <section className="space-y-2">
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <h2 className="text-base font-semibold text-ink">{tieuDe}</h2>
        {Array.isArray(ds) ? (
          <span className="rounded-chip bg-brand-50 px-2 py-0.5 text-xs font-medium text-brand-700">
            {ds.length} khách
          </span>
        ) : null}
        <p className="text-xs text-ink-muted">{moTa}</p>
      </div>
      {dauNhom}
      {ds === null ? (
        <p className="text-meta text-ink-faint">Đang tải…</p>
      ) : typeof ds === "string" ? (
        // Không đọc được ≠ không ai cần gọi — nói thẳng.
        <p role="alert" className="rounded-card border border-danger bg-danger-bg px-4 py-2.5 text-sm text-danger">
          {ds} Danh sách trống ở đây KHÔNG có nghĩa là không ai cần gọi.
        </p>
      ) : ds.length === 0 ? (
        <p className="rounded-card border border-line bg-surface px-4 py-6 text-center text-sm text-ink-muted shadow-card">
          {trong}
        </p>
      ) : (
        <ul className="space-y-2">
          {ds.map((lt) => (
            <DongLieuTrinh
              key={`${lt.id}-${lt.revision}`}
              lt={lt}
              coQuyen
              hienKhach
              onDatLich={onDatLich}
              onDaDoi={onDaDoi}
              onBao={onBao}
            />
          ))}
        </ul>
      )}
    </section>
  );
}

export default function LieuTrinhCskh({
  doctors,
  locations,
}: {
  doctors: MucChon[];
  locations: MucChon[];
}) {
  const [quaNgay, setQuaNgay] = useState<number>(QUA_NGAY_MAC_DINH);
  const [sapHet, setSapHet] = useState<Doc>(null);
  const [deXuat, setDeXuat] = useState<Doc>(null);
  const [dangDo, setDangDo] = useState<Doc>(null);
  const [lan, setLan] = useState(0);
  const [datLich, setDatLich] = useState<LieuTrinh | null>(null);
  const [thongBao, setThongBao] = useState<ThongBao | null>(null);
  const dongThongBao = useCallback(() => setThongBao(null), []);
  const napLai = useCallback(() => setLan((n) => n + 1), []);
  // `tuong_tac_cskh`: [Đã xử lý] / hoàn tác ở máy khác đổi danh sách "Sắp hết".
  useNgheBang(["lieu_trinh", "lieu_trinh_buoi", "lieu_trinh_tra_truoc", "appointment", "tuong_tac_cskh"], napLai);

  useEffect(() => {
    let huy = false;
    void Promise.all([docDs("sap_het", quaNgay), docDs("de_xuat", quaNgay), docDs("dang_do", quaNgay)]).then(
      ([s, a, b]) => {
        if (huy) return;
        setSapHet(s);
        setDeXuat(a);
        setDangDo(b);
      },
    );
    return () => {
      huy = true;
    };
  }, [quaNgay, lan]);

  return (
    <div className="space-y-5">
      <ThongBaoHoanTac thongBao={thongBao} onDong={dongThongBao} onHoanTacXong={napLai} />
      <Nhom
        tieuDe="Sắp hết lộ trình"
        moTa="Còn 1 buổi, hoặc đã dùng hết buổi trả trước. Gọi tư vấn thêm buổi / đặt lịch buổi kế; xong bấm Đã xử lý."
        ds={sapHet}
        trong="Không có liệu trình nào sắp hết cần gọi."
        onDatLich={setDatLich}
        onDaDoi={napLai}
        onBao={setThongBao}
      />
      <Nhom
        tieuDe="Đề xuất chưa đăng ký"
        moTa="Bác sĩ đề xuất liệu trình, khách chưa nhận. Gọi mời đăng ký; tiền thu ở quầy khi khách đến."
        ds={deXuat}
        trong="Không còn đề xuất nào chờ gọi."
        onDatLich={setDatLich}
        onDaDoi={napLai}
        onBao={setThongBao}
      />
      <Nhom
        tieuDe={`Đang dở, quá ${quaNgay} ngày chưa quay lại`}
        moTa="Khách đang làm liệu trình, không có buổi nào chờ làm và chưa có lịch hẹn."
        ds={dangDo}
        trong="Không có khách nào bỏ dở quá số ngày này."
        dauNhom={
          <ChipLoc
            nhan="Quá bao nhiêu ngày chưa quay lại"
            chon={quaNgay}
            onChon={setQuaNgay}
            muc={QUA_NGAY_CHON.map((n) => ({ ma: n, nhan: `${n} ngày` }))}
          />
        }
        onDatLich={setDatLich}
        onDaDoi={napLai}
        onBao={setThongBao}
      />
      {datLich ? (
        <DatLichBuoiKe
          lt={datLich}
          doctors={doctors}
          locations={locations}
          onDong={() => setDatLich(null)}
          onXong={() => {
            setDatLich(null);
            napLai();
          }}
        />
      ) : null}
    </div>
  );
}
