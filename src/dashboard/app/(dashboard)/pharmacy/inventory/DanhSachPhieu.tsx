"use client";

// Danh sách phiếu nhập / phiếu kiểm kho đã lưu (29/09/2026, kho kiểu KiotViet).
// Chỉ đọc: `GET /api/pharmacy/phieu-kho?loai=` → `GET /api/v1/pharmacy/phieu-kho`.
// Phiếu chỉ thêm — không có nút sửa / xoá (máy chủ chặn bằng trigger).

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import Button from "@/components/ui/Button";
import Chip from "@/components/ui/Chip";
import XacNhanTaiCho from "@/components/ui/XacNhanTaiCho";
import { TBL_DIV, TBL_HEAD, TBL_WRAP } from "../../form-ui";
import { guiKho, soKho, tienVnd } from "./gui-kho";

interface DongPhieu {
  stt: number;
  ten: string;
  so_lo: string;
  han_dung: string | null;
  don_vi: string | null;
  so_luong: number | null;
  gia_nhap: number | null;
  ton_may: number | null;
  thuc_te: number | null;
  lech: number | null;
  ly_do?: string | null;
  noi_chua?: "KHO" | "QUAY";
  giao_chua_gan_lo?: number | null;
}

interface Phieu {
  id: string;
  ma_phieu: string;
  nha_cung_cap: string | null;
  so_hoa_don: string | null;
  ngay_chung_tu: string | null;
  ghi_chu: string | null;
  tao_luc: string;
  nguoi_tao: string | null;
  ly_do?: string | null;
  hoan_tac_cua?: string | null;
  da_hoan_tac?: boolean;
  dong: DongPhieu[];
}

const gio = (iso: string) =>
  new Date(iso).toLocaleString("vi-VN", {
    timeZone: "Asia/Ho_Chi_Minh",
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });

const ngay = (iso: string | null) =>
  iso ? new Date(`${iso}T00:00:00`).toLocaleDateString("vi-VN") : "—";

export default function DanhSachPhieu({
  loai,
  lanTai,
  ghiDuoc = false,
}: {
  loai: "NHAP" | "KIEM";
  /** Đổi số này = đọc lại (vừa lưu phiếu mới). */
  lanTai: number;
  /** Có quyền ghi kho — chỉ ẩn / hiện nút Hoàn tác của phiếu kiểm. */
  ghiDuoc?: boolean;
}) {
  const router = useRouter();
  const [ds, setDs] = useState<Phieu[] | null>(null);
  const [loi, setLoi] = useState<string | null>(null);
  const [mo, setMo] = useState<string | null>(null);
  const [hoi, setHoi] = useState<string | null>(null);
  const [dang, setDang] = useState(false);
  const [lanDoc, setLanDoc] = useState(0);

  const hoanTac = async (id: string) => {
    setDang(true);
    setLoi(null);
    const kq = await guiKho("hoan-tac-kiem-kho", { phieu_id: id }, crypto.randomUUID());
    setDang(false);
    setHoi(null);
    if (!kq.ok) {
      setLoi(kq.loi);
      return;
    }
    setLanDoc((n) => n + 1);
    router.refresh();
  };

  useEffect(() => {
    let bo = false;
    fetch(`/api/pharmacy/phieu-kho?loai=${loai}`, { cache: "no-store" })
      .then(async (r) => {
        const d = (await r.json().catch(() => null)) as { items?: Phieu[]; error?: string } | null;
        if (bo) return;
        if (!r.ok || !d?.items) setLoi(d?.error ?? "Không đọc được danh sách phiếu.");
        else {
          setLoi(null);
          setDs(d.items);
        }
      })
      .catch(() => {
        if (!bo) setLoi("Mất kết nối — chưa đọc được danh sách phiếu.");
      });
    return () => {
      bo = true;
    };
  }, [loai, lanTai, lanDoc]);

  const nhap = loai === "NHAP";

  return (
    <section aria-label={nhap ? "Phiếu nhập đã lưu" : "Phiếu kiểm đã lưu"} className="space-y-2">
      <h3 className="text-title text-ink">{nhap ? "Phiếu nhập đã lưu" : "Phiếu kiểm đã lưu"}</h3>
      {loi ? (
        <p role="alert" className="text-body text-danger">
          {loi}
        </p>
      ) : null}
      <div className={`${TBL_WRAP} overflow-x-auto`}>
        <table className="w-full min-w-2xl text-left text-body">
          <thead className={TBL_HEAD}>
            <tr>
              <th className="px-3 py-2">Mã phiếu</th>
              <th className="px-3 py-2">Lúc</th>
              {nhap ? <th className="px-3 py-2">Nhà cung cấp · số hoá đơn</th> : null}
              <th className="px-3 py-2 text-right">Số dòng</th>
              {nhap ? <th className="px-3 py-2 text-right">Tổng tiền</th> : null}
              <th className="px-3 py-2">Người lập</th>
              <th className="px-3 py-2" />
            </tr>
          </thead>
          <tbody className={TBL_DIV}>
            {ds === null ? (
              <tr>
                <td colSpan={7} className="px-3 py-6 text-center text-ink-muted">
                  {loi ? "—" : "Đang đọc…"}
                </td>
              </tr>
            ) : ds.length === 0 ? (
              <tr>
                <td colSpan={7} className="px-3 py-6 text-center text-ink-muted">
                  Chưa có phiếu nào.
                </td>
              </tr>
            ) : (
              ds.flatMap((p) => {
                const tong = p.dong.reduce(
                  (s, d) => s + Number(d.so_luong ?? 0) * Number(d.gia_nhap ?? 0),
                  0,
                );
                const hang = (
                  <tr key={p.id}>
                    <td className="px-3 py-2 font-medium text-ink">{p.ma_phieu}</td>
                    <td className="whitespace-nowrap px-3 py-2 text-ink-muted">
                      {gio(p.tao_luc)}
                      {p.ngay_chung_tu ? (
                        <span className="block text-meta">Chứng từ {ngay(p.ngay_chung_tu)}</span>
                      ) : null}
                    </td>
                    {nhap ? (
                      <td className="px-3 py-2 text-ink-muted">
                        {[p.nha_cung_cap, p.so_hoa_don].filter(Boolean).join(" · ") || "—"}
                      </td>
                    ) : null}
                    <td className="px-3 py-2 text-right tabular-nums text-ink">
                      {p.dong.length}
                      {!nhap ? (
                        <span className="block text-meta text-ink-muted">
                          {p.dong.filter((d) => Number(d.lech) !== 0).length} lệch
                        </span>
                      ) : null}
                    </td>
                    {nhap ? (
                      <td className="px-3 py-2 text-right tabular-nums text-ink">{tienVnd(tong)}</td>
                    ) : null}
                    <td className="px-3 py-2 text-ink-muted">{p.nguoi_tao ?? "—"}</td>
                    <td className="px-3 py-2 text-right">
                      <Button
                        type="button"
                        size="sm"
                        variant="ghost"
                        onClick={() => setMo(mo === p.id ? null : p.id)}
                      >
                        {mo === p.id ? "Thu gọn" : "Xem dòng"}
                      </Button>
                      {!nhap && ghiDuoc && !p.hoan_tac_cua && !p.da_hoan_tac
                        && p.dong.some((d) => Number(d.lech) !== 0) ? (
                        hoi === p.id ? (
                          <XacNhanTaiCho
                            cau="Hoàn tác phiếu kiểm này? Tồn các lô lệch về lại số trước khi kiểm."
                            nhanDongY="Hoàn tác"
                            dangGui={dang}
                            onDongY={() => void hoanTac(p.id)}
                            onThoi={() => setHoi(null)}
                          />
                        ) : (
                          <Button type="button" size="sm" variant="ghost" onClick={() => setHoi(p.id)}>
                            Hoàn tác
                          </Button>
                        )
                      ) : null}
                      {p.hoan_tac_cua ? <Chip tone="warning">Phiếu hoàn tác</Chip> : null}
                      {p.da_hoan_tac ? <Chip tone="neutral">Đã hoàn tác</Chip> : null}
                    </td>
                  </tr>
                );
                if (mo !== p.id) return [hang];
                return [
                  hang,
                  <tr key={`${p.id}-dong`} className="bg-surface-muted">
                    <td colSpan={7} className="px-3 py-3">
                      {p.ghi_chu ? <p className="mb-2 text-meta text-ink-muted">{p.ghi_chu}</p> : null}
                      <ul className="space-y-1 text-meta text-ink">
                        {p.dong.map((d) => (
                          <li key={d.stt}>
                            {d.stt}. <span className="font-medium">{d.ten}</span> ·{" "}
                            {d.noi_chua === "KHO" ? "kho · " : ""}lô {d.so_lo}
                            {d.han_dung ? ` · HSD ${ngay(d.han_dung)}` : ""} ·{" "}
                            {nhap
                              ? `${soKho(d.so_luong)} ${d.don_vi ?? ""} × ${tienVnd(
                                  d.gia_nhap == null ? null : Number(d.gia_nhap),
                                )}`
                              : `sổ ${soKho(d.ton_may)} → thực tế ${soKho(d.thuc_te)}${
                                  d.giao_chua_gan_lo ? ` + chờ gán lô ${soKho(d.giao_chua_gan_lo)}` : ""
                                } (lệch ${Number(d.lech) > 0 ? "+" : ""}${soKho(d.lech)})${
                                  d.ly_do ? ` — ${d.ly_do}` : ""
                                }`}
                          </li>
                        ))}
                      </ul>
                    </td>
                  </tr>,
                ];
              })
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}
