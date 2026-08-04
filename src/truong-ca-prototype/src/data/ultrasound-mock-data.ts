// Mock data for Ultrasound Department ("Siêu Âm") — Matching Images 1 to 5

export interface UltrasoundQueuePatient {
  id: string;
  stt: number;
  code: string;
  patientName: string;
  patientCode: string;
  birthYear: number;
  gender: 'Nữ' | 'Nam';
  age: number;
  serviceName: string;
  appointmentTime: string;
  waitTimeStr: string;
  priority: 'Thường' | 'Ưu tiên';
  status: 'ready' | 'checked_in' | 'overdue' | 'wait_checkin' | 'wait_room' | 'wait_reception';
  statusLabel: string;
  statusBg: string;
  statusColor: string;
  indication: string;
  indicationDoctor: string;
  indicationTime: string;
  notes: string;
  readiness: {
    checkedIn: boolean;
    identityVerified: boolean;
    indicationValid: boolean;
    allowedPerform: boolean;
  };
}

export const ULTRASOUND_MASTER_QUEUE: UltrasoundQueuePatient[] = [
  {
    id: 'us-001',
    stt: 1,
    code: 'US250514-001',
    patientName: 'Lê Minh Châu',
    patientCode: 'BN250514-001',
    birthYear: 1990,
    gender: 'Nữ',
    age: 35,
    serviceName: 'Siêu âm ổ bụng tổng quát',
    appointmentTime: '10:05',
    waitTimeStr: '15 phút',
    priority: 'Thường',
    status: 'ready',
    statusLabel: 'Sẵn sàng',
    statusBg: '#dcfce7',
    statusColor: '#15803d',
    indication: 'Đánh giá đau bụng hạ vị',
    indicationDoctor: 'BS. Trần Văn Dũng',
    indicationTime: '14/05/2026 09:45',
    notes: 'Nhịn ăn 6 giờ',
    readiness: { checkedIn: true, identityVerified: true, indicationValid: true, allowedPerform: true },
  },
  {
    id: 'us-002',
    stt: 2,
    code: 'US250514-002',
    patientName: 'Trần Quang Minh',
    patientCode: 'BN250514-002',
    birthYear: 1988,
    gender: 'Nam',
    age: 36,
    serviceName: 'Siêu âm tim',
    appointmentTime: '10:40',
    waitTimeStr: 'Chưa đến hẹn',
    priority: 'Thường',
    status: 'checked_in',
    statusLabel: 'Đã check-in',
    statusBg: '#dbeafe',
    statusColor: '#1d4ed8',
    indication: 'Đánh giá nhịp tim nhanh',
    indicationDoctor: 'BS. Trần Văn Dũng',
    indicationTime: '14/05/2026 09:50',
    notes: 'Không có',
    readiness: { checkedIn: true, identityVerified: true, indicationValid: true, allowedPerform: false },
  },
  {
    id: 'us-003',
    stt: 3,
    code: 'US250514-003',
    patientName: 'Vũ Hoàng Nam',
    patientCode: 'BN250514-003',
    birthYear: 1992,
    gender: 'Nam',
    age: 34,
    serviceName: 'Siêu âm gan mật',
    appointmentTime: '09:10',
    waitTimeStr: '1 giờ 10 phút',
    priority: 'Ưu tiên',
    status: 'overdue',
    statusLabel: 'Quá SLA',
    statusBg: '#fee2e2',
    statusColor: '#b91c1c',
    indication: 'Theo dõi men gan cao',
    indicationDoctor: 'BS. Vũ Ngọc Lan',
    indicationTime: '14/05/2026 09:00',
    notes: 'Ưu tiên thực hiện trước',
    readiness: { checkedIn: true, identityVerified: true, indicationValid: true, allowedPerform: true },
  },
  {
    id: 'us-004',
    stt: 4,
    code: 'US250514-004',
    patientName: 'Đặng Thị Hồng',
    patientCode: 'BN250514-004',
    birthYear: 1996,
    gender: 'Nữ',
    age: 30,
    serviceName: 'Siêu âm tuyến giáp',
    appointmentTime: '11:10',
    waitTimeStr: 'Chưa đến hẹn',
    priority: 'Thường',
    status: 'wait_checkin',
    statusLabel: 'Chờ check-in',
    statusBg: '#ffedd5',
    statusColor: '#c2410c',
    indication: 'Khám nhân tuyến giáp',
    indicationDoctor: 'BS. Trần Văn Dũng',
    indicationTime: '14/05/2026 09:55',
    notes: 'Không có',
    readiness: { checkedIn: false, identityVerified: false, indicationValid: true, allowedPerform: false },
  },
  {
    id: 'us-005',
    stt: 5,
    code: 'US250514-005',
    patientName: 'Phạm Quốc Bảo',
    patientCode: 'BN250514-005',
    birthYear: 1985,
    gender: 'Nam',
    age: 41,
    serviceName: 'Siêu âm cơ xương khớp',
    appointmentTime: '10:15',
    waitTimeStr: '5 phút',
    priority: 'Thường',
    status: 'wait_room',
    statusLabel: 'Chờ phòng',
    statusBg: '#fef9c3',
    statusColor: '#a16207',
    indication: 'Đau khớp gối trái',
    indicationDoctor: 'BS. Trần Văn Dũng',
    indicationTime: '14/05/2026 10:00',
    notes: 'Không có',
    readiness: { checkedIn: true, identityVerified: true, indicationValid: true, allowedPerform: true },
  },
  {
    id: 'us-006',
    stt: 6,
    code: 'US250514-006',
    patientName: 'Nguyễn Thu Hà',
    patientCode: 'BN250514-006',
    birthYear: 1993,
    gender: 'Nữ',
    age: 33,
    serviceName: 'Siêu âm phụ khoa đường bụng',
    appointmentTime: '10:35',
    waitTimeStr: 'Chưa đến hẹn',
    priority: 'Thường',
    status: 'wait_reception',
    statusLabel: 'Chờ tiếp nhận',
    statusBg: '#f3f4f6',
    statusColor: '#4b5563',
    indication: 'Tầm soát phụ khoa',
    indicationDoctor: 'BS. Vũ Ngọc Lan',
    indicationTime: '14/05/2026 10:05',
    notes: 'Không có',
    readiness: { checkedIn: false, identityVerified: false, indicationValid: true, allowedPerform: false },
  },
];

// --- ROOM DISPATCH DATA (IMAGES 3 & 5) ---
export interface RoomDispatchInfo {
  roomId: 'SA1' | 'SA2' | 'SA3';
  roomName: string;
  status: 'active' | 'maintenance';
  statusLabel: string;
  currentPatient?: {
    code: string;
    patientName: string;
    patientCode: string;
    age: number;
    gender: string;
    serviceName: string;
    startTime: string;
    estEndTime: string;
    status: string;
  };
  waitingList: {
    stt: number;
    code: string;
    patientName: string;
    serviceName: string;
    waitTime: string;
    badgeLabel?: string;
    badgeBg?: string;
    badgeColor?: string;
    fromRoom?: string;
  }[];
}

export const ROOM_DISPATCH_DATA: Record<'SA1' | 'SA2' | 'SA3', RoomDispatchInfo> = {
  SA1: {
    roomId: 'SA1',
    roomName: 'Phòng SA1',
    status: 'active',
    statusLabel: 'Đang hoạt động',
    currentPatient: {
      code: 'US250514-021',
      patientName: 'Nguyễn Thị Mai',
      patientCode: 'BN250514-021',
      age: 32,
      gender: 'Nữ',
      serviceName: 'Siêu âm thai đầu dò',
      startTime: '10:05',
      estEndTime: '10:25',
      status: 'Đang thực hiện',
    },
    waitingList: [
      { stt: 1, code: 'US250514-001', patientName: 'Lê Minh Châu', serviceName: 'Siêu âm ổ bụng tổng quát', waitTime: 'Đã chờ 15 phút', badgeLabel: 'Chờ phòng', badgeBg: '#ffedd5', badgeColor: '#c2410c' },
      { stt: 2, code: 'US250514-002', patientName: 'Trần Quang Minh', serviceName: 'Siêu âm tim', waitTime: 'Hẹn 10:40', badgeLabel: 'Sắp đến lượt', badgeBg: '#fef9c3', badgeColor: '#a16207' },
      { stt: 3, code: 'US250514-003', patientName: 'Vũ Hoàng Nam', serviceName: 'Siêu âm gan mật', waitTime: 'Quá SLA 40 phút', badgeLabel: 'Ưu tiên', badgeBg: '#f3e8ff', badgeColor: '#7e22ce' },
    ],
  },
  SA2: {
    roomId: 'SA2',
    roomName: 'Phòng SA2',
    status: 'maintenance',
    statusLabel: 'Tạm dừng bảo trì',
    waitingList: [
      { stt: 1, code: 'US250514-006', patientName: 'Nguyễn Thu Hà', serviceName: 'Siêu âm phụ khoa đường bụng', waitTime: 'Chờ chuyển phòng', badgeLabel: 'Chờ chọn phòng', badgeBg: '#ffedd5', badgeColor: '#c2410c' },
      { stt: 2, code: 'US250514-007', patientName: 'Phạm Ngọc Anh', serviceName: 'Siêu âm tuyến giáp', waitTime: 'Chờ chuyển phòng', badgeLabel: 'Chờ chọn phòng', badgeBg: '#ffedd5', badgeColor: '#c2410c' },
      { stt: 3, code: 'US250514-008', patientName: 'Đỗ Thu Trang', serviceName: 'Siêu âm thai dưới 12 tuần', waitTime: 'Chờ chuyển phòng', badgeLabel: 'Chờ chọn phòng', badgeBg: '#ffedd5', badgeColor: '#c2410c' },
      { stt: 4, code: 'US250514-009', patientName: 'Trần Khánh Lý', serviceName: 'Siêu âm vú hai bên', waitTime: 'Chờ chuyển phòng', badgeLabel: 'Chờ chọn phòng', badgeBg: '#ffedd5', badgeColor: '#c2410c' },
    ],
  },
  SA3: {
    roomId: 'SA3',
    roomName: 'Phòng SA3',
    status: 'active',
    statusLabel: 'Đang hoạt động',
    currentPatient: {
      code: 'US250514-015',
      patientName: 'Phạm Thị Lan',
      patientCode: 'BN250514-015',
      age: 37,
      gender: 'Nữ',
      serviceName: 'Siêu âm ổ bụng tổng quát',
      startTime: '09:55',
      estEndTime: '10:25',
      status: 'Đang thực hiện',
    },
    waitingList: [
      { stt: 1, code: 'US250514-006', patientName: 'Nguyễn Thu Hà', serviceName: 'Siêu âm phụ khoa đường bụng', waitTime: 'Đã chờ 25 phút', badgeLabel: 'Chờ phòng', badgeBg: '#ffedd5', badgeColor: '#c2410c', fromRoom: 'Từ SA2' },
      { stt: 2, code: 'US250514-007', patientName: 'Phạm Ngọc Anh', serviceName: 'Siêu âm tuyến giáp', waitTime: 'Đã chờ 20 phút', badgeLabel: 'Chờ phòng', badgeBg: '#ffedd5', badgeColor: '#c2410c', fromRoom: 'Từ SA2' },
      { stt: 3, code: 'US250514-008', patientName: 'Đỗ Thu Trang', serviceName: 'Siêu âm thai dưới 12 tuần', waitTime: 'Hẹn 11:05', badgeLabel: 'Chờ phòng', badgeBg: '#ffedd5', badgeColor: '#c2410c', fromRoom: 'Từ SA2' },
    ],
  },
};

// --- ULTRASOUND RESULTS DRAFTS DATA (IMAGE 2) ---
export interface UltrasoundResultDraft {
  id: string;
  code: string;
  patientName: string;
  patientCode: string;
  birthYear: number;
  gender: 'Nữ' | 'Nam';
  age: number;
  serviceName: string;
  room: string;
  finishTime: string;
  status: 'wait_secretary' | 'draft' | 'wait_input' | 'wait_doctor';
  statusLabel: string;
  statusBg: string;
  statusColor: string;
  templateName: string;
  images: { id: string; name: string; url: string }[];
  imageDescription: string;
  preliminaryConclusion: string;
  recommendations: string;
  indicationDoctor: string;
  doctorPerformer: string;
  lastUpdated: string;
}

export const ULTRASOUND_RESULT_DRAFTS: UltrasoundResultDraft[] = [
  {
    id: 'res-021',
    code: 'US250514-021',
    patientName: 'Nguyễn Thị Mai',
    patientCode: 'BN250514-021',
    birthYear: 1994,
    gender: 'Nữ',
    age: 32,
    serviceName: 'Siêu âm thai đầu dò',
    room: 'SA1',
    finishTime: 'Hoàn tất 10:25',
    status: 'wait_secretary',
    statusLabel: 'Chờ thư ký hoàn thiện',
    statusBg: '#dbeafe',
    statusColor: '#1d4ed8',
    templateName: 'Siêu âm thai đầu dò',
    images: [
      { id: 'img1', name: 'Ảnh 01', url: 'https://images.unsplash.com/photo-1579684385127-1ef15d508118?auto=format&fit=crop&w=300&q=80' },
      { id: 'img2', name: 'Ảnh 02', url: 'https://images.unsplash.com/photo-1584515979956-d9f6e5d09982?auto=format&fit=crop&w=300&q=80' },
      { id: 'img3', name: 'Ảnh 03', url: 'https://images.unsplash.com/photo-1576091160399-112ba8d25d1d?auto=format&fit=crop&w=300&q=80' },
    ],
    imageDescription: 'Hình ảnh được đồng bộ từ máy SA1. Thư ký đang hoàn thiện mô tả theo mẫu và ghi nhận của bác sĩ thực hiện.',
    preliminaryConclusion: 'Chờ bác sĩ rà soát và nhập kết luận',
    recommendations: 'Chờ bác sĩ bổ sung nếu cần',
    indicationDoctor: 'BS. Trần Văn Dũng',
    doctorPerformer: 'BS. Lê Hoàng Nam',
    lastUpdated: 'Nguyễn Phương Anh · 10:18',
  },
  {
    id: 'res-015',
    code: 'US250514-015',
    patientName: 'Phạm Thị Lan',
    patientCode: 'BN250514-015',
    birthYear: 1989,
    gender: 'Nữ',
    age: 37,
    serviceName: 'Siêu âm ổ bụng tổng quát',
    room: 'SA3',
    finishTime: 'Hoàn tất 10:25',
    status: 'draft',
    statusLabel: 'Bản nháp',
    statusBg: '#dcfce7',
    statusColor: '#15803d',
    templateName: 'Siêu âm ổ bụng tổng quát',
    images: [
      { id: 'img1', name: 'Ảnh 01', url: 'https://images.unsplash.com/photo-1579684385127-1ef15d508118?auto=format&fit=crop&w=300&q=80' },
    ],
    imageDescription: 'Nhu mô gan đều. Túi mật không sỏi. Thận 2 bên kích thước bình thường.',
    preliminaryConclusion: 'Chưa phát hiện bất thường trên siêu âm ổ bụng.',
    recommendations: 'Theo dõi định kỳ 6 tháng.',
    indicationDoctor: 'BS. Vũ Ngọc Lan',
    doctorPerformer: 'BS. Lê Hoàng Nam',
    lastUpdated: 'Nguyễn Phương Anh · 10:12',
  },
  {
    id: 'res-001',
    code: 'US250514-001',
    patientName: 'Lê Minh Châu',
    patientCode: 'BN250514-001',
    birthYear: 1991,
    gender: 'Nữ',
    age: 35,
    serviceName: 'Siêu âm ổ bụng tổng quát',
    room: 'SA1',
    finishTime: 'Hoàn tất 10:42',
    status: 'wait_input',
    statusLabel: 'Chờ nhập kết quả',
    statusBg: '#ffedd5',
    statusColor: '#c2410c',
    templateName: 'Siêu âm ổ bụng tổng quát',
    images: [],
    imageDescription: '',
    preliminaryConclusion: '',
    recommendations: '',
    indicationDoctor: 'BS. Trần Văn Dũng',
    doctorPerformer: 'BS. Lê Hoàng Nam',
    lastUpdated: '10:00',
  },
  {
    id: 'res-006',
    code: 'US250514-006',
    patientName: 'Nguyễn Thu Hà',
    patientCode: 'BN250514-006',
    birthYear: 1990,
    gender: 'Nữ',
    age: 36,
    serviceName: 'Siêu âm phụ khoa đường bụng',
    room: 'SA3',
    finishTime: 'Gửi lúc 10:12',
    status: 'wait_doctor',
    statusLabel: 'Chờ bác sĩ ký',
    statusBg: '#fef9c3',
    statusColor: '#a16207',
    templateName: 'Siêu âm phụ khoa đường bụng',
    images: [
      { id: 'img1', name: 'Ảnh 01', url: 'https://images.unsplash.com/photo-1579684385127-1ef15d508118?auto=format&fit=crop&w=300&q=80' },
    ],
    imageDescription: 'Tử cung tư thế trung gian, kích thước bình thường. Nội mạc 7mm. Hai buồng trứng không u.',
    preliminaryConclusion: 'Hình ảnh siêu âm phụ khoa bình thường.',
    recommendations: 'Không',
    indicationDoctor: 'BS. Vũ Ngọc Lan',
    doctorPerformer: 'BS. Lê Hoàng Nam',
    lastUpdated: 'BS. Lê Hoàng Nam · 10:15',
  },
];

// --- ULTRASOUND SIGNED REPORTS DATA (IMAGE 1) ---
export interface SignedReportItem {
  id: string;
  code: string;
  serviceName: string;
  dateStr: string;
  timeStr: string;
  doctorName: string;
  signedStatus: string;
  publishStatus: string;
  conclusion: string;
  imageDescription: string;
  imageUrl: string;
  timeline: { time: string; action: string }[];
}

export interface PatientSignedGroup {
  id: string;
  patientName: string;
  patientCode: string;
  birthYear: number;
  gender: 'Nữ' | 'Nam';
  age: number;
  reportCount: number;
  reports: SignedReportItem[];
}

export const ULTRASOUND_SIGNED_PATIENTS: PatientSignedGroup[] = [
  {
    id: 'p-021',
    patientName: 'Nguyễn Thị Mai',
    patientCode: 'BN250514-021',
    birthYear: 1994,
    gender: 'Nữ',
    age: 32,
    reportCount: 3,
    reports: [
      {
        id: 'r-021-1',
        code: 'US250514-021',
        serviceName: 'Siêu âm thai đầu dò',
        dateStr: '14/05/2026',
        timeStr: '10:18',
        doctorName: 'BS. Trần Văn Dũng',
        signedStatus: 'Đã ký',
        publishStatus: 'Đã phát hành',
        conclusion: 'Thai trong tử cung, hình ảnh phù hợp tuổi thai. Tim thai 165 lần/phút.',
        imageDescription: 'Thai trong tử cung, hình ảnh rõ nét. CRL 62 mm, tương ứng 12 tuần 4 ngày. Tim thai đều, FHR 165 lần/phút. Không thấy bất thường cấu trúc.',
        imageUrl: 'https://images.unsplash.com/photo-1579684385127-1ef15d508118?auto=format&fit=crop&w=400&q=80',
        timeline: [
          { time: '10:18', action: 'Bác sĩ ký báo cáo' },
          { time: '10:20', action: 'Phát hành cho bệnh nhân' },
          { time: '10:21', action: 'Đã gửi qua ứng dụng' },
        ],
      },
      {
        id: 'r-021-2',
        code: 'US250402-044',
        serviceName: 'Siêu âm thai quý I',
        dateStr: '02/04/2026',
        timeStr: '09:42',
        doctorName: 'BS. Trần Văn Dũng',
        signedStatus: 'Đã ký',
        publishStatus: 'Đã gửi bệnh nhân',
        conclusion: 'Thai sống trong tử cung, hình ảnh phù hợp tuổi thai.',
        imageDescription: 'Túi thai kích thước 22mm, có phôi thai và tim thai (+).',
        imageUrl: 'https://images.unsplash.com/photo-1584515979956-d9f6e5d09982?auto=format&fit=crop&w=400&q=80',
        timeline: [
          { time: '09:42', action: 'Bác sĩ ký báo cáo' },
          { time: '09:45', action: 'Đã gửi qua ứng dụng' },
        ],
      },
      {
        id: 'r-021-3',
        code: 'US250215-018',
        serviceName: 'Siêu âm phụ khoa đường bụng',
        dateStr: '15/02/2026',
        timeStr: '14:05',
        doctorName: 'BS. Nguyễn Thanh Hà',
        signedStatus: 'Đã ký',
        publishStatus: 'Đã gửi bệnh nhân',
        conclusion: 'Tử cung và hai phần phụ hình ảnh trong giới hạn bình thường.',
        imageDescription: 'Nội mạc tử cung 6mm, hai buồng trứng kích thước bình thường.',
        imageUrl: 'https://images.unsplash.com/photo-1576091160399-112ba8d25d1d?auto=format&fit=crop&w=400&q=80',
        timeline: [
          { time: '14:05', action: 'Bác sĩ ký báo cáo' },
        ],
      },
    ],
  },
  {
    id: 'p-015',
    patientName: 'Phạm Thị Lan',
    patientCode: 'BN250514-015',
    birthYear: 1989,
    gender: 'Nữ',
    age: 37,
    reportCount: 2,
    reports: [
      {
        id: 'r-015-1',
        code: 'US250514-015',
        serviceName: 'Siêu âm ổ bụng tổng quát',
        dateStr: '14/05/2026',
        timeStr: '09:56',
        doctorName: 'BS. Lê Hoàng Nam',
        signedStatus: 'Đã ký',
        publishStatus: 'Đã phát hành',
        conclusion: 'Chưa phát hiện bất thường trên siêu âm ổ bụng.',
        imageDescription: 'Gan, mật, thận 2 bên, lách bình thường.',
        imageUrl: 'https://images.unsplash.com/photo-1579684385127-1ef15d508118?auto=format&fit=crop&w=400&q=80',
        timeline: [
          { time: '09:56', action: 'Bác sĩ ký báo cáo' },
        ],
      },
    ],
  },
  {
    id: 'p-001',
    patientName: 'Lê Minh Châu',
    patientCode: 'BN250514-001',
    birthYear: 1991,
    gender: 'Nữ',
    age: 35,
    reportCount: 4,
    reports: [],
  },
];
