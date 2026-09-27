// ICON BIẾN HÌNH CỦA THANH BÊN (Tuyền 27/09/2026: "chọn kiểu A … nên đa dạng
// cho kiểu biến hình icon").
//
// Mỗi mục một cặp icon — `tinh` (đứng yên, cùng hình với icon lucide-react ở
// thanh dưới) và `re` (khi rê chuột / đang mở) — cùng một kiểu lò xo riêng, để
// mỗi mục "cử động" một cách: nhà mở cửa, hoá đơn thành tờ tiền, ống nghe thành
// ống tiêm… Dữ liệu từ gói `lucide` (bản dữ liệu, cùng phiên bản với
// lucide-react) chạy qua `morphicons`. Mục không có trong bảng (phòng theo vị
// trí hôm nay…) giữ icon tĩnh cũ. Đây là trình bày, không có luật nghiệp vụ.

import {
  Activity,
  BadgeCheck,
  Banknote,
  BarChart3,
  Building2,
  Calendar,
  CalendarCheck,
  CalendarRange,
  CheckCheck,
  ClipboardCheck,
  ClipboardList,
  Clock,
  Cog,
  Contact,
  DoorOpen,
  FileSpreadsheet,
  FileText,
  FlaskConical,
  FlaskRound,
  Gauge,
  HeartPulse,
  History,
  House,
  KeyRound,
  LayoutGrid,
  ListChecks,
  LockOpen,
  LogOut,
  MessageSquareText,
  MessagesSquare,
  MonitorPlay,
  PhoneCall,
  PhoneOutgoing,
  Pill,
  Receipt,
  ReceiptText,
  Route,
  Rows3,
  ScanLine,
  ScanSearch,
  Settings,
  ShieldCheck,
  Signpost,
  Stethoscope,
  Syringe,
  Tablets,
  Tag,
  Tags,
  TrendingUp,
  Tv,
  UserCheck,
  UserPlus,
  UserRound,
  Users,
  Waypoints,
  type IconNode,
} from "lucide";

export type LoXo = "smooth" | "snappy" | "bouncy";

export interface BienHinh {
  tinh: IconNode;
  re: IconNode;
  lo: LoXo;
}

const b = (tinh: IconNode, re: IconNode, lo: LoXo = "smooth"): BienHinh => ({ tinh, re, lo });

export const BIEN_HINH: Record<string, BienHinh> = {
  "/home": b(House, DoorOpen, "bouncy"),
  "/viec-can-xu-ly": b(ClipboardCheck, ListChecks, "snappy"),
  "/reception/queue": b(Users, UserCheck, "smooth"),
  "/thu-ngan/dich-vu": b(Receipt, Banknote, "bouncy"),
  "/thu-ngan/thuoc": b(ReceiptText, Pill, "snappy"),
  "/reception/checkout": b(CheckCheck, LogOut, "smooth"),
  "/do-sinh-hieu": b(Activity, HeartPulse, "bouncy"),
  "/tu-van": b(MessageSquareText, MessagesSquare, "smooth"),
  "/ban-kham": b(Stethoscope, Syringe, "snappy"),
  "/phong": b(ScanLine, ScanSearch, "smooth"),
  "/appointments": b(Calendar, CalendarCheck, "bouncy"),
  "/appointments/cho-xep-bac-si": b(UserPlus, UserCheck, "snappy"),
  "/customers": b(Contact, UserRound, "smooth"),
  "/nhac-tai-kham": b(PhoneCall, PhoneOutgoing, "bouncy"),
  "/patient-list": b(ClipboardList, FileText, "smooth"),
  "/patients/new": b(UserPlus, BadgeCheck, "bouncy"),
  "/truong-ca": b(Rows3, LayoutGrid, "snappy"),
  "/truong-ca/tv": b(Tv, MonitorPlay, "bouncy"),
  "/truong-ca/lich-su": b(History, Clock, "smooth"),
  "/hanh-trinh": b(Route, Waypoints, "smooth"),
  "/doi-tac": b(FlaskConical, FlaskRound, "bouncy"),
  "/cashier/thuoc": b(Pill, Tablets, "snappy"),
  "/cashier/dich-vu": b(Tag, Tags, "smooth"),
  "/pharmacy": b(Pill, Tablets, "bouncy"),
  "/pharmacy/inventory": b(ClipboardList, ListChecks, "smooth"),
  "/pharmacy/history": b(History, Clock, "snappy"),
  "/pharmacy/consult": b(MessageSquareText, MessagesSquare, "smooth"),
  "/schedule": b(Calendar, CalendarCheck, "snappy"),
  "/lich-do-ve": b(CalendarRange, CalendarCheck, "smooth"),
  "/reports": b(BarChart3, TrendingUp, "bouncy"),
  "/audit-log": b(ClipboardCheck, FileText, "smooth"),
  "/ops": b(Gauge, Activity, "snappy"),
  "/settings/booking-policy": b(Calendar, CalendarCheck, "smooth"),
  "/settings/clinic-config": b(Building2, DoorOpen, "bouncy"),
  "/settings/day-noi": b(Route, Signpost, "smooth"),
  "/settings/mau-ket-qua": b(FileSpreadsheet, FileText, "snappy"),
  "/nhan-su": b(Users, UserRound, "smooth"),
  "/settings/tai-khoan": b(KeyRound, LockOpen, "bouncy"),
  "/phan-quyen": b(KeyRound, ShieldCheck, "snappy"),
  "/settings": b(Settings, Cog, "bouncy"),
};
