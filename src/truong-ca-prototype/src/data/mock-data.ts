// Mock data for the Trưởng Ca dispatch dashboard prototype
// All data is hardcoded — no API calls.

export type StationId = 'reception' | 'vitals' | 'doctor' | 'sa1' | 'sa2' | 'sa3' | 'lab' | 'result_review' | 'pharmacy' | 'checkout';

export interface Station {
  id: StationId;
  name: string;
  shortName: string;
  color: string;
  bgColor: string;
  icon: string; // lucide icon name
  currentServing: number;
  waiting: number;
  capacity: { current: number; total: number };
  avgWaitMinutes: number;
  slaStatus: 'ok' | 'warning' | 'critical';
  staff: string;
}

export interface Patient {
  id: string;
  code: string;       // e.g. BN250514-021
  queueCode: string;  // e.g. C007, SA025
  name: string;
  age: number;
  gender: 'Nữ' | 'Nam';
  phone: string;
  specialty: string;
  currentStation: StationId;
  currentStationName: string;
  waitMinutes: number;
  priority: 'normal' | 'high' | 'urgent';
  priorityLabel: string;
  waitReason: string;
  assignedTo: string;
  nextStation: StationId | null;
  nextStationName: string;
  slaPercent: number; // 0-100, >100 = overdue
  route: RouteStep[];
  notes: DispatchNote[];
  checkedInAt: string;
}

export interface RouteStep {
  station: StationId;
  stationName: string;
  status: 'completed' | 'in_progress' | 'waiting' | 'skipped';
  startTime?: string;
  endTime?: string;
  staff?: string;
  room?: string;
}

export interface DispatchNote {
  time: string;
  actor: string;
  action: string;
  detail: string;
}

export interface Alert {
  id: string;
  type: 'wait_too_long' | 'missing_next_step' | 'unassigned_order' | 'dual_queue';
  severity: 'warning' | 'critical';
  message: string;
  patientName: string;
  patientCode: string;
  station: string;
  time: string;
  acknowledged: boolean;
}

export interface HistoryEntry {
  id: string;
  time: string;
  actor: string;
  action: string;
  patientName: string;
  patientCode: string;
  from: string;
  to: string;
  reason: string;
}

export type RouteTemplate = {
  id: string;
  name: string;
  steps: { station: StationId; stationName: string }[];
};

// --- STATIONS ---
export const STATIONS: Station[] = [
  {
    id: 'reception', name: 'Tiếp nhận', shortName: 'Tiếp nhận',
    color: '#0f8b8d', bgColor: '#eaf7f7', icon: 'ClipboardList',
    currentServing: 2, waiting: 6, capacity: { current: 2, total: 2 },
    avgWaitMinutes: 7, slaStatus: 'ok', staff: 'Lê Minh Châu',
  },
  {
    id: 'vitals', name: 'Sinh hiệu', shortName: 'Sinh hiệu',
    color: '#0369a1', bgColor: '#e0f2fe', icon: 'Activity',
    currentServing: 2, waiting: 8, capacity: { current: 2, total: 2 },
    avgWaitMinutes: 8, slaStatus: 'ok', staff: 'Trần Quang Minh',
  },
  {
    id: 'doctor', name: 'Khám bác sĩ', shortName: 'Khám BS',
    color: '#e74c3c', bgColor: '#fdecea', icon: 'Stethoscope',
    currentServing: 4, waiting: 12, capacity: { current: 4, total: 5 },
    avgWaitMinutes: 15, slaStatus: 'ok', staff: 'KB-01 đến KB-04',
  },
  {
    id: 'sa1', name: 'Siêu âm SA1', shortName: 'SA1',
    color: '#0f8b8d', bgColor: '#eaf7f7', icon: 'Monitor',
    currentServing: 1, waiting: 9, capacity: { current: 1, total: 2 },
    avgWaitMinutes: 16, slaStatus: 'warning', staff: 'SA-01, SA-03',
  },
  {
    id: 'sa2', name: 'Siêu âm SA2', shortName: 'SA2',
    color: '#8b5cf6', bgColor: '#f3f0ff', icon: 'Monitor',
    currentServing: 1, waiting: 10, capacity: { current: 1, total: 2 },
    avgWaitMinutes: 22, slaStatus: 'critical', staff: 'XN-01, XN-02',
  },
  {
    id: 'sa3', name: 'Siêu âm SA3', shortName: 'SA3',
    color: '#2563eb', bgColor: '#eff6ff', icon: 'Monitor',
    currentServing: 0, waiting: 3, capacity: { current: 1, total: 2 },
    avgWaitMinutes: 10, slaStatus: 'ok', staff: 'DKQ-01',
  },
  {
    id: 'lab', name: 'Xét nghiệm', shortName: 'Xét nghiệm',
    color: '#1e3a5f', bgColor: '#e8eef5', icon: 'FlaskConical',
    currentServing: 3, waiting: 7, capacity: { current: 2, total: 2 },
    avgWaitMinutes: 19, slaStatus: 'warning', staff: 'Phạm Ngọc Ánh',
  },
  {
    id: 'result_review', name: 'Đọc kết quả', shortName: 'Đọc KQ',
    color: '#6366f1', bgColor: '#eef2ff', icon: 'FileCheck',
    currentServing: 2, waiting: 11, capacity: { current: 1, total: 2 },
    avgWaitMinutes: 6, slaStatus: 'ok', staff: 'NT-01',
  },
  {
    id: 'pharmacy', name: 'Nhà thuốc', shortName: 'Nhà thuốc',
    color: '#d97706', bgColor: '#fef9ee', icon: 'Pill',
    currentServing: 1, waiting: 5, capacity: { current: 1, total: 2 },
    avgWaitMinutes: 6, slaStatus: 'ok', staff: 'CO-01',
  },
  {
    id: 'checkout', name: 'Check-out', shortName: 'Check-out',
    color: '#15803d', bgColor: '#dcfce7', icon: 'LogOut',
    currentServing: 1, waiting: 0, capacity: { current: 1, total: 2 },
    avgWaitMinutes: 3, slaStatus: 'ok', staff: 'Trần Văn Dũng',
  },
];

// --- PATIENTS ---
const names = [
  'Nguyễn Thị Mai', 'Phạm Thị Lan', 'Lê Minh Châu', 'Nguyễn Thu Hà',
  'Đỗ Thu Trang', 'Trần Thị Hương', 'Vũ Hoàng Nam', 'Bùi Ngọc Anh',
  'Lý Thanh Tâm', 'Hoàng Minh Đức', 'Ngô Phương Thảo', 'Phan Thu Huyền',
  'Đinh Văn Long', 'Cao Thị Bích', 'Dương Minh Tuấn', 'Lương Thị Hồng',
  'Tô Văn Khoa', 'Hà Ngọc Linh', 'Mai Anh Thư', 'Trịnh Xuân Bắc',
  'Nguyễn Hải Yến', 'Trần Minh Phúc', 'Lê Thị Thanh', 'Đặng Văn Hùng',
  'Phạm Ngọc Bảo', 'Vũ Thị Dung', 'Bùi Quang Huy', 'Ngô Thị Tuyết',
  'Hoàng Thị Kim', 'Phan Văn Thịnh', 'Đỗ Minh Tâm', 'Cao Ngọc Mai',
  'Lý Văn Đạt', 'Hà Thu Giang', 'Trương Minh Nhật', 'Dương Thị Thúy',
  'Tô Thị Vân', 'Mai Hồng Phúc',
];

const stationSequence: StationId[] = ['reception', 'vitals', 'doctor', 'sa1', 'lab', 'result_review', 'pharmacy', 'checkout'];

function makeRoute(currentIdx: number, variant: number): RouteStep[] {
  const routes: StationId[][] = [
    ['reception', 'vitals', 'doctor', 'sa1', 'lab', 'result_review', 'pharmacy', 'checkout'],
    ['reception', 'vitals', 'doctor', 'lab', 'sa2', 'result_review', 'pharmacy', 'checkout'],
    ['reception', 'vitals', 'doctor', 'sa2', 'result_review', 'lab', 'pharmacy', 'checkout'],
    ['reception', 'vitals', 'doctor', 'sa3', 'lab', 'result_review', 'pharmacy', 'checkout'],
  ];
  const route = routes[variant % routes.length];
  const stNames: Record<StationId, string> = {
    reception: 'Tiếp nhận', vitals: 'Sinh hiệu', doctor: 'Khám bác sĩ',
    sa1: 'Siêu âm SA1', sa2: 'Siêu âm SA2', sa3: 'Siêu âm SA3',
    lab: 'Xét nghiệm', result_review: 'Đọc kết quả',
    pharmacy: 'Nhà thuốc', checkout: 'Check-out',
  };
  const baseHour = 7;
  return route.map((st, i) => {
    let status: RouteStep['status'] = 'waiting';
    if (i < currentIdx) status = 'completed';
    else if (i === currentIdx) status = 'in_progress';

    const h = baseHour + Math.floor((i * 25) / 60);
    const m = (i * 25) % 60;
    return {
      station: st,
      stationName: stNames[st],
      status,
      startTime: i <= currentIdx ? `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}` : undefined,
      endTime: i < currentIdx ? `${String(h).padStart(2, '0')}:${String(m + 15 + Math.floor(Math.random() * 10)).padStart(2, '0')}` : undefined,
      staff: i <= currentIdx ? ['BS. Trần Văn Dũng', 'KTV Nguyễn Thu Hà', 'ĐD Phạm Thị Lan', 'BS. Vũ Hoàng Nam'][i % 4] : undefined,
      room: ['TN-01', 'SH-01', 'KB-02', 'SA-01', 'XN-02', 'DKQ-01', 'NT-01', 'CO-01'][i % 8],
    };
  });
}

const stationNames: Record<StationId, string> = {
  reception: 'Tiếp nhận', vitals: 'Sinh hiệu', doctor: 'Khám bác sĩ',
  sa1: 'Siêu âm SA1', sa2: 'Siêu âm SA2', sa3: 'Siêu âm SA3',
  lab: 'Xét nghiệm', result_review: 'Đọc kết quả',
  pharmacy: 'Nhà thuốc', checkout: 'Check-out',
};

const waitReasons = [
  'Chờ duyệt kết quả ngoại', 'Đợc kết XN', 'Chờ duyệt thanh toán',
  'Quay lại bác sĩ', 'Chờ chỉ định tiếp', 'Chờ kết quả siêu âm',
];

const prefixes: Record<string, string> = {
  doctor: 'C', sa1: 'SA', sa2: 'SA', sa3: 'SA', lab: 'X', pharmacy: 'T',
  checkout: 'T', reception: 'C', vitals: 'C', result_review: 'C',
};

const currentStations: StationId[] = ['doctor', 'sa1', 'sa2', 'sa3', 'lab', 'result_review', 'pharmacy', 'checkout', 'reception', 'vitals'];
const nextStations: (StationId | null)[] = ['sa1', 'lab', 'result_review', 'lab', 'result_review', 'pharmacy', 'checkout', null, 'vitals', 'doctor'];

export const PATIENTS: Patient[] = names.map((name, i) => {
  const stIdx = i % currentStations.length;
  const currentStation = currentStations[stIdx];
  const nextStation = nextStations[stIdx];
  const routeIdx = stIdx < 3 ? stIdx : Math.min(stIdx, 4);
  const variant = i % 4;
  const prefix = prefixes[currentStation] || 'C';
  const qNum = String(i + 1).padStart(3, '0');

  return {
    id: `p-${i}`,
    code: `BN250514-${String(i + 1).padStart(3, '0')}`,
    queueCode: `${prefix}${qNum}`,
    name,
    age: 20 + (i * 3) % 35,
    gender: i % 5 === 0 ? 'Nam' as const : 'Nữ' as const,
    phone: `090${String(1000000 + i * 12345).slice(0, 7)}`,
    specialty: ['Phụ khoa', 'Sản khoa', 'Siêu âm', 'Tổng quát'][i % 4],
    currentStation,
    currentStationName: stationNames[currentStation],
    waitMinutes: [12, 9, 18, 7, 23, 5, 8, 3, 4, 11][stIdx] + (i % 5) * 3,
    priority: i % 8 === 0 ? 'urgent' as const : i % 4 === 0 ? 'high' as const : 'normal' as const,
    priorityLabel: i % 8 === 0 ? 'Khẩn' : i % 4 === 0 ? 'Cao' : 'Bình thường',
    waitReason: waitReasons[i % waitReasons.length],
    assignedTo: ['BS. Trần Văn Dũng', 'KTV Phạm Thị Lan', 'BS. Trần Thu Hương', 'KTV Nguyễn Thu Hà'][i % 4],
    nextStation,
    nextStationName: nextStation ? stationNames[nextStation] : '',
    slaPercent: [40, 60, 85, 50, 110, 30, 45, 20, 25, 70][stIdx] + (i % 3) * 15,
    route: makeRoute(routeIdx, variant),
    notes: [
      { time: '10:02', actor: 'Trưởng ca Hoàng Nam', action: 'Đọc kết quả', detail: `DKQ-01 – Lê Minh Châu — Chờ duyệt kết quả ngoại` },
      { time: '09:45', actor: 'Hệ thống', action: `Hoàn tất Siêu âm tại SA-01`, detail: `KTV Nguyễn Thu Hà` },
    ],
    checkedInAt: `0${7 + Math.floor(i / 5)}:${String((i * 7) % 60).padStart(2, '0')}`,
  };
});

// --- ALERTS ---
export const ALERTS: Alert[] = [
  { id: 'a1', type: 'wait_too_long', severity: 'critical', message: 'Chờ khám bác sĩ quá 25 phút', patientName: 'Đỗ Thu Trang', patientCode: 'BN250514-005', station: 'Khám bác sĩ', time: '10:15', acknowledged: false },
  { id: 'a2', type: 'wait_too_long', severity: 'warning', message: 'Chờ siêu âm SA2 quá 20 phút', patientName: 'Lê Minh Châu', patientCode: 'BN250514-003', station: 'Siêu âm SA2', time: '10:12', acknowledged: false },
  { id: 'a3', type: 'missing_next_step', severity: 'critical', message: 'Hoàn tất khám BS nhưng chưa có bước tiếp', patientName: 'Nguyễn Thu Hà', patientCode: 'BN250514-004', station: 'Khám bác sĩ', time: '10:08', acknowledged: false },
  { id: 'a4', type: 'unassigned_order', severity: 'warning', message: 'Chỉ định XN máu chưa được nhận', patientName: 'Trần Thị Hương', patientCode: 'BN250514-006', station: 'Xét nghiệm', time: '10:05', acknowledged: false },
  { id: 'a5', type: 'dual_queue', severity: 'critical', message: 'BN xuất hiện ở cả SA1 và Xét nghiệm', patientName: 'Bùi Ngọc Anh', patientCode: 'BN250514-008', station: 'SA1 + XN', time: '10:01', acknowledged: false },
  { id: 'a6', type: 'wait_too_long', severity: 'warning', message: 'Chờ đọc kết quả quá 15 phút', patientName: 'Hoàng Minh Đức', patientCode: 'BN250514-010', station: 'Đọc kết quả', time: '09:58', acknowledged: true },
  { id: 'a7', type: 'wait_too_long', severity: 'critical', message: 'Chờ nhà thuốc quá 30 phút', patientName: 'Ngô Phương Thảo', patientCode: 'BN250514-011', station: 'Nhà thuốc', time: '09:55', acknowledged: false },
];

// --- HISTORY ---
export const HISTORY: HistoryEntry[] = [
  { id: 'h1', time: '10:15', actor: 'Nguyễn Hoàng Nam', action: 'Điều chuyển phòng', patientName: 'Phạm Thị Lan', patientCode: 'BN250514-002', from: 'SA1', to: 'SA2', reason: 'Cân bằng tải SA1 quá đông' },
  { id: 'h2', time: '10:02', actor: 'Nguyễn Hoàng Nam', action: 'Chọn tuyến điều phối', patientName: 'Nguyễn Thị Mai', patientCode: 'BN250514-001', from: 'Khám BS', to: 'Tuyến A (SA→XN→KQ)', reason: 'BN cần siêu âm trước' },
  { id: 'h3', time: '09:45', actor: 'Nguyễn Hoàng Nam', action: 'Đổi tuyến giữa chừng', patientName: 'Lê Minh Châu', patientCode: 'BN250514-003', from: 'Tuyến A', to: 'Tuyến B (XN→SA→KQ)', reason: 'SA1 quá tải, đổi XN trước' },
  { id: 'h4', time: '09:30', actor: 'Nguyễn Hoàng Nam', action: 'Ghi chú điều phối', patientName: 'Nguyễn Thu Hà', patientCode: 'BN250514-004', from: '-', to: '-', reason: 'BN yêu cầu nghỉ 15 phút' },
  { id: 'h5', time: '09:15', actor: 'Nguyễn Hoàng Nam', action: 'Điều chuyển phòng', patientName: 'Đỗ Thu Trang', patientCode: 'BN250514-005', from: 'SA2', to: 'SA3', reason: 'SA2 đang bảo trì thiết bị' },
  { id: 'h6', time: '09:00', actor: 'Nguyễn Hoàng Nam', action: 'Ưu tiên BN', patientName: 'Vũ Hoàng Nam', patientCode: 'BN250514-007', from: 'Hàng đợi XN', to: 'Ưu tiên 1', reason: 'BN có thai, cần XN gấp' },
  { id: 'h7', time: '08:50', actor: 'Hệ thống', action: 'Cảnh báo SLA', patientName: 'Trần Thị Hương', patientCode: 'BN250514-006', from: '-', to: '-', reason: 'Chờ khám BS >20 phút' },
  { id: 'h8', time: '08:35', actor: 'Nguyễn Hoàng Nam', action: 'Mở ca', patientName: '-', patientCode: '-', from: '-', to: '-', reason: 'Bắt đầu ca sáng 14/05' },
];

// --- ROUTE TEMPLATES ---
export const ROUTE_TEMPLATES: RouteTemplate[] = [
  {
    id: 'route-a',
    name: 'Tuyến A: Siêu âm → Lấy máu → Đọc KQ',
    steps: [
      { station: 'sa1', stationName: 'Siêu âm' },
      { station: 'lab', stationName: 'Lấy máu / Xét nghiệm' },
      { station: 'result_review', stationName: 'Đọc kết quả' },
      { station: 'pharmacy', stationName: 'Nhà thuốc' },
      { station: 'checkout', stationName: 'Check-out' },
    ],
  },
  {
    id: 'route-b',
    name: 'Tuyến B: Lấy máu → Siêu âm → Đọc KQ',
    steps: [
      { station: 'lab', stationName: 'Lấy máu / Xét nghiệm' },
      { station: 'sa1', stationName: 'Siêu âm' },
      { station: 'result_review', stationName: 'Đọc kết quả' },
      { station: 'pharmacy', stationName: 'Nhà thuốc' },
      { station: 'checkout', stationName: 'Check-out' },
    ],
  },
  {
    id: 'route-c',
    name: 'Tuyến C: Siêu âm → Đọc KQ → Lấy máu',
    steps: [
      { station: 'sa1', stationName: 'Siêu âm' },
      { station: 'result_review', stationName: 'Đọc kết quả' },
      { station: 'lab', stationName: 'Lấy máu / Xét nghiệm' },
      { station: 'pharmacy', stationName: 'Nhà thuốc' },
      { station: 'checkout', stationName: 'Check-out' },
    ],
  },
];

// --- TV QUEUE DATA ---
export interface TvQueueItem {
  queueCode: string;
  room?: string;
}

export interface TvStation {
  id: string;
  name: string;
  color: string;
  bgColor: string;
  icon: string;
  currentlyServing: TvQueueItem;
  nextUp: TvQueueItem;
  waiting: TvQueueItem[];
}

export const TV_STATIONS: TvStation[] = [
  {
    id: 'doctor', name: 'KHÁM BÁC SĨ', color: '#e74c3c', bgColor: '#fdecea', icon: 'Stethoscope',
    currentlyServing: { queueCode: 'C007', room: 'PHÒNG KHÁM 2' },
    nextUp: { queueCode: 'C008' },
    waiting: [
      { queueCode: 'C009' }, { queueCode: 'C010' }, { queueCode: 'C011' },
      { queueCode: 'C012' }, { queueCode: 'C013' }, { queueCode: 'C014' },
      { queueCode: 'C015' }, { queueCode: 'C016' }, { queueCode: 'C017' },
    ],
  },
  {
    id: 'sa1', name: 'SIÊU ÂM SA1', color: '#0f8b8d', bgColor: '#eaf7f7', icon: 'Monitor',
    currentlyServing: { queueCode: 'SA025' },
    nextUp: { queueCode: 'SA026' },
    waiting: [
      { queueCode: 'SA027' }, { queueCode: 'SA028' }, { queueCode: 'SA029' },
      { queueCode: 'SA030' }, { queueCode: 'SA031' }, { queueCode: 'SA032' },
      { queueCode: 'SA033' }, { queueCode: 'SA034' }, { queueCode: 'SA035' },
    ],
  },
  {
    id: 'sa2', name: 'SIÊU ÂM SA2', color: '#8b5cf6', bgColor: '#f3f0ff', icon: 'Monitor',
    currentlyServing: { queueCode: 'SA032' },
    nextUp: { queueCode: 'SA032' },
    waiting: [
      { queueCode: 'SA033' }, { queueCode: 'SA034' }, { queueCode: 'SA035' },
      { queueCode: 'SA036' }, { queueCode: 'SA037' }, { queueCode: 'SA038' },
      { queueCode: 'SA039' }, { queueCode: 'SA040' }, { queueCode: 'SA041' },
    ],
  },
  {
    id: 'sa3', name: 'SIÊU ÂM SA3', color: '#2563eb', bgColor: '#eff6ff', icon: 'Monitor',
    currentlyServing: { queueCode: 'SA018' },
    nextUp: { queueCode: 'SA019' },
    waiting: [
      { queueCode: 'SA020' }, { queueCode: 'SA021' }, { queueCode: 'SA022' },
      { queueCode: 'SA023' }, { queueCode: 'SA024' }, { queueCode: 'SA025' },
      { queueCode: 'SA026' }, { queueCode: 'SA027' }, { queueCode: 'SA028' },
    ],
  },
  {
    id: 'lab', name: 'XÉT NGHIỆM', color: '#1e3a5f', bgColor: '#e8eef5', icon: 'FlaskConical',
    currentlyServing: { queueCode: 'X012' },
    nextUp: { queueCode: 'X013' },
    waiting: [
      { queueCode: 'X014' }, { queueCode: 'X015' }, { queueCode: 'X016' },
      { queueCode: 'X017' }, { queueCode: 'X018' }, { queueCode: 'X019' },
      { queueCode: 'X020' }, { queueCode: 'X021' }, { queueCode: 'X022' },
    ],
  },
  {
    id: 'pharmacy', name: 'THUỐC &\nTHANH TOÁN', color: '#d97706', bgColor: '#fef9ee', icon: 'Pill',
    currentlyServing: { queueCode: 'T005' },
    nextUp: { queueCode: 'T006' },
    waiting: [
      { queueCode: 'T007' }, { queueCode: 'T008' }, { queueCode: 'T009' },
      { queueCode: 'T010' }, { queueCode: 'T011' }, { queueCode: 'T012' },
      { queueCode: 'T013' }, { queueCode: 'T014' }, { queueCode: 'T015' },
    ],
  },
];

// --- KPI SUMMARY ---
export const KPI = {
  totalInClinic: 146,
  waiting: 38,
  delayed: 7,
  overSla: 5,
  resourceAvailable: 18,
  resourceTotal: 22,
};
