// (Client — chỉ `BanXetNghiem.tsx` dùng.) Thẻ MỘT việc xét nghiệm đối tác — hình theo
// bản mẫu 05/11 (bước Thu hộ · Mẫu · Tờ kết quả · Xem quá trình). Nút nào hiện là do cờ
// `nut` máy chủ trả (kể cả cờ đã xét người xem là quản lý); bước nào sáng là mốc
// "current" máy chủ chỉ. "Hoàn tác bước trước" gọi ĐÚNG lệnh bù máy chủ chỉ ra
// (`nut.hoan_tac.lenh`), luôn hỏi lý do — không quay bản chụp.

import { useState, type ReactNode } from "react";

import Button from "@/components/ui/Button";
import Chip from "@/components/ui/Chip";
import Lightbox from "@/components/ui/Lightbox";
import OChon from "@/components/ui/OChon";
import ONhap from "@/components/ui/ONhap";
import { loiDocDuoc } from "@/lib/loi-doc-duoc";

import { tepXem } from "../_lam-viec/AnhKetQua";
import BuocThuHo, { O } from "./BuocThuHo";
import { CHUA_TAI, gioNgay, lenh, ngayVN, type Viec } from "./kieu";

type Mo = null | "hoan_tac" | "gui";

/** Lệnh bù máy chủ chỉ → cửa (ánh xạ tên, không luật). Lệnh màn chưa biết ⇒ không có
 *  trong bảng ⇒ không hiện nút (khỏi âm thầm gọi nhầm lệnh khác). */
const CUA_BU: Record<string, string> = {
  huy_mau: "huy-mau",
  huy_thu: "huy-thu",
  thu_hoi: "thu-hoi",
  mo_lai: "mo-lai",
};

function thanBu(v: Viec, lenhBu: string, ly_do: string, loai: string): unknown {
  return lenhBu === "huy_mau" ? { mau_id: v.mau_id, loai, ly_do } : { order_id: v.order_id, ly_do };
}

function Buoc({ sang, children }: { sang: boolean; children: ReactNode }) {
  return (
    <div className={`flex flex-col gap-2 py-2 ${sang ? "-mx-2 rounded-control bg-brand-50 px-2" : "border-t border-line"}`}>
      {children}
    </div>
  );
}

interface DongQt {
  luc: string;
  viec: string;
  ai: string | null;
}

export default function TheViec({
  v,
  moVua = false,
  onXong,
  onLayMau,
}: {
  v: Viec;
  /** Vừa "Mở" tới việc này (popup / Còn tồn / Kết quả) ⇒ tô nền bước đang tới lượt
   *  (bản mẫu `.step.sang`); bình thường không tô. */
  moVua?: boolean;
  onXong: (bao: string) => void;
  onLayMau: (ids: string[]) => void;
}) {
  const sang = (b: Viec["buoc_dang"]) => moVua && v.buoc_dang === b;
  const [mo, setMo] = useState<Mo>(null);
  const [lyDo, setLyDo] = useState("");
  const [kenh, setKenh] = useState("ZALO");
  const [loaiHuy, setLoaiHuy] = useState("NHAP_SAI");
  const [dang, setDang] = useState(false);
  const [loi, setLoi] = useState<string | null>(null);
  const [qt, setQt] = useState<DongQt[] | null>(null);
  const [xem, setXem] = useState(false);
  const t = v.trang_thai;
  const n = v.nut;
  const cuaBu = n.hoan_tac ? CUA_BU[n.hoan_tac.lenh] : undefined;

  async function chay(duong: string, body: unknown, bao: string): Promise<boolean> {
    setDang(true);
    setLoi(null);
    const e = await lenh(duong, body);
    setDang(false);
    if (e) {
      setLoi(e);
      return false;
    }
    setMo(null);
    setLyDo("");
    onXong(bao);
    return true;
  }

  async function taiTep(f: File) {
    setDang(true);
    setLoi(null);
    const fd = new FormData();
    fd.append("order_id", v.order_id);
    fd.append("file", f, f.name);
    try {
      const r = await fetch("/api/xet-nghiem/tai-ket-qua", { method: "POST", body: fd });
      if (!r.ok) setLoi(loiDocDuoc(await r.json().catch(() => null), `Chưa tải được (HTTP ${r.status}).`));
      else onXong("Đã tải kết quả — bác sĩ và CSKH đã được báo.");
    } catch {
      setLoi("Mất kết nối — tệp CHƯA được lưu.");
    } finally {
      setDang(false);
    }
  }

  async function moQuaTrinh() {
    if (qt) {
      setQt(null);
      return;
    }
    try {
      const r = await fetch(`/api/xet-nghiem/ban/qua-trinh?order_id=${encodeURIComponent(v.order_id)}`, { cache: "no-store" });
      // Chỉ đọc: không tải được thì hiện dòng nhẹ (CHUA_TAI), không đỏ, không mã lỗi.
      if (!r.ok) setQt([{ luc: "", viec: CHUA_TAI, ai: null }]);
      else setQt(((await r.json()) as { dong: DongQt[] }).dong);
    } catch {
      setQt([{ luc: "", viec: CHUA_TAI, ai: null }]);
    }
  }

  const oLyDo = (nhan: string) => (
    <label className="flex min-w-0 flex-1 flex-col gap-1 text-meta text-ink-soft">
      {nhan}
      <ONhap value={lyDo} maxLength={500} onChange={(e) => setLyDo(e.target.value)} />
    </label>
  );

  return (
    <article className="flex flex-col gap-2 rounded-card border border-line bg-surface p-4 shadow-card">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="min-w-0 text-body">
          <span className="font-semibold text-ink">{v.ten_dich_vu}</span> <span className="text-ink-muted">· {v.ten_doi_tac}</span>
        </p>
        <div className="flex flex-wrap gap-1">
          <Chip tone={t.mau}>{t.nhan}</Chip>
          {t.mau_qua_hen ? <Chip tone={t.mau_qua_hen}>Quá hẹn {t.so_ngay_qua_hen} ngày</Chip> : null}
          {t.qua_han_lay_mau ? <Chip tone="warning">Đã thu lâu, chưa lấy mẫu</Chip> : null}
          {t.co_ban_moi_chua_gui ? <Chip tone="warning">Có kết quả mới chưa gửi</Chip> : null}
          {t.da_hoan_tien ? <Chip tone="info">Đã hoàn tiền</Chip> : null}
        </div>
      </div>

      <Buoc sang={sang("thu")}>
        <BuocThuHo
          v={v}
          dang={dang}
          oLyDo={oLyDo}
          lyDo={lyDo}
          onChay={chay}
          onAnh={() => onXong("Đã cập nhật ảnh chuyển khoản.")}
        />
      </Buoc>

      <Buoc sang={sang("mau")}>
        <div className="flex items-center justify-between gap-2">
          <span className="text-body font-semibold text-ink">Mẫu</span>
          {v.ma_mau ? <span className="font-mono text-meta font-semibold tracking-wider text-ink">Mã ống {v.ma_mau}</span> : null}
        </div>
        {n.hien_lay_mau ? (
          <div className="flex flex-wrap items-center gap-2">
            <span title={n.lay_mau ? undefined : (t.ly_do_khong_lay_mau ?? undefined)}>
              <Button type="button" variant="primary" disabled={!n.lay_mau || dang} onClick={() => onLayMau([v.order_id])}>
                Lấy mẫu
              </Button>
            </span>
            {!n.lay_mau && t.ly_do_khong_lay_mau ? <span className="text-meta text-ink-muted">{t.ly_do_khong_lay_mau}</span> : null}
          </div>
        ) : null}
        {v.hen_tra_ngay ? <p className="text-meta text-ink-muted">Hẹn trả {ngayVN(v.hen_tra_ngay)}</p> : null}
      </Buoc>

      <Buoc sang={sang("ket_qua")}>
        <span className="text-body font-semibold text-ink">Tờ kết quả</span>
        <p className="text-meta text-ink-soft">{t.vi_sao}</p>
        {v.tep_id ? (
          <p className="text-meta">
            {/* Bấm tên ⇒ đúng hộp xem của bàn khám (xem ảnh/PDF tại chỗ, phóng to, Tải về). */}
            <button type="button" className="font-semibold text-brand-700 hover:underline" onClick={() => setXem(true)}>
              {v.ten_tep}
            </button>{" "}
            <span className="text-ink-muted">
              · {v.nguon_tep ?? "Tải lên"} · {gioNgay(v.tep_luc)}
            </span>
          </p>
        ) : null}
        <div className="flex flex-wrap items-center gap-2">
          {n.tai_ket_qua ? (
            <label className="inline-flex min-h-10 cursor-pointer items-center rounded-control px-3 text-sm font-medium text-ink-soft ring-1 ring-inset ring-line-strong hover:bg-surface-sunken">
              {v.tep_id ? "Tải bản mới lên tay" : "Tải kết quả lên tay"}
              <input
                type="file"
                accept="application/pdf,image/*"
                className="sr-only"
                disabled={dang}
                onChange={(e) => {
                  const f = e.target.files?.[0];
                  if (f) void taiTep(f);
                }}
              />
            </label>
          ) : null}
          {n.gui && mo !== "gui" ? (
            <Button type="button" variant="primary" onClick={() => setMo("gui")}>
              Đúng người, gửi
            </Button>
          ) : null}
        </div>
        {mo === "gui" ? (
          <div className="flex flex-wrap items-end gap-2">
            <O nhan="Đã gửi khách qua">
              <OChon value={kenh} onChange={(e) => setKenh(e.target.value)}>
                <option value="ZALO">Zalo</option>
                <option value="SMS">SMS</option>
                <option value="TRUC_TIEP">Trực tiếp</option>
                <option value="EMAIL">Email</option>
              </OChon>
            </O>
            <Button type="button" variant="primary" disabled={dang} onClick={() => void chay("gui", { order_id: v.order_id, kenh }, "Đã ghi nhận gửi khách.")}>
              Xác nhận đúng người, đã gửi
            </Button>
            <Button type="button" variant="ghost" onClick={() => setMo(null)}>
              Thôi
            </Button>
          </div>
        ) : null}
      </Buoc>

      <div className="flex flex-col gap-2 border-t border-line pt-2">
        <div className="flex flex-wrap gap-2">
          <Button type="button" variant="ghost" onClick={() => void moQuaTrinh()}>
            {qt ? "Ẩn quá trình" : "Xem quá trình"}
          </Button>
          {n.hoan_tac && cuaBu ? (
            <Button type="button" variant="ghost" onClick={() => setMo("hoan_tac")}>
              {n.mo_lai ? n.hoan_tac.nhan : "Hoàn tác bước trước"}
            </Button>
          ) : null}
        </div>
        {mo === "hoan_tac" ? (
          <div className="flex flex-wrap items-end gap-2">
            {mo === "hoan_tac" && n.hoan_tac?.lenh === "huy_mau" ? (
              <O nhan="Loại huỷ">
                <OChon value={loaiHuy} onChange={(e) => setLoaiHuy(e.target.value)}>
                  <option value="NHAP_SAI">Nhập / dán nhầm</option>
                  <option value="MAU_HONG">Mẫu hỏng / đối tác từ chối</option>
                </OChon>
              </O>
            ) : null}
            {oLyDo(`${n.hoan_tac?.nhan ?? ""} — lý do`)}
            <Button
              type="button"
              variant="primary"
              disabled={dang}
              onClick={() => {
                if (n.hoan_tac && cuaBu) void chay(cuaBu, thanBu(v, n.hoan_tac.lenh, lyDo, loaiHuy), `Đã làm: ${n.hoan_tac.nhan}.`);
              }}
            >
              Xác nhận
            </Button>
            <Button type="button" variant="ghost" onClick={() => setMo(null)}>
              Thôi
            </Button>
          </div>
        ) : null}
        {qt ? (
          qt.length ? (
            <ol aria-label="Quá trình" className="flex flex-col gap-3 pl-1 pt-1">
              {qt.map((h, i) => (
                <li key={`${h.luc}-${i}`} className="flex gap-3">
                  <span aria-hidden className="mt-1 size-3 shrink-0 rounded-full bg-brand-600" />
                  <div className="min-w-0">
                    <p className="text-body text-ink">{h.viec}</p>
                    <p className="text-meta text-ink-muted">
                      {gioNgay(h.luc)}
                      {h.ai ? ` · ${h.ai}` : ""}
                    </p>
                  </div>
                </li>
              ))}
            </ol>
          ) : (
            <p className="text-meta text-ink-muted">Chưa có bước nào.</p>
          )
        ) : null}
      </div>

      {loi ? (
        <p role="alert" className="text-meta text-danger">
          {loi}
        </p>
      ) : null}

      {xem && v.tep_id ? (
        <Lightbox
          tieuDe={`${v.ten_dich_vu ?? "Kết quả"} · ${v.ten_khach ?? "Khách"}`}
          phuDe={[v.nguon_tep, gioNgay(v.tep_luc)].filter(Boolean).join(" · ")}
          tep={[tepXem({ id: v.tep_id, ten: v.ten_tep, loai_tep: v.loai_tep ?? "PDF", mime: v.mime_tep })]}
          onDong={() => setXem(false)}
        />
      ) : null}
    </article>
  );
}
