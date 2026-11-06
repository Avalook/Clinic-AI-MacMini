// (Client — chỉ `BanXetNghiem.tsx` dùng.) Tab "Cài đặt" của bàn XN — hình theo bản mẫu
// 05/11: Đối tác (thẻ — màn Cài đặt → Đối tác sẵn có) · Gán xét nghiệm (bảng, sửa bằng
// đúng lệnh gán của máy chủ) · Quyền (CHỈ XEM, đọc quyền thực tế; sửa ở Phân quyền).
// Mọi luật (gán được không, giá/hẹn hiệu lực) ở máy chủ — màn chỉ gửi và hiện câu lỗi.

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import Button from "@/components/ui/Button";
import Chip from "@/components/ui/Chip";
import OChon from "@/components/ui/OChon";
import ONhap from "@/components/ui/ONhap";
import ThanhTab from "@/components/ui/ThanhTab";
import { loiDocDuoc } from "@/lib/loi-doc-duoc";

import DoiTacView from "../settings/doi-tac/DoiTacView";
import { useNgheBang } from "../dung-nghe-bang";
import { CHUA_TAI, tien } from "./kieu";

interface DichVuGan {
  id: string;
  service_price_id: string;
  mac_dinh: boolean;
  gia_hieu_luc: number | null;
  hen_tra_hieu_luc: number | null;
}
interface DanhSach {
  doi_tac: { id: string; ten: string; gan_duoc: boolean; dich_vu: DichVuGan[] }[];
  dich_vu_thu_ho: { id: string; name: string; unit_price: number | null }[];
}
interface Quyen {
  staff_id: string;
  ten: string | null;
  lam_viec: boolean;
  quan_ly: boolean;
}

const TH = "px-3 py-2 text-left text-label font-semibold uppercase tracking-wide text-ink-muted";
const TD = "px-3 py-2 align-middle";

async function docGan(): Promise<DanhSach | null> {
  try {
    const r = await fetch("/api/xet-nghiem/doi-tac", { cache: "no-store" });
    return r.ok ? ((await r.json()) as DanhSach) : null;
  } catch {
    return null;
  }
}

function BangGan() {
  const [ds, setDs] = useState<DanhSach | null>(null);
  const [sua, setSua] = useState<Record<string, { doi_tac_id: string; hen: string }>>({});
  const [loi, setLoi] = useState<string | null>(null);
  const [bao, setBao] = useState<string | null>(null);
  const tai = useCallback(async () => {
    const d = await docGan();
    if (d) setDs(d);
  }, []);
  useEffect(() => {
    let huy = false;
    void docGan().then((d) => {
      if (!huy && d) setDs(d);
    });
    return () => {
      huy = true;
    };
  }, []);
  useNgheBang(["doi_tac", "doi_tac_dich_vu"], tai);

  const hienTai = (spId: string) => {
    for (const d of ds?.doi_tac ?? []) {
      const g = d.dich_vu.find((x) => x.service_price_id === spId && x.mac_dinh);
      if (g) return { doi_tac: d, gan: g };
    }
    return null;
  };

  async function luu(spId: string) {
    const s = sua[spId];
    if (!s?.doi_tac_id) return;
    setLoi(null);
    setBao(null);
    const r = await fetch("/api/xet-nghiem/doi-tac-dich-vu", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ doi_tac_id: s.doi_tac_id, service_price_id: spId, gia_goi_y: "", hen_tra_so_ngay: s.hen }),
    }).catch(() => null);
    if (!r?.ok) {
      setLoi(loiDocDuoc(await r?.json().catch(() => null), "Chưa lưu được."));
      return;
    }
    setDs((await r.json()) as DanhSach);
    setSua((x) => Object.fromEntries(Object.entries(x).filter(([k]) => k !== spId)));
    setBao("Đã lưu — áp dụng cho chỉ định MỚI, chỉ định cũ giữ nguyên.");
  }

  return (
    <div className="flex flex-col gap-3">
      <p className="text-meta text-ink-muted">
        Đối tác nào làm xét nghiệm nào và hẹn trả bao nhiêu ngày do quản lý đặt ở đây. Đổi xong áp dụng cho lần sau, lần cũ giữ
        nguyên. Loại mới: tạo dịch vụ ở Bảng giá (bên thu = đối tác), rồi gán ở đây — không phải sửa code.
      </p>
      {bao ? <p className="text-meta text-success">{bao}</p> : null}
      {loi ? (
        <p role="alert" className="text-meta text-danger">
          {loi}
        </p>
      ) : null}
      <div className="overflow-x-auto rounded-card border border-line bg-surface shadow-card">
        <table className="w-full min-w-max text-meta text-ink">
          <thead className="border-b border-line bg-surface-muted">
            <tr>
              <th className={TH}>Xét nghiệm</th>
              <th className={TH}>Đối tác nhận</th>
              <th className={TH}>Hẹn trả (ngày)</th>
              <th className={TH}>Giá gợi ý</th>
              <th className={TH}>Là việc đối tác</th>
              <th className={TH}>
                <span className="sr-only">Lưu</span>
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-line">
            {(ds?.dich_vu_thu_ho ?? []).map((s) => {
              const h = hienTai(s.id);
              const e = sua[s.id] ?? { doi_tac_id: h?.doi_tac.id ?? "", hen: "" };
              const doi = (p: Partial<typeof e>) => setSua((x) => ({ ...x, [s.id]: { ...e, ...p } }));
              return (
                <tr key={s.id}>
                  <td className={`${TD} font-semibold`}>{s.name}</td>
                  <td className={TD}>
                    <OChon aria-label={`Đối tác nhận ${s.name}`} value={e.doi_tac_id} onChange={(ev) => doi({ doi_tac_id: ev.target.value })}>
                      <option value="">— Chưa gán —</option>
                      {(ds?.doi_tac ?? [])
                        .filter((d) => d.gan_duoc || d.id === h?.doi_tac.id)
                        .map((d) => (
                          <option key={d.id} value={d.id}>
                            {d.ten}
                          </option>
                        ))}
                    </OChon>
                  </td>
                  <td className={TD}>
                    <ONhap
                      aria-label={`Số ngày hẹn trả ${s.name}`}
                      value={e.hen}
                      inputMode="numeric"
                      maxLength={2}
                      placeholder={h?.gan.hen_tra_hieu_luc?.toString() ?? ""}
                      onChange={(ev) => doi({ hen: ev.target.value })}
                    />
                  </td>
                  {/* Máy chủ trả gia_hieu_luc = null khi giá 0; rơi về unit_price 0 từng
                      hiện "0đ". 0 = chưa có giá gợi ý ⇒ "—". */}
                  <td className={`${TD} tabular-nums`}>{tien((h?.gan.gia_hieu_luc ?? s.unit_price) || null) || "—"}</td>
                  <td className={TD}>
                    <Chip tone={h ? "success" : "neutral"}>{h ? "Có" : "Chưa gán"}</Chip>
                  </td>
                  <td className={TD}>
                    <Button type="button" size="sm" variant="secondary" disabled={!sua[s.id]?.doi_tac_id} onClick={() => void luu(s.id)}>
                      Lưu
                    </Button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
        {ds && ds.dich_vu_thu_ho.length === 0 ? (
          <p className="px-4 py-3 text-body text-ink-muted">Chưa có dịch vụ nào bên thu là đối tác (Bảng giá).</p>
        ) : null}
      </div>
    </div>
  );
}

function BangQuyen() {
  const [ds, setDs] = useState<Quyen[] | null>(null);
  const [loi, setLoi] = useState(false);
  useEffect(() => {
    void fetch("/api/xet-nghiem/quyen", { cache: "no-store" })
      .then(async (r) => {
        if (!r.ok) setLoi(true);
        else setDs(((await r.json()) as { nguoi: Quyen[] }).nguoi);
      })
      .catch(() => setLoi(true));
  }, []);
  const o = (co: boolean) => <Chip tone={co ? "success" : "neutral"}>{co ? "Có" : "Không"}</Chip>;
  return (
    <div className="flex flex-col gap-3">
      <p className="text-meta text-ink-muted">
        Ai không có quyền Làm việc thì không thấy mục Việc của đối tác ở thanh bên. Bảng chỉ để xem — bật/tắt ở{" "}
        <Link href="/phan-quyen" className="font-semibold text-brand-700 hover:underline">
          Phân quyền
        </Link>{" "}
        (lego Đối tác).
      </p>
      {loi ? <p className="text-meta text-ink-muted">{CHUA_TAI}</p> : null}
      <div className="overflow-x-auto rounded-card border border-line bg-surface shadow-card">
        <table className="w-full min-w-max text-meta text-ink">
          <thead className="border-b border-line bg-surface-muted">
            <tr>
              <th className={TH}>Nhân viên</th>
              <th className={TH}>Làm việc ở bàn</th>
              <th className={TH}>Tiền thu hộ · Cài đặt</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-line">
            {(ds ?? []).map((q) => (
              <tr key={q.staff_id}>
                <td className={`${TD} font-semibold`}>{q.ten}</td>
                <td className={TD}>{o(q.lam_viec)}</td>
                <td className={TD}>{o(q.quan_ly)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {ds && ds.length === 0 ? <p className="px-4 py-3 text-body text-ink-muted">Chưa ai có quyền ở bàn này.</p> : null}
      </div>
    </div>
  );
}

export default function CaiDat() {
  const [tab, setTab] = useState<"dt" | "gan" | "quyen">("dt");
  return (
    <section aria-label="Cài đặt" className="flex flex-col gap-3">
      <ThanhTab
        nhan="Cài đặt"
        chon={tab}
        onChon={setTab}
        muc={[
          { ma: "dt", nhan: "Đối tác" },
          { ma: "gan", nhan: "Gán xét nghiệm" },
          { ma: "quyen", nhan: "Quyền" },
        ]}
      />
      {tab === "dt" ? <DoiTacView /> : null}
      {tab === "gan" ? <BangGan /> : null}
      {tab === "quyen" ? <BangQuyen /> : null}
    </section>
  );
}
