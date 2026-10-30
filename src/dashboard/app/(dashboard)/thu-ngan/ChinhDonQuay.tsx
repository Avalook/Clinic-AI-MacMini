"use client";

// Quầy thu tiền thuốc CHỈNH ĐƠN BÁN trước khi thu (Tuyền 24/09/2026).
//
// "Cho thêm ô lấy thêm thuốc, có cả số lượng, hướng dẫn sử dụng… như ở phiếu
// khám của bác sĩ để thu ngân thuốc chỉnh được, bỏ tick thuốc được nếu bệnh
// nhân không muốn, lưu hết lịch sử, có event đã bỏ thuốc này ở bản cuối."
//
// Mọi luật ở máy chủ (`quay_thuoc_service`): thuốc bác sĩ kê tích / bỏ tick /
// đặt số lượng TUỲ Ý (tăng hay giảm — C19, bỏ "trần số kê") — cách dùng là quyết định chuyên môn nên chỉ xem; thuốc
// quầy thêm sửa được số lượng, cách dùng, lưu ý. Không xoá dòng nào — "bỏ" là
// bỏ tick, dòng còn đó và tích lại được. Phần "Lấy thêm thuốc" dùng lại ĐÚNG ô
// kê đơn của bác sĩ (`DonThuocPhieu`).
//
// C14 (Tuyền 01/10/2026): bác sĩ / điều dưỡng hay vội và QUÊN số lượng. Dòng thiếu
// số lượng được TÔ NỔI "Bác sĩ chưa nhập số lượng — nhập tại quầy": quầy gõ số là
// xong (máy chủ ghi người + lúc, màn kê đơn của bác sĩ hiện "SL do thu ngân điền")
// — không chờ bác sĩ, không bị chặn. Tổng tiền tính lại ở máy chủ.
// C19 (Tuyền 02/10/2026): bác sĩ đã ghi số thì quầy vẫn gõ số khác được — chip
// "SL do thu ngân sửa (bác sĩ kê X)"; máy chủ ghi số cũ → mới.

import { useCallback, useEffect, useRef, useState } from "react";

import Button from "@/components/ui/Button";
import Chip from "@/components/ui/Chip";
import {
  donTuDong,
  tienVn,
  type DongThuoc,
  type MauThuoc,
} from "@/lib/phieu-kham";

import DonThuocPhieu from "../_lam-viec/phieu-kham/DonThuocPhieu";
import { INPUT } from "../form-ui";
import ODonVi from "../ODonVi";

interface DongBan {
  id: string;
  nguon: "BAC_SI" | "QUAY";
  ten: string;
  drug_catalog_id: string | null;
  quantity: string | null;
  so_ke: string | null;
  so_mua: string | null;
  don_vi: string | null;
  cach_dung: string | null;
  luu_y: string | null;
  mua: boolean;
  da_chot: boolean;
  gia: number | null;
  /** Bác sĩ để trống số lượng — quầy phải nhập mới thu được. */
  thieu_so_luong: boolean;
  so_luong_do_thu_ngan: boolean;
  /** Số bác sĩ kê gốc khi quầy đã sửa (null = bác sĩ để trống). */
  so_ke_goc: string | null;
  nguoi_dien: string | null;
  /** ĐVT của kho — gợi ý khi bác sĩ cũng không ghi đơn vị. */
  don_vi_goi_y: string | null;
  /** Đơn vị chọn được, gốc trước — máy chủ trả (31/10/2026). */
  don_vi_chon?: { don_vi: string; he_so: string; gia: number | null; goc: boolean }[];
  /** Vì sao đơn vị đang chọn chưa ổn: chưa khai, chưa có giá. */
  van_de_don_vi?: string | null;
  chua_khai_don_vi?: boolean;
}

/** Số kê của đơn cũ đang được bán theo (`BanLeThu` lấy từ lịch sử đơn thuốc —
 *  máy chủ đã tính `vuot`; ở đây chỉ vẽ chip cạnh dòng thuốc). */
export interface TheoDonDong {
  so_ke: string | null;
  da_mua: string;
  dang_ban: string;
  don_vi: string | null;
  vuot: boolean;
}

async function gui(than: Record<string, unknown>): Promise<string | null> {
  try {
    const r = await fetch("/api/quay-thuoc", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(than),
    });
    if (r.ok) return null;
    const d = (await r.json().catch(() => null)) as { message?: string; error?: string } | null;
    return d?.message ?? d?.error ?? `Không lưu được (HTTP ${r.status}).`;
  } catch {
    return "Mất kết nối — CHƯA lưu.";
  }
}

export default function ChinhDonQuay({
  visitId,
  onDoi,
  theoDon,
  nhacChung,
  goiYThuoc,
}: {
  visitId: string;
  /** Đơn bán vừa đổi — màn cha nạp lại hoá đơn thuốc. */
  onDoi: (cau: string | null, loi: string | null) => Promise<void>;
  /** Lượt bán lẻ đang nối đơn cũ: theo `drug_catalog_id` → số kê / đã mua. */
  theoDon?: Record<string, TheoDonDong>;
  /** Nhắc của khách (vd lần khám gần nhất quá 2 tháng) — chữ trung tính, không chặn. */
  nhacChung?: string[];
  /** Nhân viên bấm "Chọn thuốc kho" ở dòng đơn cũ: mở sẵn danh mục với tên đó. */
  goiYThuoc?: { ten: string; lan: number } | null;
}) {
  const [dong, setDong] = useState<DongBan[] | null>(null);
  const [mauThuoc, setMauThuoc] = useState<MauThuoc[]>([]);
  const [them, setThem] = useState<DongThuoc[]>([]);
  const [soNhap, setSoNhap] = useState<Record<string, string>>({});
  const [dang, setDang] = useState(false);
  const khungThem = useRef<HTMLDivElement>(null);
  const lanGoiY = goiYThuoc?.lan;
  useEffect(() => {
    if (lanGoiY) khungThem.current?.scrollIntoView({ behavior: "smooth", block: "center" });
  }, [lanGoiY]);

  const tai = useCallback(async () => {
    const r = await fetch(`/api/quay-thuoc?visit_id=${visitId}`, { cache: "no-store" });
    const d = (await r.json().catch(() => null)) as { dong?: DongBan[] } | null;
    setDong(d?.dong ?? []);
    setSoNhap({});
  }, [visitId]);

  useEffect(() => {
    let bo = false;
    fetch(`/api/quay-thuoc?visit_id=${visitId}`, { cache: "no-store" })
      .then((r) => (r.ok ? r.json() : null))
      .then((d: { dong?: DongBan[] } | null) => {
        if (!bo) setDong(d?.dong ?? []);
      })
      .catch(() => {
        if (!bo) setDong([]);
      });
    fetch("/api/phieu-kham?xem=tham-chieu")
      .then((r) => (r.ok ? r.json() : null))
      .then((d: { mau_thuoc?: MauThuoc[] } | null) => {
        if (!bo) setMauThuoc(d?.mau_thuoc ?? []);
      })
      .catch(() => {
        if (!bo) setMauThuoc([]);
      });
    return () => {
      bo = true;
    };
  }, [visitId]);

  // Lỗi hiện NGAY CẠNH nút vừa bấm: câu của màn cha nằm trên đầu trang, có khi
  // cao hơn nút cả màn hình (đo 17/10: 895px trên điện thoại) nên bấm xong tưởng
  // không có gì xảy ra.
  const [loiTaiCho, setLoiTaiCho] = useState<string | null>(null);
  const loiRef = useRef<HTMLParagraphElement>(null);
  useEffect(() => {
    if (loiTaiCho) loiRef.current?.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }, [loiTaiCho]);

  const xong = async (loi: string | null, cau: string) => {
    setLoiTaiCho(loi);
    await tai();
    await onDoi(loi ? null : cau, loi);
  };

  const chon = async (d: DongBan, mua: boolean) => {
    setDang(true);
    const loi = await gui({ thao_tac: "chon", du_lieu: { prescription_id: d.id, mua } });
    setDang(false);
    await xong(loi, mua ? `Đã tích lại “${d.ten}”.` : `Đã bỏ “${d.ten}” — khách không lấy.`);
  };

  const doiSo = async (d: DongBan) => {
    const v = (soNhap[d.id] ?? "").trim();
    if (!v) return;
    // Rời ô mà số không đổi thì không gọi máy chủ (khỏi ghi vết "10 → 10").
    if (Number(v.replace(",", ".")) === Number(d.so_mua ?? d.so_ke)) return;
    setDang(true);
    const loi = await gui({
      thao_tac: "so-luong",
      du_lieu: { prescription_id: d.id, so_luong: Number(v.replace(",", ".")) },
    });
    setDang(false);
    await xong(loi, `Đã đổi số lượng “${d.ten}”.`);
  };

  const doiDonVi = async (d: DongBan, donVi: string) => {
    if (!donVi.trim() || donVi === (d.don_vi ?? d.don_vi_goi_y)) return;
    setDang(true);
    const loi = await gui({
      thao_tac: "don-vi",
      du_lieu: { prescription_id: d.id, don_vi: donVi },
    });
    setDang(false);
    await xong(loi, `Đã đổi đơn vị “${d.ten}”.`);
  };

  const suaDongQuay = async (d: DongBan, cachDung: string, luuY: string) => {
    if (cachDung === (d.cach_dung ?? "") && luuY === (d.luu_y ?? "")) return;
    setDang(true);
    const loi = await gui({
      thao_tac: "them",
      id: visitId,
      du_lieu: {
        dong: [
          {
            id: d.id,
            drug_catalog_id: d.drug_catalog_id,
            quantity: d.quantity,
            dosage: cachDung,
            caution: luuY,
          },
        ],
      },
    });
    setDang(false);
    await xong(loi, `Đã sửa cách dùng “${d.ten}”.`);
  };

  const luuThem = async () => {
    setDang(true);
    const loi = await gui({
      thao_tac: "them",
      id: visitId,
      du_lieu: {
        dong: them.map((t) => {
          const m = donTuDong(t);
          return {
            drug_catalog_id: m.drug_catalog_id,
            quantity: m.quantity,
            dosage: m.dosage,
            caution: m.caution,
          };
        }),
      },
    });
    setDang(false);
    if (!loi) setThem([]);
    await xong(loi, `Đã thêm ${them.length} thuốc vào đơn bán.`);
  };

  if (dong === null) {
    return <p className="px-4 py-2 text-meta text-ink-muted">Đang tải đơn thuốc…</p>;
  }

  return (
    <div className="space-y-3 border-b border-line px-4 py-3">
      <p className="text-meta font-semibold uppercase tracking-wide text-ink-muted">
        Khách lấy thuốc nào?
      </p>
      {nhacChung && nhacChung.length > 0 ? (
        <ul role="status" className="space-y-1">
          {nhacChung.map((c) => (
            <li key={c} className="text-meta text-ink-muted">
              {c}
            </li>
          ))}
        </ul>
      ) : null}
      <ul className="space-y-2">
        {dong.map((d) => {
          const td = d.drug_catalog_id ? theoDon?.[d.drug_catalog_id] : undefined;
          return (
            <li
              key={d.id}
              className={`space-y-1 rounded-control border p-2 ${
                d.thieu_so_luong ? "border-warning bg-warning-bg" : "border-line"
              } ${d.mua ? "" : "opacity-60"}`}
            >
              <div className="flex flex-wrap items-center gap-2">
                <input
                  type="checkbox"
                  className="size-4 accent-brand-600"
                  checked={d.mua}
                  disabled={dang || d.da_chot}
                  onChange={(e) => void chon(d, e.target.checked)}
                  aria-label={`Khách lấy ${d.ten}`}
                />
                <span className="min-w-0 flex-1 text-body font-medium text-ink">{d.ten}</span>
                <Chip tone={d.nguon === "QUAY" ? "brand" : "neutral"}>
                  {d.nguon === "QUAY" ? "Quầy thêm" : "Bác sĩ kê"}
                </Chip>
                <span className="text-meta text-ink-muted">
                  {d.gia !== null ? tienVn(d.gia) : "chưa có giá"}
                </span>
              </div>
              <div className="flex flex-wrap items-center gap-2 pl-6">
                <label className="flex items-center gap-2 text-meta text-ink-muted">
                  Số lượng
                  <input
                    inputMode="decimal"
                    value={soNhap[d.id] ?? d.so_mua ?? d.so_ke ?? ""}
                    disabled={dang || !d.mua || d.da_chot}
                    onChange={(e) => setSoNhap({ ...soNhap, [d.id]: e.target.value })}
                    onBlur={() => void doiSo(d)}
                    className={`${INPUT} w-24`}
                    aria-label={`Số lượng ${d.ten}`}
                  />
                </label>
                <div className="w-36">
                  <ODonVi
                    value={d.don_vi ?? d.don_vi_goi_y ?? ""}
                    onChange={(v) => void doiDonVi(d, v)}
                    cuaThuoc={(d.don_vi_chon ?? []).map((x) => x.don_vi)}
                    disabled={dang || !d.mua || d.da_chot || !d.drug_catalog_id}
                    ariaLabel={`Đơn vị ${d.ten}`}
                  />
                </div>
                {d.nguon === "BAC_SI" && d.so_ke && !d.so_luong_do_thu_ngan ? (
                  <span className="text-meta text-ink-faint">bác sĩ kê {d.so_ke}</span>
                ) : null}
                {d.so_luong_do_thu_ngan ? (
                  <Chip tone="brand" title={d.nguoi_dien ? `Điền bởi ${d.nguoi_dien}` : undefined}>
                    {d.so_ke_goc ? `SL do thu ngân sửa (bác sĩ kê ${d.so_ke_goc})` : "SL do thu ngân điền"}
                  </Chip>
                ) : null}
              </div>
              {(d.don_vi_chon ?? []).length > 1 ? (
                <p className="pl-6 text-meta text-ink-muted">
                  {(d.don_vi_chon ?? [])
                    .map((x) => `${x.don_vi}${x.goc ? "" : ` (${x.he_so})`} ${tienVn(x.gia)}`)
                    .join(" · ")}
                </p>
              ) : null}
              {d.chua_khai_don_vi ? (
                <p role="status" className="pl-6 text-meta text-warning">
                  Thuốc này chưa khai đơn vị — khai ở Kho thuốc › Danh mục thuốc. Vẫn thu và giao
                  được, kho trừ sau khi khai.
                </p>
              ) : null}
              {d.van_de_don_vi ? (
                <p role="status" className="pl-6 text-meta text-warning">
                  {d.van_de_don_vi}
                </p>
              ) : null}
              {td?.vuot ? (
                <p className="pl-6">
                  <Chip tone="warning">
                    Vượt số kê — đã mua {td.da_mua} + đang bán {td.dang_ban} / kê {td.so_ke ?? "—"}
                    {td.don_vi ? ` ${td.don_vi}` : ""}
                  </Chip>
                </p>
              ) : null}
              {d.thieu_so_luong ? (
                <p className="pl-6 text-meta font-semibold text-warning" role="alert">
                  Bác sĩ chưa nhập số lượng — nhập tại quầy
                </p>
              ) : null}
              {d.nguon === "QUAY" ? (
                <DongQuaySua d={d} dang={dang} onLuu={suaDongQuay} />
              ) : d.cach_dung || d.luu_y ? (
                <p className="pl-6 text-meta text-ink-muted">
                  {d.cach_dung}
                  {d.luu_y ? ` · Lưu ý: ${d.luu_y}` : ""}
                </p>
              ) : null}
            </li>
          );
        })}
      </ul>

      <div ref={khungThem} className="space-y-2">
        {/* Nhãn đợt 3 (27/09/2026 — C2): quầy bán cả VẬT TƯ (đầu dò Bio) và
            thực phẩm chức năng từ cùng danh mục kho, không riêng thuốc. */}
        <p className="text-meta font-semibold uppercase tracking-wide text-ink-muted">
          Lấy thêm thuốc / vật tư / TPCN
        </p>
        {/* Đơn bán chỉ nhận thuốc KHO (lệnh `them` gửi `drug_catalog_id`) —
            tắt dòng gõ tự do của phiếu khám. */}
        {goiYThuoc ? (
          <p role="status" className="text-meta text-ink-muted">
            Đang chọn thuốc kho thay cho “{goiYThuoc.ten}” (đơn cũ nhập từ hồ sơ giấy) — bấm đúng
            thuốc trong danh mục, rồi nhập số lượng (không thấy thì xoá ô tìm).
          </p>
        ) : null}
        <DonThuocPhieu
          key={goiYThuoc?.lan ?? 0}
          dong={them}
          mauThuoc={mauThuoc}
          onDoi={(moi) => {
            setLoiTaiCho(null);
            setThem(moi);
          }}
          ngoaiDanhMuc={false}
          tuKhoaDau={goiYThuoc?.ten}
        />
        {loiTaiCho ? (
          <p ref={loiRef} role="alert" className="text-meta text-danger">
            {loiTaiCho}
          </p>
        ) : null}
        {them.length > 0 ? (
          <Button variant="primary" size="md" disabled={dang} onClick={() => void luuThem()}>
            Thêm {them.length} mặt hàng vào đơn bán
          </Button>
        ) : null}
      </div>
    </div>
  );
}

function DongQuaySua({
  d,
  dang,
  onLuu,
}: {
  d: DongBan;
  dang: boolean;
  onLuu: (d: DongBan, cachDung: string, luuY: string) => Promise<void>;
}) {
  const [cachDung, setCachDung] = useState(d.cach_dung ?? "");
  const [luuY, setLuuY] = useState(d.luu_y ?? "");
  return (
    <div className="grid gap-2 pl-6 sm:grid-cols-2">
      <input
        value={cachDung}
        disabled={dang || !d.mua || d.da_chot}
        onChange={(e) => setCachDung(e.target.value)}
        onBlur={() => void onLuu(d, cachDung, luuY)}
        placeholder="Cách dùng"
        aria-label={`Cách dùng ${d.ten}`}
        className={INPUT}
      />
      <input
        value={luuY}
        disabled={dang || !d.mua || d.da_chot}
        onChange={(e) => setLuuY(e.target.value)}
        onBlur={() => void onLuu(d, cachDung, luuY)}
        placeholder="Lưu ý"
        aria-label={`Lưu ý ${d.ten}`}
        className={INPUT}
      />
    </div>
  );
}
