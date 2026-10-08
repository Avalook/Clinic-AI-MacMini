"use client";

// KHỐI "PHÒNG LÀM ĐƯỢC + ĐỔI PHÒNG" cho một chỉ định (luồng chuẩn bước 7, Tuyền
// chốt 23/09/2026): "chỉ định hiện ra các phòng khả dụng và số lượng người tại
// phòng đó … phòng còn ok thì đến, còn nếu đầy thì lễ tân xem và điều phối phòng
// trống hơn mà cùng chức năng" — và "lễ tân, điều dưỡng, thư ký, bác sĩ… tất cả
// đều có thể làm".
//
// MỘT KHỐI, NHIỀU CHỖ CẮM: Bàn khám (lúc vừa chỉ định) và màn Xem lượt (mở từ
// tiếp đón, thu ngân, sinh hiệu, phòng, trưởng ca, nhà thuốc). Không màn nào tự
// chép lại logic xếp phòng.
//
// Màn này KHÔNG quyết ai được đổi: máy chủ hỏi quyền `service.routing.assign`,
// cổng tiền (đã trả dịch vụ thực làm) và revision — từ chối thì hiện câu của máy
// chủ. `choDoi` chỉ là để biết có bày nút hay không.

import { useEffect, useState } from "react";

import Button from "@/components/ui/Button";
import NutHoanTac from "@/components/ui/NutHoanTac";
import XacNhanTaiCho from "@/components/ui/XacNhanTaiCho";

import { docBang, guiThaoTac, type PhongHomNay } from "./api";
import ChonBacSiLam, { coChonBacSi, type LuaChonBacSi } from "./ChonBacSiLam";
import { lenhHoanTac } from "./hoan-tac";

interface UngVien {
  room_id: string;
  rank: number;
  queue_load: number;
  /** Phòng chuyên ★ của chỉ định (07/10/2026) — chỉ để gợi ý. */
  chuyen?: boolean;
  /** Phòng nhiều bác sĩ (30/09/2026): bác sĩ trực hôm nay — chỉ có phần tử khi
   *  ≥2 bác sĩ (một bác sĩ thì máy chủ tự gán). */
  bac_si?: LuaChonBacSi[];
}
interface GoiY {
  recommendation_ref: string;
  candidates: UngVien[];
  /** Máy chủ nói có bày ô chọn phòng không (đợt 3, 27/09/2026):
   *  CO_PHONG · DOI_TAC_LAM (chụp phim ngoài…) · KHONG_CO_PHONG. */
  trang_thai?: "CO_PHONG" | "DOI_TAC_LAM" | "KHONG_CO_PHONG";
  /** Câu máy chủ viết cho hai trạng thái không xếp được — màn vẽ nguyên văn. */
  cau?: string | null;
  /** Lối đổi phòng (29/09/2026) — MÁY CHỦ quyết theo trạng thái chỉ định + quyền
   *  người xem: XEP (khách đã chốt — V10: chưa thu cũng xếp) · DU_KIEN (trưởng
   *  ca, khách chưa chốt) · CHUYEN_DANG_LAM (trưởng ca,
   *  đang làm) · KHONG. */
  che_do?: "XEP" | "DU_KIEN" | "CHUYEN_DANG_LAM" | "KHONG";
  cau_che_do?: string | null;
  phong_du_kien_id?: string | null;
  /** Bác sĩ đã chọn trong phòng hiện tại / phòng dự kiến (máy chủ viết "BS X"). */
  bac_si_lam_id?: string | null;
  bac_si_lam?: string | null;
  phong_hien_tai?: string | null;
  dang_lam_tu?: string | null;
  /** Dây "Nhận khách tại phòng" bật (07/10/2026): chọn phòng = hướng dẫn. */
  huong_dan?: boolean;
  /** Đúng MỘT phòng chuyên ★ → máy chủ gợi ý phòng này (chưa lưu). */
  goi_y_chuyen?: string | null;
}

function gioPhut(iso: string | null | undefined): string {
  if (!iso) return "";
  const d = new Date(iso);
  return Number.isNaN(d.getTime())
    ? ""
    : d.toLocaleTimeString("vi-VN", { hour: "2-digit", minute: "2-digit", timeZone: "Asia/Ho_Chi_Minh" });
}

export default function DoiPhong({
  orderId,
  phongHienTaiId,
  routingRevision,
  choDoi,
  onDaDoi,
  nguon = "khac",
}: {
  orderId: string;
  /** Phòng đang xếp (nếu có). */
  phongHienTaiId: string | null;
  routingRevision: number | null;
  /** Máy chủ nói đổi phòng được không (đã chọn, chưa bắt đầu, không phải đối tác). */
  choDoi: boolean;
  onDaDoi?: () => void;
  /** Màn gọi (P3, 25/09/2026): quầy thu · trưởng ca · khác. Trưởng ca đã xếp thì
   *  nguồn khác không đổi được — máy chủ chặn, câu báo hiện ngay dưới ô. */
  nguon?: "quay_thu" | "truong_ca" | "khac";
}) {
  const [goiY, setGoiY] = useState<GoiY | null>(null);
  const [ten, setTen] = useState<Record<string, string>>({});
  const [chon, setChon] = useState<string>("");
  // Bác sĩ cho phòng MỚI đang chọn ("" = bác sĩ nào rảnh cũng được).
  const [chonBs, setChonBs] = useState<string>("");
  const [loi, setLoi] = useState<string | null>(null);
  const [dangGui, setDangGui] = useState(false);
  const [xacNhan, setXacNhan] = useState(false);
  const [lyDo, setLyDo] = useState("");
  const [lan, setLan] = useState(0);

  useEffect(() => {
    let huy = false;
    void Promise.all([
      docBang<GoiY>("goi-y-phong", { chi_dinh: orderId }),
      docBang<PhongHomNay>("phong-hom-nay"),
    ]).then(([g, p]) => {
      if (huy) return;
      if (g.ok) setGoiY(g.data);
      else setLoi(g.loi);
      if (p.ok) {
        setTen(Object.fromEntries(p.data.tat_ca_phong.map((x) => [x.id, x.ten])));
      }
    });
    return () => {
      huy = true;
    };
  }, [orderId, lan]);

  if (loi && !goiY) {
    return <p className="text-label text-ink-muted">Phòng làm được: {loi}</p>;
  }
  if (!goiY) return null;
  // Không bày ô chọn phòng khi máy chủ báo không cần / không xếp được — chỉ vẽ
  // câu máy chủ trả (đối tác làm: giọng thường; không phòng nào nhận: cảnh báo).
  if (goiY.trang_thai === "DOI_TAC_LAM") {
    return <p className="text-label text-ink-muted">{goiY.cau}</p>;
  }
  if (goiY.trang_thai === "KHONG_CO_PHONG" || goiY.candidates.length === 0) {
    return (
      <p className="text-label text-warning">
        {goiY.cau ?? "Chưa có phòng nào đang nhận khách làm được dịch vụ này."}
      </p>
    );
  }

  const nhan = (u: UngVien) =>
    `${ten[u.room_id] ?? "Phòng"}${u.chuyen ? " ★" : ""} · ${u.queue_load} đang chờ`;

  async function doi() {
    if (!chon || routingRevision == null) return;
    setDangGui(true);
    setLoi(null);
    const kq = await guiThaoTac("xep-phong-v1", orderId, {
      room_id: chon,
      expected_routing_revision: routingRevision,
      reason_code: phongHienTaiId ? "LOAD_BALANCE" : "INITIAL_ASSIGNMENT",
      recommendation_ref: goiY?.recommendation_ref,
      nguon,
      // Chỉ gửi khi có chọn — không gửi thì phòng một bác sĩ tự gán.
      ...(chonBs ? { bac_si_lam_id: chonBs } : {}),
    });
    setDangGui(false);
    if (!kq.ok) {
      setLoi(kq.loi);
      // 409 = chỉ định vừa được xếp / đổi (thường là hệ thống tự xếp sau thu):
      // tải lại ngay để thấy phòng hiện tại, không bắt người dùng tự tải.
      if (kq.status === 409) onDaDoi?.();
      return;
    }
    setChon("");
    setChonBs("");
    setLan((n) => n + 1);
    onDaDoi?.();
  }

  // Đổi BÁC SĨ trong phòng đang xếp (cùng lệnh xếp phòng, cùng phòng).
  async function doiBacSi(staffId: string) {
    if (!phongHienTaiId || routingRevision == null) return;
    setDangGui(true);
    setLoi(null);
    const kq = await guiThaoTac("xep-phong-v1", orderId, {
      room_id: phongHienTaiId,
      expected_routing_revision: routingRevision,
      reason_code: "MANUAL_CORRECTION",
      nguon,
      bac_si_lam_id: staffId || null,
    });
    setDangGui(false);
    if (!kq.ok) {
      setLoi(kq.loi);
      if (kq.status === 409) onDaDoi?.();
      return;
    }
    setLan((n) => n + 1);
    onDaDoi?.();
  }

  // Trưởng ca đặt PHÒNG DỰ KIẾN khi khách chưa trả tiền — thu xong dây H4 xếp
  // đúng phòng này. Máy chủ hỏi quyền Điều phối khách.
  async function datDuKien(roomId: string, bacSi?: string) {
    setDangGui(true);
    setLoi(null);
    const kq = await guiThaoTac("phong-du-kien", orderId, {
      room_id: roomId || null,
      nguon: "truong_ca",
      ...(bacSi !== undefined ? { bac_si_lam_id: bacSi || null } : {}),
    });
    setDangGui(false);
    if (!kq.ok) {
      setLoi(kq.loi);
      return;
    }
    setLan((n) => n + 1);
    onDaDoi?.();
  }

  // HƯỚNG DẪN PHÒNG (dây Nhận tại phòng bật): quầy / trưởng ca ghi phòng hướng
  // dẫn; màn khác (Bàn khám, Xem lượt) đi lệnh xếp phòng — máy chủ cũng chỉ ghi
  // hướng dẫn. Trưởng ca đổi phòng khách đang chờ = CHỈ ghi hướng dẫn (07/10:
  // khách sang phòng mới thì phòng ấy nhận chéo).
  async function huongDan(roomId: string) {
    if (nguon === "khac" && (!roomId || routingRevision == null)) return;
    setDangGui(true);
    setLoi(null);
    const kq =
      nguon === "khac"
        ? await guiThaoTac("xep-phong-v1", orderId, {
            room_id: roomId,
            expected_routing_revision: routingRevision,
            reason_code: "INITIAL_ASSIGNMENT",
            nguon,
          })
        : await guiThaoTac("phong-du-kien", orderId, { room_id: roomId || null, nguon });
    setDangGui(false);
    if (!kq.ok) {
      setLoi(kq.loi);
      return;
    }
    setLan((n) => n + 1);
    onDaDoi?.();
  }

  // Dịch vụ ĐANG LÀM: một lệnh máy chủ dừng lần làm + chuyển phòng + chuyển hàng.
  async function chuyenDangLam() {
    if (!chon || routingRevision == null) return;
    setDangGui(true);
    setLoi(null);
    const kq = await guiThaoTac("chuyen-phong-dang-lam", orderId, {
      room_id: chon,
      expected_routing_revision: routingRevision,
      ly_do: lyDo,
    });
    setDangGui(false);
    if (!kq.ok) {
      setLoi(kq.loi);
      if (kq.status === 409) onDaDoi?.();
      return;
    }
    setXacNhan(false);
    setLyDo("");
    setChon("");
    onDaDoi?.();
  }

  const cheDo = goiY.che_do ?? "XEP";
  const bsCua = (roomId: string | null | undefined) =>
    goiY.candidates.find((u) => u.room_id === roomId)?.bac_si;
  const bsHienTai = bsCua(phongHienTaiId);
  const bsPhongMoi = bsCua(chon);
  const bsDuKien = bsCua(goiY.phong_du_kien_id);
  const danhSach = (
    <p className="text-label text-ink-muted">
      Phòng làm được:{" "}
      {goiY.candidates.map((u, i) => (
        <span key={u.room_id} className={u.room_id === phongHienTaiId ? "font-semibold text-ink" : ""}>
          {i > 0 ? " · " : ""}
          {nhan(u)}
        </span>
      ))}
    </p>
  );

  if (goiY.huong_dan && (cheDo === "XEP" || cheDo === "DU_KIEN")) {
    return (
      <div className="mt-1 grid gap-1">
        {danhSach}
        <label className="flex flex-wrap items-center gap-2">
          <span className="text-label font-semibold text-ink">Hướng dẫn phòng (không bắt buộc)</span>
          <select
            aria-label="Hướng dẫn phòng"
            value={goiY.phong_du_kien_id ?? ""}
            disabled={dangGui}
            onChange={(e) => void huongDan(e.target.value)}
            className="min-h-8 rounded-control border border-line bg-surface px-2 text-xs text-ink"
          >
            <option value="">— Chưa hướng dẫn —</option>
            {goiY.candidates.map((u) => (
              <option key={u.room_id} value={u.room_id}>
                {nhan(u)}
              </option>
            ))}
          </select>
        </label>
        {/* GỢI Ý phòng chuyên ★ (07/10/2026): máy chủ chỉ gợi ý khi đúng một
            phòng chuyên; KHÔNG tự lưu — người bấm mới ghi hướng dẫn. */}
        {!goiY.phong_du_kien_id && goiY.goi_y_chuyen && ten[goiY.goi_y_chuyen] ? (
          <p className="flex flex-wrap items-center gap-2 text-label text-ink-muted">
            Gợi ý: {ten[goiY.goi_y_chuyen]} ★ (phòng chuyên, chưa lưu)
            <Button
              type="button"
              size="sm"
              variant="soft"
              disabled={dangGui}
              onClick={() => void huongDan(goiY.goi_y_chuyen as string)}
            >
              Hướng dẫn tới đây
            </Button>
          </p>
        ) : null}
        {goiY.phong_hien_tai ? (
          <p className="text-label text-ink-muted">Đã vào: {goiY.phong_hien_tai}</p>
        ) : null}
        {goiY.cau_che_do ? <p className="text-label text-ink-muted">{goiY.cau_che_do}</p> : null}
        {loi ? <p className="text-label text-danger">{loi}</p> : null}
      </div>
    );
  }

  if (cheDo === "DU_KIEN") {
    return (
      <div className="mt-1 grid gap-1">
        {danhSach}
        <div className="flex flex-wrap items-center gap-2">
          <select
            aria-label="Phòng dự kiến"
            value={goiY.phong_du_kien_id ?? ""}
            disabled={dangGui}
            onChange={(e) => void datDuKien(e.target.value)}
            className="min-h-8 rounded-control border border-line bg-surface px-2 text-xs text-ink"
          >
            <option value="">— Vui lòng chọn phòng —</option>
            {goiY.candidates.map((u) => (
              <option key={u.room_id} value={u.room_id}>
                {nhan(u)}
              </option>
            ))}
          </select>
          {coChonBacSi(bsDuKien) && goiY.phong_du_kien_id ? (
            <ChonBacSiLam
              co="nho"
              ds={bsDuKien}
              value={goiY.bac_si_lam_id ?? ""}
              disabled={dangGui}
              onChon={(id) => void datDuKien(goiY.phong_du_kien_id as string, id)}
            />
          ) : null}
          {goiY.cau_che_do ? <span className="text-label text-ink-muted">{goiY.cau_che_do}</span> : null}
        </div>
        {loi ? <p className="text-label text-danger">{loi}</p> : null}
      </div>
    );
  }

  if (cheDo === "CHUYEN_DANG_LAM") {
    const tenDen = goiY.candidates.find((u) => u.room_id === chon);
    const tu = gioPhut(goiY.dang_lam_tu);
    return (
      <div className="mt-1 grid gap-1">
        {danhSach}
        <div className="flex flex-wrap items-center gap-2">
          <select
            aria-label="Chuyển sang phòng"
            value={chon}
            onChange={(e) => {
              setChon(e.target.value);
              setXacNhan(false);
            }}
            className="min-h-8 rounded-control border border-line bg-surface px-2 text-xs text-ink"
          >
            <option value="">Chuyển sang phòng…</option>
            {goiY.candidates
              .filter((u) => u.room_id !== phongHienTaiId)
              .map((u) => (
                <option key={u.room_id} value={u.room_id}>
                  {nhan(u)}
                </option>
              ))}
          </select>
          <Button
            type="button"
            size="sm"
            variant="secondary"
            disabled={!chon || dangGui || xacNhan}
            onClick={() => setXacNhan(true)}
          >
            Chuyển phòng
          </Button>
        </div>
        {xacNhan && tenDen ? (
          <XacNhanTaiCho
            cau={`Khách đang làm ở ${goiY.phong_hien_tai ?? "phòng hiện tại"}${tu ? ` từ ${tu}` : ""} — chuyển sang ${ten[tenDen.room_id] ?? "phòng mới"}?`}
            nhanDongY="Chuyển phòng"
            onDongY={() => void chuyenDangLam()}
            onThoi={() => setXacNhan(false)}
            dangGui={dangGui}
            choDongY={lyDo.trim().length >= 3}
          >
            <input
              type="text"
              aria-label="Lý do chuyển phòng"
              placeholder="Lý do (bắt buộc) — vd máy hỏng, phòng quá tải"
              value={lyDo}
              maxLength={300}
              onChange={(e) => setLyDo(e.target.value)}
              className="min-h-8 w-full rounded-control border border-line bg-surface px-2 text-body text-ink"
            />
          </XacNhanTaiCho>
        ) : null}
        {loi ? <p className="text-label text-danger">{loi}</p> : null}
      </div>
    );
  }

  const coDoi = choDoi && cheDo === "XEP";
  return (
    <div className="mt-1 grid gap-1">
      {danhSach}
      {phongHienTaiId && coDoi && coChonBacSi(bsHienTai) ? (
        <label className="flex flex-wrap items-center gap-2">
          <span className="text-label text-ink-muted">Bác sĩ ở phòng này</span>
          <ChonBacSiLam
            co="nho"
            ds={bsHienTai}
            value={goiY.bac_si_lam_id ?? ""}
            disabled={dangGui}
            onChon={(id) => void doiBacSi(id)}
          />
        </label>
      ) : goiY.bac_si_lam && phongHienTaiId ? (
        <p className="text-label text-ink-muted">Bác sĩ: {goiY.bac_si_lam}</p>
      ) : null}
      {coDoi ? (
        <div className="flex flex-wrap items-center gap-2">
          <select
            aria-label="Chọn phòng khác"
            value={chon}
            onChange={(e) => {
              setChon(e.target.value);
              setChonBs("");
            }}
            className="min-h-8 rounded-control border border-line bg-surface px-2 text-xs text-ink"
          >
            <option value="">{phongHienTaiId ? "Đổi sang phòng…" : "— Vui lòng chọn phòng —"}</option>
            {goiY.candidates
              .filter((u) => u.room_id !== phongHienTaiId)
              .map((u) => (
                <option key={u.room_id} value={u.room_id}>
                  {nhan(u)}
                </option>
              ))}
          </select>
          {coChonBacSi(bsPhongMoi) ? (
            <ChonBacSiLam co="nho" ds={bsPhongMoi} value={chonBs} disabled={dangGui} onChon={setChonBs} />
          ) : null}
          <Button
            type="button"
            size="sm"
            variant="secondary"
            disabled={!chon || dangGui}
            onClick={() => void doi()}
          >
            {phongHienTaiId ? "Đổi phòng" : "Xếp phòng"}
          </Button>
          {phongHienTaiId && routingRevision != null ? (
            // Xếp nhầm phòng (01/10/2026): rút về "chưa xếp phòng" — chỗ chờ ở
            // phòng cũ huỷ, giữ thứ tự chờ. Máy chủ chặn khi khách đã vào làm.
            <NutHoanTac
              nhan="Huỷ xếp phòng"
              moTa="Bỏ phòng đã xếp — chỉ định về chưa xếp phòng"
              disabled={dangGui}
              goi={lenhHoanTac("huy-xep-phong-v1", orderId, {
                expected_routing_revision: routingRevision,
                reason_code: "ASSIGNED_BY_MISTAKE",
              })}
              onXong={() => {
                setChon("");
                setLan((x) => x + 1);
                onDaDoi?.();
              }}
            />
          ) : null}
        </div>
      ) : null}
      {loi ? <p className="text-label text-danger">{loi}</p> : null}
    </div>
  );
}
