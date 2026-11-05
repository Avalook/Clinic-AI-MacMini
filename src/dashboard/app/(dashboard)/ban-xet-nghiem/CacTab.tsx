// (Client — chỉ `BanXetNghiem.tsx` dùng.) Ba tab phụ của bàn XN — hình theo bản mẫu 05/11: "Còn tồn", "Kết quả", "Tiền thu hộ".
// Chỉ vẽ + lọc tại chỗ theo mã/cờ máy chủ trả (`con_ton`, `loc[].ton`, `so_ngay_cho`).
// Tiền thu hộ lọc theo NGÀY GHI NHẬN / ngày hoàn (máy chủ), có dòng hoàn (số âm).

import { useEffect, useState, type ReactNode } from "react";

import Button from "@/components/ui/Button";
import Chip from "@/components/ui/Chip";
import ChipLoc from "@/components/ui/ChipLoc";
import ONhap from "@/components/ui/ONhap";
import StatCard from "@/components/ui/StatCard";
import { loiDocDuoc } from "@/lib/loi-doc-duoc";

import { gioNgay, homNayVN, ngayNgan, ngayVN, tien, type DongTien, type Loc, type Viec } from "./kieu";

const TH = "px-3 py-2 text-left text-label font-semibold uppercase tracking-wide text-ink-muted";
const TD = "px-3 py-2 align-top";

function Bang({ dau, children, rong }: { dau: ReactNode; children: ReactNode; rong: string | null }) {
  return (
    <div className="overflow-x-auto rounded-card border border-line bg-surface shadow-card">
      <table className="w-full min-w-max text-meta text-ink">
        <thead className="border-b border-line bg-surface-muted">{dau}</thead>
        <tbody className="divide-y divide-line">{children}</tbody>
      </table>
      {rong ? <p className="px-4 py-3 text-body text-ink-muted">{rong}</p> : null}
    </div>
  );
}

const nhanNgay = (d: string) => (d === homNayVN() ? "Hôm nay" : ngayNgan(d));

export function ConTon({ viec, loc, onMo }: { viec: Viec[]; loc: Loc[]; onMo: (v: Viec) => void }) {
  const [ngay, setNgay] = useState("");
  const [tt, setTt] = useState("");
  const ton = viec.filter((v) => v.trang_thai.con_ton);
  const ngays = [...new Set(ton.map((v) => v.ngay_chi_dinh))].sort().reverse().slice(0, 7);
  const ds = ton
    .filter((v) => (!ngay || v.ngay_chi_dinh === ngay) && (!tt || v.trang_thai.ma === tt))
    .sort((a, b) => a.ngay_chi_dinh.localeCompare(b.ngay_chi_dinh));
  return (
    <section aria-label="Còn tồn" className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-label font-semibold uppercase tracking-wide text-ink-muted">Ngày chỉ định</span>
        <ChipLoc nhan="Ngày chỉ định" chon={ngay} onChon={setNgay} muc={[{ ma: "", nhan: "Mọi ngày" }, ...ngays.map((d) => ({ ma: d, nhan: nhanNgay(d) }))]} />
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-label font-semibold uppercase tracking-wide text-ink-muted">Tình trạng</span>
        <ChipLoc nhan="Tình trạng" chon={tt} onChon={setTt} muc={[{ ma: "", nhan: "Tất cả" }, ...loc.filter((l) => l.ton).map((l) => ({ ma: l.ma, nhan: l.nhan }))]} />
      </div>
      <Bang
        rong={ds.length ? null : "Không còn xét nghiệm tồn theo bộ lọc này."}
        dau={
          <tr>
            <th className={TH}>Ngày</th>
            <th className={TH}>Khách</th>
            <th className={TH}>Xét nghiệm</th>
            <th className={TH}>Tình trạng</th>
            <th className={`${TH} text-right`}>Đã chờ</th>
            <th className={TH}>Hẹn trả</th>
            <th className={TH}>
              <span className="sr-only">Mở</span>
            </th>
          </tr>
        }
      >
        {ds.map((v) => (
          <tr key={v.order_id}>
            <td className={TD}>{ngayNgan(v.ngay_chi_dinh)}</td>
            <td className={`${TD} font-semibold`}>{v.ten_khach}</td>
            <td className={TD}>
              {v.ten_dich_vu} <span className="text-ink-muted">· {v.ten_doi_tac}</span>
            </td>
            <td className={TD}>
              <Chip tone={v.trang_thai.chip_mau}>{v.trang_thai.chip_nhan}</Chip>
            </td>
            <td className={`${TD} text-right tabular-nums`}>{v.so_ngay_cho ? `${v.so_ngay_cho} ngày` : "Hôm nay"}</td>
            <td className={TD}>{v.hen_tra_ngay ? ngayVN(v.hen_tra_ngay) : "—"}</td>
            <td className={TD}>
              <Button type="button" size="sm" variant="ghost" onClick={() => onMo(v)}>
                Mở
              </Button>
            </td>
          </tr>
        ))}
      </Bang>
    </section>
  );
}

export function KetQua({ viec, onMo }: { viec: Viec[]; onMo: (v: Viec) => void }) {
  const co = viec.filter((v) => v.tep_id).sort((a, b) => (b.tep_luc ?? "").localeCompare(a.tep_luc ?? ""));
  return (
    <section aria-label="Kết quả" className="flex flex-col gap-3">
      <p className="text-meta text-ink-muted">
        Kết quả hiện đang tải tay ở thẻ từng việc. Tệp đối tác đẩy lên Drive sẽ tự về và ghép đúng khách ở chặng sau.
      </p>
      <Bang
        rong={co.length ? null : "Chưa có tờ kết quả nào."}
        dau={
          <tr>
            <th className={TH}>Tờ kết quả</th>
            <th className={TH}>Tải lên lúc</th>
          </tr>
        }
      >
        {co.map((v) => (
          <tr key={v.order_id}>
            <td className={TD}>
              <button type="button" className="text-left font-semibold text-brand-700 hover:underline" onClick={() => onMo(v)}>
                {v.ten_khach}
              </button>
              <div>{v.ten_dich_vu}</div>
              <div className="text-ink-muted">
                {v.ten_tep}
                {v.ma_mau ? ` · mã ống ${v.ma_mau}` : ""}
              </div>
            </td>
            <td className={TD}>{gioNgay(v.tep_luc)}</td>
          </tr>
        ))}
      </Bang>
    </section>
  );
}

interface So {
  tong: number;
  tien_mat: number;
  chuyen_khoan: number;
  dong: DongTien[];
}

const homQua = () => {
  const d = new Date(`${homNayVN()}T00:00:00+07:00`);
  d.setDate(d.getDate() - 1);
  return d.toLocaleDateString("sv-SE", { timeZone: "Asia/Ho_Chi_Minh" });
};

export function TienThuHo() {
  const [ngay, setNgay] = useState(homNayVN);
  const [ds, setDs] = useState<So | null>(null);
  const [loi, setLoi] = useState<string | null>(null);
  useEffect(() => {
    let huy = false;
    void fetch(`/api/xet-nghiem/ban/tien?ngay=${encodeURIComponent(ngay)}`, { cache: "no-store" })
      .then(async (r) => {
        const d = await r.json().catch(() => null);
        if (huy) return;
        if (!r.ok) setLoi(loiDocDuoc(d, `Chưa đọc được sổ thu hộ (HTTP ${r.status}).`));
        else {
          setLoi(null);
          setDs(d);
        }
      })
      .catch(() => {
        if (!huy) setLoi("Mất kết nối — chưa đọc được sổ thu hộ.");
      });
    return () => {
      huy = true;
    };
  }, [ngay]);
  const chip = [homNayVN(), homQua()];
  return (
    <section aria-label="Tiền thu hộ" className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-label font-semibold uppercase tracking-wide text-ink-muted">Ngày ghi nhận</span>
        <ChipLoc nhan="Ngày ghi nhận" chon={chip.includes(ngay) ? ngay : ""} onChon={(d) => d && setNgay(d)} muc={[
          { ma: chip[0], nhan: "Hôm nay" },
          { ma: chip[1], nhan: "Hôm qua" },
        ]} />
        <ONhap type="date" aria-label="Chọn ngày ghi nhận" value={ngay} onChange={(e) => e.target.value && setNgay(e.target.value)} />
      </div>
      <p className="text-meta text-ink-muted">Tiền khách trả cho đối tác — sổ riêng, không vào két hay doanh thu phòng khám.</p>
      {loi ? (
        <p role="alert" className="text-meta text-danger">
          {loi}
        </p>
      ) : null}
      <div className="grid grid-cols-1 gap-3 overflow-hidden sm:grid-cols-3">
        <div className="rounded-card border border-line">
          <StatCard label="Tổng thu hộ" value={tien(ds?.tong ?? 0)} />
        </div>
        <div className="rounded-card border border-line">
          <StatCard label="Tiền mặt" value={tien(ds?.tien_mat ?? 0)} />
        </div>
        <div className="rounded-card border border-line">
          <StatCard label="Chuyển khoản" value={tien(ds?.chuyen_khoan ?? 0)} />
        </div>
      </div>
      <Bang
        rong={ds && ds.dong.length === 0 ? "Không có khoản nào trong ngày này." : null}
        dau={
          <tr>
            <th className={TH}>Giờ</th>
            <th className={TH}>Khách</th>
            <th className={TH}>Xét nghiệm</th>
            <th className={`${TH} text-right`}>Khách trả</th>
            <th className={`${TH} text-right`}>Tiền mặt</th>
            <th className={`${TH} text-right`}>Chuyển khoản</th>
            <th className={TH}>Người ghi</th>
          </tr>
        }
      >
        {(ds?.dong ?? []).map((d) => (
          <tr key={`${d.loai}-${d.id}`}>
            <td className={TD}>{gioNgay(d.ghi_luc)}</td>
            <td className={`${TD} font-semibold`}>
              {d.ten_khach} <span className="font-normal text-ink-muted">{d.ma_bn}</span>
            </td>
            <td className={TD}>
              {d.ten}
              {d.loai === "HOAN" ? <span className="text-ink-muted"> · hoàn tiền</span> : null}
              {d.ma_giao_dich ? <span className="text-ink-muted"> · mã GD {d.ma_giao_dich}</span> : null}
            </td>
            <td className={`${TD} text-right tabular-nums`}>{tien(d.so_tien)}</td>
            <td className={`${TD} text-right tabular-nums`}>{d.tien_mat ? tien(d.tien_mat) : "—"}</td>
            <td className={`${TD} text-right tabular-nums`}>{d.chuyen_khoan ? tien(d.chuyen_khoan) : "—"}</td>
            <td className={TD}>{d.nguoi}</td>
          </tr>
        ))}
        {ds && ds.dong.length ? (
          <tr className="bg-surface-muted font-semibold">
            <td className={TD} colSpan={3}>
              Tổng
            </td>
            <td className={`${TD} text-right tabular-nums`}>{tien(ds.tong)}</td>
            <td className={`${TD} text-right tabular-nums`}>{tien(ds.tien_mat)}</td>
            <td className={`${TD} text-right tabular-nums`}>{tien(ds.chuyen_khoan)}</td>
            <td className={TD} />
          </tr>
        ) : null}
      </Bang>
    </section>
  );
}
