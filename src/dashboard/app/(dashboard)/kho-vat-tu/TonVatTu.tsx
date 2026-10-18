"use client";

// Tab TỒN THEO NƠI CHỨA của Kho vật tư (G8a, 14/10/2026): kho cơ sở + từng phòng.
// Tồn âm và dưới mức tối thiểu là việc BÌNH THƯỜNG của quầy (vật tư vẫn xuất được
// khi sổ hết, rồi kiểm đếm sau) → chữ / chip TRUNG TÍNH, không hộp vàng-đỏ
// (Tuyền 14/10). Máy chủ quyết `canh_bao`; ở đây chỉ vẽ và gửi mức tối thiểu.

import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";

import Button from "@/components/ui/Button";
import ChipLoc from "@/components/ui/ChipLoc";
import Chip from "@/components/ui/Chip";
import ONhap from "@/components/ui/ONhap";
import { boDauVatTu } from "@/lib/vat-tu";
import { guiVatTu, soVatTu } from "./gui-vat-tu";

export interface DongTon {
  id: string;
  vat_tu_id: string;
  room_id: string | null;
  ten: string;
  don_vi: string | null;
  noi_chua: string;
  so_luong: number;
  ton_toi_thieu: number;
  /** Chữ máy chủ đặt: "tồn âm — cần kiểm đếm" | "Dưới mức tối thiểu" | "". */
  canh_bao: string;
}

export interface NoiChua {
  room_id: string | null;
  ten: string;
  dang_bat: boolean;
}

const KHO = "kho";

export default function TonVatTu({
  ton,
  noiChua,
  onLamNhanh,
}: {
  ton: DongTon[];
  noiChua: NoiChua[];
  onLamNhanh: (tab: "nhap" | "cap" | "kiem") => void;
}) {
  const router = useRouter();
  const [noi, setNoi] = useState<string>("tat_ca");
  const [chiCanChuY, setChiCanChuY] = useState(false);
  const [tim, setTim] = useState("");
  const [nhap, setNhap] = useState<Record<string, string>>({});
  const [dang, setDang] = useState(false);
  const [loi, setLoi] = useState<string | null>(null);
  const [bao, setBao] = useState<string | null>(null);
  const canChuY = ton.filter((t) => t.canh_bao).length;
  const hien = useMemo(() => {
    const khoa = boDauVatTu(tim.trim());
    return ton.filter((t) => {
      if (noi !== "tat_ca" && (t.room_id ?? KHO) !== noi) return false;
      if (chiCanChuY && !t.canh_bao) return false;
      return !khoa || boDauVatTu(t.ten).includes(khoa);
    });
  }, [ton, noi, chiCanChuY, tim]);

  async function luuMuc(vatTuId: string, roomId: string | null, muc: string, xong: string) {
    setDang(true);
    setLoi(null);
    setBao(null);
    const kq = await guiVatTu("muc-toi-thieu", { vat_tu_id: vatTuId, room_id: roomId, muc: muc.trim().replace(",", ".") });
    setDang(false);
    if (!kq.ok) {
      setLoi(kq.loi);
      return false;
    }
    setBao(xong);
    router.refresh();
    return true;
  }

  return (
    <div className="flex flex-col gap-3">
      <section aria-label="Giải thích tồn kho" className="rounded-card border border-line bg-surface p-4">
        <h2 className="text-title font-semibold text-ink">Còn bao nhiêu vật tư ở từng kho và phòng</h2>
        <p className="mt-1 text-body text-ink-muted">
          Nhập hàng cộng vào nơi cất. Cấp cho phòng trừ ở kho cơ sở và cộng vào phòng. Kiểm kê dùng để so số đếm thật với số hệ thống.
        </p>
      </section>
      <div className="flex flex-wrap items-center gap-2" aria-label="Thao tác thường dùng">
        <Button type="button" variant="primary" onClick={() => onLamNhanh("nhap")}>
          Nhập hàng
        </Button>
        <Button type="button" variant="secondary" onClick={() => onLamNhanh("cap")}>
          Cấp cho phòng
        </Button>
        <Button type="button" variant="secondary" onClick={() => onLamNhanh("kiem")}>
          Kiểm kê tồn ban đầu
        </Button>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <label className="flex items-center gap-2 text-body text-ink-muted">
          <span>Xem tồn tại</span>
          <select
            aria-label="Xem tồn tại kho hoặc phòng"
            value={noi}
            onChange={(e) => setNoi(e.target.value)}
            className="min-h-10 rounded-control border border-line-strong bg-surface px-3 text-body text-ink"
          >
            <option value="tat_ca">Tất cả kho và phòng</option>
            <optgroup label="Kho">
              <option value="kho">Kho cơ sở</option>
            </optgroup>
            <optgroup label="Phòng">
              {noiChua.filter((n) => n.room_id).map((n) => (
                <option key={n.room_id} value={n.room_id ?? ""}>
                  {n.dang_bat ? n.ten : `${n.ten} (đã ngừng hoạt động)`}
                </option>
              ))}
            </optgroup>
          </select>
        </label>
        <ONhap
          type="search"
          aria-label="Tìm vật tư"
          placeholder="Tìm vật tư — gõ không dấu cũng được"
          value={tim}
          onChange={(e) => setTim(e.target.value)}
          className="w-full sm:ml-auto sm:w-64"
        />
      </div>
      <ChipLoc
        nhan="Lọc theo tình trạng"
        chon={chiCanChuY ? "can" : "tat_ca"}
        onChon={(v) => setChiCanChuY(v === "can")}
        muc={[
          { ma: "tat_ca", nhan: `Tất cả (${ton.length})` },
          { ma: "can", nhan: `Dưới mức / cần kiểm đếm (${canChuY})` },
        ]}
      />
      <p className="text-meta text-ink-muted">
        “Cảnh báo dưới” là mức nhắc bổ sung do quản lý đặt; nó không tự đổi số tồn và không tự tạo đơn nhập.
      </p>

      {hien.length === 0 ? (
        ton.length === 0 ? (
          <section className="space-y-2 rounded-card border border-line bg-surface p-5 text-center">
            <h3 className="text-emph font-semibold text-ink">Chưa có số tồn được ghi nhận</h3>
            <p className="text-body text-ink-muted">
              Nếu vừa nhận hàng, chọn “Nhập hàng”. Nếu đã có hàng nhưng chưa đưa vào sổ, đếm thực tế rồi chọn “Kiểm kê tồn ban đầu”.
            </p>
          </section>
        ) : (
          <p className="rounded-card border border-line bg-surface px-4 py-6 text-center text-body text-ink-muted">
            Không có vật tư phù hợp với bộ lọc hiện tại.
          </p>
        )
      ) : (
        <ul className="overflow-hidden rounded-card border border-line bg-surface shadow-card">
          {hien.map((t) => {
            const doi = nhap[t.id] !== undefined;
            return (
              <li
                key={t.id}
                className="flex flex-wrap items-center gap-x-3 gap-y-2 border-b border-hairline px-3 py-2 last:border-b-0"
              >
                <div className="min-w-0 flex-1 basis-48">
                  <p className="text-emph font-medium text-ink">{t.ten}</p>
                  <p className="text-meta text-ink-muted">
                    {t.noi_chua}
                    {t.don_vi ? ` · ${t.don_vi}` : ""}
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-emph font-semibold tabular-nums text-ink">{soVatTu(t.so_luong)}</span>
                  {t.canh_bao ? (
                    <Chip tone="neutral">{t.canh_bao.charAt(0).toUpperCase() + t.canh_bao.slice(1)}</Chip>
                  ) : null}
                </div>
                <label className="flex items-center gap-1.5 text-meta text-ink-muted">
                  <span>Cảnh báo dưới</span>
                  <ONhap
                    inputMode="decimal"
                    aria-label={`Cảnh báo khi ${t.ten} ở ${t.noi_chua} còn dưới số lượng`}
                    value={doi ? nhap[t.id] : String(t.ton_toi_thieu)}
                    onChange={(e) => setNhap((c) => ({ ...c, [t.id]: e.target.value }))}
                    className="w-24 text-right tabular-nums"
                  />
                </label>
                {doi ? (
                  <Button
                    type="button"
                    size="sm"
                    variant="primary"
                    disabled={dang}
                    onClick={async () => {
                      const ok = await luuMuc(t.vat_tu_id, t.room_id, nhap[t.id], `Đã lưu mức tối thiểu “${t.ten}”.`);
                      if (ok) setNhap((c) => Object.fromEntries(Object.entries(c).filter(([k]) => k !== t.id)));
                    }}
                  >
                    Lưu
                  </Button>
                ) : null}
              </li>
            );
          })}
        </ul>
      )}

      {loi ? (
        <p role="alert" className="text-body text-danger">
          {loi}
        </p>
      ) : null}
      {bao ? (
        <p role="status" className="text-body text-success">
          {bao}
        </p>
      ) : null}
    </div>
  );
}
