// Mock data for Doctor Workspaces ("Bác Sĩ")

export type DoctorType = 'general' | 'obgyn' | 'ultrasound';

export interface DoctorProfile {
  id: DoctorType;
  name: string;
  title: string;
  avatarText: string;
  description: string;
}

export const DOCTOR_PROFILES: Record<DoctorType, DoctorProfile> = {
  general: {
    id: 'general',
    name: 'BS. Trần Văn Dũng',
    title: 'Bác sĩ Đa khoa / Khám tổng hợp',
    avatarText: 'TD',
    description: 'Khám tổng quát, chỉ định đa khoa, xem & duyệt kết quả, hoàn tất hồ sơ.',
  },
  obgyn: {
    id: 'obgyn',
    name: 'BS. Vũ Ngọc Lan',
    title: 'Bác sĩ Phụ khoa & Sản khoa',
    avatarText: 'NL',
    description: 'Thăm khám chuyên sâu phụ khoa, tiền sử sản phụ khoa, order composer gói chỉ định & xử lý chặn chi phí.',
  },
  ultrasound: {
    id: 'ultrasound',
    name: 'BS. Lê Hoàng Nam',
    title: 'Bác sĩ Siêu âm / CĐHA',
    avatarText: 'HN',
    description: 'Thực hiện siêu âm (SA1, SA2, SA3), đo đạc hình ảnh, kết luận kết quả siêu âm & ký duyệt trả phiếu.',
  },
};

// --- DATA FOR GENERAL DOCTOR (BS. Trần Văn Dũng) ---
export interface GeneralPatient {
  id: string;
  stt: string;
  name: string;
  birthYear: number;
  gender: 'Nữ' | 'Nam';
  age: number;
  patientCode: string;
  visitCode: string;
  appointmentTime: string;
  status: 'waiting' | 'in_progress' | 'pending_result' | 'completed';
  statusLabel: string;
  reason: string;
  priority: 'normal' | 'high' | 'urgent';
  vitals: {
    pulse: number;
    bp: string;
    temp: number;
    weight: number;
    allergy: string;
  };
  clinicalReason: string;
  medicalHistory: string;
  physicalExam: string;
  diagnosisMain: string;
  diagnosisSub: string;
  treatmentPlan: string;
  relatedOrders: { name: string; status: 'completed' | 'received' | 'pending'; doctor: string; resultText?: string }[];
  prescriptions: { name: string; dose: string; usage: string }[];
  totalFee: number;
}

export const GENERAL_PATIENTS: GeneralPatient[] = [
  {
    id: 'dr-021',
    stt: 'A021',
    name: 'Nguyễn Thị Mai',
    birthYear: 1994,
    gender: 'Nữ',
    age: 32,
    patientCode: 'BN250514-021',
    visitCode: 'LK250514-021',
    appointmentTime: '09:30',
    status: 'in_progress',
    statusLabel: 'Đang khám',
    reason: 'Khám phụ khoa định kỳ, ngứa âm hộ 3 ngày',
    priority: 'high',
    vitals: {
      pulse: 78,
      bp: '110/70',
      temp: 36.6,
      weight: 52.0,
      allergy: 'Phấn hoa',
    },
    clinicalReason: 'Khí hư bất thường, ngứa âm hộ 3 ngày.',
    medicalHistory: 'Kinh nguyệt đều, chu kỳ 28-30 ngày. Chưa từng quan hệ. Không có thai. Không tiền sử bệnh mãn tính.',
    physicalExam: 'Âm hộ không xung huyết, âm đạo khí hư trắng đục lượng vừa. Cổ tử cung hồng không tổn thương. Tử cung bình thường không đau. Phần phụ không đau không u.',
    diagnosisMain: 'Viêm âm đạo mức độ nhẹ (Candida) - N76.0',
    diagnosisSub: 'Viêm âm hộ - L29.2',
    treatmentPlan: 'Điều trị thuốc kháng nấm đặt âm đạo. Hướng dẫn vệ sinh. Tái khám sau 7 ngày khi có dấu hiệu bất thường.',
    relatedOrders: [
      { name: 'Siêu âm phụ khoa (đường bụng)', status: 'completed', doctor: 'BS. Lê Hoàng Nam', resultText: 'Tử cung & phần phụ 2 bên bình thường, không u dịch.' },
      { name: 'Xét nghiệm dịch âm đạo (soi tươi)', status: 'received', doctor: 'KTV. Trần Minh Thư', resultText: 'Nấm Candida (+), Bạch cầu (+)' },
      { name: 'Nhuộm Gram dịch âm đạo', status: 'pending', doctor: 'KTV. Trần Minh Thư', resultText: 'Chờ bác sĩ duyệt kết quả v1.2' },
    ],
    prescriptions: [
      { name: 'Clotrimazole 500mg', dose: '1 viên đặt', usage: 'Đặt âm đạo 1 viên, tối, 3 ngày' },
      { name: 'Clotrimazole 1%', dose: '1 tuýp 20g', usage: 'Bôi ngoài âm hộ, 2 lần/ngày, 5 ngày' },
    ],
    totalFee: 550000,
  },
  {
    id: 'dr-015',
    stt: 'A022',
    name: 'Phạm Thị Lan',
    birthYear: 1989,
    gender: 'Nữ',
    age: 37,
    patientCode: 'BN250514-015',
    visitCode: 'LK250514-019',
    appointmentTime: '08:30',
    status: 'waiting',
    statusLabel: 'Chờ khám',
    reason: 'Tái khám tim mạch & hồi hộp',
    priority: 'normal',
    vitals: { pulse: 84, bp: '130/85', temp: 36.7, weight: 62.0, allergy: 'Không' },
    clinicalReason: 'Tái khám tim mạch, thỉnh thoảng hồi hộp đánh trống ngực.',
    medicalHistory: 'Tiền sử tăng huyết áp nhẹ 2 năm.',
    physicalExam: 'Tim đập đều, T1 T2 rõ, không tiếng thổi bất thường.',
    diagnosisMain: 'Tăng huyết áp vô căn (I10)',
    diagnosisSub: 'Rối loạn thần kinh thực vật',
    treatmentPlan: 'Tiếp tục duy trì đơn thuốc huyết áp cũ.',
    relatedOrders: [],
    prescriptions: [],
    totalFee: 350000,
  },
  {
    id: 'dr-001',
    stt: 'A023',
    name: 'Lê Minh Châu',
    birthYear: 1991,
    gender: 'Nữ',
    age: 35,
    patientCode: 'BN250514-001',
    visitCode: 'LK250514-018',
    appointmentTime: '09:00',
    status: 'waiting',
    statusLabel: 'Chờ khám',
    reason: 'Đau đầu, chóng mặt',
    priority: 'normal',
    vitals: { pulse: 72, bp: '115/75', temp: 36.5, weight: 50.0, allergy: 'Không' },
    clinicalReason: 'Đau đầu vùng thái dương 2 ngày nay.',
    medicalHistory: 'Không tiền sử bệnh đặc biệt.',
    physicalExam: 'Thần kinh tỉnh táo, phản xạ ánh sáng dương tính.',
    diagnosisMain: 'Hội chứng đau đầu do căng thẳng (G44.2)',
    diagnosisSub: '',
    treatmentPlan: 'Nghỉ ngơi, dùng giảm đau nhẹ khi cần.',
    relatedOrders: [],
    prescriptions: [],
    totalFee: 300000,
  },
];

// --- SIGNED RESULTS REGISTRY (IMAGE 1) ---
export interface SignedResultRecord {
  id: string;
  code: string;
  patientName: string;
  patientCode: string;
  visitCode: string;
  age: number;
  gender: 'Nữ' | 'Nam';
  resultType: string;
  signedTime: string;
  version: string;
  status: 'Đã ký' | 'Đã phát hành' | 'Đã điều chỉnh';
  isPublished: boolean;
  doctorName: string;
  summary: {
    conclusion: string;
    diagnosis: string;
    plan: string;
    orders: string;
  };
  historyTimeline: { time: string; actor: string; action: string; version: string }[];
}

export const SIGNED_RESULTS: SignedResultRecord[] = [
  {
    id: 'sr-021',
    code: 'DR-250514-021',
    patientName: 'Nguyễn Thị Mai',
    patientCode: 'BN250514-021',
    visitCode: 'LK250514-021',
    age: 32,
    gender: 'Nữ',
    resultType: 'Kết quả khám & tổng hợp',
    signedTime: '14/05/2026 10:18',
    version: 'v1.2',
    status: 'Đã phát hành',
    isPublished: true,
    doctorName: 'BS. Trần Văn Dũng',
    summary: {
      conclusion: 'Thai 12 tuần, sống trong tử cung. Tim thai (+), hoạt động thai tốt. Không ghi nhận bất thường.',
      diagnosis: 'Z34.8 - Thai kỳ hiện tại lần khám thứ ba\nO36.8 - Xét nghiệm sàng lọc trước sinh',
      plan: 'Tiếp tục theo dõi thai kỳ. Tái khám sau 4 tuần.',
      orders: '• Acid folic 400mcg: Uống 1 viên/ngày, buổi sáng\n• Sắt (II) sulfat 60mg: Uống 1 viên/ngày, sau ăn',
    },
    historyTimeline: [
      { time: '14/05/2026 09:42', actor: 'Thư ký Lê Hoàng Nam', action: 'Lưu bản nháp', version: 'v1.1 (nháp)' },
      { time: '14/05/2026 09:58', actor: 'BS. Trần Văn Dũng', action: 'Rà soát kết quả', version: 'v1.1' },
      { time: '14/05/2026 10:15', actor: 'BS. Trần Văn Dũng', action: 'Ký duyệt hồ sơ', version: 'v1.2' },
      { time: '14/05/2026 10:18', actor: 'Hệ thống', action: 'Phát hành kết quả', version: 'v1.2' },
    ],
  },
  {
    id: 'sr-019',
    code: 'US-250514-019',
    patientName: 'Phạm Thị Lan',
    patientCode: 'BN250514-015',
    visitCode: 'LK250514-019',
    age: 37,
    gender: 'Nữ',
    resultType: 'Kết quả siêu âm thai',
    signedTime: '14/05/2026 09:56',
    version: 'v1.0',
    status: 'Đã phát hành',
    isPublished: true,
    doctorName: 'BS. Lê Hoàng Nam',
    summary: {
      conclusion: '1 thai sống trong tử cung tương đương 20 tuần 3 ngày. Độ dày độ mờ da gối bình thường.',
      diagnosis: 'Theo dõi thai 20 tuần',
      plan: 'Tái khám mốc 24 tuần siêu âm 4D hình thái.',
      orders: 'Bổ sung Canxi & Vitamin D3.',
    },
    historyTimeline: [
      { time: '14/05/2026 09:50', actor: 'BS. Lê Hoàng Nam', action: 'Nhập kết quả', version: 'v1.0 (nháp)' },
      { time: '14/05/2026 09:56', actor: 'BS. Lê Hoàng Nam', action: 'Ký duyệt & phát hành', version: 'v1.0' },
    ],
  },
  {
    id: 'sr-018',
    code: 'LAB-250514-018',
    patientName: 'Lê Minh Châu',
    patientCode: 'BN250514-001',
    visitCode: 'LK250514-018',
    age: 35,
    gender: 'Nữ',
    resultType: 'Kết quả xét nghiệm (Huyết học)',
    signedTime: '14/05/2026 09:32',
    version: 'v1.1',
    status: 'Đã phát hành',
    isPublished: true,
    doctorName: 'BS. Trần Văn Dũng',
    summary: {
      conclusion: 'Công thức máu trong dải bình thường, không thiếu máu.',
      diagnosis: 'Bình thường',
      plan: 'Theo dõi định kỳ.',
      orders: 'Không',
    },
    historyTimeline: [
      { time: '14/05/2026 09:32', actor: 'BS. Trần Văn Dũng', action: 'Ký duyệt', version: 'v1.1' },
    ],
  },
];

// --- DATA FOR OB-GYN SPECIALIST (BS. Vũ Ngọc Lan - IMAGE 4) ---
export interface ObGynExamData {
  stt: string;
  patientName: string;
  gender: 'Nữ';
  age: number;
  patientCode: string;
  phone: string;
  visitDate: string;
  doctorName: string;
  reason: string;
  menstrualHistory: {
    cycle: string;
    duration: string;
    flow: string;
    dysmenorrhea: string;
  };
  obHistory: {
    para: string;
    birthYear: string;
    notes: string;
  };
  gynHistory: {
    fibroid: string;
    papSmear: string;
    hpvVaccine: string;
  };
  vitals: {
    bp: string;
    pulse: number;
    temp: number;
    spo2: number;
    resp: number;
    weight: number;
    height: number;
    bmi: number;
  };
  examExternal: string;
  examSpeculum: string;
  examBimanual: string;
  diagnosisPre: string;
  treatmentDirection: string;
  presetOrders: { id: string; name: string; desc: string; price: number; itemCount: number }[];
  selectedOrders: { id: string; name: string; code: string; price: number; priority: string; checked: boolean }[];
  totalOrderPrice: number;
  costConflictBlocked: boolean;
  costConflictReason: string;
}

export const OBGYN_EXAM_DATA: ObGynExamData = {
  stt: 'PKO-062',
  patientName: 'Nguyễn Thị Hằng',
  gender: 'Nữ',
  age: 35,
  patientCode: 'KH250514-087',
  phone: '0901 234 567',
  visitDate: '14/05/2026 09:15',
  doctorName: 'BS. Vũ Ngọc Lan',
  reason: 'Khí hư ra nhiều, ngứa rát âm đạo 1 tuần, rong kinh 2 chu kỳ gần đây.',
  menstrualHistory: {
    cycle: 'Chu kỳ: 26–30 ngày, hành kinh 6–7 ngày',
    duration: 'Rong kinh 2 chu kỳ gần đây (8–10 ngày)',
    flow: 'Lượng kinh: nhiều dần, có ngày thay băng 3–4 lần',
    dysmenorrhea: 'Đau bụng kinh: nhẹ',
  },
  obHistory: {
    para: 'Para: 1 – Abor: 0 – Living: 1',
    birthYear: 'Sinh thường năm 2021, bé gái 3.5 tuổi',
    notes: 'Không có sảy thai, không nạo hút',
  },
  gynHistory: {
    fibroid: 'Chưa phát hiện u xơ / u nang trước đây',
    papSmear: 'Pap smear lần cuối: 2024 – Kết quả: Bình thường',
    hpvVaccine: 'Chưa tiêm HPV vaccine',
  },
  vitals: {
    bp: '110/70',
    pulse: 78,
    temp: 36.7,
    spo2: 98,
    resp: 18,
    weight: 54,
    height: 160,
    bmi: 21.1,
  },
  examExternal: 'Âm hộ: không tổn thương. Khí hư: nhiều, màu trắng đục, mùi hôi nhẹ.',
  examSpeculum: 'Thành âm đạo: sung huyết nhẹ. Khí hư: nhiều, đặc bám thành âm đạo. Cổ tử cung: lộ tuyến (+), không chảy máu tiếp xúc.',
  examBimanual: 'Tử cung: bình thường, di động tốt. Buồng trứng: không thấy bất thường. Khối bất thường: không.',
  diagnosisPre: 'Viêm âm đạo do vi khuẩn / nấm. Lộ tuyến cổ tử cung. Rong kinh chưa rõ nguyên nhân.',
  treatmentDirection: 'Chỉ định xét nghiệm + siêu âm đầu dò. Pap smear tầm soát tế bào cổ tử cung. Tư vấn vệ sinh, theo dõi chu kỳ kinh.',
  presetOrders: [
    { id: 'p1', name: 'Bộ khám phụ khoa cơ bản', desc: 'Đánh giá viêm nhiễm, tầm soát cổ tử cung và siêu âm.', price: 1650000, itemCount: 5 },
    { id: 'p2', name: 'Bộ tầm soát cổ tử cung', desc: 'Pap smear + HPV + Soi cổ tử cung.', price: 1550000, itemCount: 3 },
    { id: 'p3', name: 'Bộ viêm nhiễm âm đạo', desc: 'Phết dịch, soi tươi, nuôi cấy khi cần.', price: 450000, itemCount: 3 },
    { id: 'p4', name: 'Bộ rối loạn kinh nguyệt', desc: 'Đánh giá nội tiết + siêu âm.', price: 980000, itemCount: 4 },
  ],
  selectedOrders: [
    { id: 'so1', name: 'Pap smear / ThinPrep', code: 'GYN-PAP-001', price: 450000, priority: 'Chuẩn bị', checked: true },
    { id: 'so2', name: 'Xét nghiệm HPV DNA (Cobas)', code: 'GYN-HPV-002', price: 850000, priority: 'Chuẩn bị', checked: true },
    { id: 'so3', name: 'Siêu âm đầu dò (TVS)', code: 'GYN-US-TVS-001', price: 550000, priority: 'Ưu tiên', checked: true },
    { id: 'so4', name: 'Soi cổ tử cung (Colposcopy)', code: 'GYN-COL-001', price: 300000, priority: 'Ưu tiên', checked: true },
    { id: 'so5', name: 'Xét nghiệm nội tiết tố (FSH, LH, E2, PRL)', code: 'GYN-HOM-001', price: 600000, priority: 'Tùy chọn', checked: true },
    { id: 'so6', name: 'Phết dịch âm đạo (Gram, soi tươi)', code: 'GYN-SWR-001', price: 200000, priority: 'Thường', checked: true },
  ],
  totalOrderPrice: 2950000,
  costConflictBlocked: true,
  costConflictReason: 'Chỉ định HPV DNA đang chờ bệnh nhân xác nhận chi phí 850.000đ. Bệnh nhân chưa xác nhận đồng ý chi trả.',
};

// --- DATA FOR ULTRASOUND SPECIALIST (BS. Lê Hoàng Nam) ---
export interface UltrasoundQueueItem {
  id: string;
  stt: string;
  patientName: string;
  patientCode: string;
  visitCode: string;
  age: number;
  gender: string;
  type: string; // e.g. "Siêu âm phụ khoa đầu dò", "Siêu âm thai 4D", "Siêu âm ổ bụng"
  room: 'SA1' | 'SA2' | 'SA3';
  status: 'waiting' | 'in_progress' | 'completed';
  indicationDoctor: string;
  reason: string;
  findings: string;
  measurements: { name: string; val: string; unit: string }[];
  conclusion: string;
  signedTime?: string;
}

export const ULTRASOUND_ITEMS: UltrasoundQueueItem[] = [
  {
    id: 'us-101',
    stt: 'SA021',
    patientName: 'Nguyễn Thị Mai',
    patientCode: 'BN250514-021',
    visitCode: 'LK250514-021',
    age: 32,
    gender: 'Nữ',
    type: 'Siêu âm phụ khoa đầu dò (TVS)',
    room: 'SA1',
    status: 'in_progress',
    indicationDoctor: 'BS. Trần Văn Dũng',
    reason: 'Khám phụ khoa định kỳ, ngứa âm đạo',
    findings: 'Tử cung ngả trước, kích thước bình thường (45 x 38 mm). Nội mạc tử cung dày 8mm, đồng nhất. Buồng trứng phải có nang noãn kích thước 18mm. Buồng trứng trái bình thường. Không có dịch túi cùng Cùng đồ.',
    measurements: [
      { name: 'Đường kính trước sau tử cung', val: '38', unit: 'mm' },
      { name: 'Chiều dài tử cung', val: '45', unit: 'mm' },
      { name: 'Bề dày nội mạc tử cung', val: '8', unit: 'mm' },
      { name: 'Kích thước nang noãn BT phải', val: '18', unit: 'mm' },
    ],
    conclusion: 'Hình ảnh siêu âm tử cung & 2 phần phụ bình thường. Nang noãn trội buồng trứng phải (18mm).',
  },
  {
    id: 'us-102',
    stt: 'SA022',
    patientName: 'Phạm Thị Lan',
    patientCode: 'BN250514-015',
    visitCode: 'LK250514-019',
    age: 37,
    gender: 'Nữ',
    type: 'Siêu âm thai 4D hình thái',
    room: 'SA2',
    status: 'waiting',
    indicationDoctor: 'BS. Vũ Ngọc Lan',
    reason: 'Khám thai định kỳ 20 tuần',
    findings: '01 thai sống trong tử cung, cử động thai tốt. Nhịp tim thai 145 lần/phút. Chiều dài xương đùi 32mm. Đường kính lưỡng đỉnh 48mm.',
    measurements: [
      { name: 'Đường kính lưỡng đỉnh (BPD)', val: '48', unit: 'mm' },
      { name: 'Chiều dài xương đùi (FL)', val: '32', unit: 'mm' },
      { name: 'Chu vi đầu (HC)', val: '175', unit: 'mm' },
      { name: 'Cân nặng thai nhi dự kiến', val: '360', unit: 'g' },
    ],
    conclusion: 'Thai 20 tuần 3 ngày phát triển bình thường theo tuổi thai. Chưa phát hiện dị tật hình thái thai nhi.',
  },
  {
    id: 'us-103',
    stt: 'SA023',
    patientName: 'Lê Minh Châu',
    patientCode: 'BN250514-001',
    visitCode: 'LK250514-018',
    age: 35,
    gender: 'Nữ',
    type: 'Siêu âm ổ bụng tổng quát',
    room: 'SA1',
    status: 'completed',
    indicationDoctor: 'BS. Trần Văn Dũng',
    reason: 'Đau hạ vị',
    findings: 'Gan kích thước không to, nhu mô đều. Mật không sỏi. Thận 2 bên kích thước bình thường, không sỏi không ứ nước. Bàng quang ứ ít nước tiểu, thành mỏng.',
    measurements: [
      { name: 'Thận phải', val: '95', unit: 'mm' },
      { name: 'Thận trái', val: '98', unit: 'mm' },
    ],
    conclusion: 'Chưa thấy bất thường trên hình ảnh siêu âm ổ bụng tổng quát.',
    signedTime: '14/05/2026 09:45',
  },
];
