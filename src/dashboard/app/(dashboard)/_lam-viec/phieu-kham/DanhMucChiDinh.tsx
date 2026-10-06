"use client";

// Mục C (cận lâm sàng) và mục F (thủ thuật) của phiếu v5 — DANH MỤC CÓ GIÁ.
//
// KIỂU PHIẾU GIẤY — Y HỆT bản giao diện mẫu (27/09/2026, mục 4; M/app.js
// `danhMuc`, M/style.css `.dm`): mọi nhóm của phiếu chỉ định giấy LUÔN MỞ, lưới
// 3/2/1 cột; mỗi dòng [ô tick | tên | giá + chip mẫu]. Dịch vụ có trong bảng giá
// mà phiếu giấy không có (nhóm "(danh mục phòng khám)") gom vào MỘT ngăn
// "Dịch vụ khác trong bảng giá" — MỞ SẴN (C21, 02/10/2026); mục C chứa MỌI dịch
// vụ đang bán (kể cả phí khám và thủ thuật của phiếu giấy). Tick nhiều mục rồi bấm MỘT lần → thành chỉ định
// thật (lệnh PlaceServiceOrders).
//
// Mã dịch vụ và giá do MÁY CHỦ gắn (bảng ghép viết tay `anh_xa_danh_muc.py`) —
// màn này không so tên. Mục chưa có mã (phòng khám chưa có dịch vụ ấy) khoá lại.
//
// CHỈ ĐỊNH THÊM (Tuyền 25/09/2026): trong CÙNG một lượt khám bác sĩ chỉ định
// được 2, 3 lần — mỗi lần vẫn đi thanh toán rồi làm như lần đầu. Lượt đã có chỉ
// định thì danh mục vẫn MỞ SẴN (C21, 02/10/2026); [Thu gọn] gập sau nút
// [+ Chỉ định thêm (lần N)]. Hộp tóm tắt "Đã chỉ
// định — Lần 1 · …" cũ đã BỎ (27/09): thẻ "Đã chỉ định & kết quả" ngay trên
// (`KetQuaChiDinh`) gom theo lần rồi — và ô "bắt buộc" của chỉ định ĐÃ đặt
// chuyển vào thẻ ấy (mỗi chỉ định một ô, đúng thẻ của nó).
//
// LẦN ỔN ĐỊNH (Tuyền thử thật 06/10/2026): lần do MÁY CHỦ quyết (`lan`). Bấm
// gửi bao nhiêu lần, vào ra màn, tải lại — vẫn vào LẦN HIỆN TẠI. Chỉ nút
// [+ Chỉ định thêm (lần N)] mới chuyển sang chế độ "mở lần mới" cho lần gửi kế.
// Câu "Đã chỉ định N mục" tính lại theo danh sách máy chủ: bỏ bớt thì câu đổi.
//
// CHỈ ĐỊNH LẠI (26/09/2026 — lát 4): dịch vụ đã chỉ định ở lần trước vẫn tick
// được ở lần mới (vd siêu âm lại sau thủ thuật) — tên tô brand đậm + "đã chỉ
// định ở lần n" (bản mẫu `.da-truoc`). Số lần do máy chủ gán.

import { Search } from "lucide-react";
import { useState } from "react";

import Button from "@/components/ui/Button";
import Chip from "@/components/ui/Chip";
import NganGap from "@/components/ui/NganGap";
import {
  chipMauDanhMuc,
  gomTheoNhomGoc,
  tachDanhMucKhac,
  tenHienMuc,
  timDanhMucChiDinh,
  tienVn,
  type ChiDinhVaKetQua,
  type KetQuaDatChiDinh,
  type LanChiDinh,
  type LenhLanChiDinh,
  tongPhongKham,
  type MucCls,
  type NhomCls,
} from "@/lib/phieu-kham";

export default function DanhMucChiDinh({
  nhom,
  daDat,
  daChiDinh = [],
  lan = null,
  onDat,
  chiDoc,
  nhanNut = "Chỉ định",
}: {
  nhom: NhomCls[];
  /** service_code đã có chỉ định (chưa huỷ) trong lượt. */
  daDat: ReadonlySet<string>;
  /** Mọi chỉ định (chưa huỷ) của lượt — để biết "đã chỉ định ở lần n". */
  daChiDinh?: readonly ChiDinhVaKetQua[];
  /** Lần hiện tại / lần kế tiếp — máy chủ trả (06/10/2026). */
  lan?: LanChiDinh | null;
  onDat: (
    codes: string[],
    /** Mã tick "Bắt buộc" (25/09/2026) — quầy thu không bỏ được. */
    batBuoc: string[],
    lan?: LenhLanChiDinh,
  ) => Promise<KetQuaDatChiDinh>;
  chiDoc: boolean;
  nhanNut?: string;
}) {
  const [chon, setChon] = useState<string[]>([]);
  const [dang, setDang] = useState(false);
  const [loi, setLoi] = useState<string | null>(null);
  // Lần gửi vừa rồi: id máy chủ trả + lần — câu báo tính lại theo danh sách.
  const [vuaDat, setVuaDat] = useState<{ ids: string[]; lan: number | null } | null>(null);
  // Đã bấm [+ Chỉ định thêm (lần N)]: lần gửi kế mở lần mới.
  const [moLanMoi, setMoLanMoi] = useState(false);
  // Danh mục MỞ SẴN kể cả khi lượt đã có chỉ định (C21, 02/10/2026 — Tuyền:
  // "cho hiện full ra"); [Thu gọn] gập lại, [+ Chỉ định thêm] / ô tìm mở ra.
  const [moThem, setMoThem] = useState(true);
  // DỊCH VỤ BẮT BUỘC (Tuyền 25/09/2026): mặc định KHÔNG tick.
  const [batBuoc, setBatBuoc] = useState<string[]>([]);
  // TÌM (01/10/2026): gõ "PRP", "NIPT", "liên cầu" ra ngay mọi dịch vụ đang
  // bán, kể cả mục trong ngăn "Dịch vụ khác trong bảng giá".
  const [tim, setTim] = useState("");
  const ketQuaTim = timDanhMucChiDinh(nhom, tim);

  const { chinh, khac } = tachDanhMucKhac(nhom);
  const moiMuc = [...chinh.flatMap((n) => n.muc), ...khac];

  // Một dịch vụ có thể đã chỉ định ở nhiều lần → nhớ lần GẦN nhất.
  const lanCua = new Map<string, number>();
  for (const c of daChiDinh) {
    if (c.lan != null) lanCua.set(c.service_code, Math.max(c.lan, lanCua.get(c.service_code) ?? 0));
  }
  // Lượt đã có chỉ định: bấm [Thu gọn] → gập sau nút [+ Chỉ định thêm].
  const coTruoc = daChiDinh.length > 0;
  // Số lần do máy chủ trả — màn không tự đếm.
  const lanKeTiep = lan?.ke_tiep ?? null;
  const moMoi = moLanMoi && Boolean(lan?.mo_moi_duoc);
  const lanGui = moMoi ? lanKeTiep : (lan?.hien_tai ?? lanKeTiep);
  const conSong = new Set(daChiDinh.map((c) => c.service_order_id));
  const bao = (() => {
    if (!vuaDat || vuaDat.ids.length === 0) return null;
    const con = vuaDat.ids.filter((id) => conSong.has(id)).length;
    const bo = vuaDat.ids.length - con;
    const vao = vuaDat.lan ? ` vào lần ${vuaDat.lan}` : "";
    if (con === 0) return `Đã bỏ cả ${vuaDat.ids.length} mục vừa chỉ định${vao}.`;
    if (bo > 0) return `Đã chỉ định${vao}: còn ${con} mục (đã bỏ ${bo}) — khách vào hàng chờ phòng sau khi thu tiền.`;
    return `Đã chỉ định ${con} mục${vao} — khách vào hàng chờ phòng sau khi thu tiền.`;
  })();
  const hienDanhMuc = !coTruoc || moThem || chon.length > 0;

  // Chỉ cộng phần PHÒNG KHÁM thu — mục khách trả đối tác (cờ máy chủ) không cộng.
  const tong = tongPhongKham(chon, moiMuc);
  const chonTrongKhac = khac.filter((m) => m.service_code && chon.includes(m.service_code)).length;

  const bat = (ma: string, co: boolean) => {
    setChon((cu) => (co ? [...cu, ma] : cu.filter((x) => x !== ma)));
    if (!co) setBatBuoc((cu) => cu.filter((x) => x !== ma));
  };

  const dat = async () => {
    setDang(true);
    setLoi(null);
    setVuaDat(null);
    const kq = await onDat(
      chon,
      batBuoc.filter((c) => chon.includes(c)),
      moMoi ? { lan_moi: true, lan_dang_thay: lan?.hien_tai ?? 0 } : undefined,
    );
    setDang(false);
    if (!kq.ok) {
      setLoi(kq.loi);
      return;
    }
    setVuaDat({ ids: kq.order_ids ?? [], lan: kq.lan ?? null });
    setMoLanMoi(false);
    setChon([]);
    setBatBuoc([]);
  };

  /** Một dòng kiểu phiếu giấy: ô tick (20px) · tên · giá + chip mẫu. */
  const dong = (m: MucCls, phu?: string) => {
    const ma = m.service_code;
    const da = ma ? daDat.has(ma) : false;
    const dangChon = ma ? chon.includes(ma) : false;
    const lan = ma ? lanCua.get(ma) : undefined;
    const mau = chipMauDanhMuc(m);
    const ten = tenHienMuc(m);
    // Máy chủ khoá ô (vd dịch vụ chưa gắn nhóm việc — chỉ định không xếp được).
    const khoa = chiDoc || !ma || Boolean(m.khoa);
    return (
      <li key={`${m.nhan}-${ma ?? ""}`} className="border-b border-hairline">
        <label
          className={`grid min-h-10 grid-cols-[1.25rem_minmax(0,1fr)_auto] items-center gap-1.5 py-1 sm:min-h-8 ${
            dangChon ? "bg-surface-selected" : ""
          } ${khoa ? "" : "cursor-pointer"}`}
        >
          <input
            type="checkbox"
            className="m-0 size-4 accent-brand-600"
            disabled={khoa}
            checked={dangChon}
            onChange={(e) => ma && bat(ma, e.target.checked)}
          />
          <span className="min-w-0">
            <span className={da ? "font-semibold text-brand-700" : "text-ink"}>{ten.chinh}</span>
            {ten.phieuGiay ? (
              <span className="block text-meta text-ink-faint">Trên phiếu giấy: {ten.phieuGiay}</span>
            ) : null}
            {da ? (
              <span className="block text-label font-semibold text-brand-600">
                {lan ? `đã chỉ định ở lần ${lan}` : "đã chỉ định"}
              </span>
            ) : null}
            {phu ? <span className="block text-meta text-ink-faint">{phu}</span> : null}
            {m.khoa ? <span className="block text-meta text-warning">{m.khoa}</span> : null}
          </span>
          <span className="flex flex-col items-end gap-0.5 whitespace-nowrap text-right text-meta text-ink-muted">
            {!ma ? (
              <span className="text-ink-faint">chưa có trong danh mục</span>
            ) : m.gia == null ? (
              <span className="text-ink-faint">chưa có giá</span>
            ) : m.doi_tac_thu ? (
              <span className="tabular-nums" title="Khách trả trực tiếp cho đối tác — không cộng vào tổng">
                {tienVn(m.gia)} · trả đối tác
              </span>
            ) : (
              <span className="tabular-nums">{tienVn(m.gia)}</span>
            )}
            {ma ? <Chip tone={mau.tone}>{mau.nhan}</Chip> : null}
          </span>
        </label>
        {ma && !chiDoc && dangChon ? (
          <label className="ml-6.5 flex min-h-10 items-center gap-2 pb-1 text-meta text-ink sm:min-h-8">
            <input
              type="checkbox"
              className="size-4 accent-brand-600"
              checked={batBuoc.includes(ma)}
              onChange={(e) =>
                setBatBuoc((cu) => (e.target.checked ? [...cu, ma] : cu.filter((x) => x !== ma)))
              }
            />
            Bắt buộc — quầy thu không bỏ được
          </label>
        ) : null}
      </li>
    );
  };

  return (
    <div className="space-y-3">
      {coTruoc && !chiDoc && lan?.mo_moi_duoc && !moMoi ? (
        <Button
          type="button"
          variant="secondary"
          onClick={() => {
            setMoLanMoi(true);
            setMoThem(true);
          }}
        >
          + Chỉ định thêm (lần {lanKeTiep})
        </Button>
      ) : null}
      {coTruoc && !chiDoc && !hienDanhMuc && !lan?.mo_moi_duoc ? (
        <Button type="button" variant="secondary" onClick={() => setMoThem(true)}>
          Mở danh mục chỉ định{lanGui ? ` (lần ${lanGui})` : ""}
        </Button>
      ) : null}
      {moMoi && !chiDoc ? (
        <div className="flex flex-wrap items-center gap-2 rounded-control bg-surface-selected px-3 py-2">
          <Chip tone="brand">Lần {lanKeTiep}</Chip>
          <span className="text-meta text-ink">Các mục tick dưới đây là chỉ định LẦN {lanKeTiep}.</span>
          <Button type="button" variant="ghost" size="sm" onClick={() => setMoLanMoi(false)}>
            Thôi, vẫn lần {lan?.hien_tai}
          </Button>
        </div>
      ) : null}
      {coTruoc && chiDoc ? (
        <p className="text-meta text-ink-muted">
          Phiếu chỉ xem — các chỉ định đã đặt nằm ở thẻ “Đã chỉ định &amp; kết quả”.
        </p>
      ) : null}
      {/* Ô TÌM LUÔN HIỆN (C21, 02/10/2026 — Tuyền: "thêm nút tìm nữa cho
          tiện"): kể cả khi danh mục đang gập sau [+ Chỉ định thêm] — gõ hoặc
          bấm Tìm là mở danh mục, ra kết quả ngay. */}
      {!chiDoc || hienDanhMuc ? (
        <form
          role="search"
          className="flex items-center gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            setMoThem(true);
          }}
        >
          <label className="flex min-h-10 min-w-0 flex-1 items-center gap-2 rounded-control border border-line bg-surface px-2.5 focus-within:border-brand-500 sm:min-h-8">
            <Search aria-hidden className="size-4 shrink-0 text-ink-muted" />
            <span className="sr-only">Tìm dịch vụ để chỉ định</span>
            <input
              type="search"
              value={tim}
              onChange={(e) => {
                setTim(e.target.value);
                if (e.target.value.trim()) setMoThem(true);
              }}
              placeholder="Tìm dịch vụ — vd “ghế điện”, “PRP”, “NIPT”, “siêu âm thai”"
              className="min-w-0 flex-1 bg-transparent text-body text-ink outline-none placeholder:text-ink-faint"
            />
          </label>
          <Button type="submit" variant="secondary">
            Tìm
          </Button>
        </form>
      ) : null}
      {hienDanhMuc && tim.trim() ? (
        ketQuaTim.length === 0 ? (
          <p className="text-meta text-ink-muted">Không thấy dịch vụ nào khớp “{tim.trim()}”.</p>
        ) : (
          <div className="grid items-start gap-4 md:grid-cols-2 xl:grid-cols-3">
            {ketQuaTim.map((n) => (
              <div key={n.nhom} className="min-w-0">
                <h4 className="mb-1 text-label font-semibold uppercase tracking-wide text-ink-muted">
                  {n.nhom}
                </h4>
                <ul>{n.muc.map((m) => dong(m, m.ma_kiotviet ?? undefined))}</ul>
              </div>
            ))}
          </div>
        )
      ) : hienDanhMuc ? (
        <>
          <div className="grid items-start gap-4 md:grid-cols-2 xl:grid-cols-3">
            {chinh.map((n) => (
              <div key={n.nhom} className="min-w-0">
                <h4 className="mb-1 text-label font-semibold uppercase tracking-wide text-ink-muted">
                  {n.nhom}
                </h4>
                <ul>{n.muc.map((m) => dong(m))}</ul>
              </div>
            ))}
          </div>
          {khac.length > 0 ? (
            // Mở sẵn (C21): bác sĩ thấy ĐỦ mọi dịch vụ đang bán, gập lại được.
            <NganGap
              moSan
              tieuDe={`Dịch vụ khác trong bảng giá — không có trên phiếu giấy (${khac.length})`}
              chip={chonTrongKhac > 0 ? <Chip tone="brand">{chonTrongKhac} đang chọn</Chip> : null}
            >
              {/* HAI CỘT CHẢY DỌC từ trên xuống (Tuyền 02/10/2026): xếp hàng hết
                  ra cho nhân viên dò nhanh; nhóm không bị cắt đôi giữa hai cột. */}
              <div className="gap-6 md:columns-2">
                {gomTheoNhomGoc(khac).map(([ten, ds]) => (
                  <div key={ten} className="mb-3 min-w-0 break-inside-avoid">
                    <h4 className="mb-1 text-label font-semibold uppercase tracking-wide text-ink-muted">
                      {ten}
                    </h4>
                    <ul>{ds.map((m) => dong(m, m.ma_kiotviet ?? undefined))}</ul>
                  </div>
                ))}
              </div>
            </NganGap>
          ) : null}
        </>
      ) : null}
      {!chiDoc && hienDanhMuc ? (
        <div className="flex flex-wrap items-center gap-2">
          <Button
            type="button"
            variant="primary"
            disabled={dang || chon.length === 0}
            onClick={() => void dat()}
          >
            {dang
              ? "Đang ghi…"
              : chon.length > 0
                ? `${nhanNut} ${chon.length} mục${lanGui ? ` · lần ${lanGui}` : ""} · ${tienVn(tong)}`
                : `Tick mục cần ${nhanNut.toLowerCase()}${lanGui ? ` (lần ${lanGui})` : ""}`}
          </Button>
          {coTruoc && chon.length === 0 ? (
            <Button type="button" variant="ghost" onClick={() => setMoThem(false)}>
              Thu gọn
            </Button>
          ) : null}
          {loi ? (
            <p role="alert" className="text-meta text-danger">
              {loi}
            </p>
          ) : null}
          {bao ? <p className="text-meta text-success">{bao}</p> : null}
        </div>
      ) : bao ? (
        <p className="text-meta text-success">{bao}</p>
      ) : null}
    </div>
  );
}
