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
import { fmtDate, fmtDateTime } from "@/lib/datetime";
import {
  NHAN_HANH_DONG_LT,
  NHAN_TRANG_THAI_LT,
  docLT,
  lenhLT,
  nhanBuoi,
  tienLT,
  type ChiDinhLieuTrinh,
  type DongLichSuLT,
  type LieuTrinh,
  type LieuTrinhLuot,
  type TrangThaiLieuTrinh,
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
                {d.loai === "SUA" && d.ban_moi ? (
                  <span>
                    {String(d.ban_cu?.so_buoi ?? "—")} → {String(d.ban_moi.so_buoi ?? "—")} buổi
                  </span>
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

/** Thân một liệu trình: số liệu, nút kế hoạch, lịch sử, danh sách buổi. */
export function KhungLieuTrinh({
  lt,
  buoiSo,
  traTruoc,
  choGhi,
  onDoi,
  them,
}: {
  lt: LieuTrinh;
  /** Buổi của chỉ định đang xem (thẻ chỉ định); không có = liệu trình chỉ đề xuất. */
  buoiSo?: number | null;
  traTruoc?: boolean | null;
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
  const [xemBuoi, setXemBuoi] = useState(false);

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

  const buoi = (lt.buoi ?? []).filter((b) => b.song);
  return (
    <div className="space-y-2 rounded-control border border-hairline bg-surface-muted/50 p-2.5">
      <div className="flex flex-wrap items-center gap-1.5">
        <span className="text-label font-semibold uppercase text-ink-muted">Liệu trình</span>
        <Chip tone={TONE_LT[lt.trang_thai]}>{NHAN_TRANG_THAI_LT[lt.trang_thai]}</Chip>
        {buoiSo ? <Chip tone="brand">{nhanBuoi(buoiSo, lt.so_buoi, traTruoc)}</Chip> : null}
        <span className="text-meta text-ink">
          {buoiSo ? "" : `${lt.so_buoi} buổi · `}đã làm {lt.da_lam} · đã trả {lt.da_tra}
          {lt.chua_tra > 0 ? ` · còn nợ ${lt.chua_tra} buổi (${tienLT(lt.tien_con_lai)})` : ""}
        </span>
      </div>
      {lt.ghi_chu_lo_trinh ? <p className="text-meta text-ink-soft">{lt.ghi_chu_lo_trinh}</p> : null}
      {lt.trang_thai === "DUNG" && lt.ly_do_dung ? (
        <p className="text-meta text-ink-muted">Lý do dừng: {lt.ly_do_dung}</p>
      ) : null}

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
            Hoàn tác {(NHAN_HANH_DONG_LT[lt.hoan_tac.hanh_dong] ?? "").toLowerCase()}
          </Button>
        ) : null}
        {choGhi ? them : null}
        {buoi.length > 0 ? (
          <Button size="sm" variant="ghost" aria-expanded={xemBuoi} onClick={() => setXemBuoi(!xemBuoi)}>
            {xemBuoi ? "Ẩn các buổi" : `Các buổi (${buoi.length})`}
          </Button>
        ) : null}
      </div>
      <LichSuLT ltId={lt.id} />

      {xemBuoi ? (
        <ul className="divide-y divide-hairline rounded-control border border-hairline bg-surface text-meta">
          {buoi.map((b) => (
            <li key={b.id} className="flex flex-wrap items-center gap-x-2 gap-y-1 px-2 py-1.5">
              <span className="font-semibold text-ink">Buổi {b.buoi_so}</span>
              <span className="text-ink-soft">{b.ngay ? fmtDate(b.ngay) : "—"}</span>
              <span className="text-ink-soft">{b.noi_lam ?? "chưa xếp nơi làm"}</span>
              <Chip tone={b.da_lam ? "success" : "neutral"}>{b.da_lam ? "Đã làm" : "Chưa làm"}</Chip>
              {b.tra_truoc ? <Chip tone="info">đã trả trước</Chip> : null}
              <a
                href={`/print/ket-qua/${b.order_id}`}
                target="_blank"
                rel="noopener"
                className={`${buttonClass("ghost", "sm")} ml-auto`}
              >
                Phiếu điều trị
              </a>
            </li>
          ))}
        </ul>
      ) : null}
      {bao ? <p className="text-meta text-warning">{bao}</p> : null}
      {loi ? (
        <p role="alert" className="text-meta text-danger">
          {loi}
        </p>
      ) : null}
    </div>
  );
}

/** Dải liệu trình của MỘT chỉ định điều trị (trong thẻ của nó). */
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
  const [hoiTach, setHoiTach] = useState<{ n: number; gc: string } | null>(null);
  const [moTach, setMoTach] = useState(false);
  const [hoiGo, setHoiGo] = useState(false);
  const lt = cd.lieu_trinh_id ? luot.lieu_trinh.find((x) => x.id === cd.lieu_trinh_id) : undefined;

  const tao = async (n: number, gc: string, tach: boolean) => {
    setDang(true);
    setLoi(null);
    const kq = await lenhLT("tao", {
      visit_id: visitId,
      so_buoi: n,
      service_order_id: cd.order_id,
      ghi_chu: gc || null,
      tach_khoi_lieu_trinh_cu: tach,
    });
    setDang(false);
    if (!kq.ok && kq.ma === "DA_GAN_LIEU_TRINH" && !tach) {
      // Chỉ định vừa được tự gắn vào liệu trình khách đang làm (#14): hỏi rõ.
      setHoiTach({ n, gc });
    } else if (!kq.ok) {
      setLoi(kq.loi);
    } else {
      setHoiTach(null);
      setMoTach(false);
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

  const nhanUngVien = (id: string) => {
    const u = cd.ung_vien.find((x) => x.id === id);
    return u
      ? `${NHAN_TRANG_THAI_LT[u.trang_thai]} · ${u.da_lam}/${u.so_buoi} buổi${u.tao_luc ? ` · lập ${fmtDate(u.tao_luc)}` : ""}`
      : id;
  };
  const khac = cd.ung_vien.filter((u) => u.id !== cd.lieu_trinh_id);

  return (
    <div className="space-y-2">
      {lt ? (
        <KhungLieuTrinh
          lt={lt}
          buoiSo={cd.buoi_so}
          traTruoc={cd.tra_truoc}
          choGhi={choGhi}
          onDoi={onDoi}
          them={
            <>
              {cd.nut?.go ? (
                <Button size="sm" variant="ghost" disabled={dang} onClick={() => setHoiGo(true)}>
                  Gỡ khỏi liệu trình
                </Button>
              ) : null}
              {cd.nut?.tach && !moTach ? (
                <Button size="sm" variant="ghost" disabled={dang} onClick={() => setMoTach(true)}>
                  Lập liệu trình mới
                </Button>
              ) : null}
            </>
          }
        />
      ) : null}
      {choGhi && hoiGo ? (
        <XacNhanTaiCho
          cau="Gỡ chỉ định này khỏi liệu trình? Buổi hôm nay thành buổi lẻ (tính tiền như thường)."
          nhanDongY="Gỡ"
          dangGui={dang}
          onDongY={() => void go()}
          onThoi={() => setHoiGo(false)}
        />
      ) : null}
      {choGhi && cd.can_chon ? (
        <p className="text-meta text-warning">
          Khách có {cd.ung_vien.length} liệu trình cùng dịch vụ — chọn liệu trình cho chỉ định này.
        </p>
      ) : null}
      {choGhi && cd.nut?.chon && khac.length > 0 ? (
        <label className="flex flex-wrap items-center gap-2 text-meta text-ink-soft">
          {cd.lieu_trinh_id ? "Chuyển sang liệu trình" : "Gắn vào liệu trình có sẵn"}
          <OChon
            value=""
            disabled={dang}
            onChange={(e) => e.target.value && void gan(e.target.value)}
            aria-label="Chọn liệu trình cho chỉ định"
            className="min-w-0 flex-1"
          >
            <option value="">— Chọn liệu trình —</option>
            {khac.map((u) => (
              <option key={u.id} value={u.id}>
                {nhanUngVien(u.id)}
              </option>
            ))}
          </OChon>
        </label>
      ) : null}
      {choGhi && (cd.nut?.tao || moTach) && !hoiTach ? (
        <OLoTrinh
          nhanNut="Tạo liệu trình"
          soBuoiDau={null}
          ghiChuDau=""
          dang={dang}
          onGui={(n, gc) => void tao(n, gc, moTach)}
          onThoi={moTach ? () => setMoTach(false) : undefined}
          truoc={<span className="text-meta text-ink-muted">Buổi hôm nay = buổi 1 ·</span>}
        />
      ) : null}
      {choGhi && hoiTach ? (
        <XacNhanTaiCho
          cau="Chỉ định này đang là một buổi của liệu trình khách đang làm. Lập liệu trình MỚI và tách buổi hôm nay sang?"
          nhanDongY="Lập liệu trình mới"
          dangGui={dang}
          onDongY={() => void tao(hoiTach.n, hoiTach.gc, true)}
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
