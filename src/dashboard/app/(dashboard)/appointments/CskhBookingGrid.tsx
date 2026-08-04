"use client";

import { useState } from "react";
import {
  Calendar,
  Plus,
  History,
  Phone,
  Mail,
  MapPin,
  ChevronDown,
  Info,
  CheckCircle2,
  X,
  Pencil,
} from "lucide-react";
import { slotRange } from "@/lib/datetime";

interface Doctor {
  id: string;
  name: string;
  specialty: string;
  avatar?: string;
}

const DOCTORS: Doctor[] = [
  { id: "doc1", name: "BS. Trần Minh Đức", specialty: "Dịch vụ khám Sản" },
  { id: "doc2", name: "BS. Nguyễn Thu Hà", specialty: "Dịch vụ khám Nội tiết" },
  { id: "doc3", name: "BS. Phạm Quốc Huy", specialty: "Dịch vụ khám Giới tính" },
];

const TIME_SLOTS = [
  "08:00",
  "09:00",
  "10:00",
  "11:00",
  "12:00",
  "13:00", // Nghỉ trưa
  "14:00",
  "15:00",
  "16:00",
  "17:00",
];

export default function CskhBookingGrid() {
  const [selectedService, setSelectedService] = useState("Sản");
  const [selectedDoctorId, setSelectedDoctorId] = useState<string>("all");
  const [viewMode, setViewMode] = useState<"day" | "week">("day");

  const [selectedSlot, setSelectedSlot] = useState<{
    doctorId: string;
    doctorName: string;
    time: string;
  }>({
    doctorId: "doc2",
    doctorName: "BS. Nguyễn Thu Hà",
    time: "10:00",
  });

  const [note, setNote] = useState("");
  const [sendEmail, setSendEmail] = useState(true);
  const [confirmedMsg, setConfirmedMsg] = useState<string | null>(null);

  const getSlotStatus = (docId: string, time: string) => {
    if (time === "13:00") return "lunch";
    if (selectedSlot.doctorId === docId && selectedSlot.time === time) return "selected";
    if ((docId === "doc2" && time === "10:00") || (docId === "doc2" && time === "14:00")) {
      return "almost_full";
    }
    if (docId === "doc3" && (time === "08:00" || time === "09:00" || time === "15:00" || time === "17:00")) {
      return "full";
    }
    return "available";
  };

  const handleConfirmBooking = () => {
    const timeDisplay = slotRange(selectedSlot.time, 15);
    setConfirmedMsg(
      `Đã đặt lịch hẹn thành công cho khách hàng Nguyễn Văn An vào khung giờ ${timeDisplay} ngày 22/05/2026 với ${selectedSlot.doctorName}!`,
    );
  };

  return (
    <div className="space-y-4">
      {/* Top Header & Breadcrumb */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <div className="flex items-center gap-2 text-xs text-ink-muted">
            <span>Chăm sóc khách hàng</span>
            <span>&gt;</span>
            <span className="font-medium text-ink">Đặt lịch hẹn cho khách</span>
          </div>
          <h1 className="mt-1 text-lg font-bold text-ink">Đặt lịch hẹn cho khách</h1>
          <p className="text-xs text-ink-muted">Tìm lịch trống và đặt lịch hẹn mới cho khách hàng</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            className="inline-flex items-center gap-1.5 rounded-lg border border-brand-600 px-3 py-1.5 text-xs font-semibold text-brand-700 hover:bg-brand-50"
          >
            <Plus size={14} /> Tạo lịch hẹn nhanh
          </button>
          <button
            type="button"
            className="inline-flex items-center gap-1.5 rounded-lg border border-line bg-surface px-3 py-1.5 text-xs font-medium text-ink-soft hover:bg-surface-muted"
          >
            <History size={14} /> Lịch sử đặt hẹn
          </button>
        </div>
      </div>

      {confirmedMsg && (
        <div className="flex items-center justify-between rounded-card border border-success/30 bg-success/10 p-3 text-xs text-success">
          <div className="flex items-center gap-2">
            <CheckCircle2 size={16} />
            <span className="font-semibold">{confirmedMsg}</span>
          </div>
          <button onClick={() => setConfirmedMsg(null)} className="text-success hover:underline">
            <X size={14} />
          </button>
        </div>
      )}

      {/* Main 3-Column Grid Layout */}
      <div className="grid items-start gap-4 xl:grid-cols-[280px_1fr_320px]">
        {/* LEFT COLUMN: Customer Info & History */}
        <aside className="space-y-3">
          {/* Customer Profile Card */}
          <div className="rounded-card border border-line bg-surface p-3.5 shadow-card space-y-3">
            <div className="flex items-start justify-between">
              <span className="text-xs font-semibold text-ink-muted uppercase">Thông tin khách hàng</span>
              <button className="text-ink-muted hover:text-brand-600" title="Chỉnh sửa">
                <Pencil size={13} />
              </button>
            </div>
            <div className="flex items-center gap-3">
              <div className="grid size-11 place-items-center rounded-full bg-brand-100 text-sm font-bold text-brand-700">
                NT
              </div>
              <div>
                <h3 className="text-sm font-bold text-ink">Nguyễn Văn An</h3>
                <p className="text-xs text-ink-muted">Nam, 32 tuổi | 12/05/1992</p>
              </div>
            </div>
            <div className="space-y-1.5 pt-1 text-xs text-ink-soft border-t border-line">
              <div className="flex items-center gap-2">
                <Phone size={13} className="text-ink-muted shrink-0" />
                <span>0901 234 567</span>
              </div>
              <div className="flex items-center gap-2 truncate">
                <Mail size={13} className="text-ink-muted shrink-0" />
                <span className="truncate">vanan@gmail.com</span>
              </div>
              <div className="flex items-center gap-2">
                <MapPin size={13} className="text-ink-muted shrink-0" />
                <span>Quận 3, TP. Hồ Chí Minh</span>
              </div>
            </div>
          </div>

          {/* Related Medical Info Card */}
          <div className="rounded-card border border-line bg-surface p-3.5 shadow-card space-y-2 text-xs">
            <span className="block font-semibold text-ink-muted uppercase text-[11px]">Thông tin y tế liên quan</span>
            <div className="space-y-1">
              <div className="flex justify-between">
                <span className="text-ink-muted">Mã bệnh nhân:</span>
                <span className="font-mono font-medium text-ink">BN00001256</span>
              </div>
              <div className="flex justify-between">
                <span className="text-ink-muted">Lượt khám gần nhất:</span>
                <span className="text-ink">15/05/2024</span>
              </div>
              <div className="flex justify-between">
                <span className="text-ink-muted">Bác sĩ điều trị:</span>
                <span className="font-medium text-ink">BS. Trần Minh Đức</span>
              </div>
              <div className="flex justify-between">
                <span className="text-ink-muted">Chẩn đoán:</span>
                <span className="text-ink font-medium">Viêm xoang mạn</span>
              </div>
            </div>
            <button className="inline-flex items-center gap-1 text-[11px] font-medium text-brand-600 hover:underline pt-1">
              Xem thêm <ChevronDown size={12} />
            </button>
          </div>

          {/* Past Booking History */}
          <div className="rounded-card border border-line bg-surface p-3.5 shadow-card space-y-2.5">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-ink-muted uppercase">Lịch sử đặt hẹn (3)</span>
              <button className="text-[11px] font-medium text-brand-600 hover:underline">Xem tất cả</button>
            </div>
            <div className="space-y-2 text-xs">
              <div className="rounded-lg border border-line p-2 space-y-1 bg-surface-muted">
                <div className="flex items-center justify-between">
                  <span className="font-mono text-ink-muted text-[11px]">20/05/2024 • 09:00</span>
                  <span className="rounded-full bg-success/15 px-2 py-0.5 text-[10px] font-semibold text-success">
                    Đã đến
                  </span>
                </div>
                <p className="font-medium text-ink">BS. Trần Minh Đức • Khám dịch vụ Sản</p>
                <p className="text-[11px] text-ink-muted">Phòng 201</p>
              </div>

              <div className="rounded-lg border border-line p-2 space-y-1 bg-surface-muted">
                <div className="flex items-center justify-between">
                  <span className="font-mono text-ink-muted text-[11px]">15/05/2024 • 14:30</span>
                  <span className="rounded-full bg-amber-500/15 px-2 py-0.5 text-[10px] font-semibold text-amber-700">
                    Đã hủy
                  </span>
                </div>
                <p className="font-medium text-ink">BS. Trần Minh Đức • Khám dịch vụ Sản</p>
                <p className="text-[11px] text-ink-muted">Phòng 201</p>
              </div>

              <div className="rounded-lg border border-line p-2 space-y-1 bg-surface-muted">
                <div className="flex items-center justify-between">
                  <span className="font-mono text-ink-muted text-[11px]">10/05/2024 • 10:00</span>
                  <span className="rounded-full bg-success/15 px-2 py-0.5 text-[10px] font-semibold text-success">
                    Đã đến
                  </span>
                </div>
                <p className="font-medium text-ink">BS. Nguyễn Thu Hà • Siêu âm</p>
                <p className="text-[11px] text-ink-muted">Phòng 302</p>
              </div>
            </div>
          </div>
        </aside>

        {/* MIDDLE COLUMN: Doctor Grid & Time Slots */}
        <main className="space-y-4 rounded-card border border-line bg-surface p-4 shadow-card">
          {/* Controls Bar */}
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line pb-3">
            <div className="flex flex-wrap items-center gap-2">
              <div>
                <label className="block text-[11px] font-medium text-ink-muted mb-0.5">Chọn dịch vụ khám</label>
                <select
                  value={selectedService}
                  onChange={(e) => setSelectedService(e.target.value)}
                  className="rounded-lg border border-line bg-surface px-3 py-1.5 text-xs text-ink outline-none focus:border-brand-600"
                >
                  <option value="Sản">Sản</option>
                  <option value="Phụ khoa">Phụ khoa</option>
                  <option value="Nội tiết">Nội tiết</option>
                  <option value="Siêu âm">Siêu âm</option>
                </select>
              </div>

              <div>
                <label className="block text-[11px] font-medium text-ink-muted mb-0.5">Chọn bác sĩ (tùy chọn)</label>
                <select
                  value={selectedDoctorId}
                  onChange={(e) => setSelectedDoctorId(e.target.value)}
                  className="rounded-lg border border-line bg-surface px-3 py-1.5 text-xs text-ink outline-none focus:border-brand-600"
                >
                  <option value="all">Tất cả bác sĩ</option>
                  {DOCTORS.map((d) => (
                    <option key={d.id} value={d.id}>
                      {d.name}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-[11px] font-medium text-ink-muted mb-0.5">Ngày</label>
                <div className="flex items-center gap-1 rounded-lg border border-line bg-surface px-3 py-1.5 text-xs text-ink">
                  <Calendar size={13} className="text-ink-muted" />
                  <span>Thứ Tư, 22/05/2026</span>
                </div>
              </div>
            </div>

            <div className="flex rounded-lg border border-line p-0.5 bg-surface-muted text-xs">
              <button
                type="button"
                onClick={() => setViewMode("day")}
                className={`rounded-md px-3 py-1 font-medium transition-all ${
                  viewMode === "day" ? "bg-brand-600 text-white shadow-xs" : "text-ink-soft hover:text-ink"
                }`}
              >
                Theo ngày
              </button>
              <button
                type="button"
                onClick={() => setViewMode("week")}
                className={`rounded-md px-3 py-1 font-medium transition-all ${
                  viewMode === "week" ? "bg-brand-600 text-white shadow-xs" : "text-ink-soft hover:text-ink"
                }`}
              >
                Theo tuần
              </button>
            </div>
          </div>

          {/* Doctor Headers */}
          <div className="grid grid-cols-3 gap-3 border-b border-line pb-2">
            {DOCTORS.map((doc) => (
              <div key={doc.id} className="flex items-center gap-2.5 p-2 rounded-lg bg-surface-muted">
                <div className="grid size-9 shrink-0 place-items-center rounded-full bg-brand-100 text-xs font-bold text-brand-700">
                  {doc.name.split(" ").pop()?.[0]}
                </div>
                <div className="min-w-0 flex-1">
                  <h4 className="text-xs font-bold text-ink truncate">{doc.name}</h4>
                  <p className="text-[11px] text-ink-muted truncate">{doc.specialty}</p>
                </div>
              </div>
            ))}
          </div>

          {/* Time Slot Rows */}
          <div className="space-y-2">
            {TIME_SLOTS.map((time) => {
              if (time === "13:00") {
                return (
                  <div key={time} className="my-2 rounded-lg bg-surface-sunken p-2 text-center text-xs font-medium text-ink-muted">
                    ☕ Nghỉ trưa
                  </div>
                );
              }
              const displayRange = slotRange(time, 15);
              return (
                <div key={time} className="grid grid-cols-3 gap-3 items-center">
                  {DOCTORS.map((doc) => {
                    const status = getSlotStatus(doc.id, time);
                    if (status === "selected") {
                      return (
                        <button
                          key={doc.id}
                          type="button"
                          className="flex items-center justify-center rounded-lg border-2 border-brand-600 bg-brand-600 py-2.5 text-xs font-bold text-white shadow-sm"
                        >
                          {displayRange}
                        </button>
                      );
                    }
                    if (status === "almost_full") {
                      return (
                        <button
                          key={doc.id}
                          type="button"
                          onClick={() =>
                            setSelectedSlot({ doctorId: doc.id, doctorName: doc.name, time })
                          }
                          className="flex items-center justify-center rounded-lg border border-amber-500 bg-amber-50 py-2.5 text-xs font-medium text-amber-700 hover:bg-amber-100"
                        >
                          {displayRange}
                        </button>
                      );
                    }
                    if (status === "full") {
                      return (
                        <button
                          key={doc.id}
                          disabled
                          type="button"
                          className="flex items-center justify-center rounded-lg border border-line bg-surface-sunken py-2.5 text-xs font-medium text-ink-faint cursor-not-allowed opacity-60"
                        >
                          {displayRange}
                        </button>
                      );
                    }
                    return (
                      <button
                        key={doc.id}
                        type="button"
                        onClick={() =>
                          setSelectedSlot({ doctorId: doc.id, doctorName: doc.name, time })
                        }
                        className="flex items-center justify-center rounded-lg border border-brand-300 bg-surface py-2.5 text-xs font-medium text-brand-700 hover:bg-brand-50"
                      >
                        {displayRange}
                      </button>
                    );
                  })}
                </div>
              );
            })}
          </div>

          {/* Legend Footer */}
          <div className="flex items-center justify-center gap-6 pt-3 border-t border-line text-xs">
            <span className="flex items-center gap-1.5 text-brand-700">
              <span className="size-3 rounded-xs border border-brand-500 bg-surface" /> Còn trống
            </span>
            <span className="flex items-center gap-1.5 text-amber-700">
              <span className="size-3 rounded-xs border border-amber-500 bg-amber-50" /> Sắp hết chỗ
            </span>
            <span className="flex items-center gap-1.5 text-ink-muted">
              <span className="size-3 rounded-xs border border-line bg-surface-sunken" /> Đã kín
            </span>
            <span className="flex items-center gap-1.5 text-brand-700 font-semibold">
              <span className="size-3 rounded-xs bg-brand-600" /> Đang chọn
            </span>
          </div>

          {/* Booking Guide */}
          <div className="rounded-lg border border-line bg-surface-muted p-3 text-xs text-ink-muted space-y-1">
            <span className="font-semibold text-ink flex items-center gap-1 text-[11px]">
              <Info size={13} className="text-brand-600" /> Hướng dẫn đặt lịch
            </span>
            <div className="flex flex-wrap items-center gap-3 text-[11px]">
              <span>1. Chọn dịch vụ khám</span>
              <span>➔</span>
              <span>2. Chọn bác sĩ &amp; thời gian</span>
              <span>➔</span>
              <span>3. Xác nhận thông tin</span>
              <span>➔</span>
              <span>4. Gửi nhắc lịch</span>
            </div>
          </div>
        </main>

        {/* RIGHT COLUMN: Booking Summary & Confirm */}
        <aside className="space-y-4 rounded-card border border-line bg-surface p-4 shadow-card">
          <h3 className="text-sm font-bold text-ink border-b border-line pb-2">Thông tin lịch hẹn</h3>

          <div className="space-y-2 text-xs">
            <div className="flex justify-between">
              <span className="text-ink-muted">Khách hàng:</span>
              <span className="font-bold text-ink">Nguyễn Văn An</span>
            </div>
            <div className="flex justify-between">
              <span className="text-ink-muted">Dịch vụ khám:</span>
              <span className="text-ink font-medium">{selectedService}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-ink-muted">Bác sĩ:</span>
              <span className="font-bold text-ink">{selectedSlot.doctorName}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-ink-muted">Thời gian:</span>
              <span className="font-bold text-brand-700">
                Thứ Tư, 22/05/2026 • {slotRange(selectedSlot.time, 15)}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-ink-muted">Phòng khám:</span>
              <span className="text-ink font-medium">Phòng 201</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-ink-muted">Loại lịch hẹn:</span>
              <span className="rounded-full bg-brand-50 px-2.5 py-0.5 text-[10px] font-bold text-brand-700">
                Khám bệnh
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-ink-muted">Lý do khám:</span>
              <span className="text-ink">Khám sản định kỳ</span>
            </div>
          </div>

          {/* Optional Note */}
          <div className="space-y-1 pt-2 border-t border-line">
            <label className="text-xs font-semibold text-ink">Ghi chú (tùy chọn)</label>
            <textarea
              rows={2}
              value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder="Nhập ghi chú cho lịch hẹn..."
              className="w-full rounded-lg border border-line p-2 text-xs text-ink outline-none focus:border-brand-600 focus:ring-1 focus:ring-brand-600/20"
            />
            <span className="block text-[10px] text-ink-muted text-right">0/200</span>
          </div>

          {/* Reminders Checkbox List */}
          <div className="space-y-2 pt-2 border-t border-line">
            <label className="text-xs font-semibold text-ink">Nhắc lịch cho khách</label>
            <div className="space-y-1.5 text-xs text-ink-soft">
              <label className="flex items-center gap-2 cursor-pointer text-ink-muted">
                <input
                  type="checkbox"
                  disabled
                  checked={false}
                  className="rounded border-line text-brand-600 focus:ring-brand-500 cursor-not-allowed"
                />
                <span>Gửi SMS nhắc lịch</span>
                <span className="rounded bg-brand-50 px-1.5 py-0.5 text-[10px] font-medium text-brand-700">Sắp ra mắt v2</span>
              </label>
              <label className="flex items-center gap-2 cursor-pointer text-ink-muted">
                <input
                  type="checkbox"
                  disabled
                  checked={false}
                  className="rounded border-line text-brand-600 focus:ring-brand-500 cursor-not-allowed"
                />
                <span>Gửi Zalo nhắc lịch</span>
                <span className="rounded bg-brand-50 px-1.5 py-0.5 text-[10px] font-medium text-brand-700">Sắp ra mắt v2</span>
              </label>
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={sendEmail}
                  onChange={(e) => setSendEmail(e.target.checked)}
                  className="rounded border-line text-brand-600 focus:ring-brand-500"
                />
                Gửi email nhắc lịch
              </label>
            </div>
          </div>

          {/* Notice Callout */}
          <div className="rounded-lg bg-brand-50 p-2.5 text-[11px] text-brand-800 flex items-start gap-2">
            <Info size={14} className="shrink-0 mt-0.5 text-brand-600" />
            <span>Hệ thống sẽ gửi nhắc lịch trước 24 giờ về cuộc hẹn phía trên.</span>
          </div>

          {/* Buttons */}
          <div className="space-y-2 pt-2">
            <button
              type="button"
              onClick={handleConfirmBooking}
              className="w-full rounded-lg bg-brand-600 py-2.5 text-xs font-bold text-white shadow-sm hover:bg-brand-700"
            >
              Xác nhận đặt lịch
            </button>
            <button
              type="button"
              className="w-full rounded-lg border border-line bg-surface py-2 text-xs font-medium text-ink-soft hover:bg-surface-muted"
            >
              Hủy
            </button>
          </div>
        </aside>
      </div>
    </div>
  );
}
