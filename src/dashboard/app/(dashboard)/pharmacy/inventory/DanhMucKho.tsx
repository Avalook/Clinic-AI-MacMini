"use client";

// Danh mục thuốc kho — MỘT nguồn tên, giá bán, đơn vị, hướng dẫn sử dụng
// (Tuyền 25/09/2026). Nạp sẵn theo KiotViet + hướng dẫn phiếu v5 (migration
// 20260925000014); dược sĩ thêm / sửa / tắt ở đây. Màn kê đơn của bác sĩ và
// quầy thu đọc thẳng danh mục này — sửa ở đây là hai nơi kia đổi theo.

import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";

import Button from "@/components/ui/Button";
import Chip from "@/components/ui/Chip";
import { INPUT, LABEL, TBL_DIV, TBL_HEAD, TBL_WRAP } from "../../form-ui";
import { guiKho, soKho, tienVnd, tonTheoDonVi } from "./gui-kho";

export interface ThuocKho {
  id: string;
  ten: string;
  ma_hang: string | null;
  gia: number | null;
  don_vi_ban: string | null;
  duong_dung: string | null;
  cach_dung: string | null;
  luu_y: string | null;
  biet_duoc: string | null;
  dang_dung: boolean;
  can_soat: boolean;
  ton: number;
  so_lo: number;
  /** Ngưỡng sắp hết hàng (29/09/2026); null = không canh. */
  ton_toi_thieu: number | null;
  /** Máy chủ tính: đang dùng, có ngưỡng, tổng tồn ≤ ngưỡng. */
  sap_het_hang: boolean;
  /** Đơn vị các lô đang có (máy chủ trả) — phiếu nhập điền sẵn theo đây. */
  don_vi_lo: string[];
  /** Tồn tách theo đơn vị lô — không cộng hộp với viên (29/09/2026). */
  ton_theo_don_vi: { don_vi: string | null; ton: number }[];
}

type Loc = "dang_dung" | "sap_het" | "can_soat" | "da_tat" | "tat_ca";

const NHAN_LOC: Record<Loc, string> = {
  dang_dung: "Đang dùng",
  sap_het: "Sắp hết hàng",
  can_soat: "Cần soát",
  da_tat: "Đã tắt",
  tat_ca: "Tất cả",
};

const TRONG = {
  ten: "",
  ma_hang: "",
  gia: "",
  don_vi_ban: "",
  duong_dung: "",
  biet_duoc: "",
  cach_dung: "",
  luu_y: "",
  ton_toi_thieu: "",
  dang_dung: true,
};

type Form = typeof TRONG;

function tuThuoc(t: ThuocKho): Form {
  return {
    ten: t.ten,
    ma_hang: t.ma_hang ?? "",
    gia: t.gia == null ? "" : String(t.gia),
    don_vi_ban: t.don_vi_ban ?? "",
    duong_dung: t.duong_dung ?? "",
    biet_duoc: t.biet_duoc ?? "",
    cach_dung: t.cach_dung ?? "",
    luu_y: t.luu_y ?? "",
    ton_toi_thieu: t.ton_toi_thieu == null ? "" : String(t.ton_toi_thieu),
    dang_dung: t.dang_dung,
  };
}

export default function DanhMucKho({
  thuoc,
  ghiDuoc = false,
  onXemThe,
}: {
  thuoc: ThuocKho[];
  /** Có quyền ghi kho — chỉ ẩn/hiện nút, máy chủ tự kiểm. */
  ghiDuoc?: boolean;
  /** Bấm tên thuốc → tab Thẻ kho. */
  onXemThe?: (id: string) => void;
}) {
  const router = useRouter();
  const [loc, setLoc] = useState<Loc>("dang_dung");
  const [tim, setTim] = useState("");
  // null = không sửa gì · "" = đang thêm thuốc mới · id = đang sửa thuốc ấy.
  const [sua, setSua] = useState<string | null>(null);
  const [form, setForm] = useState<Form>(TRONG);
  const [dang, setDang] = useState(false);
  const [loi, setLoi] = useState<string | null>(null);
  const [bao, setBao] = useState<string | null>(null);

  const dem = useMemo(
    () => ({
      dang_dung: thuoc.filter((t) => t.dang_dung).length,
      sap_het: thuoc.filter((t) => t.sap_het_hang).length,
      can_soat: thuoc.filter((t) => t.dang_dung && t.can_soat).length,
      da_tat: thuoc.filter((t) => !t.dang_dung).length,
      tat_ca: thuoc.length,
    }),
    [thuoc],
  );

  const hang = useMemo(() => {
    const q = tim.trim().toLowerCase();
    return thuoc.filter((t) => {
      if (loc === "dang_dung" && !t.dang_dung) return false;
      if (loc === "sap_het" && !t.sap_het_hang) return false;
      if (loc === "can_soat" && !(t.dang_dung && t.can_soat)) return false;
      if (loc === "da_tat" && t.dang_dung) return false;
      if (!q) return true;
      return [t.ten, t.ma_hang, t.biet_duoc].some((x) => x?.toLowerCase().includes(q));
    });
  }, [thuoc, loc, tim]);

  const mo = (t: ThuocKho | null) => {
    setSua(t ? t.id : "");
    setForm(t ? tuThuoc(t) : TRONG);
    setLoi(null);
    setBao(null);
  };

  const luu = async () => {
    setDang(true);
    setLoi(null);
    const kq = await guiKho("luu-thuoc", {
      drug_catalog_id: sua || null,
      ten: form.ten,
      gia: form.gia.trim() === "" ? null : form.gia.trim(),
      ma_hang: form.ma_hang,
      don_vi_ban: form.don_vi_ban,
      duong_dung: form.duong_dung,
      biet_duoc: form.biet_duoc,
      cach_dung: form.cach_dung,
      luu_y: form.luu_y,
      // Rỗng = bỏ canh; máy chủ đọc số, từ chối số âm.
      ton_toi_thieu: form.ton_toi_thieu.trim() === "" ? null : form.ton_toi_thieu.trim(),
      dang_dung: form.dang_dung,
    });
    setDang(false);
    if (!kq.ok) {
      setLoi(kq.loi);
      return;
    }
    setBao(`Đã lưu “${form.ten.trim()}”.`);
    setSua(null);
    router.refresh();
  };

  const o = (ma: keyof Omit<Form, "dang_dung">, nhan: string, dai = false) => (
    <label className={dai ? "block sm:col-span-2" : "block"}>
      <span className={LABEL}>{nhan}</span>
      {dai ? (
        <textarea
          rows={3}
          value={form[ma]}
          onChange={(e) => setForm({ ...form, [ma]: e.target.value })}
          className={INPUT}
        />
      ) : (
        <input
          value={form[ma]}
          inputMode={ma === "gia" ? "numeric" : ma === "ton_toi_thieu" ? "decimal" : undefined}
          onChange={(e) => setForm({ ...form, [ma]: e.target.value })}
          className={INPUT}
        />
      )}
    </label>
  );

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        {(Object.keys(NHAN_LOC) as Loc[]).map((l) => (
          <Button
            key={l}
            type="button"
            size="sm"
            variant={loc === l ? "primary" : "secondary"}
            onClick={() => setLoc(l)}
          >
            {NHAN_LOC[l]} · {dem[l]}
          </Button>
        ))}
        <input
          value={tim}
          onChange={(e) => setTim(e.target.value)}
          placeholder="Tìm tên / mã hàng / biệt dược…"
          aria-label="Tìm thuốc"
          className={`${INPUT} sm:ml-auto sm:w-64`}
        />
        {ghiDuoc ? (
          <Button type="button" variant="primary" size="sm" onClick={() => mo(null)}>
            + Thêm thuốc
          </Button>
        ) : null}
      </div>

      {bao ? <p className="text-meta text-success">{bao}</p> : null}

      {sua !== null ? (
        <section
          aria-label={sua ? "Sửa thuốc" : "Thêm thuốc"}
          className="space-y-3 rounded-card border border-line bg-surface p-4 shadow-card"
        >
          <h3 className="text-title text-ink">{sua ? `Sửa: ${form.ten}` : "Thêm thuốc mới"}</h3>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            {o("ten", "Tên thuốc")}
            {o("ma_hang", "Mã hàng (KiotViet)")}
            {o("gia", "Giá bán (đ / một đơn vị)")}
            {o("don_vi_ban", "Đơn vị bán (hộp, viên, ống…)")}
            {o("ton_toi_thieu", "Tồn tối thiểu (để trống = không cảnh báo)")}
            {o("duong_dung", "Đường dùng")}
            {o("biet_duoc", "Biệt dược / hoạt chất")}
            {o("cach_dung", "Cách dùng (điền sẵn vào đơn)", true)}
            {o("luu_y", "Lưu ý", true)}
          </div>
          <label className="flex min-h-10 items-center gap-2 text-body text-ink">
            <input
              type="checkbox"
              className="size-4 accent-brand-600"
              checked={form.dang_dung}
              onChange={(e) => setForm({ ...form, dang_dung: e.target.checked })}
            />
            Đang dùng (bỏ tick = tắt: không hiện khi kê đơn, không xoá)
          </label>
          <div className="flex flex-wrap items-center gap-2">
            <Button
              type="button"
              variant="primary"
              disabled={dang || !form.ten.trim()}
              onClick={() => void luu()}
            >
              {dang ? "Đang lưu…" : "Lưu thuốc"}
            </Button>
            <Button type="button" variant="ghost" onClick={() => setSua(null)}>
              Thôi
            </Button>
            {loi ? (
              <p role="alert" className="text-meta text-danger">
                {loi}
              </p>
            ) : null}
          </div>
        </section>
      ) : null}

      <div className={`${TBL_WRAP} overflow-x-auto`}>
        <table className="w-full min-w-2xl text-left text-body">
          <thead className={TBL_HEAD}>
            <tr>
              <th className="px-3 py-2">Thuốc</th>
              <th className="px-3 py-2">Đơn vị</th>
              <th className="px-3 py-2 text-right">Giá bán</th>
              <th className="px-3 py-2 text-right">Tồn</th>
              <th className="px-3 py-2">Cách dùng</th>
              <th className="px-3 py-2" />
            </tr>
          </thead>
          <tbody className={TBL_DIV}>
            {hang.length === 0 ? (
              <tr>
                <td colSpan={6} className="px-3 py-6 text-center text-ink-muted">
                  Không có thuốc nào.
                </td>
              </tr>
            ) : (
              hang.map((t) => (
                <tr key={t.id} className={t.dang_dung ? "" : "text-ink-faint"}>
                  <td className="px-3 py-2">
                    {onXemThe ? (
                      <button
                        type="button"
                        onClick={() => onXemThe(t.id)}
                        title="Xem thẻ kho"
                        className="text-left font-medium text-brand-700 hover:underline"
                      >
                        {t.ten}
                      </button>
                    ) : (
                      <span className="font-medium text-ink">{t.ten}</span>
                    )}
                    <span className="block text-meta text-ink-muted">
                      {[t.ma_hang, t.biet_duoc].filter(Boolean).join(" · ")}
                    </span>
                    {t.sap_het_hang ? <Chip tone="danger">Sắp hết</Chip> : null}
                    {t.can_soat && t.dang_dung ? <Chip tone="warning">Cần soát</Chip> : null}
                    {!t.dang_dung ? <Chip tone="neutral">Đã tắt</Chip> : null}
                  </td>
                  <td className="px-3 py-2 text-ink-muted">{t.don_vi_ban ?? "—"}</td>
                  <td className="px-3 py-2 text-right tabular-nums text-ink">{tienVnd(t.gia)}</td>
                  <td className="px-3 py-2 text-right tabular-nums text-ink">
                    {tonTheoDonVi(t.ton_theo_don_vi)}
                    {t.so_lo > 0 ? <span className="block text-meta text-ink-muted">{t.so_lo} lô</span> : null}
                    {t.ton_toi_thieu != null ? (
                      <span className="block text-meta text-ink-muted">tối thiểu {soKho(t.ton_toi_thieu)}</span>
                    ) : null}
                  </td>
                  <td className="max-w-xs px-3 py-2 text-meta text-ink-muted">
                    {t.cach_dung ? (
                      <span className="line-clamp-2">{t.cach_dung}</span>
                    ) : (
                      <Chip tone="warning">Chưa có hướng dẫn</Chip>
                    )}
                  </td>
                  <td className="px-3 py-2 text-right">
                    {ghiDuoc ? (
                      <Button type="button" size="sm" variant="ghost" onClick={() => mo(t)}>
                        Sửa
                      </Button>
                    ) : null}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
