"use client";

// DẢI LIỆU TRÌNH trong thẻ chỉ định điều trị (khối 3 hồ sơ khám) — 08/10/2026,
// đặc tả `docs/KE-HOACH-LIEU-TRINH.md` Phần B.
//   · Chưa có liệu trình → ô "Lộ trình [N] buổi · ghi chú tần suất" + [Tạo liệu
//     trình] (chỉ định hôm nay = buổi 1).
//   · Có → "Buổi 3/10 · đã làm 2 · đã trả 5 · còn nợ 5 buổi (… đ)" + trạng thái,
//     [Điều chỉnh] · [Dừng]/[Mở lại] · [Lịch sử sửa] · [Hoàn tác] lần sửa mới
//     nhất · [Gỡ khỏi liệu trình] · danh sách buổi (ngày, nơi làm, phiếu điều trị
//     mở chỉ đọc).
//   · Khách có 2 liệu trình cùng dịch vụ (`can_chon`) → chọn liệu trình.
// MỌI con số, trạng thái và nút nào hiện do MÁY CHỦ trả (`/api/lieu-trinh`,
// `nut`, `hoan_tac`); màn chỉ vẽ và gửi lệnh. `choGhi` tắt (popup Lịch sử khám,
// /patient-list) → chỉ đọc. Liệu trình KHÔNG sinh dòng ở danh sách vận hành nào.

import { useState, type ReactNode } from "react";

import Button, { buttonClass } from "@/components/ui/Button";
import Chip, { type ChipTone } from "@/components/ui/Chip";
import OChon from "@/components/ui/OChon";
import ONhap from "@/components/ui/ONhap";
import XacNhanTaiCho from "@/components/ui/XacNhanTaiCho";
import { fmtDate, fmtDateTime, fmtTime } from "@/lib/datetime";
import {
  NHAN_HANH_DONG_LT,
  NHAN_TRANG_THAI_LT,
  docLT,
  lenhLT,
  nhanDaTra,
  nhanDoiLieuTrinh,
  nhanNutHoanTac,
  tienLT,
  type BuoiLieuTrinh,
  type ChiDinhLieuTrinh,
  type DongLichSuLT,
  type LieuTrinh,
  type LieuTrinhLuot,
  type TrangThaiLieuTrinh,
  type UngVien,
} from "@/lib/lieu-trinh";

const TONE_LT: Record<TrangThaiLieuTrinh, ChipTone> = {
  DE_XUAT: "info",
  DANG_LAM: "run",
  XONG: "success",
  DUNG: "warning",
};

/** Ô "Lộ trình [N] buổi · ghi chú" + nút gửi — dùng cho tạo / điều chỉnh / đề xuất. */
function OLoTrinh({
  nhanNut,
  soBuoiDau,
  ghiChuDau,
  dang,
  onGui,
  onThoi,
  truoc,
}: {
  nhanNut: string;
  soBuoiDau: number | null;
  ghiChuDau: string;
  dang: boolean;
  onGui: (soBuoi: number, ghiChu: string) => void;
  onThoi?: () => void;
  truoc?: ReactNode;
}) {
  const [so, setSo] = useState(soBuoiDau ? String(soBuoiDau) : "");
  const [gc, setGc] = useState(ghiChuDau);
  const n = Number.parseInt(so, 10);
  return (
    <div className="flex flex-wrap items-center gap-2">
      {truoc}
      <label className="flex items-center gap-1.5 text-meta text-ink-soft">
        Lộ trình
        <ONhap
          type="number"
          inputMode="numeric"
          min={1}
          max={200}
          value={so}
          onChange={(e) => setSo(e.target.value)}
          aria-label="Số buổi của lộ trình"
          className="w-20"
        />
        buổi
      </label>
      <ONhap
        value={gc}
        onChange={(e) => setGc(e.target.value)}
        maxLength={1000}
        placeholder="Ghi chú tần suất (vd 2 buổi/tuần)"
        aria-label="Ghi chú tần suất"
        className="min-w-0 flex-1"
      />
      <Button size="sm" variant="primary" disabled={dang || !(n >= 1)} onClick={() => onGui(n, gc.trim())}>
        {dang ? "Đang ghi…" : nhanNut}
      </Button>
      {onThoi ? (
        <Button size="sm" variant="ghost" disabled={dang} onClick={onThoi}>
          Thôi
        </Button>
      ) : null}
    </div>
  );
}

function LichSuLT({ ltId }: { ltId: string }) {
  const [ds, setDs] = useState<DongLichSuLT[] | null>(null);
  const [mo, setMo] = useState(false);
  const bat = async () => {
    setMo(!mo);
    if (!mo) setDs((await docLT<{ dong: DongLichSuLT[] }>("lich-su", ltId))?.dong ?? []);
  };
  return (
    <div className="space-y-1">
      <Button size="sm" variant="ghost" aria-expanded={mo} onClick={() => void bat()}>
        {mo ? "Ẩn lịch sử sửa" : "Lịch sử sửa"}
      </Button>
      {mo ? (
        ds === null ? (
          <p className="text-meta text-ink-muted">Đang tải…</p>
        ) : (
          <ul className="divide-y divide-hairline rounded-control border border-hairline text-meta">
            {ds.map((d) => (
              <li key={`${d.loai}-${d.id}`} className="flex flex-wrap gap-x-2 px-2 py-1 text-ink-soft">
                <span className="text-ink">
                  {d.loai === "SUA"
                    ? (NHAN_HANH_DONG_LT[d.hanh_dong ?? ""] ?? d.hanh_dong)
                    : `${d.loai === "GAN" ? "Gắn" : "Gỡ"} buổi ${d.buoi_so ?? ""}`}
                </span>
                {d.loai === "SUA" && nhanDoiLieuTrinh(d.ban_cu, d.ban_moi) ? (
                  <span>{nhanDoiLieuTrinh(d.ban_cu, d.ban_moi)}</span>
                ) : null}
                <span className="text-ink-muted">
                  {[d.boi ?? (d.cach === "TU_DONG" ? "Tự động" : null), d.luc ? fmtDateTime(d.luc) : null]
                    .filter(Boolean)
                    .join(" · ")}
                </span>
              </li>
            ))}
          </ul>
        )
      ) : null}
    </div>
  );
}

/** Một dòng trong danh sách buổi: buổi đã gắn (có chỉ định) hoặc ô còn trống
 *  của kế hoạch. Số buổi máy chủ đánh theo thứ tự LÀM XONG. */
function DongBuoi({ so, b, homNay }: { so: number; b: BuoiLieuTrinh | null; homNay: boolean }) {
  const daLam = Boolean(b?.da_lam);
  const chiTiet = b
    ? [
        b.ngay ? fmtDate(b.ngay) : null,
        b.noi_lam ?? (daLam ? null : "chưa xếp nơi làm"),
        daLam && b.xong_luc ? `xong ${fmtTime(b.xong_luc)}` : null,
      ]
        .filter(Boolean)
        .join(" · ")
    : "chưa có lượt";
  return (
    <li className={`flex items-start gap-3 px-3 py-2.5 ${homNay ? "bg-surface-selected" : ""}`}>
      <span
        aria-hidden
        className={`mt-0.5 grid size-7 shrink-0 place-items-center rounded-full text-meta font-semibold ${
          daLam
            ? "bg-success text-surface"
            : b
              ? "bg-status-in-progress-bg text-status-in-progress"
              : "bg-surface-sunken text-ink-faint"
        }`}
      >
        {daLam ? "✓" : so}
      </span>
      <div className="min-w-0 flex-1 space-y-1">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-body font-semibold text-ink">Buổi {so}</span>
          <Chip tone={daLam ? "success" : "neutral"}>{daLam ? "ĐÃ LÀM" : "CHƯA LÀM"}</Chip>
          {homNay ? <Chip tone="brand">Hôm nay</Chip> : null}
          {b?.tra_truoc ? <Chip tone="info">Đã trả trước</Chip> : null}
        </div>
        <p className="text-meta text-ink-muted">{chiTiet}</p>
        {(b?.ket_qua ?? []).map((o) => (
          <p key={o.ma} className="text-meta text-ink-soft">
            <span className="font-medium text-ink">{o.ten}:</span> {o.gia_tri}
          </p>
        ))}
      </div>
      {b ? (
        <a
          href={`/print/ket-qua/${b.order_id}`}
          target="_blank"
          rel="noopener"
          className={`${buttonClass("ghost", "sm")} shrink-0`}
        >
          Phiếu
        </a>
      ) : null}
    </li>
  );
}

/** Số ô trống của kế hoạch hiện sẵn; dài hơn thì gom một dòng "còn k buổi". */
const TRONG_HIEN_TOI_DA = 3;

/** Thân một liệu trình: tiến độ, tiền, nút kế hoạch, lịch sử, MỌI buổi. */
export function KhungLieuTrinh({
  lt,
  orderHomNay,
  choGhi,
  onDoi,
  them,
}: {
  lt: LieuTrinh;
  /** Chỉ định của thẻ đang xem — dòng buổi ấy tô "Hôm nay". */
  orderHomNay?: string | null;
  choGhi: boolean;
  onDoi: () => void;
  /** Nút riêng của thẻ chỉ định (gỡ / tách) — vẽ cùng hàng nút. */
  them?: ReactNode;
}) {
  const [sua, setSua] = useState(false);
  const [hoiDung, setHoiDung] = useState(false);
  const [dang, setDang] = useState(false);
  const [loi, setLoi] = useState<string | null>(null);
  const [bao, setBao] = useState<string | null>(null);
  const [xemHet, setXemHet] = useState(false);

  const gui = async (thaoTac: string, duLieu: Record<string, unknown>) => {
    setDang(true);
    setLoi(null);
    setBao(null);
    const kq = await lenhLT<{ lieu_trinh?: LieuTrinh }>(thaoTac, { expected_revision: lt.revision, ...duLieu }, lt.id);
    setDang(false);
    if (!kq.ok) {
      setLoi(kq.loi);
      onDoi();
      return false;
    }
    // Dừng khi còn buổi đã trả chưa dùng → chỉ đường hoàn tiền (Q5).
    const sau = kq.data.lieu_trinh;
    if (thaoTac === "dung" && sau && sau.con_tra_truoc > 0) {
      setBao(`Còn ${sau.con_tra_truoc} buổi đã trả chưa dùng — hoàn tiền ở quầy thu dịch vụ (tab “Đã thanh toán”).`);
    }
    onDoi();
    return true;
  };

  const deXuat = lt.trang_thai === "DE_XUAT";
  const song = (lt.buoi ?? []).filter((b) => b.song).sort((a, b) => a.buoi_so - b.buoi_so);
  const conTrong = lt.chua_gan ?? 0;
  const hienTrong = xemHet ? conTrong : Math.min(conTrong, soTrongHien(conTrong));
  return (
    <div className="space-y-3 rounded-card border border-line bg-surface p-3">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0 space-y-1">
          <p className="text-label font-semibold uppercase text-ink-muted">Lộ trình điều trị</p>
          <p className="text-emph font-semibold text-ink">
            {lt.service_name} · {lt.so_buoi} buổi
          </p>
          <div className="flex flex-wrap items-center gap-1.5">
            <Chip tone={TONE_LT[lt.trang_thai]}>
              {deXuat ? "Bác sĩ đề xuất — khách chưa chọn" : NHAN_TRANG_THAI_LT[lt.trang_thai]}
            </Chip>
            {lt.ghi_chu_lo_trinh ? <span className="text-meta text-ink-soft">{lt.ghi_chu_lo_trinh}</span> : null}
          </div>
        </div>
        <p className="text-title font-semibold text-ink">
          Đã làm {lt.da_lam}/{lt.so_buoi}
        </p>
      </div>
      {lt.so_buoi <= 40 ? (
        <div className="flex gap-1" aria-hidden>
          {Array.from({ length: lt.so_buoi }, (_, i) => (
            <span
              key={i}
              className={`h-2 flex-1 rounded-full ${
                i < lt.da_lam ? "bg-success" : i < song.length ? "bg-status-in-progress-bg" : "bg-surface-sunken"
              }`}
            />
          ))}
        </div>
      ) : null}
      {!deXuat ? (
        <p className="text-body text-ink-soft">
          {(() => {
            const c = nhanDaTra(lt.da_tra, lt.tra_le ?? 0);
            return c.charAt(0).toUpperCase() + c.slice(1);
          })()}
          {lt.chua_tra > 0 ? ` · còn nợ ${lt.chua_tra} buổi (${tienLT(lt.tien_con_lai)})` : " · đã trả đủ"}
        </p>
      ) : null}
      {lt.trang_thai === "DUNG" && lt.ly_do_dung ? (
        <p className="text-meta text-ink-muted">Lý do dừng: {lt.ly_do_dung}</p>
      ) : null}

      <ol className="divide-y divide-hairline rounded-control border border-hairline">
        {song.map((b) => (
          <DongBuoi key={b.id} so={b.buoi_so} b={b} homNay={Boolean(orderHomNay) && b.order_id === orderHomNay} />
        ))}
        {Array.from({ length: hienTrong }, (_, i) => (
          <DongBuoi key={`trong-${i}`} so={song.length + i + 1} b={null} homNay={false} />
        ))}
        {hienTrong < conTrong ? (
          <li className="px-3 py-2">
            <Button size="sm" variant="ghost" onClick={() => setXemHet(true)}>
              Còn {conTrong - hienTrong} buổi chưa làm — xem hết
            </Button>
          </li>
        ) : null}
      </ol>

      {choGhi && sua ? (
        <OLoTrinh
          nhanNut="Lưu điều chỉnh"
          soBuoiDau={lt.so_buoi}
          ghiChuDau={lt.ghi_chu_lo_trinh ?? ""}
          dang={dang}
          onGui={(n, gc) =>
            void gui("dieu-chinh", { so_buoi: n, ghi_chu: gc }).then((ok) => ok && setSua(false))
          }
          onThoi={() => setSua(false)}
        />
      ) : null}
      {choGhi && hoiDung ? (
        <XacNhanTaiCho
          cau={`Dừng liệu trình ${lt.service_name}? Mở lại được bất cứ lúc nào.`}
          nhanDongY="Dừng"
          dangGui={dang}
          onDongY={() => void gui("dung", {}).then(() => setHoiDung(false))}
          onThoi={() => setHoiDung(false)}
        />
      ) : null}

      <div className="flex flex-wrap items-center gap-1.5">
        {choGhi && lt.nut?.dieu_chinh && !sua ? (
          <Button size="sm" variant="soft" disabled={dang} onClick={() => setSua(true)}>
            Điều chỉnh
          </Button>
        ) : null}
        {choGhi && lt.nut?.dung && !hoiDung ? (
          <Button size="sm" variant="ghost" disabled={dang} onClick={() => setHoiDung(true)}>
            Dừng
          </Button>
        ) : null}
        {choGhi && lt.nut?.mo_lai ? (
          <Button size="sm" variant="soft" disabled={dang} onClick={() => void gui("mo-lai", {})}>
            Mở lại
          </Button>
        ) : null}
        {choGhi && lt.hoan_tac ? (
          <Button
            size="sm"
            variant="ghost"
            disabled={dang}
            onClick={() => void gui("hoan-tac", { lich_su_id: lt.hoan_tac?.lich_su_id })}
          >
            {nhanNutHoanTac(lt.hoan_tac.hanh_dong)}
          </Button>
        ) : null}
        {choGhi ? them : null}
      </div>
      <LichSuLT ltId={lt.id} />
      {bao ? <p className="text-meta text-warning">{bao}</p> : null}
      {loi ? (
        <p role="alert" className="text-meta text-danger">
          {loi}
        </p>
      ) : null}
    </div>
  );
}

/** Ô trống hiện sẵn: kế hoạch ngắn hiện hết, dài thì vài ô đầu. */
function soTrongHien(conTrong: number): number {
  return conTrong <= TRONG_HIEN_TOI_DA + 1 ? conTrong : TRONG_HIEN_TOI_DA;
}

/** [Khách chọn lộ trình] cho một lộ trình bác sĩ đã đề xuất: tick "tính buổi
 *  hôm nay" (mặc định) = gắn chỉ định hôm nay (máy chủ ghi đăng ký luôn); bỏ
 *  tick = đăng ký, buổi hôm nay vẫn là buổi lẻ. Hoàn tác trên dải. */
function KhachChonLoTrinh({
  u,
  orderId,
  onDoi,
}: {
  u: UngVien;
  orderId: string;
  onDoi: () => void;
}) {
  const [mo, setMo] = useState(false);
  const [tinhHomNay, setTinhHomNay] = useState(true);
  const [dang, setDang] = useState(false);
  const [loi, setLoi] = useState<string | null>(null);
  const chon = async () => {
    setDang(true);
    setLoi(null);
    const kq = tinhHomNay
      ? await lenhLT("gan", { service_order_id: orderId, lieu_trinh_id: u.id, expected_lieu_trinh_id: null })
      : await lenhLT("dang-ky", { expected_revision: u.revision }, u.id);
    setDang(false);
    if (!kq.ok) setLoi(kq.loi);
    else setMo(false);
    onDoi();
  };
  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-body text-ink">
          Bác sĩ đề xuất lộ trình <span className="font-semibold">{u.so_buoi} buổi</span>
          {u.tao_luc ? ` (${fmtDate(u.tao_luc)})` : ""} — khách chưa chọn.
        </span>
        {!mo ? (
          <Button size="sm" variant="primary" onClick={() => setMo(true)}>
            Khách chọn lộ trình
          </Button>
        ) : null}
      </div>
      {mo ? (
        <div className="flex flex-wrap items-center gap-2 rounded-control border border-line bg-surface-muted p-2.5">
          <label className="flex min-h-9 items-center gap-2 text-body text-ink">
            <input
              type="checkbox"
              className="size-4 accent-brand-600"
              checked={tinhHomNay}
              onChange={(e) => setTinhHomNay(e.target.checked)}
            />
            Tính buổi hôm nay vào lộ trình
          </label>
          <Button size="sm" variant="primary" disabled={dang} onClick={() => void chon()}>
            {dang ? "Đang ghi…" : "Xác nhận khách chọn"}
          </Button>
          <Button size="sm" variant="ghost" disabled={dang} onClick={() => setMo(false)}>
            Thôi
          </Button>
        </div>
      ) : null}
      {loi ? (
        <p role="alert" className="text-meta text-danger">
          {loi}
        </p>
      ) : null}
    </div>
  );
}

/** Dải liệu trình của MỘT chỉ định điều trị (trong thẻ của nó) — bàn khám và
 *  phòng dịch vụ dùng chung. Chưa vào lộ trình = BUỔI LẺ (Tuyền 09/10/2026). */
export function DaiLieuTrinh({
  visitId,
  cd,
  luot,
  choGhi,
  onDoi,
}: {
  visitId: string;
  cd: ChiDinhLieuTrinh;
  luot: LieuTrinhLuot;
  choGhi: boolean;
  onDoi: () => void;
}) {
  const [dang, setDang] = useState(false);
  const [loi, setLoi] = useState<string | null>(null);
  const [hoiTach, setHoiTach] = useState<{ n: number; gc: string; chon: boolean } | null>(null);
  const [moTach, setMoTach] = useState(false);
  const [hoiGo, setHoiGo] = useState(false);
  const [khachChonLuon, setKhachChonLuon] = useState(false);
  const lt = cd.lieu_trinh_id ? luot.lieu_trinh.find((x) => x.id === cd.lieu_trinh_id) : undefined;
  // Lộ trình bác sĩ đề xuất TỪ chính chỉ định này (chỉ định vẫn là buổi lẻ).
  const deXuatTuDay = lt
    ? undefined
    : luot.lieu_trinh.find((x) => x.trang_thai === "DE_XUAT" && x.nguon_order_id === cd.order_id);

  const tao = async (n: number, gc: string, tach: boolean, chon: boolean) => {
    setDang(true);
    setLoi(null);
    const kq = await lenhLT("tao", {
      visit_id: visitId,
      so_buoi: n,
      service_order_id: cd.order_id,
      ghi_chu: gc || null,
      tach_khoi_lieu_trinh_cu: tach,
      khach_chon: chon,
    });
    setDang(false);
    if (!kq.ok && kq.ma === "DA_GAN_LIEU_TRINH" && !tach) {
      // Chỉ định đang là buổi của liệu trình khách đang làm (#14): hỏi rõ.
      setHoiTach({ n, gc, chon });
    } else if (!kq.ok) {
      setLoi(kq.loi);
    } else {
      setHoiTach(null);
      setMoTach(false);
      setKhachChonLuon(false);
    }
    onDoi();
  };

  const gan = async (ltId: string) => {
    setDang(true);
    setLoi(null);
    const kq = await lenhLT("gan", {
      service_order_id: cd.order_id,
      lieu_trinh_id: ltId,
      expected_lieu_trinh_id: cd.lieu_trinh_id,
    });
    setDang(false);
    if (!kq.ok) setLoi(kq.loi);
    onDoi();
  };

  const go = async () => {
    if (!cd.lieu_trinh_id) return;
    setDang(true);
    setLoi(null);
    const kq = await lenhLT("go", { service_order_id: cd.order_id, expected_lieu_trinh_id: cd.lieu_trinh_id });
    setDang(false);
    setHoiGo(false);
    if (!kq.ok) setLoi(kq.loi);
    onDoi();
  };

  const nhanUngVien = (u: UngVien) =>
    `${NHAN_TRANG_THAI_LT[u.trang_thai]} · đã làm ${u.da_lam}/${u.so_buoi} buổi${u.tao_luc ? ` · lập ${fmtDate(u.tao_luc)}` : ""}`;
  const khac = cd.ung_vien.filter((u) => u.id !== cd.lieu_trinh_id);
  const deXuat = khac.filter((u) => u.trang_thai === "DE_XUAT");
  const dangLam = khac.filter((u) => u.trang_thai !== "DE_XUAT");

  return (
    <div className="space-y-2">
      {lt ? (
        <>
          {cd.chu_buoi ? (
            <p className="text-emph font-semibold text-ink">
              Buổi này: {cd.chu_buoi}
              {cd.tra_truoc ? " · đã trả trước" : ""}
            </p>
          ) : null}
          <KhungLieuTrinh
            lt={lt}
            orderHomNay={cd.order_id}
            choGhi={choGhi}
            onDoi={onDoi}
            them={
              <>
                {cd.nut?.go ? (
                  <Button size="sm" variant="ghost" disabled={dang} onClick={() => setHoiGo(true)}>
                    Gỡ khỏi lộ trình (thành buổi lẻ)
                  </Button>
                ) : null}
                {cd.nut?.tach && !moTach ? (
                  <Button size="sm" variant="ghost" disabled={dang} onClick={() => setMoTach(true)}>
                    Lập lộ trình mới
                  </Button>
                ) : null}
              </>
            }
          />
        </>
      ) : cd.song ? (
        <div className="space-y-2 rounded-card border border-dashed border-line-strong p-3">
          <p className="text-body text-ink">
            <span className="font-semibold">Buổi lẻ</span> — làm xong trả tiền như thường, chưa vào lộ trình nào.
          </p>
          {deXuat.map((u) =>
            choGhi ? (
              <KhachChonLoTrinh key={u.id} u={u} orderId={cd.order_id} onDoi={onDoi} />
            ) : (
              <p key={u.id} className="text-body text-ink-soft">
                Bác sĩ đề xuất lộ trình {u.so_buoi} buổi — khách chưa chọn.
              </p>
            ),
          )}
          {deXuatTuDay ? <KhungLieuTrinh lt={deXuatTuDay} choGhi={choGhi} onDoi={onDoi} /> : null}
        </div>
      ) : null}
      {choGhi && hoiGo ? (
        <XacNhanTaiCho
          cau="Gỡ chỉ định này khỏi lộ trình? Buổi hôm nay thành buổi lẻ (tính tiền như thường)."
          nhanDongY="Gỡ"
          dangGui={dang}
          onDongY={() => void go()}
          onThoi={() => setHoiGo(false)}
        />
      ) : null}
      {choGhi && cd.can_chon ? (
        <p className="text-body text-warning">
          Khách có {dangLam.length} lộ trình đang làm cùng dịch vụ — chọn lộ trình cho buổi này.
        </p>
      ) : null}
      {choGhi && cd.nut?.chon && dangLam.length > 0 ? (
        <label className="flex flex-wrap items-center gap-2 text-body text-ink-soft">
          {cd.lieu_trinh_id ? "Chuyển sang lộ trình" : "Đưa buổi này vào lộ trình đang làm"}
          <OChon
            value=""
            disabled={dang}
            onChange={(e) => e.target.value && void gan(e.target.value)}
            aria-label="Chọn lộ trình cho chỉ định"
            className="min-w-0 flex-1"
          >
            <option value="">— Chọn lộ trình —</option>
            {dangLam.map((u) => (
              <option key={u.id} value={u.id}>
                {nhanUngVien(u)}
              </option>
            ))}
          </OChon>
        </label>
      ) : null}
      {choGhi && ((cd.nut?.tao && !deXuatTuDay) || moTach) && !hoiTach ? (
        <div className="space-y-2">
          <OLoTrinh
            nhanNut={khachChonLuon ? "Lập lộ trình" : "Đề xuất lộ trình"}
            soBuoiDau={null}
            ghiChuDau=""
            dang={dang}
            onGui={(n, gc) => void tao(n, gc, moTach, khachChonLuon || moTach)}
            onThoi={moTach ? () => setMoTach(false) : undefined}
          />
          {!moTach ? (
            <label className="flex min-h-9 items-center gap-2 text-body text-ink">
              <input
                type="checkbox"
                className="size-4 accent-brand-600"
                checked={khachChonLuon}
                onChange={(e) => setKhachChonLuon(e.target.checked)}
              />
              Khách chọn lộ trình luôn — tính buổi hôm nay là buổi 1
            </label>
          ) : null}
        </div>
      ) : null}
      {choGhi && hoiTach ? (
        <XacNhanTaiCho
          cau="Chỉ định này đang là một buổi của lộ trình khách đang làm. Lập lộ trình MỚI và tách buổi hôm nay sang?"
          nhanDongY="Lập lộ trình mới"
          dangGui={dang}
          onDongY={() => void tao(hoiTach.n, hoiTach.gc, true, true)}
          onThoi={() => setHoiTach(null)}
        />
      ) : null}
      {loi ? (
        <p role="alert" className="text-meta text-danger">
          {loi}
        </p>
      ) : null}
    </div>
  );
}

/** "Chỉ đề xuất liệu trình (không làm hôm nay)" — dịch vụ nhóm Điều trị, không
 *  tạo chỉ định; liệu trình ở trạng thái Đề xuất, CSKH gọi khách đăng ký sau. */
export function DeXuatLieuTrinh({
  visitId,
  dichVu,
  onDoi,
}: {
  visitId: string;
  dichVu: { service_code: string; ten: string }[];
  onDoi: () => void;
}) {
  const [mo, setMo] = useState(false);
  const [ma, setMa] = useState("");
  const [dang, setDang] = useState(false);
  const [loi, setLoi] = useState<string | null>(null);
  if (dichVu.length === 0) return null;
  const gui = async (n: number, gc: string) => {
    setDang(true);
    setLoi(null);
    const kq = await lenhLT("tao", { visit_id: visitId, so_buoi: n, service_code: ma, ghi_chu: gc || null });
    setDang(false);
    if (!kq.ok) setLoi(kq.loi);
    else {
      setMo(false);
      setMa("");
    }
    onDoi();
  };
  return (
    <div className="space-y-2">
      {mo ? (
        <div className="space-y-2 rounded-control border border-dashed border-line p-2.5">
          <p className="text-meta text-ink-muted">
            Chỉ đề xuất liệu trình — không làm hôm nay, không tạo chỉ định, không tính tiền.
          </p>
          <OChon
            value={ma}
            onChange={(e) => setMa(e.target.value)}
            aria-label="Dịch vụ điều trị đề xuất"
            className="w-full"
          >
            <option value="">— Chọn dịch vụ điều trị —</option>
            {dichVu.map((d) => (
              <option key={d.service_code} value={d.service_code}>
                {d.ten}
              </option>
            ))}
          </OChon>
          {ma ? (
            <OLoTrinh
              nhanNut="Đề xuất"
              soBuoiDau={null}
              ghiChuDau=""
              dang={dang}
              onGui={(n, gc) => void gui(n, gc)}
              onThoi={() => setMo(false)}
            />
          ) : (
            <Button size="sm" variant="ghost" onClick={() => setMo(false)}>
              Thôi
            </Button>
          )}
        </div>
      ) : (
        <Button size="sm" variant="soft" onClick={() => setMo(true)}>
          Chỉ đề xuất liệu trình (không làm hôm nay)
        </Button>
      )}
      {loi ? (
        <p role="alert" className="text-meta text-danger">
          {loi}
        </p>
      ) : null}
    </div>
  );
}
