"use client";

// CÀI ĐẶT → ĐỐI TÁC XÉT NGHIỆM (05/11/2026, ADR-0015).
//
// Mỗi đối tác một thẻ: tên · mã ngắn · hẹn trả mặc định · thư mục Drive · dịch vụ đã
// gán (giá gợi ý, hẹn trả riêng). [Ngưng] cần lý do, [Bật lại] là hoàn tác của nó
// (không có Xoá — việc cũ vẫn trỏ vào đối tác). Màn không tự quyết luật nào: máy chủ
// từ chối gán dịch vụ phòng khám thu, đối tác đã ngưng, mã ngắn trùng — màn chỉ hiện câu lỗi.

import { useCallback, useEffect, useState } from "react";

import Button from "@/components/ui/Button";
import Chip from "@/components/ui/Chip";
import ONhap from "@/components/ui/ONhap";
import { loiDocDuoc } from "@/lib/loi-doc-duoc";
import { useNgheBang } from "../../dung-nghe-bang";
import FormDoiTac, { TRONG, type FormDT } from "./FormDoiTac";
import GanDichVu, { type DichVuGan } from "./GanDichVu";

interface DoiTac {
  id: string;
  ten: string;
  ma_ngan: string;
  sdt: string | null;
  ghi_chu: string | null;
  drive_folder_id: string | null;
  tai_khoan_nhan_ck: string | null;
  hen_tra_so_ngay_mac_dinh: number | null;
  ngung_luc: string | null;
  ly_do_ngung: string | null;
  gan_duoc: boolean;
  dich_vu: DichVuGan[];
  drive_den: { nhan: string; mau: "neutral" | "success" | "danger" };
  email_gui_ket_qua: string | null;
  /** Đèn nhịp Gmail — chữ + màu máy chủ tính (`gmail_cai_dat.den_email`). */
  email_den: { nhan: string; mau: "neutral" | "success" | "danger" };
}
interface DanhSach {
  doi_tac: DoiTac[];
  dich_vu_thu_ho: { id: string; name: string; unit_price: number | null }[];
  nguong_lay_mau_ngay: number;
  /** Thư Gmail nhận từ ngày này mới được tự ghép (null = chưa tự ghép). */
  gmail_tu_ngay: string | null;
}
async function docDanhSach(): Promise<DanhSach | null> {
  try {
    const r = await fetch("/api/xet-nghiem/doi-tac", { cache: "no-store" });
    return r.ok ? ((await r.json()) as DanhSach) : null;
  } catch {
    return null;
  }
}

export default function DoiTacView() {
  const [ds, setDs] = useState<DanhSach | null>(null);
  const [form, setForm] = useState<FormDT | null>(null);
  const [ngung, setNgung] = useState<{ id: string; ly_do: string } | null>(null);
  const [nguong, setNguong] = useState("");
  const [moc, setMoc] = useState("");
  const [dang, setDang] = useState(false);
  const [loi, setLoi] = useState<string | null>(null);
  const [bao, setBao] = useState<string | null>(null);

  const nhan = useCallback((d: DanhSach) => {
    setDs(d);
    setNguong(String(d.nguong_lay_mau_ngay));
    setMoc(d.gmail_tu_ngay ?? "");
  }, []);
  const tai = useCallback(async () => {
    const d = await docDanhSach();
    if (d) nhan(d);
  }, [nhan]);
  useEffect(() => {
    let huy = false;
    void docDanhSach().then((d) => {
      if (!huy && d) nhan(d);
    });
    return () => {
      huy = true;
    };
  }, [nhan]);
  // Người khác sửa đối tác / gán / ngưỡng: màn tải lại (bảng có trigger notify).
  useNgheBang(["doi_tac", "doi_tac_dich_vu", "xet_nghiem_cai_dat", "drive_nhip"], tai);

  async function gui(method: "POST" | "PUT", duong: string, body: unknown, cau: string): Promise<boolean> {
    setDang(true);
    setLoi(null);
    setBao(null);
    try {
      const r = await fetch(`/api/xet-nghiem/${duong}`, {
        method,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const d = (await r.json().catch(() => null)) as DanhSach | null;
      if (!r.ok || !d || !Array.isArray(d.doi_tac)) {
        setLoi(loiDocDuoc(d, `Chưa lưu được (HTTP ${r.status}).`));
        return false;
      }
      setDs(d);
      setBao(cau);
      return true;
    } catch {
      setLoi("Mất kết nối — chưa lưu.");
      return false;
    } finally {
      setDang(false);
    }
  }

  const sua = (k: keyof FormDT, v: string) => setForm((f) => (f ? { ...f, [k]: v } : f));

  return (
    <section aria-label="Đối tác xét nghiệm" className="space-y-4">
      <div className="flex flex-wrap items-start justify-end gap-3">
        {!form ? (
          <Button type="button" variant="primary" onClick={() => setForm({ ...TRONG })}>
            + Thêm đối tác
          </Button>
        ) : null}
      </div>

      <div className="flex flex-wrap items-end gap-2 rounded-card border border-line bg-surface p-4 shadow-card">
        <label className="flex flex-col gap-1 text-meta text-ink-soft">
          Đã thu mà chưa lấy mẫu quá bao nhiêu ngày thì báo vàng
          <ONhap value={nguong} inputMode="numeric" maxLength={2} onChange={(e) => setNguong(e.target.value)} />
        </label>
        <Button
          type="button"
          variant="secondary"
          disabled={dang || nguong === String(ds?.nguong_lay_mau_ngay ?? "")}
          onClick={() => void gui("PUT", "cai-dat", { nguong_lay_mau_ngay: nguong }, `Đã lưu: ${nguong} ngày.`)}
        >
          Lưu
        </Button>
      </div>

      <div className="flex flex-wrap items-end gap-2 rounded-card border border-line bg-surface p-4 shadow-card">
        <label className="flex flex-col gap-1 text-meta text-ink-soft">
          Tự ghép kết quả email từ ngày (thư trước ngày này chỉ lưu ở Kho email; để trống = chưa tự ghép)
          <ONhap type="date" value={moc} onChange={(e) => setMoc(e.target.value)} />
        </label>
        <Button
          type="button"
          variant="secondary"
          disabled={dang || moc === (ds?.gmail_tu_ngay ?? "")}
          onClick={() =>
            void gui(
              "PUT",
              "cai-dat/gmail",
              { gmail_tu_ngay: moc },
              moc ? `Đã lưu: tự ghép thư từ ${moc}.` : "Đã tắt tự ghép thư email.",
            )
          }
        >
          Lưu
        </Button>
      </div>

      {bao ? <p className="text-meta text-success">{bao}</p> : null}
      {loi ? (
        <p role="alert" className="text-meta text-danger">
          {loi}
        </p>
      ) : null}

      {form ? (
        <FormDoiTac
          form={form}
          dang={dang}
          onSua={sua}
          onThoi={() => setForm(null)}
          onLuu={async () => {
            const ok = await gui(form.id ? "PUT" : "POST", form.id ? `doi-tac/${form.id}` : "doi-tac", form, "Đã lưu đối tác.");
            if (ok) setForm(null);
          }}
        />
      ) : null}

      {!ds ? <p className="text-body text-ink-muted">Đang tải…</p> : null}
      {ds && ds.doi_tac.length === 0 ? <p className="text-body text-ink-muted">Chưa có đối tác nào.</p> : null}

      <ul className="space-y-3">
        {(ds?.doi_tac ?? []).map((d) => (
          <li
            key={d.id}
            className={`space-y-3 rounded-card border border-line p-4 shadow-card ${d.ngung_luc ? "bg-surface-muted" : "bg-surface"}`}
          >
            <div className="flex flex-wrap items-start gap-x-4 gap-y-2">
              <div className="min-w-0 flex-1">
                <p className="flex flex-wrap items-center gap-2 text-emph font-medium text-ink">
                  {d.ten} <Chip tone="neutral">{d.ma_ngan}</Chip>
                  {d.ngung_luc ? <Chip tone="neutral">Đã ngưng</Chip> : null}
                </p>
                <p className="text-meta text-ink-muted">
                  {d.hen_tra_so_ngay_mac_dinh != null ? `Hẹn trả ${d.hen_tra_so_ngay_mac_dinh} ngày` : "Chưa đặt hẹn trả"}
                  {d.sdt ? ` · ${d.sdt}` : ""}
                </p>
                {/* Đèn nhịp Drive / Email: chữ + màu do máy chủ tính (một luật đèn). */}
                <p className="flex flex-wrap gap-2">
                  <Chip tone={d.drive_den.mau}>{d.drive_den.nhan}</Chip>
                  <Chip tone={d.email_den.mau}>{d.email_den.nhan}</Chip>
                </p>
                {d.email_gui_ket_qua ? (
                  <p className="text-meta text-ink-muted">
                    Email gửi kết quả: <span className="text-ink">{d.email_gui_ket_qua}</span>
                  </p>
                ) : null}
                <p className="text-meta text-ink-muted">
                  Tiền thu hộ vào: <span className="text-ink">{d.tai_khoan_nhan_ck ?? "chưa đặt"}</span>
                </p>
                {d.ghi_chu ? <p className="text-meta text-ink-muted">Ghi chú: {d.ghi_chu}</p> : null}
                {d.ngung_luc && d.ly_do_ngung ? <p className="text-meta text-ink-muted">Lý do ngưng: {d.ly_do_ngung}</p> : null}
              </div>
              <div className="flex flex-wrap gap-2">
                <Button
                  type="button"
                  size="sm"
                  variant="secondary"
                  onClick={() =>
                    setForm({
                      id: d.id,
                      ten: d.ten,
                      ma_ngan: d.ma_ngan,
                      sdt: d.sdt ?? "",
                      ghi_chu: d.ghi_chu ?? "",
                      drive_folder: d.drive_folder_id ?? "",
                      tai_khoan_nhan_ck: d.tai_khoan_nhan_ck ?? "",
                      hen_tra_so_ngay_mac_dinh: d.hen_tra_so_ngay_mac_dinh?.toString() ?? "",
                      email_gui_ket_qua: d.email_gui_ket_qua ?? "",
                    })
                  }
                >
                  Sửa
                </Button>
                {d.ngung_luc ? (
                  <Button
                    type="button"
                    size="sm"
                    variant="ghost"
                    disabled={dang}
                    onClick={() => void gui("POST", `doi-tac/${d.id}/ngung`, { ngung: false }, `Đã bật lại ${d.ten}.`)}
                  >
                    Bật lại
                  </Button>
                ) : (
                  <Button type="button" size="sm" variant="ghost" onClick={() => setNgung({ id: d.id, ly_do: "" })}>
                    Ngưng
                  </Button>
                )}
              </div>
            </div>

            {ngung?.id === d.id ? (
              <div className="flex flex-wrap items-end gap-2">
                <label className="flex min-w-0 flex-1 flex-col gap-1 text-meta text-ink-soft">
                  Lý do ngưng (việc đang làm dở vẫn ở lại bàn xét nghiệm)
                  <ONhap value={ngung.ly_do} maxLength={500} onChange={(e) => setNgung({ id: d.id, ly_do: e.target.value })} />
                </label>
                <Button
                  type="button"
                  size="sm"
                  variant="primary"
                  disabled={dang}
                  onClick={async () => {
                    const ok = await gui("POST", `doi-tac/${d.id}/ngung`, { ngung: true, ly_do: ngung.ly_do }, `Đã ngưng ${d.ten} — bấm Bật lại để hoàn tác.`);
                    if (ok) setNgung(null);
                  }}
                >
                  Ngưng
                </Button>
                <Button type="button" size="sm" variant="ghost" onClick={() => setNgung(null)}>
                  Thôi
                </Button>
              </div>
            ) : null}

            <GanDichVu
              doiTacId={d.id}
              ganDuoc={d.gan_duoc}
              henMacDinh={d.hen_tra_so_ngay_mac_dinh}
              dichVu={d.dich_vu}
              dichVuThuHo={ds?.dich_vu_thu_ho ?? []}
              dang={dang}
              gui={gui}
            />
          </li>
        ))}
      </ul>
    </section>
  );
}
