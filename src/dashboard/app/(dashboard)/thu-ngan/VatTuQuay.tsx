"use client";

// MUA THÊM VẬT TƯ — ở quầy THU TIỀN DỊCH VỤ (Tuyền 01/10/2026, C13): nhân viên
// thêm vật tư khách mua thêm vào hoá đơn dịch vụ. Hai đầu dò Bio là nút chọn
// nhanh (một cú bấm = một dòng; bấm nữa = cộng số lượng) — lượt có "Tập máy Bio
// (chưa bao gồm đầu dò)" thì hai nút ấy NỔI lên đầu. Hàng khác: gõ tên (không dấu
// cũng ra) rồi [Thêm].
//
// Máy chủ quyết tất cả (`GET/POST /luot-kham/visits/{id}/vat-tu`, `/luot-kham/
// vat-tu/{id}[/bo]`): bán được hay không (giá 0 / chưa có giá = không bán), hàng
// cần quản lý duyệt (vòng Mirena), ai thêm được (chỉ quầy Thu tiền dịch vụ —
// quầy thuốc không), khoá khi đã thu. Đổi số lượng / bỏ làm được tới khi thu;
// thu nhầm thì "Hoàn tác lần thu" trả dòng về chờ thu. Tiền vật tư là tiền DỊCH
// VỤ: cộng vào tổng hoá đơn của quầy.

import { useCallback, useEffect, useState } from "react";

import Button from "@/components/ui/Button";
import Chip from "@/components/ui/Chip";
import { timVatTu, type VatTuDong, type VatTuGoi, type VatTuMuc } from "@/lib/vat-tu";

import { docBang, guiThaoTac } from "../_lam-viec/api";
import { useNgheBang } from "../dung-nghe-bang";
import { INPUT } from "../form-ui";

const tien = (n: number | null) =>
  n == null ? "chưa có giá" : `${new Intl.NumberFormat("vi-VN").format(n)}đ`;

interface DuyetMo {
  muc: VatTuMuc;
  quanLy: string;
  lyDo: string;
}

export default function VatTuQuay({
  visitId,
  reloadToken,
  onDoi,
  onDangLuu,
}: {
  visitId: string;
  /** Đổi khi hoá đơn từ sự kiện đổi — nạp lại để không giữ dòng đã cũ. */
  reloadToken?: string | number | null;
  /** Gọi sau mỗi lần lưu xong (quầy tải lại hoá đơn để tổng đổi liền). */
  onDoi?: () => void | Promise<void>;
  onDangLuu?: (dang: boolean) => void;
}) {
  const [goi, setGoi] = useState<VatTuGoi | null>(null);
  const [tim, setTim] = useState("");
  const [dangGui, setDangGui] = useState(false);
  const [loi, setLoi] = useState<string | null>(null);
  const [duyet, setDuyet] = useState<DuyetMo | null>(null);
  const [nhapSl, setNhapSl] = useState<Record<string, string>>({});

  const nap = useCallback(async () => {
    const kq = await docBang<VatTuGoi>("vat-tu", { luot: visitId });
    if (kq.ok) setGoi(kq.data);
    else setLoi(kq.loi);
  }, [visitId]);

  useEffect(() => {
    // Nạp lần đầu và nạp lại khi hoá đơn đổi từ thao tác khác / sự kiện.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void nap();
  }, [nap, reloadToken]);

  // Quầy khác thêm / bỏ vật tư cho cùng lượt → cập nhật liền.
  useNgheBang(["luot_vat_tu"], () => void nap());

  async function gui(
    thaoTac: string,
    id: string,
    duLieu: Record<string, unknown>,
  ): Promise<boolean> {
    setDangGui(true);
    onDangLuu?.(true);
    setLoi(null);
    try {
      const kq = await guiThaoTac(thaoTac, id, duLieu);
      if (!kq.ok) {
        setLoi(kq.loi);
        return false;
      }
      const moi = kq.data as unknown as Pick<VatTuGoi, "danh_muc" | "dong" | "tong">;
      setGoi((cu) => (cu ? { ...cu, ...moi } : cu));
      await onDoi?.();
      return true;
    } finally {
      setDangGui(false);
      onDangLuu?.(false);
    }
  }

  if (!goi) return loi ? <p className="text-meta text-danger">{loi}</p> : null;

  const sua = goi.duoc_sua && !dangGui;
  const nhanh = goi.danh_muc.filter((m) => m.chon_nhanh);
  const ketQua = timVatTu(goi.danh_muc, tim);

  async function them(m: VatTuMuc) {
    if (m.can_ql_duyet) {
      // Hàng thường không bán (vòng Mirena…): mở ô xin quản lý duyệt.
      setDuyet({ muc: m, quanLy: "", lyDo: "" });
      return;
    }
    const ok = await gui("vat-tu-them", visitId, { service_price_id: m.id, so_luong: 1 });
    if (ok) setTim("");
  }

  async function xacNhanDuyet() {
    if (!duyet) return;
    const ok = await gui("vat-tu-them", visitId, {
      service_price_id: duyet.muc.id,
      so_luong: 1,
      ...(duyet.quanLy ? { duyet_boi: duyet.quanLy } : {}),
      ly_do_duyet: duyet.lyDo,
    });
    if (ok) {
      setDuyet(null);
      setTim("");
    }
  }

  async function datSoLuong(d: VatTuDong, vao: string) {
    const n = Number(vao);
    setNhapSl((c) => Object.fromEntries(Object.entries(c).filter(([k]) => k !== d.id)));
    if (!Number.isInteger(n) || n === d.so_luong) return;
    await gui("vat-tu-so-luong", d.id, { so_luong: n });
  }

  return (
    <section aria-label="Mua thêm vật tư" className="space-y-3 rounded-control border border-line bg-surface p-3">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h3 className="text-body font-semibold text-ink">Mua thêm vật tư</h3>
        <span className="text-meta text-ink-muted">Tiền vật tư thu cùng hoá đơn dịch vụ</span>
      </div>

      {goi.duoc_sua && nhanh.length > 0 ? (
        <div className="space-y-1">
          {nhanh.some((m) => m.goi_y) ? (
            <p className="text-meta text-brand-700">
              Khách làm máy Bio — gợi ý đầu dò (bấm nữa = thêm một cái):
            </p>
          ) : null}
          <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap">
            {nhanh.map((m) => (
              <Button
                key={m.id}
                type="button"
                size="lg"
                variant={m.goi_y ? "soft" : "secondary"}
                disabled={!sua || !m.ban_duoc}
                onClick={() => void them(m)}
                aria-label={`Thêm ${m.ten}`}
              >
                {m.ten} · {tien(m.don_gia)}
              </Button>
            ))}
          </div>
        </div>
      ) : null}

      {goi.duoc_sua ? (
        <div className="space-y-1">
          <label className="block">
            <span className="sr-only">Tìm vật tư</span>
            <input
              type="search"
              value={tim}
              onChange={(e) => setTim(e.target.value)}
              placeholder="Tìm vật tư — gõ tên, không dấu cũng được"
              className={INPUT}
              disabled={dangGui}
            />
          </label>
          {tim.trim() !== "" ? (
            ketQua.length > 0 ? (
              <ul className="divide-y divide-line rounded-control border border-line">
                {ketQua.map((m) => (
                  <li key={m.id} className="flex flex-wrap items-center gap-x-3 gap-y-1 px-3 py-2">
                    <span className="min-w-0 flex-1">
                      <span className="block text-body text-ink">
                        {m.ten}
                        {m.don_vi ? <span className="text-meta text-ink-muted"> · {m.don_vi}</span> : null}
                      </span>
                      {!m.ban_duoc ? (
                        <span className="block text-meta text-ink-muted">{m.ly_do_khong_ban}</span>
                      ) : m.can_ql_duyet ? (
                        <span className="block text-meta text-warning">
                          Thường không bán — cần quản lý duyệt
                        </span>
                      ) : null}
                    </span>
                    {m.ban_duoc ? (
                      <span className="tabular-nums text-body text-ink">{tien(m.don_gia)}</span>
                    ) : null}
                    <Button
                      type="button"
                      size="sm"
                      variant="secondary"
                      disabled={!sua || !m.ban_duoc}
                      onClick={() => void them(m)}
                      aria-label={`Thêm ${m.ten}`}
                    >
                      Thêm
                    </Button>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-meta text-ink-muted">Không có vật tư tên này.</p>
            )
          ) : null}
        </div>
      ) : (
        <p className="text-meta text-ink-muted">Bạn chỉ xem — thêm vật tư là việc của quầy Thu tiền dịch vụ.</p>
      )}

      {duyet ? (
        <div role="group" aria-label="Quản lý duyệt bán" className="space-y-2 rounded-control bg-warning-bg px-3 py-2">
          <p className="text-body text-warning">
            <b>{duyet.muc.ten}</b> thường không bán (đã nằm trong giá dịch vụ). Chỉ bán khi sự cố cần cái thứ hai —
            phải có quản lý duyệt.
          </p>
          {goi.la_quan_ly ? (
            <p className="text-meta text-ink-soft">Bạn là quản lý — bạn duyệt bán dòng này.</p>
          ) : (
            <label className="block">
              <span className="mb-1 block text-meta font-medium text-ink-soft">Quản lý đã duyệt</span>
              <select
                value={duyet.quanLy}
                onChange={(e) => setDuyet({ ...duyet, quanLy: e.target.value })}
                className={INPUT}
              >
                <option value="">Chọn quản lý…</option>
                {goi.quan_ly.map((q) => (
                  <option key={q.id} value={q.id}>
                    {q.ten}
                  </option>
                ))}
              </select>
            </label>
          )}
          <label className="block">
            <span className="mb-1 block text-meta font-medium text-ink-soft">Lý do duyệt (5–500 ký tự)</span>
            <input
              value={duyet.lyDo}
              onChange={(e) => setDuyet({ ...duyet, lyDo: e.target.value })}
              maxLength={500}
              className={INPUT}
              placeholder="VD: vòng đầu tụt khi đặt, cần vòng thứ hai"
            />
          </label>
          <div className="flex flex-wrap gap-2">
            <Button
              type="button"
              variant="primary"
              disabled={
                dangGui || duyet.lyDo.trim().length < 5 || (!goi.la_quan_ly && duyet.quanLy === "")
              }
              onClick={() => void xacNhanDuyet()}
            >
              Xác nhận bán
            </Button>
            <Button type="button" variant="ghost" onClick={() => setDuyet(null)}>
              Huỷ
            </Button>
          </div>
        </div>
      ) : null}

      {goi.dong.length > 0 ? (
        <ul className="divide-y divide-line rounded-control border border-line">
          {goi.dong.map((d) => {
            const khoa = !sua || d.da_thu;
            return (
              <li key={d.id} className="flex flex-wrap items-center gap-x-3 gap-y-2 px-3 py-2">
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-body text-ink">{d.ten}</span>
                  <span className="block text-meta text-ink-muted">
                    {tien(d.don_gia)}
                    {d.don_vi ? ` / ${d.don_vi}` : ""}
                    {d.nguoi_duyet ? ` · QL duyệt: ${d.nguoi_duyet}` : ""}
                  </span>
                </span>
                <span className="flex items-center gap-1">
                  <Button
                    type="button"
                    size="sm"
                    variant="secondary"
                    disabled={khoa || d.so_luong <= 1}
                    onClick={() => void gui("vat-tu-so-luong", d.id, { so_luong: d.so_luong - 1 })}
                    aria-label={`Giảm số lượng ${d.ten}`}
                  >
                    −
                  </Button>
                  <input
                    inputMode="numeric"
                    aria-label={`Số lượng ${d.ten}`}
                    value={nhapSl[d.id] ?? String(d.so_luong)}
                    disabled={khoa}
                    onChange={(e) => setNhapSl((c) => ({ ...c, [d.id]: e.target.value.replace(/\D/g, "") }))}
                    onBlur={() => {
                      if (nhapSl[d.id] !== undefined) void datSoLuong(d, nhapSl[d.id]);
                    }}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") e.currentTarget.blur();
                    }}
                    className="h-10 w-14 rounded-control border border-line bg-surface px-1 text-center text-body tabular-nums text-ink outline-none focus:border-brand-600 disabled:bg-surface-sunken sm:h-8"
                  />
                  <Button
                    type="button"
                    size="sm"
                    variant="secondary"
                    disabled={khoa || d.so_luong >= 99}
                    onClick={() => void gui("vat-tu-so-luong", d.id, { so_luong: d.so_luong + 1 })}
                    aria-label={`Tăng số lượng ${d.ten}`}
                  >
                    +
                  </Button>
                </span>
                <span className="w-28 text-right text-body font-semibold tabular-nums text-ink">
                  {tien(d.thanh_tien)}
                </span>
                {d.da_thu ? (
                  <Chip tone="success">Đã thu</Chip>
                ) : (
                  <Button
                    type="button"
                    size="sm"
                    variant="danger"
                    disabled={khoa}
                    onClick={() => void gui("vat-tu-bo", d.id, {})}
                    aria-label={`Bỏ ${d.ten}`}
                  >
                    Bỏ
                  </Button>
                )}
              </li>
            );
          })}
          <li className="flex items-center justify-between px-3 py-2 text-body">
            <span className="text-ink-muted">Vật tư</span>
            <span className="font-semibold tabular-nums text-ink">{tien(goi.tong)}</span>
          </li>
        </ul>
      ) : null}
      {loi ? (
        <p role="alert" className="text-meta text-danger">
          {loi}
        </p>
      ) : null}
    </section>
  );
}
