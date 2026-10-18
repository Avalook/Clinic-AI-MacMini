"use client";

// Lập PHIẾU Kho vật tư (G8a, 14/10/2026): Nhập kho · Xuất kho → phòng · Phòng trả
// kho · Chuyển phòng → phòng · Kiểm đếm · Huỷ hỏng. Màn chỉ gom ô nhập (ô nào hiện
// theo loại phiếu) và gửi; số rác → 422 có lời do MÁY CHỦ trả, vật tư hết trên sổ
// vẫn xuất được (tồn âm = việc bình thường, kiểm đếm sau). Idempotency-Key: bấm
// hai lần / mạng chập = MỘT phiếu.

import { useRouter } from "next/navigation";
import { useState } from "react";

import Button from "@/components/ui/Button";
import OChon from "@/components/ui/OChon";
import ONhap from "@/components/ui/ONhap";
import { guiVatTu, khoaMoi, soVatTu } from "./gui-vat-tu";
import type { DongTon, NoiChua } from "./TonVatTu";

type Cho = null | "noi" | "phong";

interface Kieu {
  nhan: string;
  /** Ô "từ" / "đến": không có · nơi bất kỳ (kho hoặc phòng) · chỉ phòng. */
  tu: Cho;
  den: Cho;
  nhanTu: string;
  nhanDen: string;
  nhanSo: string;
  /** Ghi chú ngầm khi kho cơ sở là đầu còn lại. */
  goiY?: string;
}

export const KIEU_PHIEU: Record<string, Kieu> = {
  NHAP: { nhan: "Nhập hàng vào kho", tu: null, den: "noi", nhanTu: "", nhanDen: "Cất tại", nhanSo: "Số lượng nhận" },
  XUAT_PHONG: {
    nhan: "Cấp vật tư từ kho cho phòng",
    tu: null,
    den: "phong",
    nhanTu: "",
    nhanDen: "Phòng nhận",
    nhanSo: "Số lượng giao",
    goiY: "Ghi vật tư đã lấy khỏi kho cơ sở và giao cho phòng. Nếu số chưa kịp ghi sổ, hệ thống vẫn ghi giao dịch và đánh dấu tồn cần đối chiếu.",
  },
  TRA_KHO: {
    nhan: "Phòng trả vật tư về kho",
    tu: "phong",
    den: null,
    nhanTu: "Phòng trả",
    nhanDen: "",
    nhanSo: "Số lượng chưa dùng trả",
    goiY: "Trừ số ở phòng trả và cộng lại Kho cơ sở. Chỉ nhập lượng thực sự chưa dùng.",
  },
  CHUYEN_PHONG: {
    nhan: "Chuyển vật tư giữa hai phòng",
    tu: "phong",
    den: "phong",
    nhanTu: "Từ phòng",
    nhanDen: "Sang phòng",
    nhanSo: "Số lượng chuyển",
  },
  DIEU_CHINH: {
    nhan: "Kiểm kê và cập nhật tồn",
    tu: "noi",
    den: null,
    nhanTu: "Nơi kiểm",
    nhanDen: "",
    nhanSo: "Số đếm thực tế",
    goiY: "Gõ số đang có thật. Hệ thống tính chênh lệch và cập nhật tồn về đúng số đếm; nếu ghi nhầm, có thể hoàn tác từ Lịch sử thao tác.",
  },
  KIEM: {
    nhan: "Chỉ ghi số đếm để đối chiếu",
    tu: "noi",
    den: null,
    nhanTu: "Nơi kiểm",
    nhanDen: "",
    nhanSo: "Số đếm thực tế",
    goiY: "Lưu số đếm và chênh lệch để rà soát; số tồn hệ thống chưa đổi.",
  },
  HUY: { nhan: "Ghi nhận vật tư hỏng hoặc huỷ", tu: "noi", den: null, nhanTu: "Nơi có hàng hỏng", nhanDen: "", nhanSo: "Số lượng huỷ" },
};

interface Dong {
  k: number;
  ten: string;
  tu: string;
  den: string;
  so: string;
  gia: string;
}

let dem = 0;
const dongMoi = (): Dong => ({ k: ++dem, ten: "", tu: "", den: "", so: "", gia: "" });

/** Câu báo sau khi máy chủ nhận phiếu NHẬP có dòng "cần duyệt nhập" (G8b). Máy chủ trả
 *  `cho_duyet` + `trang_thai`; màn chỉ chọn câu chữ, không tự quyết phiếu có cần duyệt. */
function baoYeuCau(d: {
  cho_duyet?: boolean;
  trang_thai?: string;
  ma_yeu_cau?: string;
  ma_phieu?: string;
  gui_lai?: boolean;
}): string | null {
  if (!d.ma_yeu_cau) return null;
  const lai = d.gui_lai ? " (phiếu này đã gửi trước đó)" : "";
  if (d.cho_duyet) {
    return `Phiếu có dòng cần duyệt — đã gửi xin duyệt ${d.ma_yeu_cau}${lai}, chưa vào kho. Người có quyền Duyệt vật tư sẽ duyệt ở tab Chờ duyệt.`;
  }
  if (d.trang_thai === "DA_DUYET" && !d.gui_lai) {
    return `Phiếu có dòng cần duyệt — bạn có quyền Duyệt vật tư nên đã tự duyệt và nhập kho (${d.ma_yeu_cau}${d.ma_phieu ? `, phiếu ${d.ma_phieu}` : ""}). Sai thì bấm Hoàn tác ở danh sách bên dưới.`;
  }
  return `Phiếu này đã gửi xin duyệt trước đó (${d.ma_yeu_cau}) và đã được quyết — xem ở tab Chờ duyệt, không lập thêm phiếu.`;
}

export default function LapPhieuVatTu({
  noiChua,
  vatTu,
  ton,
  xemChoDuyet,
  loaiBanDau,
}: {
  noiChua: NoiChua[];
  vatTu: { id: string; name: string }[];
  ton: DongTon[];
  /** Chuyển sang tab Chờ duyệt khi phiếu vừa gửi đang chờ. */
  xemChoDuyet?: () => void;
  loaiBanDau: "NHAP" | "XUAT_PHONG" | "DIEU_CHINH";
}) {
  const router = useRouter();
  const [loai, setLoai] = useState<string>(loaiBanDau);
  const [ghiChu, setGhiChu] = useState("");
  const [dong, setDong] = useState<Dong[]>(() => [dongMoi()]);
  const [khoa, setKhoa] = useState(khoaMoi);
  const [dang, setDang] = useState(false);
  const [loi, setLoi] = useState<string | null>(null);
  const [bao, setBao] = useState<string | null>(null);
  const [dangCho, setDangCho] = useState(false);

  const kieu = KIEU_PHIEU[loai];
  const phong = noiChua.filter((n) => n.room_id);
  const phongNhan = phong.filter((n) => n.dang_bat);
  const chon = (cho: Cho, nhan: string, gia: string, dat: (v: string) => void, den: boolean) =>
    cho ? (
      <label className="block">
        <span className="mb-1 block text-meta text-ink-soft">{nhan}</span>
        <OChon value={gia} onChange={(e) => dat(e.target.value)} className="w-full">
          {cho === "noi" ? (
            <option value="">Kho cơ sở</option>
          ) : (
            <option value="">Chọn phòng…</option>
          )}
          {(den ? phongNhan : phong).map((n) => (
            <option key={n.room_id} value={n.room_id ?? ""}>
              {n.dang_bat ? n.ten : `${n.ten} (đã tắt)`}
            </option>
          ))}
        </OChon>
      </label>
    ) : null;

  const suaDong = (k: number, doi: Partial<Dong>) =>
    setDong((ds) => ds.map((d) => (d.k === k ? { ...d, ...doi } : d)));

  const thieu = dong.some(
    (d) =>
      !d.ten.trim() ||
      !d.so.trim() ||
      (kieu.tu === "phong" && !d.tu) ||
      (kieu.den === "phong" && !d.den),
  );

  const luu = async () => {
    const sai = dong.findIndex((d) => !vatTu.some((v) => v.name === d.ten));
    if (sai >= 0) {
      setLoi(`Dòng ${sai + 1}: chọn vật tư có trong danh mục (gõ rồi chọn trong danh sách).`);
      return;
    }
    setDang(true);
    setLoi(null);
    setBao(null);
    setDangCho(false);
    const kq = await guiVatTu(
      "phieu",
      {
        loai,
        ghi_chu: ghiChu.trim() || null,
        dong: dong.map((d) => ({
          vat_tu_id: vatTu.find((v) => v.name === d.ten)?.id,
          tu_room_id: kieu.tu ? d.tu || null : null,
          den_room_id: kieu.den ? d.den || null : null,
          so_luong: d.so.trim().replace(",", "."),
          gia_nhap: d.gia.trim() || null,
        })),
      },
      khoa,
    );
    setDang(false);
    if (!kq.ok) {
      setLoi(kq.loi);
      return;
    }
    const d = kq.data as Parameters<typeof baoYeuCau>[0] | null;
    const yeuCau = d ? baoYeuCau(d) : null;
    setDangCho(d?.cho_duyet === true);
    setBao(
      yeuCau ?? `Đã ghi nhận “${kieu.nhan}”${d?.ma_phieu ? ` · mã ${d.ma_phieu}` : ""}. Tồn đã cập nhật; nếu ghi nhầm, mở Lịch sử thao tác để hoàn tác.`,
    );
    setDong([dongMoi()]);
    setGhiChu("");
    setKhoa(khoaMoi());
    router.refresh();
  };

  return (
    <section aria-label="Ghi nhận thao tác kho" className="space-y-3 rounded-card border border-line bg-surface p-4 shadow-card">
      <div className="flex flex-wrap items-end gap-3">
        <label className="block min-w-0 flex-1 basis-56">
          <span className="mb-1 block text-meta text-ink-soft">Thao tác cần ghi</span>
          <OChon
            value={loai}
            onChange={(e) => {
              setLoai(e.target.value);
              setDong([dongMoi()]);
              setKhoa(khoaMoi());
            }}
            className="w-full"
          >
            {Object.entries(KIEU_PHIEU).map(([ma, k]) => (
              <option key={ma} value={ma}>
                {k.nhan}
              </option>
            ))}
          </OChon>
        </label>
      </div>
      {kieu.goiY ? (
        <p className="rounded-control bg-surface-muted px-3 py-2 text-body text-ink-muted">{kieu.goiY}</p>
      ) : null}

      <datalist id="vat-tu-phieu">
        {vatTu.map((v) => (
          <option key={v.id} value={v.name} />
        ))}
      </datalist>
      <ol className="space-y-3">
        {dong.map((d, i) => (
          <li
            key={d.k}
            aria-label={`Dòng ${i + 1}`}
            className="grid grid-cols-2 gap-2 rounded-control border border-line bg-surface-muted p-3 lg:grid-cols-6"
          >
            <label className="col-span-2 block">
              <span className="mb-1 block text-meta text-ink-soft">{i + 1}. Vật tư</span>
              <ONhap
                list="vat-tu-phieu"
                value={d.ten}
                placeholder="Gõ tên vật tư…"
                onChange={(e) => suaDong(d.k, { ten: e.target.value })}
                className="w-full"
              />
            </label>
            {chon(kieu.tu, kieu.nhanTu, d.tu, (v) => suaDong(d.k, { tu: v }), false)}
            {chon(kieu.den, kieu.nhanDen, d.den, (v) => suaDong(d.k, { den: v }), true)}
            <label className="block">
              <span className="mb-1 block text-meta text-ink-soft">
                {loai === "DIEU_CHINH" || loai === "KIEM" ? "Số đếm thực tế" : kieu.nhanSo}
              </span>
              <ONhap
                inputMode="decimal"
                value={d.so}
                onChange={(e) => suaDong(d.k, { so: e.target.value })}
                className="w-full text-right tabular-nums"
              />
            </label>
            {(loai === "DIEU_CHINH" || loai === "KIEM") && (() => {
              const vatTuId = vatTu.find((v) => v.name === d.ten)?.id;
              const roomId = d.tu || null;
              const soTrenSo = ton.find((t) => t.vat_tu_id === vatTuId && t.room_id === roomId)?.so_luong ?? 0;
              const soDem = Number(d.so.trim().replace(",", "."));
              const chenhLech = d.so.trim() && Number.isFinite(soDem) ? soDem - soTrenSo : null;
              const dau = chenhLech !== null && chenhLech > 0 ? "+" : "";
              return (
                <p className="col-span-2 text-meta text-ink-muted">
                  Tồn sổ: {soVatTu(soTrenSo)}. {chenhLech === null
                    ? "Nhập số đếm thực tế để xem chênh lệch."
                    : `Chênh lệch dự kiến: ${dau}${soVatTu(chenhLech)}.`}
                  {loai === "KIEM" ? " Chỉ ghi số đếm; tồn chưa đổi." : " Khi lưu, tồn sẽ cập nhật bằng số đếm thực tế."}
                </p>
              );
            })()}
            {loai === "NHAP" ? (
              <label className="block min-w-0 flex-1">
                <span className="mb-1 block text-meta text-ink-soft">Giá mua một đơn vị (đ)</span>
                <ONhap
                  inputMode="numeric"
                  value={d.gia}
                  placeholder="Lấy giá đã cài nếu để trống"
                  onChange={(e) => suaDong(d.k, { gia: e.target.value })}
                  className="w-full text-right tabular-nums"
                />
              </label>
            ) : null}
            {dong.length > 1 ? (
              <Button
                type="button"
                size="sm"
                variant="ghost"
                aria-label={`Bỏ dòng ${i + 1}`}
                onClick={() => setDong((ds) => ds.filter((x) => x.k !== d.k))}
              >
                Bỏ dòng này
              </Button>
            ) : null}
          </li>
        ))}
      </ol>

      <label className="block">
        <span className="mb-1 block text-meta text-ink-soft">Ghi chú / lý do (nên ghi khi kiểm kê hoặc huỷ)</span>
        <ONhap
          value={ghiChu}
          maxLength={1000}
          placeholder={loai === "HUY" ? "Vì sao huỷ — vỡ, hỏng…" : "Ghi chú thao tác (tuỳ chọn)"}
          onChange={(e) => setGhiChu(e.target.value)}
          className="w-full"
        />
      </label>

      <div className="flex flex-wrap items-center gap-2">
        <Button type="button" size="sm" variant="secondary" onClick={() => setDong((ds) => [...ds, dongMoi()])}>
          + Thêm dòng
        </Button>
        <Button type="button" variant="primary" disabled={dang || thieu} onClick={() => void luu()} className="sm:ml-auto">
          {dang
            ? "Đang lưu…"
            : loai === "HUY"
              ? kieu.nhan
              : `Ghi nhận ${kieu.nhan.toLocaleLowerCase("vi")}`}
        </Button>
      </div>
      {loi ? (
        <p role="alert" className="text-body text-danger">
          {loi}
        </p>
      ) : null}
      {bao ? (
        <div className="flex flex-wrap items-center gap-2">
          <p role="status" className="min-w-0 flex-1 basis-64 text-body text-success">
            {bao}
          </p>
          {dangCho && xemChoDuyet ? (
            <Button type="button" size="sm" variant="secondary" onClick={xemChoDuyet}>
              Xem ở Chờ duyệt
            </Button>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}
