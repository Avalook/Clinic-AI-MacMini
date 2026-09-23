"use client";

// MỘT PHÒNG DỊCH VỤ: siêu âm, thủ thuật, lấy mẫu (Tuyền chốt 16/09/2026).
//
// Trái: hàng chờ của phòng. Phải: khách đang chọn —
//   Bắt đầu  → mở một LẦN LÀM (giờ vào) + dời con trỏ "khách đang ở đâu"
//   phiếu kết quả + gửi ảnh/video/PDF vào ô (xem ngay tại chỗ)
//   Xong     → đóng lần làm ấy, khách sang bước tiếp theo
//
// MỘT NÚT CHÍNH, NHIỀU SỰ THẬT PHÍA SAU (ChatGPT tin số 156, Tuyền tin số 157: *"chỉ cần
// 1 nút bắt đầu … xử lý thông minh phía sau, nút chỉ 1"*). Người làm thấy đúng
// hai nút trong cả ca: [Bắt đầu] rồi [Hoàn tất]. Bấm [Hoàn tất] một lần, hệ
// thống ghi cả ba việc: xác nhận toàn bộ phiếu · đóng dịch vụ
// (`service.completed`) · phát "đã có kết quả" (`result.ready`) nếu dịch vụ
// này có kết quả ngay tại phòng.
//
// Dịch vụ KHÔNG có phiếu kết quả (lấy mẫu gửi đi) thì [Hoàn tất] gọi thẳng
// lệnh đóng dịch vụ — vẫn một nút, vẫn một chỗ bấm.
//
// BA NGOẠI LỆ nằm ở hàng phụ, không phải nút chính: Không làm được (chưa bắt
// đầu) · Dừng giữa chừng (đã bắt đầu) · Làm lại. Đời thật có máy hỏng lúc
// 10:05 và khách đổi ý ở cửa phòng — nhưng đó là ngoại lệ, và giao diện không
// được bày ngoại lệ ngang hàng với việc thường. Bốn thứ KHÔNG BAO GIỜ tự động
// khi dừng: không tự hoàn tiền, không tự đánh dấu xong, không tự mở lần mới,
// không tự đổi phòng.
//
// Ai bấm được là do MÁY CHỦ quyết — nay theo QUYỀN (khối "Thực hiện dịch vụ"),
// không theo vai. Màn này không tự đoán, chỉ hiện câu từ chối của máy chủ.
// Ẩn nút không phải bảo mật: mỗi lệnh vẫn tự hỏi quyền của nó khi bấm.
//
// BỎ HẲN [GỌI VÀO] (Tuyền chốt 23/09/2026): `Gọi vào → Bắt đầu` là hai bước
// cho một việc. Nay chỉ còn `Chờ → Bắt đầu → Hoàn tất`. Lệnh Bắt đầu đã hấp
// thụ phần việc thật mà [Gọi vào] từng làm — dời con trỏ "khách đang ở đâu" —
// nên đây không phải xoá một cái nút rồi để state mắc lại.
//
// `called_at` trong database GIỮ NGUYÊN: lượt cũ còn đọc được giờ gọi. Chỉ
// thôi ghi mới từ màn này.
//
// KẾT QUẢ KHÔNG NẰM TRONG LỆNH "XONG" nữa. "Đã làm xong" và "đã có kết quả" là
// hai sự thật khác nhau — kết quả đi qua phiếu (`PhieuKetQua`), có vòng đời và
// người chịu trách nhiệm riêng. Hoàn tất phiếu lúc dịch vụ còn đang làm dở thì
// máy chủ đóng hộ dịch vụ và NÓI RA là đã đóng hay chưa.

import { useCallback, useEffect, useState } from "react";

import {
  docBang,
  guiThaoTac,
  gioVn,
  soPhutTu,
  LY_DO_TIENG_VIET,
  type DongHangCho,
  type Phong,
  type PhongHomNay,
  type ThucHien,
} from "../../_lam-viec/api";
import HangChoCot from "../../_lam-viec/HangChoCot";
import KhungTep from "../../_lam-viec/KhungTep";
import PhieuKetQua from "../../_lam-viec/PhieuKetQua";
import XemLuot from "../../_lam-viec/XemLuot";
import Button from "@/components/ui/Button";

type LoaiPhong = "SIEU_AM" | "THU_THUAT" | "LAY_MAU" | "KHAC";

function loaiCua(node: string | null): LoaiPhong {
  if (!node) return "KHAC";
  if (node === "DICHVU-SIEUAM") return "SIEU_AM";
  if (node.startsWith("DICHVU-LAYMAU")) return "LAY_MAU";
  if (node === "DICHVU-THUTHUAT" || node === "DICHVU-SANGLOC-COTUCUNG") {
    return "THU_THUAT";
  }
  return "KHAC";
}

const NUT_XONG: Record<LoaiPhong, string> = {
  SIEU_AM: "Siêu âm xong",
  THU_THUAT: "Làm thủ thuật xong",
  LAY_MAU: "Đã lấy mẫu",
  KHAC: "Làm xong",
};

export default function PhongDichVu({ ma }: { ma: string }) {
  const [phong, setPhong] = useState<Phong | null>(null);
  const [khongCo, setKhongCo] = useState(false);
  const [hang, setHang] = useState<DongHangCho[] | null>(null);
  const [loi, setLoi] = useState<string | null>(null);
  const [chonId, setChonId] = useState<string | null>(null);
  const [lanNap, setLanNap] = useState(0);

  useEffect(() => {
    let huy = false;
    void docBang<PhongHomNay>("phong-hom-nay").then((kq) => {
      if (huy) return;
      if (!kq.ok) {
        setLoi(kq.loi);
        return;
      }
      const p = kq.data.tat_ca_phong.find((x) => x.code === ma) ?? null;
      setPhong(p);
      setKhongCo(p === null);
    });
    return () => {
      huy = true;
    };
  }, [ma]);

  useEffect(() => {
    if (!phong) return;
    let huy = false;
    const nap = async () => {
      const kq = await docBang<{ hang_cho: DongHangCho[] }>("hang-cho", {
        phong: phong.id,
      });
      if (huy) return;
      if (kq.ok) {
        setLoi(null);
        setHang(kq.data.hang_cho.filter((d) => d.loai === "DICH_VU"));
      } else setLoi(kq.loi);
    };
    void nap();
    const t = setInterval(() => void nap(), 15000);
    return () => {
      huy = true;
      clearInterval(t);
    };
  }, [phong, lanNap]);

  const napLai = useCallback(() => setLanNap((n) => n + 1), []);

  if (khongCo) {
    return (
      <p className="rounded-card border border-danger bg-danger-bg p-4 text-sm text-danger">
        Không có phòng “{ma}”, hoặc phòng đã tắt.
      </p>
    );
  }

  const ds = hang ?? [];
  const macDinh =
    ds.find((d) => d.trang_thai === "serving") ??
    ds.find((d) => d.trang_thai === "waiting" || d.trang_thai === "called") ??
    null;
  const chon = ds.find((d) => d.id === chonId) ?? macDinh;

  return (
    <div className="grid gap-4">
      <header className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <h1 className="text-xl font-semibold text-ink">{phong?.ten ?? "Đang tải…"}</h1>
        {phong?.tang ? <p className="text-sm text-ink-muted">{phong.tang}</p> : null}
        {hang ? (
          <p className="text-sm text-ink-muted">
            {ds.filter((d) => d.trang_thai === "waiting" || d.trang_thai === "called").length}{" "}
            đang chờ · {ds.filter((d) => d.trang_thai === "serving").length} đang làm ·{" "}
            {ds.filter((d) => d.trang_thai === "done").length} đã xong
          </p>
        ) : null}
        {loi ? (
          <p role="alert" className="text-sm text-danger">
            {loi}
          </p>
        ) : null}
      </header>

      <div className="grid items-start gap-4 lg:grid-cols-[minmax(240px,0.6fr)_minmax(0,1.8fr)]">
        <aside aria-label="Hàng chờ phòng">
          {hang === null ? (
            <p className="text-sm text-ink-muted">Đang tải hàng chờ…</p>
          ) : (
            <HangChoCot
              dong={ds}
              chon={chon?.id ?? null}
              onChon={(id) => {
                setChonId(id);
                // Màn hẹp: khung khách nằm DƯỚI danh sách — tự cuộn tới (smoke
                // 18/09, 375).
                if (window.innerWidth < 1024) {
                  requestAnimationFrame(() =>
                    document
                      .getElementById("khung-khach-trong-phong")
                      ?.scrollIntoView({ block: "start" }),
                  );
                }
              }}
              trong="Chưa có khách nào được chỉ định vào phòng này."
            />
          )}
        </aside>
        {chon ? (
          <KhachTrongPhong key={chon.id} dong={chon} onDaBam={napLai} />
        ) : (
          <section className="grid min-h-72 place-items-center rounded-card bg-surface p-8 text-center text-sm text-ink-muted shadow-card">
            Chọn một khách trong hàng chờ.
          </section>
        )}
      </div>
    </div>
  );
}

function KhachTrongPhong({
  dong,
  onDaBam,
}: {
  dong: DongHangCho;
  onDaBam: () => void;
}) {
  const loai = loaiCua(dong.node_code);
  const [th, setTh] = useState<ThucHien | null>(null);
  const [moLyDo, setMoLyDo] = useState<"khong-lam" | "gian-doan" | null>(null);
  const [lyDo, setLyDo] = useState("");
  const [ghiChu, setGhiChu] = useState("");
  const [dangGui, setDangGui] = useState(false);
  const [loi, setLoi] = useState<string | null>(null);
  const [bao, setBao] = useState<string | null>(null);
  const [xemLuot, setXemLuot] = useState(false);
  const [lanDoc, setLanDoc] = useState(0);

  // Trạng thái thực hiện đọc riêng, không lấy từ hàng chờ: hàng chờ không mang
  // hai số revision, mà thiếu chúng thì mọi lệnh đều phải đoán.
  useEffect(() => {
    let huy = false;
    void docBang<ThucHien>("thuc-hien", { chi_dinh: dong.ref_id }).then((kq) => {
      if (huy) return;
      if (kq.ok) setTh(kq.data);
      else setLoi(kq.loi);
    });
    return () => {
      huy = true;
    };
  }, [dong.ref_id, lanDoc]);

  const docLai = () => setLanDoc((n) => n + 1);

  /** Một lệnh thực hiện. Xong thì đọc lại trạng thái VÀ nạp lại hàng chờ. */
  const lenh = async (thaoTac: string, duLieu: Record<string, unknown>) => {
    setDangGui(true);
    setLoi(null);
    setBao(null);
    const kq = await guiThaoTac(thaoTac, dong.ref_id, duLieu);
    setDangGui(false);
    if (!kq.ok) {
      setLoi(kq.loi);
      return;
    }
    setMoLyDo(null);
    setLyDo("");
    setGhiChu("");
    docLai();
    onDaBam();
  };

  const trangThai = th?.execution_status ?? null;
  const dangLam = trangThai === "IN_PROGRESS" && th?.lan_dang_chay != null;
  const daDung = trangThai === "INTERRUPTED" && th?.lan_da_dung != null;
  const daXong = trangThai === "COMPLETED" || trangThai === "NOT_PERFORMED";
  const chuaLam = trangThai === "PENDING";

  return (
    <section
      id="khung-khach-trong-phong"
      aria-label={`Khách ${dong.ten}`}
      className="min-w-0 space-y-4 rounded-card bg-surface p-4 shadow-card"
    >
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-label font-semibold uppercase tracking-wide text-ink-muted">
            Số {dong.so_thu_tu}
          </p>
          <h2 className="text-lg font-semibold text-ink">{dong.ten}</h2>
          <p className="text-sm text-ink-muted">
            {dong.ma_bn} · {dong.viec ?? "—"}
            {dong.bac_si ? ` · BS chỉ định: ${dong.bac_si}` : ""}
          </p>
          <p className="mt-1 text-label text-ink-muted">
            {daXong
              ? `Xong lúc ${gioVn(dong.xong_luc)}`
              : dangLam
                ? `Lần làm #${th?.lan_dang_chay?.attempt_no} · bắt đầu ${gioVn(
                    th?.lan_dang_chay?.started_at ?? null,
                  )} · đã làm ${soPhutTu(th?.lan_dang_chay?.started_at ?? null)}`
                : daDung
                  ? `Lần làm #${th?.lan_da_dung?.attempt_no} đã dừng${
                      th?.lan_da_dung?.interruption_reason_code
                        ? ` — ${nhanLyDo(th.lan_da_dung.interruption_reason_code)}`
                        : ""
                    }`
                  : dong.trang_thai === "blocked"
                    ? "Khách đang ở một bước khác — chưa làm bước này được."
                    : `Vào hàng ${gioVn(dong.vao_hang_luc)} · chờ ${soPhutTu(dong.vao_hang_luc)}`}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          {chuaLam && th ? (
            <Button
              size="lg"
              variant="primary"
              disabled={dangGui}
              onClick={() =>
                void lenh("bat-dau-v1", {
                  expected_execution_revision: th.execution_revision,
                  expected_routing_revision: th.routing_revision,
                })
              }
            >
              {dangGui ? "Đang ghi…" : "Bắt đầu"}
            </Button>
          ) : null}
          {daDung && th?.lan_da_dung ? (
            <Button
              size="lg"
              variant="primary"
              disabled={dangGui}
              onClick={() =>
                void lenh("lam-lai-v1", {
                  interrupted_attempt_id: th.lan_da_dung!.id,
                  expected_execution_revision: th.execution_revision,
                })
              }
            >
              {dangGui ? "Đang ghi…" : "Làm lại"}
            </Button>
          ) : null}
        </div>
      </header>

      {loi ? (
        <p
          role="alert"
          className="rounded-control border border-danger bg-danger-bg px-3 py-2 text-sm text-danger"
        >
          {loi}
        </p>
      ) : null}
      {bao ? (
        <p className="rounded-control border border-warning bg-warning-bg px-3 py-2 text-sm text-warning">
          {bao}
        </p>
      ) : null}

      {/* Lịch sử các lần làm: máy hỏng lúc 10:05 rồi làm lại 10:18 là chuyện
          phải đọc được, không phải chuyện bị ghi đè. */}
      {th && th.cac_lan.length > 1 ? (
        <ol className="space-y-1 rounded-control bg-surface-muted px-3 py-2 text-xs text-ink-soft">
          {th.cac_lan.map((l) => (
            <li key={l.id}>
              Lần #{l.attempt_no} · {gioVn(l.started_at)}
              {l.status === "COMPLETED"
                ? ` → xong ${gioVn(l.completed_at)}`
                : l.status === "INTERRUPTED"
                  ? ` → dừng ${gioVn(l.interrupted_at)}${
                      l.interruption_reason_code
                        ? ` (${nhanLyDo(l.interruption_reason_code)})`
                        : ""
                    }`
                  : " → đang làm"}
              {l.bat_dau_boi ? ` · ${l.bat_dau_boi}` : ""}
            </li>
          ))}
        </ol>
      ) : null}

      {/* ĐÃ XONG: xem lại đúng cái đã ghi (batch pilot 18/09). */}
      {daXong ? (
        <div className="rounded-control bg-surface-muted px-3 py-2 text-sm">
          <p className="text-ink">
            {trangThai === "NOT_PERFORMED" ? "Không làm được" : "Đã làm"}
            {dong.nguoi_lam ? ` · ${dong.nguoi_lam}` : ""} · {gioVn(dong.xong_luc)}
          </p>
          {dong.ly_do_khong_lam ? (
            <p className="text-xs text-warning">
              Lý do: {nhanLyDo(dong.ly_do_khong_lam)}
            </p>
          ) : null}
          <Button
            size="sm"
            variant="ghost"
            className="mt-1 -ml-3"
            onClick={() => setXemLuot(true)}
          >
            Xem lại cả lượt
          </Button>
          {xemLuot ? (
            <XemLuot visitId={dong.visit_id} onDong={() => setXemLuot(false)} />
          ) : null}
        </div>
      ) : null}

      {/* Ô TỆP: có ngay từ lúc khách đang làm, để gửi ảnh/video ngay khi chụp. */}
      {(dangLam || daXong) && loai !== "LAY_MAU" ? (
        <KhungTep
          clinicPatientId={dong.clinic_patient_id}
          serviceOrderId={dong.ref_id}
          tieuDe={loai === "SIEU_AM" ? "Ảnh & video siêu âm" : "Ảnh · video · phiếu"}
        />
      ) : null}

      {/* Phiếu kết quả: mở được ngay khi đang làm, và vẫn xem/điền được sau khi
          dịch vụ đã đóng — kết quả về muộn là chuyện thường. */}
      {th && (dangLam || daXong) ? (
        <PhieuKetQua
          serviceOrderId={dong.ref_id}
          mau={th.mau_ket_qua}
          onHoanTat={({ daDongDichVu, viSao, laLanSua }) => {
            setBao(
              laLanSua
                ? "Đã ghi bản sửa của kết quả."
                : daDongDichVu
                  ? "Đã hoàn tất phiếu, đóng dịch vụ và báo có kết quả."
                  : `Đã hoàn tất phiếu. Dịch vụ CHƯA đóng: ${viSao ?? "không rõ lý do"}.`,
            );
            docLai();
            onDaBam();
          }}
        />
      ) : null}

      {/* HÀNG PHỤ: ba ngoại lệ. Không nút chính nào ở đây — nút chính là
          [Bắt đầu] trên đầu và [Hoàn tất] trong phiếu. */}
      {th && (chuaLam || dangLam) ? (
        <div className="space-y-3 border-t border-line pt-3">
          {dangLam && th.lan_dang_chay && th.mau_ket_qua.length === 0 ? (
            // Dịch vụ không có phiếu kết quả (lấy mẫu gửi đi): [Hoàn tất] gọi
            // thẳng lệnh đóng dịch vụ. Vẫn đúng một nút kết thúc.
            <Button
              size="lg"
              variant="primary"
              disabled={dangGui}
              onClick={() =>
                void lenh("xong-v1", {
                  attempt_id: th.lan_dang_chay!.id,
                  expected_execution_revision: th.execution_revision,
                })
              }
            >
              {dangGui ? "Đang ghi…" : NUT_XONG[loai]}
            </Button>
          ) : null}

          <button
            type="button"
            onClick={() =>
              setMoLyDo((v) => (v ? null : dangLam ? "gian-doan" : "khong-lam"))
            }
            className="text-sm text-ink-muted underline underline-offset-4 hover:text-ink"
          >
            {dangLam ? "Phải dừng giữa chừng?" : "Không làm được?"}
          </button>

          {moLyDo ? (
            <div className="space-y-2 rounded-control border border-line bg-surface-muted p-3">
              <label className="block">
                <span className="text-xs font-semibold text-ink">
                  {moLyDo === "gian-doan"
                    ? "Vì sao phải dừng giữa chừng"
                    : "Vì sao không làm được"}
                </span>
                <select
                  value={lyDo}
                  onChange={(e) => setLyDo(e.target.value)}
                  className="mt-1 min-h-10 w-full max-w-md rounded-control border border-line bg-surface px-3 text-sm text-ink"
                >
                  <option value="">— chọn lý do —</option>
                  {(moLyDo === "gian-doan"
                    ? th.ly_do_gian_doan
                    : th.ly_do_khong_lam
                  ).map((m) => (
                    <option key={m} value={m}>
                      {nhanLyDo(m)}
                    </option>
                  ))}
                </select>
              </label>
              <label className="block">
                <span className="text-xs font-semibold text-ink">
                  Ghi chú (không bắt buộc)
                </span>
                <input
                  value={ghiChu}
                  onChange={(e) => setGhiChu(e.target.value)}
                  className="mt-1 min-h-10 w-full rounded-control border border-line bg-surface px-3 text-sm text-ink"
                />
              </label>
              <p className="text-label text-ink-muted">
                Ghi xong KHÔNG tự hoàn tiền, không tự mở lần làm mới, không tự
                đổi phòng — mỗi việc ấy là một quyết định riêng.
              </p>
              <Button
                size="md"
                variant="danger"
                disabled={dangGui || !lyDo}
                onClick={() =>
                  void lenh(
                    moLyDo === "gian-doan" ? "gian-doan-v1" : "khong-lam-v1",
                    moLyDo === "gian-doan"
                      ? {
                          attempt_id: th.lan_dang_chay?.id,
                          expected_execution_revision: th.execution_revision,
                          ly_do: lyDo,
                          ghi_chu: ghiChu || null,
                        }
                      : {
                          expected_execution_revision: th.execution_revision,
                          ly_do: lyDo,
                          ghi_chu: ghiChu || null,
                        },
                  )
                }
              >
                {moLyDo === "gian-doan" ? "Ghi dừng giữa chừng" : "Ghi không làm được"}
              </Button>
            </div>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}

/** Mã lý do → câu người đọc được. Mã lạ hiện nguyên mã, không giấu đi. */
function nhanLyDo(ma: string): string {
  return LY_DO_TIENG_VIET[ma] ?? ma;
}
