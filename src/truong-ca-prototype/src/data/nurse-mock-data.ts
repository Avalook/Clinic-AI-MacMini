// Mock data for Nurse Vitals Dashboard ("Đo & ghi sinh hiệu")

export interface NurseQueuePatient {
  id: string;
  stt: string;
  name: string;
  birthYear: number;
  gender: 'Nữ' | 'Nam';
  age: number;
  patientCode: string;
  visitCode: string;
  waitTimeMinutes: number;
  statusTag?: 'Đang đo' | 'Ưu tiên' | 'Cần đo lại';
  nextStep: 'Chuyển khám' | 'Đo sinh hiệu' | 'Đo lại sinh hiệu';
}

export interface VitalSignItem {
  id: string;
  label: string;
  value: string | number;
  secondaryValue?: string | number;
  unit: string;
  source: string;
  time: string;
  status: 'normal' | 'warning' | 'critical';
  statusText: string;
  normalRange: string;
}

export interface NurseKpi {
  waiting: number;
  inProgress: number;
  alertAbnormal: number;
  alertLongWait: number;
  completedToday: number;
}

export interface VitalsHistoryRecord {
  id: string;
  stt: string;
  patientName: string;
  patientCode: string;
  visitCode: string;
  age: number;
  gender: 'Nữ' | 'Nam';
  nurseName: string;
  doctorName: string;
  room: string;
  startTime: string;
  endTime: string;
  duration: string;
  status: 'completed' | 'warning' | 'remeasured';
  statusLabel: string;
  alertsHistory: { time: string; text: string; severity: 'warning' | 'info' | 'critical' }[];
  vitalsSummary: {
    pulse: string;
    bp: string;
    respiration: string;
    spo2: string;
    temp: string;
    weight: string;
    height: string;
    bmi: string;
    pain: string;
  };
  notes: string;
}

export const NURSE_KPI: NurseKpi = {
  waiting: 9,
  inProgress: 2,
  alertAbnormal: 3,
  alertLongWait: 3,
  completedToday: 31,
};

export const NURSE_PATIENTS: NurseQueuePatient[] = [
  {
    id: 'p-021',
    stt: 'A021',
    name: 'Nguyễn Thị Mai',
    birthYear: 1994,
    gender: 'Nữ',
    age: 32,
    patientCode: 'BN250514-021',
    visitCode: 'LK250514-021',
    waitTimeMinutes: 6,
    statusTag: 'Đang đo',
    nextStep: 'Chuyển khám',
  },
  {
    id: 'p-018',
    stt: 'A022',
    name: 'Phạm Thị Lan',
    birthYear: 1989,
    gender: 'Nữ',
    age: 37,
    patientCode: 'BN250514-018',
    visitCode: 'LK250514-018',
    waitTimeMinutes: 12,
    statusTag: 'Ưu tiên',
    nextStep: 'Đo sinh hiệu',
  },
  {
    id: 'p-001',
    stt: 'A023',
    name: 'Lê Minh Châu',
    birthYear: 1991,
    gender: 'Nữ',
    age: 35,
    patientCode: 'BN250514-001',
    visitCode: 'LK250514-001',
    waitTimeMinutes: 15,
    nextStep: 'Đo sinh hiệu',
  },
  {
    id: 'p-006',
    stt: 'A024',
    name: 'Nguyễn Thu Hà',
    birthYear: 1990,
    gender: 'Nữ',
    age: 36,
    patientCode: 'BN250514-006',
    visitCode: 'LK250514-006',
    waitTimeMinutes: 18,
    nextStep: 'Đo sinh hiệu',
  },
  {
    id: 'p-007',
    stt: 'A025',
    name: 'Phạm Ngọc Anh',
    birthYear: 1992,
    gender: 'Nữ',
    age: 34,
    patientCode: 'BN250514-007',
    visitCode: 'LK250514-007',
    waitTimeMinutes: 20,
    statusTag: 'Cần đo lại',
    nextStep: 'Đo lại sinh hiệu',
  },
];

export const INITIAL_VITALS: VitalSignItem[] = [
  {
    id: 'pulse',
    label: 'Mạch',
    value: 84,
    unit: 'lần/phút',
    source: 'Monitor M3',
    time: '10:19',
    status: 'normal',
    statusText: 'Trong giới hạn',
    normalRange: '60 - 100',
  },
  {
    id: 'bp',
    label: 'Huyết áp',
    value: 126,
    secondaryValue: 78,
    unit: 'mmHg',
    source: 'BP-02',
    time: '10:19',
    status: 'normal',
    statusText: 'Trong giới hạn',
    normalRange: '90/60 - 140/90',
  },
  {
    id: 'respiration',
    label: 'Nhịp thở',
    value: 18,
    unit: 'lần/phút',
    source: 'Quan sát',
    time: '10:19',
    status: 'normal',
    statusText: 'Trong giới hạn',
    normalRange: '12 - 20',
  },
  {
    id: 'spo2',
    label: 'SpO2',
    value: 98,
    unit: '%',
    source: 'SpO2-01',
    time: '10:18',
    status: 'normal',
    statusText: 'Trong giới hạn',
    normalRange: '95 - 100',
  },
  {
    id: 'temp',
    label: 'Nhiệt độ',
    value: '36,7',
    unit: '°C',
    source: 'Nhiệt kế TM-01',
    time: '10:18',
    status: 'normal',
    statusText: 'Trong giới hạn',
    normalRange: '36,0 - 37,5',
  },
  {
    id: 'weight',
    label: 'Cân nặng',
    value: '56,0',
    unit: 'kg',
    source: 'Cân điện tử',
    time: '10:18',
    status: 'normal',
    statusText: 'Trong giới hạn',
    normalRange: '40 - 100',
  },
  {
    id: 'height',
    label: 'Chiều cao',
    value: 160,
    unit: 'cm',
    source: 'Thước đo',
    time: '10:18',
    status: 'normal',
    statusText: 'Trong giới hạn',
    normalRange: '140 - 200',
  },
  {
    id: 'bmi',
    label: 'BMI',
    value: '21,9',
    unit: 'kg/m²',
    source: 'Tự động tính toán',
    time: '10:19',
    status: 'normal',
    statusText: 'Trong giới hạn',
    normalRange: '18,5 - 24,9',
  },
  {
    id: 'pain',
    label: 'Mức độ đau',
    value: 2,
    unit: '/ 10',
    source: 'Hỏi bệnh nhân',
    time: '10:20',
    status: 'normal',
    statusText: 'Trong giới hạn',
    normalRange: '0 - 10',
  },
];

export const NURSE_VITALS_HISTORY: VitalsHistoryRecord[] = [
  {
    id: 'h-020',
    stt: 'A020',
    patientName: 'Trần Thị Thu Hương',
    patientCode: 'BN250514-020',
    visitCode: 'LK250514-020',
    age: 29,
    gender: 'Nữ',
    nurseName: 'NT Nguyễn Thị Tâm',
    doctorName: 'BS. Trần Văn Dũng',
    room: 'Phòng khám số 2',
    startTime: '10:05',
    endTime: '10:09',
    duration: '04:00',
    status: 'completed',
    statusLabel: 'Hoàn tất & Chuyển khám',
    alertsHistory: [],
    vitalsSummary: {
      pulse: '76 lần/phút',
      bp: '118/75 mmHg',
      respiration: '16 lần/phút',
      spo2: '99%',
      temp: '36.5 °C',
      weight: '52 kg',
      height: '158 cm',
      bmi: '20.8 kg/m²',
      pain: '0/10',
    },
    notes: 'Sinh hiệu bình thường, bệnh nhân sẵn sàng vào khám bác sĩ.',
  },
  {
    id: 'h-019',
    stt: 'A019',
    patientName: 'Đỗ Thị Hồng',
    patientCode: 'BN250514-019',
    visitCode: 'LK250514-019',
    age: 42,
    gender: 'Nữ',
    nurseName: 'NT Nguyễn Thị Tâm',
    doctorName: 'BS. Vũ Hoàng Nam',
    room: 'Phòng khám số 1',
    startTime: '09:50',
    endTime: '09:56',
    duration: '06:00',
    status: 'warning',
    statusLabel: 'Có cảnh báo (Đã xử lý)',
    alertsHistory: [
      { time: '09:51', text: 'Huyết áp 145/95 mmHg (Vượt ngưỡng tâm thu)', severity: 'warning' },
      { time: '09:54', text: 'Nghỉ 3 phút đo lại lần 2: 135/88 mmHg (Chấp nhận)', severity: 'info' },
      { time: '09:55', text: 'Đã báo BS. Vũ Hoàng Nam ghi nhận huyết áp nền cao', severity: 'info' },
    ],
    vitalsSummary: {
      pulse: '92 lần/phút',
      bp: '135/88 mmHg',
      respiration: '18 lần/phút',
      spo2: '97%',
      temp: '36.8 °C',
      weight: '68 kg',
      height: '155 cm',
      bmi: '28.3 kg/m²',
      pain: '3/10',
    },
    notes: 'BN tiền sử tăng huyết áp nhẹ, đã đo lại lần 2 và báo bác sĩ.',
  },
  {
    id: 'h-017',
    stt: 'A017',
    patientName: 'Vũ Thị Tuyết',
    patientCode: 'BN250514-017',
    visitCode: 'LK250514-017',
    age: 31,
    gender: 'Nữ',
    nurseName: 'NT Nguyễn Thị Tâm',
    doctorName: 'BS. Trần Văn Dũng',
    room: 'Phòng khám số 2',
    startTime: '09:35',
    endTime: '09:42',
    duration: '07:00',
    status: 'remeasured',
    statusLabel: 'Yêu cầu đo lại',
    alertsHistory: [
      { time: '09:36', text: 'Mạch 110 lần/phút (Mạch nhanh do BN vừa đi cầu thang)', severity: 'warning' },
      { time: '09:40', text: 'Cho BN ngồi nghỉ 5 phút, đo lại mạch 82 lần/phút', severity: 'info' },
    ],
    vitalsSummary: {
      pulse: '82 lần/phút',
      bp: '120/80 mmHg',
      respiration: '17 lần/phút',
      spo2: '98%',
      temp: '36.6 °C',
      weight: '54 kg',
      height: '162 cm',
      bmi: '20.6 kg/m²',
      pain: '1/10',
    },
    notes: 'Đã đo lại sau khi nghỉ ngơi, các chỉ số đạt yêu cầu.',
  },
  {
    id: 'h-015',
    stt: 'A015',
    patientName: 'Hoàng Minh Thảo',
    patientCode: 'BN250514-015',
    visitCode: 'LK250514-015',
    age: 26,
    gender: 'Nữ',
    nurseName: 'NT Nguyễn Thị Tâm',
    doctorName: 'BS. Lê Minh Châu',
    room: 'Phòng khám số 3',
    startTime: '09:20',
    endTime: '09:24',
    duration: '04:00',
    status: 'completed',
    statusLabel: 'Hoàn tất & Chuyển khám',
    alertsHistory: [],
    vitalsSummary: {
      pulse: '74 lần/phút',
      bp: '115/72 mmHg',
      respiration: '15 lần/phút',
      spo2: '100%',
      temp: '36.4 °C',
      weight: '48 kg',
      height: '160 cm',
      bmi: '18.8 kg/m²',
      pain: '0/10',
    },
    notes: 'Sức khỏe tốt, thai 12 tuần.',
  },
];
