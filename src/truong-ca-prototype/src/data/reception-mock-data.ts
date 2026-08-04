// Mock data for Receptionist Dashboard ("Lễ Tân")

// --- CHECKIN TAB DATA ---
export interface CheckinPatient {
  id: string;
  stt: string;
  name: string;
  birthYear: number;
  gender: 'Nữ' | 'Nam';
  age: number;
  arrivalTime: string;
  appointmentTime: string;
  statusTag: 'Có hẹn' | 'Đến sớm' | 'Đến muộn' | 'Walk-in' | 'No-show';
  specialty: string;
  patientCode: string;
  cmnd: string;
  issueDate: string;
  issuePlace: string;
  phone: string;
  email: string;
  address: string;
  doctorName: string;
  roomName: string;
  reason: string;
  registeredService: string;
  servicePrice: number;
  bhytCode?: string;
}

export const CHECKIN_PATIENTS: CheckinPatient[] = [
  {
    id: 'ck-021',
    stt: 'A021',
    name: 'Nguyễn Thị Mai',
    birthYear: 1994,
    gender: 'Nữ',
    age: 32,
    arrivalTime: '09:18',
    appointmentTime: '09:30',
    statusTag: 'Có hẹn',
    specialty: 'Phụ khoa',
    patientCode: 'BN250514-021',
    cmnd: '001194034567',
    issueDate: '12/05/2021',
    issuePlace: 'Cục CSQLHC về TTXH',
    phone: '090 123 4567',
    email: 'mainguyen@gmail.com',
    address: '123 Lê Lợi, P. Bến Nghé, Q. 1, TP. Hồ Chí Minh',
    doctorName: 'BS. Trần Văn Dũng',
    roomName: 'Phòng khám số 2',
    reason: 'Khám phụ khoa, kiểm tra định kỳ',
    registeredService: 'Khám phụ khoa',
    servicePrice: 450000,
    bhytCode: 'GD 4 79 79 1234567890123',
  },
  {
    id: 'ck-015',
    stt: 'A022',
    name: 'Phạm Thị Lan',
    birthYear: 1989,
    gender: 'Nữ',
    age: 37,
    arrivalTime: '09:40',
    appointmentTime: '09:45',
    statusTag: 'Đến sớm',
    specialty: 'Khám tim mạch',
    patientCode: 'BN250514-015',
    cmnd: '079189012345',
    issueDate: '15/08/2020',
    issuePlace: 'Cục CSQLHC về TTXH',
    phone: '091 234 5678',
    email: 'lanpham@gmail.com',
    address: '45 Nguyễn Thị Minh Khai, Q. 3, TP. Hồ Chí Minh',
    doctorName: 'BS. Lê Hoàng Nam',
    roomName: 'Phòng khám số 1',
    reason: 'Tái khám tim mạch, kiểm tra nhịp tim',
    registeredService: 'Khám chuyên khoa tim mạch',
    servicePrice: 500000,
    bhytCode: 'HS 4 79 79 9876543210123',
  },
  {
    id: 'ck-001',
    stt: 'A023',
    name: 'Lê Minh Châu',
    birthYear: 1991,
    gender: 'Nữ',
    age: 35,
    arrivalTime: '10:16',
    appointmentTime: '10:15',
    statusTag: 'Đến muộn',
    specialty: 'Khám nội tổng quát',
    patientCode: 'BN250514-001',
    cmnd: '001191054321',
    issueDate: '10/10/2019',
    issuePlace: 'Công an TP. HCM',
    phone: '098 765 4321',
    email: 'chaule@gmail.com',
    address: '88 Võ Văn Tần, Q. 3, TP. Hồ Chí Minh',
    doctorName: 'BS. Trần Văn Dũng',
    roomName: 'Phòng khám số 2',
    reason: 'Khám tổng quát, đau mỏi vai gáy',
    registeredService: 'Khám nội tổng quát',
    servicePrice: 350000,
  },
  {
    id: 'ck-006',
    stt: 'A024',
    name: 'Nguyễn Thu Hà',
    birthYear: 1990,
    gender: 'Nữ',
    age: 36,
    arrivalTime: '10:35',
    appointmentTime: '10:30',
    statusTag: 'Đến muộn',
    specialty: 'Tái khám da liễu',
    patientCode: 'BN250514-006',
    cmnd: '001190088776',
    issueDate: '05/01/2022',
    issuePlace: 'Cục CSQLHC về TTXH',
    phone: '093 333 4444',
    email: 'hanguyen@gmail.com',
    address: '12 Lý Tự Trọng, Q. 1, TP. Hồ Chí Minh',
    doctorName: 'BS. Phạm Thị Lan',
    roomName: 'Phòng khám số 3',
    reason: 'Tái khám da liễu sau 2 tuần',
    registeredService: 'Khám da liễu',
    servicePrice: 400000,
  },
  {
    id: 'ck-007',
    stt: 'A025',
    name: 'Phạm Ngọc Anh',
    birthYear: 1992,
    gender: 'Nữ',
    age: 34,
    arrivalTime: '10:45',
    appointmentTime: '10:45',
    statusTag: 'No-show',
    specialty: 'Khám sản khoa',
    patientCode: 'BN250514-007',
    cmnd: '001192099887',
    issueDate: '20/03/2021',
    issuePlace: 'Cục CSQLHC về TTXH',
    phone: '097 888 9999',
    email: 'anhpham@gmail.com',
    address: '200 Điện Biên Phủ, Q. Bình Thạnh, TP. HCM',
    doctorName: 'BS. Trần Văn Dũng',
    roomName: 'Phòng khám số 2',
    reason: 'Khám thai định kỳ tuần 16',
    registeredService: 'Khám thai chuyên khoa',
    servicePrice: 450000,
  },
  {
    id: 'ck-008',
    stt: 'A026',
    name: 'Vũ Thị Hương',
    birthYear: 1987,
    gender: 'Nữ',
    age: 39,
    arrivalTime: '11:02',
    appointmentTime: '11:00',
    statusTag: 'Đến muộn',
    specialty: 'Khám nội tiết',
    patientCode: 'BN250514-008',
    cmnd: '001187066554',
    issueDate: '14/07/2020',
    issuePlace: 'Công an TP. HCM',
    phone: '094 555 6666',
    email: 'huongvu@gmail.com',
    address: '56 Trần Hưng Đạo, Q. 1, TP. Hồ Chí Minh',
    doctorName: 'BS. Lê Hoàng Nam',
    roomName: 'Phòng khám số 1',
    reason: 'Kiểm tra đường huyết & tuyến giáp',
    registeredService: 'Khám nội tiết',
    servicePrice: 400000,
  },
];

// --- QUEUE TAB DATA ---
export interface ReceptionQueueItem {
  stt: string;
  name: string;
  birthYear: number;
  gender: 'Nữ' | 'Nam';
  age: number;
  arrivalTime: string;
  waitTimeStr: string;
  tag?: string;
  counter: string;
  type: 'Đặt hẹn' | 'Đến trực tiếp' | 'Bảo hiểm y tế';
}

export const RECEPTION_QUEUE_ITEMS: ReceptionQueueItem[] = [
  { stt: 'A021', name: 'Nguyễn Thị Mai', birthYear: 1994, gender: 'Nữ', age: 32, arrivalTime: '10:10', waitTimeStr: "08'", tag: '★ Ưu tiên', counter: 'Quầy 2', type: 'Đặt hẹn' },
  { stt: 'A022', name: 'Phạm Thị Lan', birthYear: 1989, gender: 'Nữ', age: 37, arrivalTime: '10:05', waitTimeStr: "13'", counter: 'Quầy 1', type: 'Đặt hẹn' },
  { stt: 'A023', name: 'Lê Minh Châu', birthYear: 1991, gender: 'Nữ', age: 35, arrivalTime: '10:03', waitTimeStr: "15'", counter: 'Quầy 2', type: 'Đến trực tiếp' },
  { stt: 'A024', name: 'Nguyễn Thu Hà', birthYear: 1990, gender: 'Nữ', age: 36, arrivalTime: '10:01', waitTimeStr: "17'", counter: 'Quầy 1', type: 'Bảo hiểm y tế' },
  { stt: 'A025', name: 'Phạm Ngọc Anh', birthYear: 1992, gender: 'Nữ', age: 34, arrivalTime: '09:58', waitTimeStr: "20'", counter: 'Quầy 2', type: 'Đặt hẹn' },
  { stt: 'A026', name: 'Trần Văn Dũng', birthYear: 1985, gender: 'Nam', age: 41, arrivalTime: '09:55', waitTimeStr: "23'", counter: 'Quầy 1', type: 'Đến trực tiếp' },
];

// --- CHECKOUT TAB DATA ---
export interface CheckoutPatient {
  id: string;
  stt: string;
  name: string;
  birthYear: number;
  gender: 'Nữ' | 'Nam';
  age: number;
  patientCode: string;
  visitCode: string;
  checkinTime: string;
  statusTag: 'Đủ điều kiện đóng lượt' | 'Còn nghĩa vụ thanh toán' | 'Chưa có follow-up cho kết quả trả sau';
  statusType: 'ready' | 'finance_pending' | 'blocked';
  doctorName: string;
  roomName: string;
  services: { name: string; doctor: string; status: 'completed' | 'pending'; note?: string }[];
  finances: { name: string; status: 'paid' | 'unpaid'; amount: number }[];
  documents: { name: string; type: string; ready: boolean }[];
  followup?: { code: string; note: string; owner: string; dueDate: string };
}

export const CHECKOUT_PATIENTS: CheckoutPatient[] = [
  {
    id: 'co-021',
    stt: 'A021',
    name: 'Nguyễn Thị Mai',
    birthYear: 1994,
    gender: 'Nữ',
    age: 32,
    patientCode: 'BN250514-021',
    visitCode: 'LK250514-021',
    checkinTime: '10:18',
    statusTag: 'Đủ điều kiện đóng lượt',
    statusType: 'ready',
    doctorName: 'BS. Trần Văn Dũng',
    roomName: 'Phòng khám số 2',
    services: [
      { name: 'Khám bác sĩ', doctor: 'BS. Trần Văn Dũng', status: 'completed' },
      { name: 'Siêu âm', doctor: 'BS. Lê Hoàng Nam', status: 'completed' },
      { name: 'Xét nghiệm ngoài', doctor: 'Lab Hoàn Mỹ', status: 'pending', note: 'Đã lấy mẫu · Đang chờ kết quả (Kết quả trả sau — đã tạo theo dõi)' },
    ],
    finances: [
      { name: 'Nghĩa vụ: Xét nghiệm', status: 'paid', amount: 350000 },
      { name: 'Nghĩa vụ: Thuốc', status: 'paid', amount: 620000 },
      { name: 'Nghĩa vụ: Khám & Dịch vụ', status: 'paid', amount: 280000 },
    ],
    documents: [
      { name: 'Kết quả xét nghiệm (1)', type: 'PDF', ready: true },
      { name: 'Kết quả siêu âm (1)', type: 'PDF', ready: true },
      { name: 'Đơn thuốc (1)', type: 'PDF', ready: true },
      { name: 'Hướng dẫn sau khám (1)', type: 'PDF', ready: true },
      { name: 'Giấy hẹn tái khám', type: 'PDF', ready: true },
    ],
    followup: {
      code: 'FU-250514-009',
      note: 'Kết quả xét nghiệm ngoài',
      owner: 'CSKH',
      dueDate: '15/05/2026',
    },
  },
  {
    id: 'co-015',
    stt: 'A022',
    name: 'Phạm Thị Lan',
    birthYear: 1989,
    gender: 'Nữ',
    age: 37,
    patientCode: 'BN250514-015',
    visitCode: 'LK250514-019',
    checkinTime: '09:56',
    statusTag: 'Còn nghĩa vụ thanh toán',
    statusType: 'finance_pending',
    doctorName: 'BS. Lê Hoàng Nam',
    roomName: 'Phòng khám số 1',
    services: [
      { name: 'Khám bác sĩ', doctor: 'BS. Lê Hoàng Nam', status: 'completed' },
      { name: 'Siêu âm tim', doctor: 'BS. Lê Hoàng Nam', status: 'completed' },
    ],
    finances: [
      { name: 'Nghĩa vụ: Khám & Siêu âm', status: 'unpaid', amount: 500000 },
    ],
    documents: [
      { name: 'Kết quả siêu âm tim (1)', type: 'PDF', ready: true },
      { name: 'Đơn thuốc (1)', type: 'PDF', ready: true },
    ],
  },
  {
    id: 'co-001',
    stt: 'A023',
    name: 'Lê Minh Châu',
    birthYear: 1991,
    gender: 'Nữ',
    age: 35,
    patientCode: 'BN250514-001',
    visitCode: 'LK250514-018',
    checkinTime: '09:32',
    statusTag: 'Đủ điều kiện đóng lượt',
    statusType: 'ready',
    doctorName: 'BS. Trần Văn Dũng',
    roomName: 'Phòng khám số 2',
    services: [
      { name: 'Khám bác sĩ', doctor: 'BS. Trần Văn Dũng', status: 'completed' },
    ],
    finances: [
      { name: 'Nghĩa vụ: Khám tổng quát', status: 'paid', amount: 350000 },
    ],
    documents: [
      { name: 'Phiếu khám bệnh (1)', type: 'PDF', ready: true },
      { name: 'Đơn thuốc (1)', type: 'PDF', ready: true },
    ],
  },
  {
    id: 'co-006',
    stt: 'A024',
    name: 'Nguyễn Thu Hà',
    birthYear: 1990,
    gender: 'Nữ',
    age: 36,
    patientCode: 'BN250514-006',
    visitCode: 'LK250514-017',
    checkinTime: '09:05',
    statusTag: 'Chưa có follow-up cho kết quả trả sau',
    statusType: 'blocked',
    doctorName: 'BS. Phạm Thị Lan',
    roomName: 'Phòng khám số 3',
    services: [
      { name: 'Khám bác sĩ', doctor: 'BS. Phạm Thị Lan', status: 'completed' },
      { name: 'Sinh thiết da', doctor: 'BS. Phạm Thị Lan', status: 'pending', note: 'Đã gửi lab · Chưa có kết quả' },
    ],
    finances: [
      { name: 'Nghĩa vụ: Khám & Thủ thuật', status: 'paid', amount: 650000 },
    ],
    documents: [
      { name: 'Đơn thuốc (1)', type: 'PDF', ready: true },
    ],
  },
  {
    id: 'co-007',
    stt: 'A025',
    name: 'Phạm Ngọc Anh',
    birthYear: 1992,
    gender: 'Nữ',
    age: 34,
    patientCode: 'BN250514-007',
    visitCode: 'LK250514-016',
    checkinTime: '08:41',
    statusTag: 'Đủ điều kiện đóng lượt',
    statusType: 'ready',
    doctorName: 'BS. Trần Văn Dũng',
    roomName: 'Phòng khám số 2',
    services: [
      { name: 'Khám sản khoa', doctor: 'BS. Trần Văn Dũng', status: 'completed' },
      { name: 'Siêu âm 4D', doctor: 'BS. Lê Hoàng Nam', status: 'completed' },
    ],
    finances: [
      { name: 'Nghĩa vụ: Gói khám thai', status: 'paid', amount: 800000 },
    ],
    documents: [
      { name: 'Kết quả siêu âm 4D (1)', type: 'PDF', ready: true },
      { name: 'Đơn thuốc (1)', type: 'PDF', ready: true },
    ],
  },
];
