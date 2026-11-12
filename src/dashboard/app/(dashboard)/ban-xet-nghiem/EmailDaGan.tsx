// (Client — chỉ `KetQuaKhach.tsx` dùng.) Gmail G11: thư email ĐÃ gắn khách — gắn nhầm
// thì "Gán lại cho khách khác" (Tuyền 11/11: ở tab Kết quả Việc của đối tác). Máy chủ
// (`gmail_gan_lai.py`) thu hồi / từ chối tờ cũ rồi gán khách đúng bằng đúng lệnh gán
// G10; cờ quyền, chữ trạng thái tờ, "gắn vào đâu" đều do máy chủ tính — màn chỉ vẽ.

import { useCallback, useEffect, useState } from "react";

import Button from "@/components/ui/Button";
import Lightbox, { type TepXem } from "@/components/ui/Lightbox";
import ONhap from "@/components/ui/ONhap";

import { tepXem } from "../_lam-viec/AnhKetQua";
import ChuyenVaoChiDinh from "./ChuyenVaoChiDinh";
import GanKhachEmail from "./GanKhachEmail";
import { useNgheBang } from "../dung-nghe-bang";
import { CHUA_TAI, gioNgay, lenh } from "./kieu";

interface ThuDaGan {
  id: string;
  ten: string;
  email_tieu_de: string | null;
  ghep_luc: string | null;
  email_nhan_luc: string | null;
  ten_doi_tac: string;
  ghep_boi: string;
  tep_id: string;
  loai_tep: string;
  nhan_to: string;
  canh_bao: string | null;
  /** Chữ tình trạng gửi (máy chủ tính): "đã gửi khách" / "kết quả cũ, đã trả ngoài hệ thống" / null. */
  gui: string | null;
  /** G13: đổi sang chỉ định khác của cùng khách (máy chủ tính: quyền, còn hiệu lực, chưa gửi). */
  chuyen_chi_dinh_duoc: boolean;
  /** Tờ đang nằm trong một chỉ định (máy chủ tính) — nút chuyển đọc là "đổi". */
  vao_chi_dinh: boolean;
  gan_vao: string;
  ten_khach: string;
  patient_code: string | null;
  phone_primary: string | null;
}

interface DaGan {
  thu: ThuDaGan[];
  co_quyen_gan_lai: boolean;
}

async function docDaGan(q: string): Promise<DaGan | null> {
  try {
    const r = await fetch(`/api/xet-nghiem/ban/email-da-gan?${new URLSearchParams({ q })}`, { cache: "no-store" });
    return r.ok ? ((await r.json()) as DaGan) : null;
  } catch {
    return null;
  }
}

export default function EmailDaGan({ onXong }: { onXong: (bao: string) => void }) {
  const [go, setGo] = useState("");
  const [q, setQ] = useState("");
  const [dl, setDl] = useState<DaGan | null>(null);
  const [loiDoc, setLoiDoc] = useState(false);
  const [mo, setMo] = useState<string | null>(null);
  const [dang, setDang] = useState(false);
  const [loi, setLoi] = useState<string | null>(null);
  const [xem, setXem] = useState<{ tieuDe: string; tep: TepXem } | null>(null);

  useEffect(() => {
    const h = setTimeout(() => setQ(go.trim()), 350);
    return () => clearTimeout(h);
  }, [go]);

  const tai = useCallback(async () => {
    const d = await docDaGan(q);
    setLoiDoc(d === null);
    if (d) setDl(d);
  }, [q]);

  useNgheBang(["drive_tep", "tep_ket_qua"], tai);

  useEffect(() => {
    let huy = false;
    void docDaGan(q).then((d) => {
      if (huy) return;
      setLoiDoc(d === null);
      if (d) setDl(d);
    });
    return () => {
      huy = true;
    };
  }, [q]);

  async function ganLai(t: ThuDaGan, kh: string, ten: string, lyDo: string) {
    setDang(true);
    setLoi(null);
    const e = await lenh("drive-gan-lai", { drive_tep_id: t.id, clinic_patient_id: kh, ly_do: lyDo });
    setDang(false);
    // Lỗi sau khi tờ cũ đã bù (thư về mục "chưa khớp khách") cũng phải tải lại.
    await tai();
    if (e) {
      setLoi(e);
      return;
    }
    setMo(null);
    onXong(`Đã gán lại thư cho ${ten}.`);
  }

  return (
    <section aria-label="Thư email đã gán" className="flex flex-col gap-2">
      {xem ? <Lightbox tieuDe={xem.tieuDe} tep={[xem.tep]} onDong={() => setXem(null)} /> : null}
      <h3 className="text-body font-semibold text-ink">Thư email đã gán — gán nhầm thì gán lại</h3>
      <ONhap
        className="w-full sm:w-80"
        type="search"
        aria-label="Lọc thư đã gán theo tên khách, SĐT, mã BN hoặc tên tệp"
        placeholder="Lọc theo tên khách, SĐT, mã BN, tên tệp"
        value={go}
        onChange={(e) => setGo(e.target.value)}
      />
      {loi ? (
        <p role="alert" className="text-meta text-danger">
          {loi}
        </p>
      ) : null}
      {loiDoc ? <p className="text-meta text-ink-muted">{CHUA_TAI}</p> : null}
      <ul className="flex flex-col gap-2">
        {dl?.thu.map((t) => (
          <li key={t.id} className="flex flex-col gap-2 rounded-card border border-line bg-surface p-3 text-meta">
            <div className="flex flex-wrap items-start justify-between gap-2">
              <div className="min-w-0">
                <button
                  type="button"
                  className="break-all text-left font-semibold text-brand-700 hover:underline"
                  onClick={() => setXem({ tieuDe: t.ten, tep: tepXem({ id: t.tep_id, ten: t.ten, loai_tep: t.loai_tep }) })}
                >
                  {t.ten}
                </button>
                {t.email_tieu_de ? <div className="break-words text-ink">{t.email_tieu_de}</div> : null}
                <div className="text-ink-soft">
                  Đang gắn: <span className="font-semibold text-ink">{t.ten_khach}</span>
                  {t.patient_code ? ` · ${t.patient_code}` : ""} · {t.gan_vao} · {t.nhan_to}
                  {t.gui ? ` · ${t.gui}` : ""}
                </div>
                {t.canh_bao ? <div className="font-semibold text-danger">{t.canh_bao}</div> : null}
              </div>
              <div className="text-right text-ink-muted">
                {t.ten_doi_tac} · {t.ghep_boi} · {gioNgay(t.ghep_luc ?? t.email_nhan_luc)}
              </div>
            </div>
            {mo === t.id ? (
              <div className="flex flex-col gap-2">
                <GanKhachEmail
                  dang={dang}
                  canLyDo
                  nhanNut="Xác nhận gán lại"
                  onGan={(kh, ten, lyDo) => void ganLai(t, kh, ten, lyDo)}
                />
                <div>
                  <Button type="button" size="sm" variant="ghost" onClick={() => setMo(null)}>
                    Thôi
                  </Button>
                </div>
              </div>
            ) : dl.co_quyen_gan_lai ? (
              <div className="flex flex-wrap items-start gap-2">
                <Button type="button" size="sm" variant="ghost" onClick={() => setMo(t.id)}>
                  Gán lại cho khách khác
                </Button>
                {t.chuyen_chi_dinh_duoc ? (
                  <ChuyenVaoChiDinh
                    tepId={t.tep_id}
                    daOChiDinh={t.vao_chi_dinh}
                    onXong={(ten) => {
                      void tai();
                      onXong(`Đã chuyển tờ vào chỉ định ${ten}.`);
                    }}
                  />
                ) : null}
              </div>
            ) : (
              <div className="text-ink-muted">Gán lại cần quyền Xác nhận kết quả (Quản lý cấp ở Phân quyền).</div>
            )}
          </li>
        ))}
        {dl && !dl.thu.length ? <li className="text-meta text-ink-muted">Không có thư email nào đã gán khớp bộ lọc.</li> : null}
      </ul>
    </section>
  );
}
