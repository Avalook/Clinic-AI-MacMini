"use client";

/**
 * Dọn dữ liệu khách thử (30/09/2026). Danh sách theo NGÀY như Tiếp đón: giờ,
 * số, tên, SĐT che, bác sĩ, loại khám, trạng thái, chỉ định / đã thu / tệp.
 * Tick từng khách (hoặc cả ngày) → [Xoá đã chọn] → hộp xác nhận liệt kê tên +
 * số dòng theo loại (máy chủ tính, `xem-truoc`) → gõ XOA → xoá.
 *
 * Màn chỉ VẼ: khách nào bị chặn, xoá những dòng nào, ai được xoá — máy chủ quyết.
 */

import { useMemo, useState } from "react";

import Button from "@/components/ui/Button";
import Chip from "@/components/ui/Chip";
import HopXacNhan from "@/components/ui/HopXacNhan";
import ThanhNgay from "@/components/ui/ThanhNgay";
import { tienVn } from "@/lib/phieu-kham";
import { ngayNgan } from "@/lib/thanh-ngay";

export interface DongKhach {
  loai: "lich" | "luot";
  id: string;
  gio: string | null;
  so_booking: number | null;
  so_quay: number | null;
  khach: { id: string; ma: string; ten: string; sdt: string };
  bac_si: string | null;
  loai_kham: string | null;
  vang_lai: boolean;
  trang_thai: string;
  trang_thai_ten: string;
  so_chi_dinh: number;
  da_thu: number;
  so_tep: number;
  ngay_khac: string[];
  dang_mo_hom_nay: boolean;
}

export interface LanDon {
  id: string;
  luc: string;
  boi: string | null;
  nguon: string;
  khach: { ma: string; ten: string }[];
  so_dong: number;
}

export interface DuLieuNgay {
  ngay: string;
  hom_nay: string;
  dong: DongKhach[];
  lan_gan_day: LanDon[];
}

interface XemTruoc {
  khach: { id: string; ma: string; ten: string; ngay: string[] }[];
  nhom: { ma: string; ten: string; so: number }[];
  tong_dong: number;
  so_tep: number;
  bi_chan: { id: string; ten: string }[];
}

interface KetQuaXoa {
  khach: { ma: string; ten: string }[];
  nhom: { ma: string; ten: string; so: number }[];
  tong_dong: number;
  tep: { tong?: number; da_chuyen?: number; khong_co?: number; loi?: unknown[] };
}

async function docLoi(r: Response): Promise<string> {
  try {
    const j = (await r.json()) as { message?: string; detail?: unknown };
    if (typeof j.message === "string") return j.message;
    if (typeof j.detail === "string") return j.detail;
  } catch {
    /* thân không phải JSON */
  }
  return `Máy chủ trả lỗi ${r.status}.`;
}

function gioLuc(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleString("vi-VN", {
    timeZone: "Asia/Ho_Chi_Minh",
    hour: "2-digit",
    minute: "2-digit",
    day: "2-digit",
    month: "2-digit",
  });
}

export default function DonDuLieuThu({ banDau }: { banDau: DuLieuNgay }) {
  const [duLieu, setDuLieu] = useState<DuLieuNgay>(banDau);
  const [dangTai, setDangTai] = useState(false);
  const [chon, setChon] = useState<Set<string>>(new Set());
  const [loiTai, setLoiTai] = useState<string | null>(null);
  const [xemTruoc, setXemTruoc] = useState<XemTruoc | null>(null);
  const [dangXem, setDangXem] = useState(false);
  const [dangXoa, setDangXoa] = useState(false);
  const [loiXoa, setLoiXoa] = useState<string | null>(null);
  const [ketQua, setKetQua] = useState<KetQuaXoa | null>(null);

  // Mỗi khách một ô tick (khách có 2 lịch trong ngày → 2 dòng, cùng một ô).
  const khachDuocChon = useMemo(() => {
    const m = new Map<string, DongKhach>();
    for (const d of duLieu.dong) if (!d.dang_mo_hom_nay) m.set(d.khach.id, d);
    return m;
  }, [duLieu.dong]);
  const soKhachNgay = useMemo(
    () => new Set(duLieu.dong.map((d) => d.khach.id)).size,
    [duLieu.dong],
  );
  const chonCaNgay = khachDuocChon.size > 0 && [...khachDuocChon.keys()].every((id) => chon.has(id));

  async function taiNgay(ngay: string) {
    setDangTai(true);
    setLoiTai(null);
    try {
      const r = await fetch(`/api/don-du-lieu-thu?ngay=${encodeURIComponent(ngay)}`, { cache: "no-store" });
      if (!r.ok) {
        setLoiTai(await docLoi(r));
        return;
      }
      setDuLieu((await r.json()) as DuLieuNgay);
      setChon(new Set());
    } catch {
      setLoiTai("Mất kết nối — chưa tải được danh sách.");
    } finally {
      setDangTai(false);
    }
  }

  function doiTick(id: string) {
    setChon((cu) => {
      const moi = new Set(cu);
      if (moi.has(id)) moi.delete(id);
      else moi.add(id);
      return moi;
    });
  }

  async function moXacNhan() {
    setDangXem(true);
    setLoiXoa(null);
    setKetQua(null);
    try {
      const r = await fetch("/api/don-du-lieu-thu", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ thao_tac: "xem-truoc", khach: [...chon] }),
      });
      if (!r.ok) {
        setLoiTai(await docLoi(r));
        return;
      }
      setXemTruoc((await r.json()) as XemTruoc);
    } catch {
      setLoiTai("Mất kết nối — chưa tính được số dòng sẽ xoá.");
    } finally {
      setDangXem(false);
    }
  }

  async function xoaThat() {
    setDangXoa(true);
    setLoiXoa(null);
    try {
      const r = await fetch("/api/don-du-lieu-thu", {
        method: "POST",
        headers: { "Content-Type": "application/json", "Idempotency-Key": crypto.randomUUID() },
        body: JSON.stringify({ thao_tac: "xoa", khach: [...chon], xac_nhan: "XOA" }),
      });
      if (!r.ok) {
        setLoiXoa(await docLoi(r));
        return;
      }
      setKetQua((await r.json()) as KetQuaXoa);
      setXemTruoc(null);
      await taiNgay(duLieu.ngay);
    } catch {
      setLoiXoa("Mất kết nối — không rõ đã xoá chưa. Tải lại danh sách để xem.");
    } finally {
      setDangXoa(false);
    }
  }

  const biChan = new Set((xemTruoc?.bi_chan ?? []).map((k) => k.id));

  return (
    <div className="grid min-w-0 gap-4">
      <header className="space-y-1">
        <h1 className="text-title font-semibold text-ink">Dọn dữ liệu khách thử</h1>
        <p className="text-body text-ink-muted">
          Tick khách thử để xoá hẳn khách ấy cùng MỌI dữ liệu (lịch, lượt, chỉ định, phiếu thu, tệp…) ở mọi ngày.
          Mỗi dòng bị xoá được lưu nguyên văn để khôi phục tay; nhật ký ghi ai xoá, lúc nào.
        </p>
      </header>

      <ThanhNgay
        motNgay
        nhan="Xem khách theo ngày"
        khoang={{ tu: duLieu.ngay, den: duLieu.ngay }}
        homNay={duLieu.hom_nay}
        soNgayTruoc={20}
        soNgaySau={0}
        dangTai={dangTai}
        onChon={(k) => {
          const moi = k?.den ?? duLieu.hom_nay;
          if (moi !== duLieu.ngay) void taiNgay(moi);
        }}
      />

      {ketQua ? (
        <div role="status" className="rounded-card bg-success-bg px-4 py-3 text-body text-success">
          Đã xoá {ketQua.khach.length} khách ({ketQua.khach.map((k) => k.ten).join(", ")}) — {ketQua.tong_dong} dòng
          dữ liệu; chuyển {ketQua.tep.da_chuyen ?? 0}/{ketQua.tep.tong ?? 0} tệp kết quả sang thư mục lưu trữ.
        </div>
      ) : null}
      {loiTai ? (
        <p role="alert" className="rounded-card bg-danger-bg px-4 py-3 text-body text-danger">
          {loiTai}
        </p>
      ) : null}

      <section className="min-w-0 rounded-card bg-surface shadow-card ring-1 ring-line">
        <div className="flex flex-wrap items-center gap-3 border-b border-line px-4 py-3">
          <label className="inline-flex min-h-10 items-center gap-2 text-body text-ink md:min-h-8">
            <input
              type="checkbox"
              className="size-4 accent-brand-600"
              checked={chonCaNgay}
              disabled={khachDuocChon.size === 0}
              onChange={() =>
                setChon(chonCaNgay ? new Set() : new Set(khachDuocChon.keys()))
              }
            />
            Chọn cả ngày {ngayNgan(duLieu.ngay)} ({soKhachNgay} khách)
          </label>
          <span className="text-body text-ink-muted">Đã chọn {chon.size}</span>
          <Button
            type="button"
            variant="danger"
            className="ml-auto"
            disabled={chon.size === 0 || dangXem}
            onClick={() => void moXacNhan()}
          >
            {dangXem ? "Đang tính…" : `Xoá đã chọn (${chon.size})`}
          </Button>
        </div>

        {duLieu.dong.length === 0 ? (
          <p className="px-4 py-6 text-body text-ink-muted">Ngày {ngayNgan(duLieu.ngay)} không có khách nào.</p>
        ) : (
          <ul className="divide-y divide-line">
            {duLieu.dong.map((d) => {
              const dangChon = chon.has(d.khach.id);
              return (
                <li key={`${d.loai}-${d.id}`} className={dangChon ? "bg-danger-bg/40" : ""}>
                  <label className="flex min-w-0 cursor-pointer items-start gap-3 px-4 py-3">
                    <input
                      type="checkbox"
                      className="mt-1 size-4 shrink-0 accent-brand-600"
                      checked={dangChon}
                      disabled={d.dang_mo_hom_nay}
                      onChange={() => doiTick(d.khach.id)}
                      aria-label={`Chọn ${d.khach.ten}`}
                    />
                    <span className="w-14 shrink-0 text-body tabular-nums text-ink">
                      <span className="block font-semibold">{d.gio ?? "—"}</span>
                      <span className="block text-meta text-ink-muted">
                        {d.so_booking != null ? `#${d.so_booking}` : d.vang_lai ? "Vãng lai" : ""}
                        {d.so_quay != null ? ` · Q${d.so_quay}` : ""}
                      </span>
                    </span>
                    <span className="min-w-0 flex-1 space-y-1">
                      <span className="flex flex-wrap items-baseline gap-x-2">
                        <span className="text-emph font-semibold text-ink">{d.khach.ten}</span>
                        <span className="text-body tabular-nums text-ink-muted">{d.khach.sdt}</span>
                        <span className="text-meta text-ink-faint">{d.khach.ma}</span>
                      </span>
                      <span className="block text-body text-ink-muted">
                        {[d.bac_si, d.loai_kham].filter(Boolean).join(" · ") || "Chưa có bác sĩ / loại khám"}
                      </span>
                      <span className="flex flex-wrap items-center gap-1.5">
                        <Chip tone={d.trang_thai === "CANCELLED" || d.trang_thai === "NO_SHOW" ? "neutral" : "info"}>
                          {d.trang_thai_ten}
                        </Chip>
                        <Chip tone="neutral">{d.so_chi_dinh} chỉ định</Chip>
                        <Chip tone="neutral">Đã thu {tienVn(d.da_thu)}</Chip>
                        <Chip tone="neutral">{d.so_tep} tệp</Chip>
                        {d.ngay_khac.length > 0 ? (
                          <Chip tone="warning">
                            Có lượt ngày khác: {d.ngay_khac.map(ngayNgan).join(", ")}
                          </Chip>
                        ) : null}
                        {d.dang_mo_hom_nay ? <Chip tone="danger">Đang khám hôm nay — không xoá được</Chip> : null}
                      </span>
                    </span>
                  </label>
                </li>
              );
            })}
          </ul>
        )}
      </section>

      {duLieu.lan_gan_day.length > 0 ? (
        <section className="min-w-0 space-y-2">
          <h2 className="text-emph font-semibold text-ink">Nhật ký dọn gần đây</h2>
          <ul className="divide-y divide-line rounded-card bg-surface ring-1 ring-line">
            {duLieu.lan_gan_day.map((l) => (
              <li key={l.id} className="px-4 py-2 text-body text-ink">
                <span className="font-medium tabular-nums">{gioLuc(l.luc)}</span>
                {" · "}
                {l.boi ?? "?"}
                {l.nguon === "script_moc" ? " (script theo mốc)" : ""} xoá {l.khach.length} khách, {l.so_dong} dòng
                <span className="block text-meta text-ink-muted">
                  {l.khach.map((k) => `${k.ten} (${k.ma})`).join(", ")}
                </span>
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      {xemTruoc ? (
      <HopXacNhan
        mo
        khoa={xemTruoc.bi_chan.length > 0}
        tieuDe={`Xoá hẳn ${xemTruoc?.khach.length ?? 0} khách?`}
        nhanXacNhan={`Xoá ${xemTruoc?.khach.length ?? 0} khách`}
        goChu="XOA"
        dangChay={dangXoa}
        loi={
          loiXoa ??
          (xemTruoc && xemTruoc.bi_chan.length > 0
            ? `${xemTruoc.bi_chan.map((k) => k.ten).join(", ")} đang có lượt khám mở hôm nay — bỏ tick trước khi xoá.`
            : null)
        }
        onDong={() => {
          setXemTruoc(null);
          setLoiXoa(null);
        }}
        onXacNhan={() => void xoaThat()}
      >
        {xemTruoc ? (
          <div className="space-y-3">
            <ul className="space-y-1">
              {xemTruoc.khach.map((k) => (
                <li key={k.id} className={biChan.has(k.id) ? "text-danger" : ""}>
                  <span className="font-semibold">{k.ten}</span>{" "}
                  <span className="text-meta text-ink-muted">{k.ma}</span>
                  {k.ngay.length > 0 ? (
                    <span className={`block text-meta ${k.ngay.length > 1 ? "text-warning" : "text-ink-muted"}`}>
                      {k.ngay.length > 1 ? "Dữ liệu ở NHIỀU ngày — xoá hết: " : "Ngày có dữ liệu: "}
                      {k.ngay.map(ngayNgan).join(", ")}
                    </span>
                  ) : null}
                </li>
              ))}
            </ul>
            <div>
              <p className="font-medium">Sẽ xoá {xemTruoc.tong_dong} dòng:</p>
              <ul className="mt-1 space-y-0.5 text-ink-muted">
                {xemTruoc.nhom.map((n) => (
                  <li key={n.ma} className="flex justify-between gap-3">
                    <span>{n.ten}</span>
                    <span className="tabular-nums text-ink">{n.so}</span>
                  </li>
                ))}
              </ul>
              {xemTruoc.so_tep > 0 ? (
                <p className="mt-2 text-meta text-ink-muted">
                  {xemTruoc.so_tep} tệp kết quả được chuyển sang thư mục lưu trữ (không xoá hẳn).
                </p>
              ) : null}
            </div>
          </div>
        ) : null}
      </HopXacNhan>
      ) : null}
    </div>
  );
}
