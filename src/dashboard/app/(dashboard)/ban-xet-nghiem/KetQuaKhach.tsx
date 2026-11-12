// (Client — chỉ `BanXetNghiem.tsx` dùng.) Tab "Kết quả" kiểu Tuyền 05/11: MỖI VIỆC MỘT
// DÒNG, tờ kết quả cùng dòng — đã gán XANH, chưa gán ĐỎ; tệp Drive / thư Email chưa khớp
// khách là dòng đỏ riêng bên dưới. Lệnh: Gán (tệp → việc), Gán theo gợi ý (việc máy chủ
// gợi ý), Gán sang (gán nhầm), Từ chối tệp.
// Mọi luật (gán được không, cùng đối tác, đã lấy mẫu) ở máy chủ `ghep_tay.py`; màn chỉ
// lọc danh sách chọn theo đúng đối tác (máy chủ vẫn chặn) và hiện câu lỗi.

import { useCallback, useEffect, useState } from "react";

import Button from "@/components/ui/Button";
import ChipLoc from "@/components/ui/ChipLoc";
import Lightbox, { type TepXem } from "@/components/ui/Lightbox";
import OChon from "@/components/ui/OChon";
import ONhap from "@/components/ui/ONhap";

import { tepXem } from "../_lam-viec/AnhKetQua";
import EmailDaGan from "./EmailDaGan";
import GanKhachEmail from "./GanKhachEmail";
import { useNgheBang } from "../dung-nghe-bang";
import { CHUA_TAI, gioNgay, homNayVN, lenh, ngayNgan, type DriveCho, type Viec } from "./kieu";

type Mo = null | { loai: "sang" | "tu_choi"; id: string };

async function docCho(): Promise<DriveCho[] | null> {
  try {
    const r = await fetch("/api/xet-nghiem/ban/drive-cho", { cache: "no-store" });
    return r.ok ? ((await r.json()) as { tep: DriveCho[] }).tep : null;
  } catch {
    return null;
  }
}

function xemDrive(t: DriveCho): TepXem {
  const src = `/api/xet-nghiem/drive-tep?id=${encodeURIComponent(t.id)}`;
  return { id: t.id, src, ten: t.ten, loai: t.loai, phu: t.vi_sao, taiVe: src };
}

const khach = (v: Viec) => `${v.ten_khach ?? "Khách"}${v.sdt ? ` · ${v.sdt}` : ""}`;

/** "Drive · người thả · giờ" hoặc "Email · giờ nhận thư". */
function nguonCho(t: DriveCho): string {
  if (t.nguon === "GMAIL") return ["Email", gioNgay(t.email_nhan_luc ?? t.nhan_luc)].join(" · ");
  return [t.drive_nguoi_tai ? `Drive · ${t.drive_nguoi_tai}` : "Drive", gioNgay(t.drive_tao_luc ?? t.nhan_luc)].join(" · ");
}

export default function KetQuaKhach({
  viec,
  onMo,
  onXong,
}: {
  viec: Viec[];
  onMo: (v: Viec) => void;
  onXong: (bao: string) => void;
}) {
  const [cho, setCho] = useState<DriveCho[] | null>(null);
  const [loiDoc, setLoiDoc] = useState(false);
  const [ngay, setNgay] = useState("");
  const [chonTep, setChonTep] = useState<Record<string, string>>({});
  const [chonViec, setChonViec] = useState<Record<string, string>>({});
  const [mo, setMo] = useState<Mo>(null);
  const [lyDo, setLyDo] = useState("");
  const [dich, setDich] = useState("");
  const [loi, setLoi] = useState<string | null>(null);
  const [dang, setDang] = useState(false);
  const [xem, setXem] = useState<{ tieuDe: string; tep: TepXem } | null>(null);

  const tai = useCallback(async () => {
    const d = await docCho();
    setLoiDoc(d === null);
    if (d) setCho(d);
  }, []);
  useEffect(() => {
    let huy = false;
    void docCho().then((d) => {
      if (huy) return;
      setLoiDoc(d === null);
      if (d) setCho(d);
    });
    return () => {
      huy = true;
    };
  }, []);
  useNgheBang(["drive_tep", "tep_ket_qua"], tai);

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
    setDich("");
    await tai();
    onXong(bao);
  }

  // Việc đã lấy mẫu hoặc đã có tờ — việc chưa lấy mẫu thì chưa chờ kết quả.
  const dong = viec.filter((v) => v.mau_id || v.tep_id);
  const ngays = [...new Set(dong.map((v) => v.ngay_chi_dinh))].sort().reverse().slice(0, 7);
  const ds = dong
    .filter((v) => !ngay || v.ngay_chi_dinh === ngay)
    .sort((a, b) => Number(Boolean(a.tep_id)) - Number(Boolean(b.tep_id)) || b.ngay_chi_dinh.localeCompare(a.ngay_chi_dinh));
  const choCua = (doiTac: string) => (cho ?? []).filter((t) => t.doi_tac_id === doiTac);
  const viecNhan = (doiTac: string, tru?: string) => dong.filter((v) => v.doi_tac_id === doiTac && v.order_id !== tru && v.nut.tai_ket_qua);
  // Ô chọn của một tệp chờ: việc của khách máy chủ gợi ý (khớp tên + SĐT) lên đầu.
  const viecChoTep = (t: DriveCho) => {
    const ds = viecNhan(t.doi_tac_id);
    const kh = t.goi_y_clinic_patient_id;
    return kh ? [...ds.filter((v) => v.clinic_patient_id === kh), ...ds.filter((v) => v.clinic_patient_id !== kh)] : ds;
  };
  const homNay = homNayVN();

  return (
    <section aria-label="Kết quả" className="flex flex-col gap-3">
      {xem ? <Lightbox tieuDe={xem.tieuDe} tep={[xem.tep]} onDong={() => setXem(null)} /> : null}
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-label font-semibold uppercase tracking-wide text-ink-muted">Ngày chỉ định</span>
        <ChipLoc
          nhan="Ngày chỉ định"
          chon={ngay}
          onChon={setNgay}
          muc={[{ ma: "", nhan: "Mọi ngày" }, ...ngays.map((d) => ({ ma: d, nhan: d === homNay ? "Hôm nay" : ngayNgan(d) }))]}
        />
      </div>
      {loi ? (
        <p role="alert" className="text-meta text-danger">
          {loi}
        </p>
      ) : null}
      {loiDoc ? <p className="text-meta text-ink-muted">{CHUA_TAI}</p> : null}

      <h3 className="text-body font-semibold text-ink">Kết quả của khách</h3>
      <ul className="flex flex-col gap-2">
        {ds.map((v) => {
          const tep = v.tep_id;
          const tepCho = choCua(v.doi_tac_id);
          return (
            <li key={v.order_id} className={`flex flex-col gap-2 rounded-card border p-3 ${tep ? "border-success bg-success-bg" : "border-danger bg-danger-bg"}`}>
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div className="min-w-0 text-meta">
                  <button type="button" className="text-body font-semibold text-ink hover:underline" onClick={() => onMo(v)}>
                    {khach(v)}
                  </button>
                  <div className="text-ink-soft">
                    {v.ten_dich_vu} · {v.ten_doi_tac}
                    {v.ma_mau ? ` · mã ống ${v.ma_mau}` : ""}
                  </div>
                </div>
                <div className="min-w-0 text-right text-meta">
                  {tep ? (
                    <>
                      <button
                        type="button"
                        className="font-semibold text-brand-700 hover:underline"
                        onClick={() =>
                          setXem({
                            tieuDe: `${v.ten_dich_vu ?? "Kết quả"} · ${v.ten_khach ?? "Khách"}`,
                            tep: tepXem({ id: tep, ten: v.ten_tep, loai_tep: v.loai_tep ?? "PDF", mime: v.mime_tep }),
                          })
                        }
                      >
                        {v.ten_tep}
                      </button>
                      <div className="text-ink-muted">
                        {[v.nguon_tep, gioNgay(v.tep_luc), v.so_ban > 1 ? `Bản ${v.so_ban}` : null].filter(Boolean).join(" · ")}
                      </div>
                    </>
                  ) : (
                    <span className="font-semibold text-danger">Chưa có kết quả</span>
                  )}
                </div>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                {!tep && tepCho.length ? (
                  <>
                    <OChon
                      aria-label={`Chọn tệp cho ${khach(v)}`}
                      value={chonTep[v.order_id] ?? ""}
                      onChange={(e) => setChonTep((x) => ({ ...x, [v.order_id]: e.target.value }))}
                    >
                      <option value="">— Chọn tệp Drive / Email —</option>
                      {tepCho.map((t) => (
                        <option key={t.id} value={t.id}>
                          {t.ten}
                        </option>
                      ))}
                    </OChon>
                    <Button
                      type="button"
                      size="sm"
                      variant="primary"
                      disabled={!chonTep[v.order_id] || dang}
                      onClick={() => void chay("drive-ghep", { drive_tep_id: chonTep[v.order_id], order_id: v.order_id }, `Đã gán kết quả cho ${khach(v)}.`)}
                    >
                      Gán
                    </Button>
                  </>
                ) : null}
                {tep && !(mo?.loai === "sang" && mo.id === v.order_id) ? (
                  <Button type="button" size="sm" variant="ghost" onClick={() => setMo({ loai: "sang", id: v.order_id })}>
                    Gán sang
                  </Button>
                ) : null}
              </div>
              {mo?.loai === "sang" && mo.id === v.order_id ? (
                <div className="flex flex-wrap items-end gap-2">
                  <OChon aria-label="Gán sang khách" value={dich} onChange={(e) => setDich(e.target.value)}>
                    <option value="">— Gán sang khách —</option>
                    {viecNhan(v.doi_tac_id, v.order_id).map((x) => (
                      <option key={x.order_id} value={x.order_id}>
                        {khach(x)} · {x.ten_dich_vu}
                      </option>
                    ))}
                  </OChon>
                  <ONhap aria-label="Lý do gán sang" placeholder="Lý do (bắt buộc)" value={lyDo} maxLength={500} onChange={(e) => setLyDo(e.target.value)} />
                  <Button
                    type="button"
                    size="sm"
                    variant="primary"
                    disabled={!dich || dang}
                    onClick={() => void chay("gan-sang", { order_id: v.order_id, order_id_moi: dich, ly_do: lyDo }, "Đã gán sang — tờ cũ đã thu hồi.")}
                  >
                    Xác nhận gán sang
                  </Button>
                  <Button type="button" size="sm" variant="ghost" onClick={() => setMo(null)}>
                    Thôi
                  </Button>
                </div>
              ) : null}
            </li>
          );
        })}
        {!ds.length ? <li className="text-body text-ink-muted">Chưa có việc nào đã lấy mẫu.</li> : null}
      </ul>

      {cho && cho.length ? (
        <>
          <h3 className="text-body font-semibold text-ink">Tệp Drive / Email chưa khớp khách ({cho.length})</h3>
          <ul className="flex flex-col gap-2">
            {cho.map((t) => {
              const goiY = t.goi_y_order_id ? viec.find((v) => v.order_id === t.goi_y_order_id) : undefined;
              return (
              <li key={t.id} className="flex flex-col gap-2 rounded-card border border-danger bg-danger-bg p-3">
                <div className="flex flex-wrap items-start justify-between gap-2 text-meta">
                  <div className="min-w-0">
                    <button type="button" className="break-all text-left font-semibold text-brand-700 hover:underline" onClick={() => setXem({ tieuDe: t.ten, tep: xemDrive(t) })}>
                      {t.ten}
                    </button>
                    {t.email_tieu_de ? <div className="break-words text-ink">{t.email_tieu_de}</div> : null}
                    <div className="text-ink-soft">
                      {t.ten_doi_tac} · {t.vi_sao}
                    </div>
                  </div>
                  <div className="text-right text-ink-muted">{nguonCho(t)}</div>
                </div>
                {goiY ? (
                  <div className="flex flex-wrap items-center gap-2 text-meta">
                    <span className="text-ink-soft">
                      Gợi ý: <span className="font-semibold text-ink">{khach(goiY)}</span> · {goiY.ten_dich_vu}
                      {goiY.nut.tai_ket_qua ? "" : ` — việc đang «${goiY.trang_thai.nhan}», chưa gán được`}
                    </span>
                    {goiY.nut.tai_ket_qua ? (
                      <Button
                        type="button"
                        size="sm"
                        variant="primary"
                        disabled={dang}
                        onClick={() => void chay("drive-ghep", { drive_tep_id: t.id, order_id: goiY.order_id }, `Đã gán kết quả cho ${khach(goiY)}.`)}
                      >
                        Gán theo gợi ý
                      </Button>
                    ) : null}
                  </div>
                ) : t.gan_goi_y_duoc ? (
                  // G9: khách máy gợi ý (tên / SĐT lệch hồ sơ), không cần việc Bàn XN —
                  // máy chủ chọn chỉ định đúng loại hoặc hồ sơ theo lượt khám.
                  <div className="flex flex-wrap items-center gap-2 text-meta">
                    <span className="text-ink-soft">
                      Gợi ý: <span className="font-semibold text-ink">{t.goi_y_ten}</span>
                      {t.goi_y_ma ? ` · ${t.goi_y_ma}` : ""}
                    </span>
                    <Button
                      type="button"
                      size="sm"
                      variant="primary"
                      disabled={dang}
                      // Gửi đúng khách ĐANG HIỆN — máy chủ gán cho khách này, không đọc
                      // lại gợi ý (xét lại có thể vừa đổi).
                      onClick={() =>
                        void chay(
                          "drive-gan-khach",
                          { drive_tep_id: t.id, clinic_patient_id: t.goi_y_clinic_patient_id },
                          `Đã gán kết quả cho ${t.goi_y_ten ?? "khách"}.`,
                        )
                      }
                    >
                      Gán cho khách này
                    </Button>
                  </div>
                ) : null}
                {t.gan_khach_duoc ? (
                  // G10: thư email — tìm khách rồi gán (không cần việc Bàn XN).
                  <GanKhachEmail
                    dang={dang}
                    onGan={(kh, ten) =>
                      void chay("drive-gan-khach", { drive_tep_id: t.id, clinic_patient_id: kh }, `Đã gán kết quả cho ${ten}.`)
                    }
                  />
                ) : null}
                <div className="flex flex-wrap items-end gap-2">
                  {/* Ô chọn việc Bàn XN đã lấy mẫu — chỉ hiện khi có việc để chọn
                      (thư email không có việc Bàn XN thì dùng ô tìm khách ở trên). */}
                  {viecChoTep(t).length ? (
                    <>
                      <OChon
                        // Tên dịch vụ dài làm ô rộng 650px ⇒ 375 cuộn ngang; giữ trong khung.
                        className="w-full min-w-0 max-w-full sm:w-auto"
                        aria-label={`Gán ${t.ten} cho khách`}
                        value={chonViec[t.id] ?? ""}
                        onChange={(e) => setChonViec((x) => ({ ...x, [t.id]: e.target.value }))}
                      >
                        <option value="">— Gán cho việc đã lấy mẫu —</option>
                        {viecChoTep(t).map((x) => (
                          <option key={x.order_id} value={x.order_id}>
                            {x.clinic_patient_id && x.clinic_patient_id === t.goi_y_clinic_patient_id ? "Gợi ý · " : ""}
                            {khach(x)} · {x.ten_dich_vu}
                            {x.ma_mau ? ` · ${x.ma_mau}` : ""}
                          </option>
                        ))}
                      </OChon>
                      <Button
                        type="button"
                        size="sm"
                        variant="primary"
                        disabled={!chonViec[t.id] || dang}
                        onClick={() => void chay("drive-ghep", { drive_tep_id: t.id, order_id: chonViec[t.id] }, "Đã gán tệp cho khách.")}
                      >
                        Gán
                      </Button>
                    </>
                  ) : null}
                  {mo?.loai === "tu_choi" && mo.id === t.id ? (
                    <>
                      <ONhap aria-label="Lý do từ chối tệp" placeholder="Lý do (bắt buộc)" value={lyDo} maxLength={500} onChange={(e) => setLyDo(e.target.value)} />
                      <Button type="button" size="sm" variant="danger" disabled={dang} onClick={() => void chay("drive-tu-choi", { drive_tep_id: t.id, ly_do: lyDo }, "Đã từ chối tệp.")}>
                        Xác nhận từ chối
                      </Button>
                      <Button type="button" size="sm" variant="ghost" onClick={() => setMo(null)}>
                        Thôi
                      </Button>
                    </>
                  ) : (
                    <Button type="button" size="sm" variant="ghost" onClick={() => setMo({ loai: "tu_choi", id: t.id })}>
                      Từ chối tệp
                    </Button>
                  )}
                </div>
              </li>
              );
            })}
          </ul>
        </>
      ) : null}
      <EmailDaGan onXong={onXong} />
    </section>
  );
}
