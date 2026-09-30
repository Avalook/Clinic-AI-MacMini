"use client";

// Phiếu nhập nhiều dòng kiểu KiotViet (Tuyền 29/09/2026: "toàn quyền điều
// chỉnh thuốc, không lo hết thuốc"). [Lưu phiếu nhập] → `POST /api/pharmacy/
// phieu-nhap` → `POST /api/v1/pharmacy/phieu-nhap` kèm Idempotency-Key: bấm
// hai lần / mạng chập = MỘT phiếu. Máy chủ đọc số, ngày, bắt dòng thiếu và
// cộng tồn qua sổ kho — ở đây chỉ gom ô nhập và hiện câu máy chủ trả.

import { useRouter } from "next/navigation";
import { useState } from "react";

import Button from "@/components/ui/Button";
import { homNayVn } from "@/lib/validation";
import { INPUT, LABEL } from "../../form-ui";
import DanhSachPhieu from "./DanhSachPhieu";
import type { ThuocKho } from "./DanhMucKho";
import { guiKho, tienVnd } from "./gui-kho";

interface Dong {
  k: number;
  ten: string;
  so_lo: string;
  han: string;
  so_luong: string;
  don_vi: string;
  gia_nhap: string;
}

let demDong = 0;
const dongMoi = (): Dong => ({
  k: ++demDong,
  ten: "",
  so_lo: "",
  han: "",
  so_luong: "",
  don_vi: "",
  gia_nhap: "",
});

const khoaMoi = () =>
  typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : `pn-${Date.now()}-${Math.random().toString(36).slice(2)}`;

export default function PhieuNhap({ thuoc, ghiDuoc }: { thuoc: ThuocKho[]; ghiDuoc: boolean }) {
  const router = useRouter();
  const dangDung = thuoc.filter((t) => t.dang_dung);
  const [dau, setDau] = useState(() => ({
    nha_cung_cap: "",
    so_hoa_don: "",
    ngay: homNayVn(),
    ghi_chu: "",
  }));
  const [dong, setDong] = useState<Dong[]>(() => [dongMoi()]);
  // Một khoá cho một phiếu đang soạn; lưu xong mới đổi.
  const [khoa, setKhoa] = useState(khoaMoi);
  const [dang, setDang] = useState(false);
  const [loi, setLoi] = useState<string | null>(null);
  const [bao, setBao] = useState<string | null>(null);
  const [lanTai, setLanTai] = useState(0);

  const suaDong = (k: number, doi: Partial<Dong>) =>
    setDong((ds) =>
      ds.map((d) => {
        if (d.k !== k) return d;
        const moi = { ...d, ...doi };
        // Chọn đúng thuốc → điền sẵn ĐƠN VỊ CỦA LÔ ĐANG CÓ (máy chủ trả
        // `don_vi_lo`); chưa có lô mới lấy đơn vị bán. Sửa được.
        if (doi.ten !== undefined && !d.don_vi) {
          const t = dangDung.find((x) => x.ten === doi.ten);
          const dv = t?.don_vi_lo?.[0] ?? t?.don_vi_ban;
          if (dv) moi.don_vi = dv;
        }
        return moi;
      }),
    );

  // Cảnh báo nhỏ, KHÔNG chặn: đơn vị gõ khác mọi đơn vị lô đang có của thuốc
  // → tồn sẽ tách thành hai dòng đơn vị. Trả chuỗi đơn vị lô để hiện, hoặc null.
  const khacDonViLo = (d: Dong): string | null => {
    const lo = dangDung.find((t) => t.ten === d.ten)?.don_vi_lo ?? [];
    const go = d.don_vi.trim().toLowerCase();
    if (!go || lo.length === 0) return null;
    return lo.some((x) => x.trim().toLowerCase() === go) ? null : lo.join(", ");
  };

  const tong = dong.reduce(
    (s, d) => s + (Number(d.so_luong.replace(",", ".")) || 0) * (Number(d.gia_nhap) || 0),
    0,
  );

  const luu = async () => {
    const thieu = dong.findIndex((d) => !dangDung.some((t) => t.ten === d.ten));
    if (thieu >= 0) {
      setLoi(`Dòng ${thieu + 1}: chọn thuốc có trong danh mục (gõ rồi chọn trong danh sách).`);
      return;
    }
    setDang(true);
    setLoi(null);
    setBao(null);
    const kq = await guiKho(
      "phieu-nhap",
      {
        nha_cung_cap: dau.nha_cung_cap.trim() || null,
        so_hoa_don: dau.so_hoa_don.trim() || null,
        ngay_chung_tu: dau.ngay || null,
        ghi_chu: dau.ghi_chu.trim() || null,
        dong: dong.map((d) => ({
          drug_catalog_id: dangDung.find((t) => t.ten === d.ten)?.id,
          batch_code: d.so_lo.trim(),
          expiry_date: d.han || null,
          so_luong: d.so_luong.trim(),
          unit: d.don_vi.trim() || null,
          gia_nhap: d.gia_nhap.trim() || null,
        })),
      },
      khoa,
    );
    setDang(false);
    if (!kq.ok) {
      setLoi(kq.loi);
      return;
    }
    const ma = (kq.data as { ma_phieu?: string } | null)?.ma_phieu;
    setBao(`Đã lưu phiếu nhập ${ma ?? ""} — tồn đã cộng.`);
    setDong([dongMoi()]);
    setDau({ nha_cung_cap: "", so_hoa_don: "", ngay: homNayVn(), ghi_chu: "" });
    setKhoa(khoaMoi());
    setLanTai((n) => n + 1);
    router.refresh();
  };

  const oDau = (ma: keyof typeof dau, nhan: string, kieu = "text") => (
    <label className="block">
      <span className={LABEL}>{nhan}</span>
      <input
        type={kieu}
        value={dau[ma]}
        onChange={(e) => setDau({ ...dau, [ma]: e.target.value })}
        className={INPUT}
      />
    </label>
  );

  return (
    <div className="flex flex-col gap-4">
      {ghiDuoc ? (
        <section
          aria-label="Lập phiếu nhập"
          className="space-y-3 rounded-card border border-line bg-surface p-4 shadow-card"
        >
          <h3 className="text-title text-ink">Phiếu nhập hàng</h3>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {oDau("nha_cung_cap", "Nhà cung cấp")}
            {oDau("so_hoa_don", "Số hoá đơn")}
            {oDau("ngay", "Ngày chứng từ", "date")}
            {oDau("ghi_chu", "Ghi chú")}
          </div>

          <datalist id="phieu-nhap-thuoc">
            {dangDung.map((t) => (
              <option key={t.id} value={t.ten} />
            ))}
          </datalist>
          <ol className="space-y-3">
            {dong.map((d, i) => (
              <li
                key={d.k}
                aria-label={`Dòng ${i + 1}`}
                className="grid grid-cols-2 gap-2 rounded-control border border-line bg-surface-muted p-3 lg:grid-cols-7"
              >
                <label className="col-span-2 block">
                  <span className={LABEL}>
                    {i + 1}. Thuốc
                  </span>
                  <input
                    list="phieu-nhap-thuoc"
                    value={d.ten}
                    placeholder="Gõ tên thuốc…"
                    onChange={(e) => suaDong(d.k, { ten: e.target.value })}
                    className={INPUT}
                  />
                </label>
                <label className="block">
                  <span className={LABEL}>Số lô</span>
                  <input
                    value={d.so_lo}
                    onChange={(e) => suaDong(d.k, { so_lo: e.target.value })}
                    className={INPUT}
                  />
                </label>
                <label className="block">
                  <span className={LABEL}>Hạn dùng</span>
                  <input
                    type="date"
                    value={d.han}
                    onChange={(e) => suaDong(d.k, { han: e.target.value })}
                    className={INPUT}
                  />
                </label>
                <label className="block">
                  <span className={LABEL}>Số lượng</span>
                  <input
                    value={d.so_luong}
                    inputMode="decimal"
                    onChange={(e) => suaDong(d.k, { so_luong: e.target.value })}
                    className={INPUT}
                  />
                </label>
                <label className="block">
                  <span className={LABEL}>Đơn vị</span>
                  <input
                    value={d.don_vi}
                    onChange={(e) => suaDong(d.k, { don_vi: e.target.value })}
                    className={INPUT}
                  />
                  {khacDonViLo(d) ? (
                    <span role="status" className="mt-1 block text-meta text-warning">
                      Lô đang có tính theo {khacDonViLo(d)} — nhập “{d.don_vi.trim()}” sẽ thành tồn
                      riêng.
                    </span>
                  ) : null}
                </label>
                <div className="flex items-end gap-2">
                  <label className="block min-w-0 flex-1">
                    <span className={LABEL}>Giá nhập (đ)</span>
                    <input
                      value={d.gia_nhap}
                      inputMode="numeric"
                      onChange={(e) => suaDong(d.k, { gia_nhap: e.target.value })}
                      className={INPUT}
                    />
                  </label>
                  {dong.length > 1 ? (
                    <Button
                      type="button"
                      size="sm"
                      variant="ghost"
                      aria-label={`Bỏ dòng ${i + 1}`}
                      onClick={() => setDong((ds) => ds.filter((x) => x.k !== d.k))}
                    >
                      Bỏ
                    </Button>
                  ) : null}
                </div>
              </li>
            ))}
          </ol>

          <div className="flex flex-wrap items-center gap-2">
            <Button
              type="button"
              size="sm"
              variant="secondary"
              onClick={() => setDong((ds) => [...ds, dongMoi()])}
            >
              + Thêm dòng
            </Button>
            <p className="text-body text-ink sm:ml-auto">
              Tổng tiền: <span className="font-semibold tabular-nums">{tienVnd(tong)}</span>
            </p>
            <Button
              type="button"
              variant="primary"
              disabled={dang || dong.some((d) => !d.ten || !d.so_lo.trim() || !d.han || !d.so_luong.trim())}
              onClick={() => void luu()}
            >
              {dang ? "Đang lưu…" : "Lưu phiếu nhập"}
            </Button>
          </div>
          {loi ? (
            <p role="alert" className="text-meta text-danger">
              {loi}
            </p>
          ) : null}
          {bao ? <p className="text-meta text-success">{bao}</p> : null}
        </section>
      ) : null}

      <DanhSachPhieu loai="NHAP" lanTai={lanTai} />
    </div>
  );
}
