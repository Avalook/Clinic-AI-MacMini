// (Client — chỉ `BanXetNghiem.tsx` dùng.) Một việc xét nghiệm đối tác: trạng thái (máy chủ tính) + các thao tác. Nút nào hiện
// là do cờ `nut` của máy chủ — màn không tự suy luật. "Hoàn tác bước trước" gọi ĐÚNG
// lệnh bù máy chủ chỉ ra (`nut.hoan_tac.lenh`), luôn hỏi lý do.

import { useState } from "react";

import Button from "@/components/ui/Button";
import Chip from "@/components/ui/Chip";
import OChon from "@/components/ui/OChon";
import ONhap from "@/components/ui/ONhap";
import { loiDocDuoc } from "@/lib/loi-doc-duoc";

import { lenh, ngayVN, tien, type Viec } from "./kieu";

type Mo = null | "thu" | "hoan" | "cho_qua" | "dong" | "hoan_tac" | "gui";

/** Lệnh bù → cửa + thân (chỉ ánh xạ tên lệnh máy chủ chỉ ra, không luật). */
function thanHoanTac(v: Viec, ten: string, ly_do: string, loai: string): [string, unknown] {
  if (ten === "huy_mau") return ["huy-mau", { mau_id: v.mau_id, loai, ly_do }];
  if (ten === "huy_thu") return ["huy-thu", { order_id: v.order_id, ly_do }];
  if (ten === "thu_hoi") return ["thu-hoi", { order_id: v.order_id, ly_do }];
  if (ten === "go_cho_qua") return ["go-cho-qua", { order_id: v.order_id, ly_do }];
  return ["mo-lai", { order_id: v.order_id, ly_do }];
}

export default function ThaoTacViec({ v, onXong }: { v: Viec; onXong: (bao: string) => void }) {
  const [mo, setMo] = useState<Mo>(null);
  const [tm, setTm] = useState("");
  const [ck, setCk] = useState("");
  const [maGd, setMaGd] = useState("");
  const [lyDo, setLyDo] = useState("");
  const [kenh, setKenh] = useState("ZALO");
  const [loaiHuy, setLoaiHuy] = useState("NHAP_SAI");
  const [dang, setDang] = useState(false);
  const [loi, setLoi] = useState<string | null>(null);
  const t = v.trang_thai;
  const n = v.nut;

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

  const oLyDo = (nhan: string) => (
    <label className="flex min-w-0 flex-1 flex-col gap-1 text-meta text-ink-soft">
      {nhan}
      <ONhap value={lyDo} maxLength={500} onChange={(e) => setLyDo(e.target.value)} />
    </label>
  );

  return (
    <div className="space-y-2 rounded-card border border-line bg-surface p-3">
      <div className="flex flex-wrap items-center gap-2">
        <span className="min-w-0 flex-1 text-body font-medium text-ink">{v.ten_dich_vu}</span>
        <Chip tone="neutral">{t.nhan}</Chip>
        {t.muc_qua_hen ? (
          <Chip tone={t.muc_qua_hen === "DO" ? "danger" : "warning"}>Quá hẹn {t.so_ngay_qua_hen} ngày</Chip>
        ) : null}
        {t.qua_han_lay_mau ? <Chip tone="warning">Đã thu lâu, chưa lấy mẫu</Chip> : null}
        {t.co_ban_moi_chua_gui ? <Chip tone="warning">Có kết quả mới chưa gửi</Chip> : null}
        {t.da_hoan_tien ? <Chip tone="info">Đã hoàn tiền</Chip> : null}
      </div>
      <p className="text-meta text-ink-muted">
        {v.ten_doi_tac}
        {v.da_thu !== null ? ` · Đã thu ${tien(v.da_thu)} (TM ${tien(v.tien_mat)}, CK ${tien(v.chuyen_khoan)})` : ""}
        {v.da_hoan ? ` · Đã hoàn ${tien(v.da_hoan)}` : ""}
        {v.hen_tra_ngay ? ` · Hẹn trả ${ngayVN(v.hen_tra_ngay)}` : ""}
      </p>
      {v.ma_mau ? (
        <p className="text-meta text-ink-soft">
          Mã ống <span className="font-mono text-emph font-semibold tracking-wider text-ink">{v.ma_mau}</span>
          {v.ten_tep ? ` · Kết quả: ${v.ten_tep}` : ""}
        </p>
      ) : null}

      <div className="flex flex-wrap gap-2">
        {n.ghi_thu ? (
          <Button type="button" size="sm" variant="primary" onClick={() => setMo("thu")}>
            Ghi nhận thu hộ
          </Button>
        ) : null}
        {n.cho_qua ? (
          <Button type="button" size="sm" variant="ghost" onClick={() => setMo("cho_qua")}>
            Cho lấy mẫu trước (quản lý)
          </Button>
        ) : null}
        {n.tai_ket_qua ? (
          <label className="inline-flex cursor-pointer items-center">
            <span className="sr-only">Tải kết quả</span>
            <input
              type="file"
              accept="application/pdf,image/*"
              className="text-meta"
              disabled={dang}
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) void taiTep(f);
              }}
            />
          </label>
        ) : null}
        {n.gui ? (
          <Button type="button" size="sm" variant="primary" onClick={() => setMo("gui")}>
            Đúng người, gửi
          </Button>
        ) : null}
        {n.hoan_tien ? (
          <Button type="button" size="sm" variant="ghost" onClick={() => setMo("hoan")}>
            Hoàn tiền
          </Button>
        ) : null}
        {n.dong ? (
          <Button type="button" size="sm" variant="ghost" onClick={() => setMo("dong")}>
            Đối tác đã tự trả khách
          </Button>
        ) : null}
        {n.hoan_tac ? (
          <Button type="button" size="sm" variant="ghost" onClick={() => setMo("hoan_tac")}>
            Hoàn tác bước trước
          </Button>
        ) : null}
      </div>

      {mo === "thu" ? (
        <div className="grid gap-2 sm:grid-cols-4 sm:items-end">
          <label className="flex flex-col gap-1 text-meta text-ink-soft">
            Tiền mặt
            <ONhap value={tm} inputMode="numeric" placeholder={tien(v.gia_goi_y)} onChange={(e) => setTm(e.target.value)} />
          </label>
          <label className="flex flex-col gap-1 text-meta text-ink-soft">
            Chuyển khoản
            <ONhap value={ck} inputMode="numeric" onChange={(e) => setCk(e.target.value)} />
          </label>
          <label className="flex flex-col gap-1 text-meta text-ink-soft">
            Mã giao dịch (CK)
            <ONhap value={maGd} maxLength={100} onChange={(e) => setMaGd(e.target.value)} />
          </label>
          <div className="flex gap-2">
            <Button
              type="button"
              size="sm"
              variant="primary"
              disabled={dang}
              onClick={() =>
                void chay(
                  "ghi-thu",
                  { order_id: v.order_id, tien_mat: tm, chuyen_khoan: ck, ma_giao_dich: maGd },
                  "Đã ghi nhận thu hộ.",
                )
              }
            >
              Lưu
            </Button>
            <Button type="button" size="sm" variant="ghost" onClick={() => setMo(null)}>
              Thôi
            </Button>
          </div>
          <p className="text-meta text-ink-muted sm:col-span-4">
            Ghi đúng số khách trả (giá gợi ý chỉ để tham khảo; miễn phí thì gõ 0). Tiền này của đối tác — không vào két.
          </p>
        </div>
      ) : null}

      {mo === "hoan" ? (
        <div className="flex flex-wrap items-end gap-2">
          <label className="flex flex-col gap-1 text-meta text-ink-soft">
            Hoàn tiền mặt
            <ONhap value={tm} inputMode="numeric" placeholder={tien(n.con_hoan_duoc)} onChange={(e) => setTm(e.target.value)} />
          </label>
          <label className="flex flex-col gap-1 text-meta text-ink-soft">
            Hoàn chuyển khoản
            <ONhap value={ck} inputMode="numeric" onChange={(e) => setCk(e.target.value)} />
          </label>
          {oLyDo("Lý do hoàn")}
          <Button
            type="button"
            size="sm"
            variant="primary"
            disabled={dang}
            onClick={() => void chay("hoan-tien", { order_id: v.order_id, tien_mat: tm, chuyen_khoan: ck, ly_do: lyDo }, "Đã ghi hoàn tiền.")}
          >
            Hoàn
          </Button>
        </div>
      ) : null}

      {mo === "gui" ? (
        <div className="flex flex-wrap items-end gap-2">
          <label className="flex flex-col gap-1 text-meta text-ink-soft">
            Đã gửi khách qua
            <OChon value={kenh} onChange={(e) => setKenh(e.target.value)}>
              <option value="ZALO">Zalo</option>
              <option value="SMS">SMS</option>
              <option value="TRUC_TIEP">Trực tiếp</option>
              <option value="EMAIL">Email</option>
            </OChon>
          </label>
          <Button
            type="button"
            size="sm"
            variant="primary"
            disabled={dang}
            onClick={() => void chay("gui", { order_id: v.order_id, kenh }, "Đã ghi nhận gửi khách.")}
          >
            Xác nhận đúng người, đã gửi
          </Button>
        </div>
      ) : null}

      {mo === "cho_qua" || mo === "dong" || mo === "hoan_tac" ? (
        <div className="flex flex-wrap items-end gap-2">
          {mo === "hoan_tac" && n.hoan_tac?.lenh === "huy_mau" ? (
            <label className="flex flex-col gap-1 text-meta text-ink-soft">
              Loại huỷ
              <OChon value={loaiHuy} onChange={(e) => setLoaiHuy(e.target.value)}>
                <option value="NHAP_SAI">Nhập / dán nhầm</option>
                <option value="MAU_HONG">Mẫu hỏng / đối tác từ chối</option>
              </OChon>
            </label>
          ) : null}
          {oLyDo(mo === "cho_qua" ? "Lý do cho lấy mẫu khi chưa thu" : mo === "dong" ? "Đối tác trả khách lúc nào, qua đâu" : `${n.hoan_tac?.nhan ?? ""} — lý do`)}
          <Button
            type="button"
            size="sm"
            variant="primary"
            disabled={dang}
            onClick={() => {
              if (mo === "cho_qua") void chay("cho-qua", { order_id: v.order_id, ly_do: lyDo }, "Đã cho lấy mẫu trước.");
              else if (mo === "dong") void chay("dong", { order_id: v.order_id, ly_do: lyDo }, "Đã đóng việc.");
              else if (n.hoan_tac) {
                const [d, b] = thanHoanTac(v, n.hoan_tac.lenh, lyDo, loaiHuy);
                void chay(d, b, `Đã hoàn tác: ${n.hoan_tac.nhan}.`);
              }
            }}
          >
            Xác nhận
          </Button>
          <Button type="button" size="sm" variant="ghost" onClick={() => setMo(null)}>
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
