"use client";

// CHỈ ĐỊNH HÔM NAY — batch pilot 18/09/2026 (Pack B, vai Trưởng ca).
//
// Bốn nhóm: Cần điều phối · Đã điều phối · Đang thực hiện · Đã hoàn tất. Trưởng
// ca chỉ XẾP PHÒNG từng chỉ định (ở mục "Bác sĩ chỉ định gì" của từng khách) —
// không tạo chỉ định, không bấm xong thay phòng. Bấm một dòng mở dòng thời gian
// đầy đủ: BS chỉ định → xếp phòng → phòng gọi → bắt đầu → xong → có kết quả →
// quay lại bác sĩ (viewer dùng chung, máy chủ cắt nội dung theo vai).

import { useEffect, useState } from "react";

import { docBang, gioVn } from "../_lam-viec/api";
import XemLuot from "../_lam-viec/XemLuot";
import { useNgheBang } from "../dung-nghe-bang";

interface ChiDinh {
  id: string;
  visit_id: string;
  ten: string;
  ma_bn: string | null;
  dich_vu: string;
  trang_thai: string;
  nhom: "can_dieu_phoi" | "da_dieu_phoi" | "dang_thuc_hien" | "da_hoan_tat";
  phong: string | null;
  nguoi_lam: string | null;
  can: string | null;
  vong_doc: string | null;
  khong_co_phong: boolean;
  chi_dinh_luc: string | null;
  xep_phong_luc: string | null;
  bat_dau_luc: string | null;
  xong_luc: string | null;
  ket_qua_luc: string | null;
}

const NHOM: { ma: ChiDinh["nhom"]; nhan: string }[] = [
  { ma: "can_dieu_phoi", nhan: "Cần điều phối" },
  { ma: "da_dieu_phoi", nhan: "Đã điều phối" },
  { ma: "dang_thuc_hien", nhan: "Đang thực hiện" },
  { ma: "da_hoan_tat", nhan: "Đã hoàn tất" },
];
const VONG: Record<string, string> = {
  collecting: "vòng đọc: chờ làm xong / có kết quả",
  ready: "khách chờ bác sĩ đọc",
  in_review: "bác sĩ đang đọc",
  closed: "đã quay lại bác sĩ",
};

export default function ChiDinhHomNay() {
  const [ds, setDs] = useState<ChiDinh[] | null>(null);
  // Backend cắt bảng ở một trần (500 dòng). Cắt mà không nói là để trưởng ca
  // nhìn một bảng thiếu người mà tưởng đã hết — nên màn phải nói ra.
  const [biCat, setBiCat] = useState<{ tong: number; hien: number } | null>(null);
  const [loi, setLoi] = useState<string | null>(null);
  const [tab, setTab] = useState<ChiDinh["nhom"]>("can_dieu_phoi");
  const [xem, setXem] = useState<string | null>(null);
  // SỰ KIỆN THAY NHỊP HỎI (27/09/2026): nghe tin bảng đổi qua dòng SSE chung
  // (`useNgheBang`) → nạp lại NGAY; nhịp hỏi giãn còn 60 giây làm lưới an toàn.
  const [lanNghe, setLanNghe] = useState(0);
  useNgheBang(["service_order", "queue_entry", "payment", "visit"], () =>
    setLanNghe((n) => n + 1),
  );

  useEffect(() => {
    let huy = false;
    const nap = () =>
      void docBang<{ chi_dinh: ChiDinh[]; tong?: number; bi_cat?: boolean }>(
        "chi-dinh-hom-nay",
      ).then((kq) => {
        if (huy) return;
        if (kq.ok) {
          setDs(kq.data.chi_dinh);
          setBiCat(
            kq.data.bi_cat
              ? { tong: kq.data.tong ?? 0, hien: kq.data.chi_dinh.length }
              : null,
          );
          setLoi(null);
        } else setLoi(kq.loi);
      });
    nap();
    const t = setInterval(nap, 60000);
    return () => {
      huy = true;
      clearInterval(t);
    };
  }, [lanNghe]);

  const trongTab = (ds ?? []).filter((c) => c.nhom === tab);

  return (
    <section aria-label="Chỉ định hôm nay" className="rounded-card border border-line bg-surface p-3 shadow-card">
      <h2 className="text-sm font-semibold text-ink">Chỉ định hôm nay</h2>
      {biCat ? (
        <p role="status" className="mt-1 text-label text-warning">
          Bảng đang hiện {biCat.hien}/{biCat.tong} chỉ định của hôm nay. Lọc theo
          phòng hoặc xử lý bớt để thấy phần còn lại.
        </p>
      ) : null}
      <div role="tablist" aria-label="Nhóm chỉ định" className="mt-2 flex flex-wrap gap-1">
        {NHOM.map((n) => {
          const so = (ds ?? []).filter((c) => c.nhom === n.ma).length;
          const dang = tab === n.ma;
          return (
            <button
              key={n.ma}
              type="button"
              role="tab"
              aria-selected={dang}
              onClick={() => setTab(n.ma)}
              className={`min-h-9 rounded-control px-3 text-xs font-medium ${
                dang ? "bg-brand-600 text-white" : "bg-surface-muted text-ink-soft hover:bg-surface-sunken"
              }`}
            >
              {n.nhan} ({so})
            </button>
          );
        })}
      </div>
      {loi ? (
        <p role="alert" className="mt-2 text-xs text-danger">
          {loi}
        </p>
      ) : ds === null ? (
        <p className="mt-2 text-xs text-ink-muted">Đang tải…</p>
      ) : trongTab.length === 0 ? (
        <p className="mt-2 text-xs text-ink-muted">Không có chỉ định nào ở nhóm này.</p>
      ) : (
        <ul className="mt-2 grid gap-1">
          {trongTab.map((c) => (
            <li key={c.id}>
              <button
                type="button"
                onClick={() => setXem(c.visit_id)}
                className="w-full rounded-control bg-surface-muted px-3 py-2 text-left hover:bg-surface-sunken"
              >
                <span className="block text-sm font-medium text-ink">
                  {c.ten}
                  <span className="font-normal text-ink-muted"> · {c.dich_vu}</span>
                </span>
                <span className="block text-xs text-ink-soft">
                  Chỉ định {gioVn(c.chi_dinh_luc)}
                  {c.phong ? ` · ${c.phong}` : " · chưa có phòng"}
                  {c.xep_phong_luc ? ` (xếp ${gioVn(c.xep_phong_luc)})` : ""}
                  {c.bat_dau_luc ? ` · bắt đầu ${gioVn(c.bat_dau_luc)}` : ""}
                  {c.xong_luc
                    ? ` · ${c.trang_thai === "not_performed" ? "không làm được" : "xong"} ${gioVn(c.xong_luc)}`
                    : ""}
                  {c.nguoi_lam ? ` — ${c.nguoi_lam}` : ""}
                  {c.can === "VALID_RESULT"
                    ? c.ket_qua_luc
                      ? ` · có kết quả ${gioVn(c.ket_qua_luc)}`
                      : " · chờ kết quả"
                    : ""}
                  {c.vong_doc ? ` · ${VONG[c.vong_doc] ?? c.vong_doc}` : ""}
                </span>
                {c.khong_co_phong && c.nhom === "can_dieu_phoi" ? (
                  <span className="block text-xs font-medium text-danger">
                    Chưa có phòng nào làm dịch vụ này — báo quản lý gán phòng ở Cấu trúc phòng khám.
                  </span>
                ) : null}
              </button>
            </li>
          ))}
        </ul>
      )}
      {xem ? <XemLuot visitId={xem} onDong={() => setXem(null)} /> : null}
    </section>
  );
}
