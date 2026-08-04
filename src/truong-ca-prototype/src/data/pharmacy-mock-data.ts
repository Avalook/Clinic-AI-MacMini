// Mock data for Pharmacy Department ("Nhà Thuốc / Dược Sĩ") — Matching Images 1 to 5

export interface PrescriptionItem {
  id: string;
  drugName: string;
  doseInfo: string;
  usageInstructions: string;
  prescribedQty: number;
  unit: string;
  stockQty: number;
  spec: string;
  dispensedQty?: number;
  lotNumber?: string;
  expiryDate?: string;
  verified?: boolean;
  price?: number;
  counseling?: {
    timing: string;
    method: string;
    missedDose: string;
    sideEffects: string;
    interactions: string;
  };
}

export interface PendingPrescription {
  id: string;
  code: string;
  patientName: string;
  patientCode: string;
  birthYear: number;
  gender: 'Nữ' | 'Nam';
  age: number;
  doctorName: string;
  doctorCode: string;
  prescriptionDate: string;
  prescriptionTime: string;
  version: string;
  status: 'allowed' | 'payment_pending' | 'verify_pending';
  statusLabel: string;
  statusBg: string;
  statusColor: string;
  waitTimeMinutes: number;
  items: PrescriptionItem[];
  doctorNote: string;
  eligibility: {
    validPrescription: boolean;
    rightPatient: boolean;
    allowedPrepare: boolean;
    stockAvailable: boolean;
  };
  financials?: {
    examPaid: boolean;
    examFee: number;
    medsPaid: boolean;
    medsFee: number;
    otherPaid: boolean;
    otherFee: number;
  };
}

export const PHARMACY_PENDING_PRESCRIPTIONS: PendingPrescription[] = [
  {
    id: 'rx-021',
    code: 'RX250514-021',
    patientName: 'Nguyễn Thị Mai',
    patientCode: 'BN250514-021',
    birthYear: 1994,
    gender: 'Nữ',
    age: 32,
    doctorName: 'BS. Trần Văn Dũng',
    doctorCode: 'BS250314-028',
    prescriptionDate: '14/05/2026',
    prescriptionTime: '09:55',
    version: 'v1.0',
    status: 'allowed',
    statusLabel: 'Được phép chuẩn bị',
    statusBg: '#dcfce7',
    statusColor: '#15803d',
    waitTimeMinutes: 8,
    doctorNote: 'Uống đúng liều theo hướng dẫn. Tái khám sau 4 tuần hoặc khi có bất kỳ dấu hiệu bất thường.',
    items: [
      {
        id: 'med-1',
        drugName: 'Folic Mum 5mg',
        doseInfo: 'Acid folic 5mg',
        spec: 'Hộp 30 viên nén',
        usageInstructions: 'Uống 1 viên mỗi ngày, sau bữa ăn sáng',
        prescribedQty: 1,
        unit: 'hộp',
        stockQty: 152,
        price: 180000,
        counseling: {
          timing: 'Uống sau bữa ăn sáng.',
          method: 'Nuốt nguyên viên với nước lọc, không nghiền.',
          missedDose: 'Uống ngay khi nhớ ra. Bỏ qua nếu gần liều kế tiếp; không uống gấp đôi.',
          sideEffects: 'Buồn nôn nhẹ, đầy hơi. Nếu khó chịu kéo dài, báo bác sĩ.',
          interactions: 'Tránh dùng cùng rượu bia. Báo bác sĩ nếu đang dùng thuốc chống co giật.',
        },
      },
      {
        id: 'med-2',
        drugName: 'DHA 200mg',
        doseInfo: 'Docosahexaenoic acid 200mg',
        spec: 'Hộp 30 viên nang mềm',
        usageInstructions: 'Uống 1 viên mỗi ngày, sau bữa ăn tối',
        prescribedQty: 1,
        unit: 'hộp',
        stockQty: 98,
        price: 320000,
        counseling: {
          timing: 'Uống sau bữa ăn.',
          method: 'Nuốt nguyên viên với nước lọc.',
          missedDose: 'Uống ngay khi nhớ ra. Bỏ qua nếu gần liều kế tiếp; không uống gấp đôi.',
          sideEffects: 'Ợ hơi, khó chịu dạ dày nhẹ.',
          interactions: 'Có thể tăng nguy cơ chảy máu nếu dùng cùng thuốc chống đông.',
        },
      },
      {
        id: 'med-3',
        drugName: 'Canxi 500mg',
        doseInfo: 'Calcium carbonate 500mg',
        spec: 'Hộp 60 viên nén',
        usageInstructions: 'Uống 1 viên, ngày 2 lần, sau bữa sáng và tối',
        prescribedQty: 2,
        unit: 'hộp',
        stockQty: 210,
        price: 250000,
        counseling: {
          timing: 'Uống sau bữa tối.',
          method: 'Nuốt nguyên viên với nước lọc.',
          missedDose: 'Uống ngay khi nhớ ra. Bỏ qua nếu gần liều kế tiếp; không uống gấp đôi.',
          sideEffects: 'Táo bón, đầy bụng.',
          interactions: 'Cách sắt, kẽm, Levothyroxine ít nhất 2 giờ.',
        },
      },
    ],
    eligibility: {
      validPrescription: true,
      rightPatient: true,
      allowedPrepare: true,
      stockAvailable: true,
    },
    financials: {
      examPaid: true,
      examFee: 250000,
      medsPaid: true,
      medsFee: 750000,
      otherPaid: true,
      otherFee: 100000,
    },
  },
  {
    id: 'rx-015',
    code: 'RX250514-015',
    patientName: 'Phạm Thị Lan',
    patientCode: 'BN250514-015',
    birthYear: 1989,
    gender: 'Nữ',
    age: 37,
    doctorName: 'BS. Lê Hoàng Nam',
    doctorCode: 'BS250314-012',
    prescriptionDate: '14/05/2026',
    prescriptionTime: '10:05',
    version: 'v1.0',
    status: 'payment_pending',
    statusLabel: 'Chờ thanh toán thuốc',
    statusBg: '#ffedd5',
    statusColor: '#c2410c',
    waitTimeMinutes: 22,
    doctorNote: 'Dùng thuốc đúng giờ.',
    items: [],
    eligibility: {
      validPrescription: true,
      rightPatient: true,
      allowedPrepare: false,
      stockAvailable: true,
    },
    financials: {
      examPaid: true,
      examFee: 250000,
      medsPaid: false,
      medsFee: 860000,
      otherPaid: true,
      otherFee: 100000,
    },
  },
  {
    id: 'rx-001',
    code: 'RX250514-001',
    patientName: 'Lê Minh Châu',
    patientCode: 'BN250514-001',
    birthYear: 1991,
    gender: 'Nữ',
    age: 35,
    doctorName: 'BS. Trần Văn Dũng',
    doctorCode: 'BS250314-028',
    prescriptionDate: '14/05/2026',
    prescriptionTime: '09:40',
    version: 'v1.0',
    status: 'payment_pending',
    statusLabel: 'Chờ thanh toán thuốc',
    statusBg: '#ffedd5',
    statusColor: '#c2410c',
    waitTimeMinutes: 35,
    doctorNote: 'Nghỉ ngơi nhiều.',
    items: [],
    eligibility: { validPrescription: true, rightPatient: true, allowedPrepare: false, stockAvailable: true },
  },
];

// --- PREPARATION ORDERS DATA (IMAGE 3) ---
export interface PreparationOrder {
  id: string;
  code: string;
  patientName: string;
  patientCode: string;
  birthYear: number;
  gender: string;
  age: number;
  doctorName: string;
  prescriptionCode: string;
  status: 'draft' | 'wait_check' | 'out_of_stock';
  statusLabel: string;
  statusBg: string;
  statusColor: string;
  items: {
    drugName: string;
    spec: string;
    prescribedQty: number;
    dispensedQty: number;
    unit: string;
    lotNumber: string;
    expiryDate: string;
    verified: boolean;
  }[];
  checklist: {
    patientMatch: boolean;
    drugsMatch: boolean;
    qtyMatch: boolean;
    lotExpiryMatch: boolean;
    labelingDone: boolean;
    finalConfirmed: boolean;
  };
  pharmacistName: string;
  startTime: string;
  durationTimeStr: string;
}

export const PREPARATION_ORDERS_DATA: PreparationOrder[] = [
  {
    id: 'prep-021',
    code: 'PREP-250514-021',
    patientName: 'Nguyễn Thị Mai',
    patientCode: 'BN250514-021',
    birthYear: 1994,
    gender: 'Nữ',
    age: 32,
    doctorName: 'BS. Trần Văn Dũng',
    prescriptionCode: 'RX250514-021',
    status: 'draft',
    statusLabel: 'Đang soạn',
    statusBg: '#dbeafe',
    statusColor: '#1d4ed8',
    items: [
      { drugName: 'Folic Mum 5mg (Acid folic 5mg)', spec: 'Hộp 30 viên nén', prescribedQty: 1, dispensedQty: 1, unit: 'hộp', lotNumber: 'LOT240501', expiryDate: '31/05/2027', verified: true },
      { drugName: 'DHA 200mg (Docosahexaenoic acid)', spec: 'Hộp 30 viên nang mềm', prescribedQty: 1, dispensedQty: 1, unit: 'hộp', lotNumber: 'LOT240612', expiryDate: '30/06/2027', verified: true },
      { drugName: 'Canxi 500mg (Calcium carbonate)', spec: 'Hộp 60 viên nén', prescribedQty: 2, dispensedQty: 2, unit: 'hộp', lotNumber: 'LOT240804', expiryDate: '30/08/2027', verified: true },
    ],
    checklist: {
      patientMatch: true,
      drugsMatch: true,
      qtyMatch: true,
      lotExpiryMatch: true,
      labelingDone: true,
      finalConfirmed: false,
    },
    pharmacistName: 'Lê Hoàng Minh',
    startTime: '10:12 · 14/05/2026',
    durationTimeStr: '08:14',
  },
  {
    id: 'prep-006',
    code: 'PREP-250514-006',
    patientName: 'Nguyễn Thu Hà',
    patientCode: 'BN250514-006',
    birthYear: 1990,
    gender: 'Nữ',
    age: 36,
    doctorName: 'BS. Nguyễn Phương Anh',
    prescriptionCode: 'RX250514-006',
    status: 'wait_check',
    statusLabel: 'Chờ kiểm tra',
    statusBg: '#ffedd5',
    statusColor: '#c2410c',
    items: [],
    checklist: { patientMatch: true, drugsMatch: true, qtyMatch: true, lotExpiryMatch: true, labelingDone: true, finalConfirmed: false },
    pharmacistName: 'Lê Hoàng Minh',
    startTime: '10:00',
    durationTimeStr: '20:00',
  },
  {
    id: 'prep-007',
    code: 'PREP-250514-007',
    patientName: 'Phạm Ngọc Anh',
    patientCode: 'BN250514-007',
    birthYear: 1992,
    gender: 'Nữ',
    age: 34,
    doctorName: 'BS. Trần Văn Dũng',
    prescriptionCode: 'RX250514-007',
    status: 'out_of_stock',
    statusLabel: 'Thiếu 1 hộp — cần xử lý cấp một phần',
    statusBg: '#fee2e2',
    statusColor: '#b91c1c',
    items: [],
    checklist: { patientMatch: true, drugsMatch: false, qtyMatch: false, lotExpiryMatch: true, labelingDone: false, finalConfirmed: false },
    pharmacistName: 'Lê Hoàng Minh',
    startTime: '09:50',
    durationTimeStr: '30:00',
  },
];

// --- HANDOVER HISTORY DATA (IMAGE 2) ---
export interface HandoverRecord {
  id: string;
  code: string;
  prescriptionCode: string;
  dispensingCode: string;
  dateStr: string;
  timeStr: string;
  patientName: string;
  patientCode: string;
  birthYear: number;
  gender: string;
  age: number;
  doctorName: string;
  pharmacistName: string;
  status: 'Cấp đủ' | 'Cấp một phần';
  recipientName: string;
  counselingStatus: string;
  deliveryMethod: string;
  notes: string;
  dispensedItems: {
    stt: number;
    drugName: string;
    strength: string;
    form: string;
    prescribedQty: number;
    dispensedQty: number;
  }[];
  timeline: { time: string; action: string }[];
}

export interface PatientHandoverGroup {
  id: string;
  patientName: string;
  patientCode: string;
  birthYear: number;
  gender: string;
  age: number;
  handoverCount: number;
  records: HandoverRecord[];
}

export const HANDOVER_PATIENTS_DATA: PatientHandoverGroup[] = [
  {
    id: 'p-021',
    patientName: 'Nguyễn Thị Mai',
    patientCode: 'BN250514-021',
    birthYear: 1994,
    gender: 'Nữ',
    age: 32,
    handoverCount: 3,
    records: [
      {
        id: 'ho-021-1',
        code: 'RX250514-021',
        prescriptionCode: 'RX250514-021',
        dispensingCode: 'MDR-250514-021',
        dateStr: '14/05/2026',
        timeStr: '10:32',
        patientName: 'Nguyễn Thị Mai',
        patientCode: 'BN250514-021',
        birthYear: 1994,
        gender: 'Nữ',
        age: 32,
        doctorName: 'BS. Trần Văn Dũng',
        pharmacistName: 'Lê Hoàng Minh',
        status: 'Cấp đủ',
        recipientName: 'Nguyễn Thị Mai',
        counselingStatus: 'Đã tư vấn',
        deliveryMethod: 'Tại quầy',
        notes: '—',
        dispensedItems: [
          { stt: 1, drugName: 'Paracetamol', strength: '500 mg', form: 'Viên nén', prescribedQty: 20, dispensedQty: 20 },
          { stt: 2, drugName: 'Cetirizine', strength: '10 mg', form: 'Viên nén', prescribedQty: 10, dispensedQty: 10 },
          { stt: 3, drugName: 'Omeprazole', strength: '20 mg', form: 'Viên nang', prescribedQty: 14, dispensedQty: 14 },
        ],
        timeline: [
          { time: '10:21', action: 'Soạn thuốc' },
          { time: '10:27', action: 'Kiểm tra' },
          { time: '10:30', action: 'Tư vấn' },
          { time: '10:32', action: 'Bàn giao' },
        ],
      },
      {
        id: 'ho-021-2',
        code: 'RX250402-044',
        prescriptionCode: 'RX250402-044',
        dispensingCode: 'MDR-250402-044',
        dateStr: '02/04/2026',
        timeStr: '09:18',
        patientName: 'Nguyễn Thị Mai',
        patientCode: 'BN250514-021',
        birthYear: 1994,
        gender: 'Nữ',
        age: 32,
        doctorName: 'BS. Trần Văn Dũng',
        pharmacistName: 'Phạm Thu Trang',
        status: 'Cấp đủ',
        recipientName: 'Nguyễn Thị Mai',
        counselingStatus: 'Đã tư vấn',
        deliveryMethod: 'Tại quầy',
        notes: '—',
        dispensedItems: [],
        timeline: [{ time: '09:18', action: 'Bàn giao' }],
      },
      {
        id: 'ho-021-3',
        code: 'RX250215-018',
        prescriptionCode: 'RX250215-018',
        dispensingCode: 'MDR-250215-018',
        dateStr: '15/02/2026',
        timeStr: '14:22',
        patientName: 'Nguyễn Thị Mai',
        patientCode: 'BN250514-021',
        birthYear: 1994,
        gender: 'Nữ',
        age: 32,
        doctorName: 'BS. Nguyễn Thanh Hà',
        pharmacistName: 'Lê Hoàng Minh',
        status: 'Cấp một phần',
        recipientName: 'Nguyễn Thị Mai',
        counselingStatus: 'Đã tư vấn',
        deliveryMethod: 'Tại quầy',
        notes: 'Thiếu 1 loại do hết hàng',
        dispensedItems: [],
        timeline: [{ time: '14:22', action: 'Bàn giao cấp một phần' }],
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
    handoverCount: 2,
    records: [],
  },
];
