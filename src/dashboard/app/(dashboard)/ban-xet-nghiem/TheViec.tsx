// (Client — chỉ `BanXetNghiem.tsx` dùng.) Thẻ MỘT việc xét nghiệm đối tác — hình theo bản mẫu 05/11 (bước Thu hộ · Mẫu · Tờ kết
// quả · Xem quá trình). Nút nào hiện là do cờ `nut` / `quanLy` máy chủ trả; bước nào
// sáng là mốc "current" máy chủ chỉ. "Hoàn tác bước trước" gọi ĐÚNG lệnh bù máy chủ chỉ
// ra (`nut.hoan_tac.lenh`), luôn hỏi lý do — không quay bản chụp.

import { useState, type ReactNode } from "react";

import Button from "@/components/ui/Button";
import Chip from "@/components/ui/Chip";
import OChon from "@/components/ui/OChon";
import ONhap from "@/components/ui/ONhap";
import { loiDocDuoc } from "@/lib/loi-doc-duoc";

import { gioNgay, lenh, ngayVN, tien, type Viec } from "./kieu";

type Mo = null | "thu" | "hoan" | "cho_qua" | "dong" | "hoan_tac" | "gui";

/** Lệnh bù → cửa + thân (chỉ ánh xạ tên lệnh máy chủ chỉ ra, không luật). */
function thanHoanTac(v: Viec, ten: string, ly_do: string, loai: string): [string, unknown] {
  if (ten === "huy_mau") return ["huy-mau", { mau_id: v.mau_id, loai, ly_do }];
  if (ten === "huy_thu") return ["huy-thu", { order_id: v.order_id, ly_do }];
  if (ten === "thu_hoi") return ["thu-hoi", { order_id: v.order_id, ly_do }];
  if (ten === "go_cho_qua") return ["go-cho-qua", { order_id: v.order_id, ly_do }];
  return ["mo-lai", { order_id: v.order_id, ly_do }];
}

function Buoc({ sang, children }: { sang: boolean; children: ReactNode }) {
  return (
    <div
      className={`flex flex-col gap-2 py-2 ${sang ? "-mx-2 rounded-control bg-brand-50 px-2" : "border-t border-line"}`}
    >
      {children}
    </div>
  );
}

const O = ({ nhan, children }: { nhan: string; children: ReactNode }) => (
  <label className="flex flex-col gap-1 text-meta text-ink-soft">
    {nhan}
    {children}
  </label>
);

export default function TheViec({
  v,
  quanLy,
  onXong,
  onLayMau,
}: {
  v: Viec;
  quanLy: boolean;
  onXong: (bao: string) => void;
  onLayMau: (ids: string[]) => void;
}) {
  const [mo, setMo] = useState<Mo>(null);
  const [coTm, setCoTm] = useState(true);
  const [coCk, setCoCk] = useState(false);
  const [tm, setTm] = useState("");
  const [ck, setCk] = useState("");
  const [maGd, setMaGd] = useState("");
  const [lyDo, setLyDo] = useState("");
  const [kenh, setKenh] = useState("ZALO");
  const [loaiHuy, setLoaiHuy] = useState("NHAP_SAI");
  const [dang, setDang] = useState(false);
  const [loi, setLoi] = useState<string | null>(null);
  const [qt, setQt] = useState<{ luc: string; viec: string; ai: string | null }[] | null>(null);
  const t = v.trang_thai;
  const n = v.nut;
  // Bước nào đang tới lượt — đọc mốc "current" máy chủ chỉ (1 thu · 2 mẫu · 3–4 kết quả).
  const dangO = v.hanh_trinh.findIndex((m) => m.trang_thai === "current");

  async function chay(duong: string, body: unknown, bao: string) {
    setDang(true);
    setLoi(null);
    const e = await lenh(duong, body);
    setDang(false);
    if (e) {
      setLoi(e);
      return;
    }
    setMo(null);
    setLyDo("");
    onXong(bao);
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
      const r = await fetch(`/api/xet-nghiem/ban/qua-trinh?order_id=${encodeURIComponent(v.order_id)}`, {
        cache: "no-store",
      });
      const d = await r.json().catch(() => null);
      if (!r.ok) setLoi(loiDocDuoc(d, `Chưa đọc được quá trình (HTTP ${r.status}).`));
      else setQt((d as { dong: { luc: string; viec: string; ai: string | null }[] }).dong);
    } catch {
      setLoi("Mất kết nối — chưa đọc được quá trình.");
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
          <span className="font-semibold text-ink">{v.ten_dich_vu}</span>{" "}
          <span className="text-ink-muted">· {v.ten_doi_tac}</span>
        </p>
        <div className="flex flex-wrap gap-1">
          <Chip tone={t.mau}>{t.nhan}</Chip>
          {t.muc_qua_hen ? (
            <Chip tone={t.muc_qua_hen === "DO" ? "danger" : "warning"}>Quá hẹn {t.so_ngay_qua_hen} ngày</Chip>
          ) : null}
          {t.qua_han_lay_mau ? <Chip tone="warning">Đã thu lâu, chưa lấy mẫu</Chip> : null}
          {t.co_ban_moi_chua_gui ? <Chip tone="warning">Có kết quả mới chưa gửi</Chip> : null}
          {t.da_hoan_tien ? <Chip tone="info">Đã hoàn tiền</Chip> : null}
        </div>
      </div>

      <Buoc sang={dangO === 1}>
        <div className="flex items-center justify-between gap-2">
          <span className="text-body font-semibold text-ink">Thu hộ</span>
          <span className="text-body tabular-nums text-ink-soft">
            {v.gia_goi_y !== null ? `Giá gợi ý ${tien(v.gia_goi_y)}` : "Chưa có giá gợi ý"}
          </span>
        </div>
        {v.da_thu !== null ? (
          <p className="text-meta text-ink-soft">
            Đã thu {tien(v.da_thu)} — tiền mặt {tien(v.tien_mat)}, chuyển khoản {tien(v.chuyen_khoan)}
            {v.ma_giao_dich ? ` · mã GD ${v.ma_giao_dich}` : ""} · không tính doanh thu
            {v.da_hoan ? ` · đã hoàn ${tien(v.da_hoan)}` : ""}
          </p>
        ) : null}
        <div className="flex flex-wrap gap-2">
          {n.ghi_thu && mo !== "thu" ? (
            <Button type="button" variant="primary" onClick={() => setMo("thu")}>
              Thu tiền
            </Button>
          ) : null}
          {n.cho_qua && quanLy ? (
            <Button type="button" variant="ghost" onClick={() => setMo("cho_qua")}>
              Cho lấy mẫu trước (quản lý)
            </Button>
          ) : null}
          {n.hoan_tien ? (
            <Button type="button" variant="ghost" onClick={() => setMo("hoan")}>
              Hoàn tiền
            </Button>
          ) : null}
        </div>
        {mo === "thu" ? (
          <div className="flex flex-col gap-2">
            <div className="flex flex-wrap items-center gap-2">
              <Button type="button" size="sm" variant={coTm ? "primary" : "secondary"} aria-pressed={coTm} onClick={() => setCoTm(!coTm)}>
                Tiền mặt
              </Button>
              <Button type="button" size="sm" variant={coCk ? "primary" : "secondary"} aria-pressed={coCk} onClick={() => setCoCk(!coCk)}>
                Chuyển khoản
              </Button>
              {coTm && coCk ? <span className="text-meta text-ink-muted">khách trả bằng cả hai</span> : null}
            </div>
            <div className="flex flex-wrap items-end gap-2">
              {coTm ? (
                <O nhan="Tiền mặt">
                  <ONhap value={tm} inputMode="numeric" placeholder={tien(v.gia_goi_y)} onChange={(e) => setTm(e.target.value)} />
                </O>
              ) : null}
              {coCk ? (
                <>
                  <O nhan="Chuyển khoản">
                    <ONhap value={ck} inputMode="numeric" placeholder={coTm ? "" : tien(v.gia_goi_y)} onChange={(e) => setCk(e.target.value)} />
                  </O>
                  <O nhan="Mã giao dịch">
                    <ONhap value={maGd} maxLength={100} onChange={(e) => setMaGd(e.target.value)} />
                  </O>
                </>
              ) : null}
            </div>
            {coCk ? (
              <p className="text-meta text-ink-soft">
                <span className="text-ink-muted">Chuyển khoản vào:</span> <b>Tài khoản thu hộ</b>
              </p>
            ) : null}
            <p className="text-meta text-ink-muted">
              Ghi đúng số khách trả (giá gợi ý chỉ để tham khảo; miễn phí thì gõ 0). Tiền này của đối tác — không vào két.
            </p>
            <div className="flex gap-2">
              <Button
                type="button"
                variant="primary"
                disabled={dang || (!coTm && !coCk)}
                onClick={() =>
                  void chay(
                    "ghi-thu",
                    { order_id: v.order_id, tien_mat: coTm ? tm : "", chuyen_khoan: coCk ? ck : "", ma_giao_dich: coCk ? maGd : "" },
                    "Đã ghi nhận thu hộ.",
                  )
                }
              >
                Ghi nhận thu hộ
              </Button>
              <Button type="button" variant="ghost" onClick={() => setMo(null)}>
                Thôi
              </Button>
            </div>
          </div>
        ) : null}
        {mo === "hoan" ? (
          <div className="flex flex-wrap items-end gap-2">
            <O nhan="Hoàn tiền mặt">
              <ONhap value={tm} inputMode="numeric" placeholder={tien(n.con_hoan_duoc)} onChange={(e) => setTm(e.target.value)} />
            </O>
            <O nhan="Hoàn chuyển khoản">
              <ONhap value={ck} inputMode="numeric" onChange={(e) => setCk(e.target.value)} />
            </O>
            {oLyDo("Lý do hoàn")}
            <Button
              type="button"
              variant="primary"
              disabled={dang}
              onClick={() => void chay("hoan-tien", { order_id: v.order_id, tien_mat: tm, chuyen_khoan: ck, ly_do: lyDo }, "Đã ghi hoàn tiền.")}
            >
              Hoàn
            </Button>
          </div>
        ) : null}
      </Buoc>

      <Buoc sang={dangO === 2}>
        <div className="flex items-center justify-between gap-2">
          <span className="text-body font-semibold text-ink">Mẫu</span>
          {v.ma_mau ? <span className="font-mono text-meta font-semibold tracking-wider text-ink">Mã ống {v.ma_mau}</span> : null}
        </div>
        {!v.ma_mau && t.con_ton ? (
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

      <Buoc sang={dangO === 3 || dangO === 4}>
        <span className="text-body font-semibold text-ink">Tờ kết quả</span>
        <p className="text-meta text-ink-soft">{t.vi_sao}</p>
        {v.tep_id ? (
          <p className="text-meta">
            <span className="font-semibold text-brand-700">{v.ten_tep}</span>{" "}
            <span className="text-ink-muted">· tải lên {gioNgay(v.tep_luc)}</span>
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
          {n.dong ? (
            <Button type="button" variant="ghost" onClick={() => setMo("dong")}>
              Đối tác đã tự trả khách
            </Button>
          ) : null}
          {n.hoan_tac && (n.hoan_tac.lenh !== "go_cho_qua" || quanLy) ? (
            <Button type="button" variant="ghost" onClick={() => setMo("hoan_tac")}>
              {n.hoan_tac.lenh === "mo_lai" ? n.hoan_tac.nhan : "Hoàn tác bước trước"}
            </Button>
          ) : null}
        </div>
        {mo === "cho_qua" || mo === "dong" || mo === "hoan_tac" ? (
          <div className="flex flex-wrap items-end gap-2">
            {mo === "hoan_tac" && n.hoan_tac?.lenh === "huy_mau" ? (
              <O nhan="Loại huỷ">
                <OChon value={loaiHuy} onChange={(e) => setLoaiHuy(e.target.value)}>
                  <option value="NHAP_SAI">Nhập / dán nhầm</option>
                  <option value="MAU_HONG">Mẫu hỏng / đối tác từ chối</option>
                </OChon>
              </O>
            ) : null}
            {oLyDo(
              mo === "cho_qua"
                ? "Lý do cho lấy mẫu khi chưa thu"
                : mo === "dong"
                  ? "Đối tác trả khách lúc nào, qua đâu"
                  : `${n.hoan_tac?.nhan ?? ""} — lý do`,
            )}
            <Button
              type="button"
              variant="primary"
              disabled={dang}
              onClick={() => {
                if (mo === "cho_qua") void chay("cho-qua", { order_id: v.order_id, ly_do: lyDo }, "Đã cho lấy mẫu trước.");
                else if (mo === "dong") void chay("dong", { order_id: v.order_id, ly_do: lyDo }, "Đã đóng việc.");
                else if (n.hoan_tac) {
                  const [d, b] = thanHoanTac(v, n.hoan_tac.lenh, lyDo, loaiHuy);
                  void chay(d, b, `Đã làm: ${n.hoan_tac.nhan}.`);
                }
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
    </article>
  );
}
