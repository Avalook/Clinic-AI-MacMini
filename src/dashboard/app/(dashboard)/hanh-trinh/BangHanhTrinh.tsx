"use client";

// Bảng hành trình chung — CHỈ VẼ. Mọi câu "đang ở đâu / còn chờ gì" do máy chủ
// tính (bang_hanh_trinh_service.py); màn không tự suy trạng thái.

import { useCallback, useEffect, useState } from "react";

import Button from "@/components/ui/Button";
import Chip from "@/components/ui/Chip";
import type { HanhTrinhGon } from "@/lib/hanh-trinh-khach";

import { DongHanhTrinhGon, NutXemHanhTrinh } from "../_lam-viec/HanhTrinhKhach";
import NutXemLuot from "../_lam-viec/NutXemLuot";
import NutCheckOut from "../_lam-viec/NutCheckOut";
import { docBang, gioVn } from "../_lam-viec/api";
import SoLuot from "@/components/ui/SoLuot";
import { doctorName } from "@/lib/doctor-name";
import { useNgheBang } from "../dung-nghe-bang";
import { nhipKhiHien } from "@/lib/nhip-khi-hien";

interface Luot {
  visit_id: string;
  ten: string;
  ma: string | null;
  so_booking: number | null;
  so_quay: number | null;
  loai_kham: string | null;
  bac_si: string | null;
  check_in_luc: string | null;
  dang_o: string;
  da_xong: { nhan: string; luc: string }[];
  con_cho: string[];
  da_ve: boolean;
  /** Hành trình khách dạng gọn (29/09/2026) — máy chủ tính, cùng hàm với
   *  trang chủ + khung đầy đủ. */
  gon?: HanhTrinhGon | null;
}

interface Bang {
  luot: Luot[];
  bi_cat: boolean;
}

export default function BangHanhTrinh() {
  const [bang, setBang] = useState<Bang | null>(null);
  const [loi, setLoi] = useState<string | null>(null);
  const [anDaVe, setAnDaVe] = useState(true);
  const [tim, setTim] = useState("");
  // Đồng hồ cho nhãn "đang 12 phút" trên đoạn nối — vẽ lại mỗi 30 giây.
  const [bayGio, setBayGio] = useState(() => Date.now());
  useEffect(() => {
    const t = setInterval(() => setBayGio(Date.now()), 30_000);
    return () => clearInterval(t);
  }, []);

  const tai = useCallback(async () => {
    const kq = await docBang<Bang>("hanh-trinh");
    if (kq.ok) {
      setBang(kq.data);
      setBayGio(Date.now());
      setLoi(null);
    } else {
      setLoi(kq.loi);
    }
  }, []);

  useEffect(() => {
    let huy = false;
    void docBang<Bang>("hanh-trinh").then((kq) => {
      if (huy) return;
      if (kq.ok) setBang(kq.data);
      else setLoi(kq.loi);
    });
    // SỰ KIỆN THAY NHỊP HỎI (27/09/2026): nghe tin bảng đổi qua dòng SSE chung
    // (`useNgheBang`) → nạp lại NGAY; nhịp hỏi giãn còn 60 giây làm lưới an toàn.
    // Tab ẩn thì huỷ hẳn nhịp; hiện lại thì tin `null` của RealtimeRefresher (qua
    // `useNgheBang`) đã hỏi lại một lần — nhịp không hỏi thêm (30/09/2026).
    const goNhip = nhipKhiHien(() => void tai(), 60_000, { hoiKhiHien: false });
    return () => {
      huy = true;
      goNhip();
    };
  }, [tai]);

  useNgheBang(["luot_dong_thoi_gian", "visit", "queue_entry"], () => void tai());

  if (loi && !bang) {
    return (
      <p role="alert" className="text-body text-danger">
        {loi}
      </p>
    );
  }
  if (!bang) return <p className="text-body text-ink-muted">Đang tải…</p>;

  const q = tim.trim().toLowerCase();
  const ds = bang.luot.filter(
    (l) =>
      (!anDaVe || !l.da_ve) &&
      (!q || l.ten.toLowerCase().includes(q) || (l.ma ?? "").toLowerCase().includes(q)),
  );

  return (
    <section className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <input
          value={tim}
          onChange={(e) => setTim(e.target.value)}
          placeholder="Tìm tên / mã khách"
          aria-label="Tìm khách"
          className="min-h-10 flex-1 rounded-control border border-line bg-surface px-3 text-body text-ink"
        />
        <Button size="lg" variant="secondary" onClick={() => setAnDaVe((v) => !v)}>
          {anDaVe ? "Hiện cả khách đã về" : "Ẩn khách đã về"}
        </Button>
        <Button size="lg" variant="ghost" onClick={() => void tai()}>
          Tải lại
        </Button>
      </div>
      {bang.bi_cat ? (
        <p className="text-meta text-warning">
          Bảng chỉ hiện 300 lượt đầu trong ngày — tìm theo tên để thấy khách khác.
        </p>
      ) : null}
      <p className="text-meta text-ink-muted">{ds.length} khách</p>
      <ul className="space-y-2">
        {ds.map((l) => (
          <li
            key={l.visit_id}
            className="rounded-card border border-line bg-surface p-3 shadow-card"
          >
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <div className="min-w-0">
                <p className="flex flex-wrap items-center gap-x-2 gap-y-1 text-emph font-semibold text-ink">
                  {l.ten}
                  {l.ma ? <span className="text-meta font-normal text-ink-muted">{l.ma}</span> : null}
                  <SoLuot booking={l.so_booking} checkin={l.so_quay} />
                </p>
                <p className="text-meta text-ink-muted">
                  {[
                    l.loai_kham,
                    l.bac_si ? doctorName(l.bac_si) : null,
                    l.check_in_luc ? `tới ${gioVn(l.check_in_luc)}` : null,
                  ]
                    .filter(Boolean)
                    .join(" · ")}
                </p>
              </div>
              {/* Có dòng gọn thì câu "đang ở" nằm ở đó — không nói hai lần. */}
              {l.gon ? null : <Chip tone={l.da_ve ? "neutral" : "brand"}>{l.dang_o}</Chip>}
            </div>
            {/* HÀNH TRÌNH KHÁCH dạng gọn (Tuyền chốt 29/09/2026): đang ở / đang
                chờ PHÒNG nào, thanh đoạn màu, x/y dịch vụ xong — cùng component
                với trang chủ; [Xem kỹ] mở khung đầy đủ. Máy chủ cũ chưa có
                `gon` thì lùi về hai cột Đã xong / Còn chờ như trước. */}
            {l.gon ? (
              <div className="mt-3">
                <DongHanhTrinhGon gon={l.gon} bayGio={bayGio} />
              </div>
            ) : (
              <div className="mt-2 grid gap-2 sm:grid-cols-2">
                <div>
                  <p className="text-label font-semibold uppercase tracking-wide text-ink-muted">
                    Đã xong
                  </p>
                  {l.da_xong.length === 0 ? (
                    <p className="text-meta text-ink-faint">—</p>
                  ) : (
                    <ol className="text-meta text-ink">
                      {l.da_xong.map((x, i) => (
                        <li key={i}>
                          <span className="text-ink-muted">{gioVn(x.luc)}</span> {x.nhan}
                        </li>
                      ))}
                    </ol>
                  )}
                </div>
                <div>
                  <p className="text-label font-semibold uppercase tracking-wide text-ink-muted">
                    Còn chờ
                  </p>
                  {l.con_cho.length === 0 ? (
                    <p className="text-meta text-ink-faint">Không còn gì chờ</p>
                  ) : (
                    <ul className="text-meta text-ink">
                      {l.con_cho.map((x, i) => (
                        <li key={i}>• {x}</li>
                      ))}
                    </ul>
                  )}
                </div>
              </div>
            )}
            <div className="mt-2 flex flex-wrap items-start gap-2">
              <NutXemHanhTrinh visitId={l.visit_id} ten={l.ten} nhan="Xem kỹ hành trình ›" />
              <NutXemLuot visitId={l.visit_id} nhan="Xem lượt" />
              {/* Check-out ngay trên dòng khách (27/09/2026, đợt 3): chỉ tài
                  khoản có quyền đóng lượt thấy; máy chủ quyết, xong thì nạp
                  lại để mốc "đã về" đổi ngay. */}
              {!l.da_ve ? (
                <NutCheckOut
                  key={l.visit_id}
                  visitId={l.visit_id}
                  ten={l.ten}
                  onXong={() => void tai()}
                />
              ) : null}
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}
