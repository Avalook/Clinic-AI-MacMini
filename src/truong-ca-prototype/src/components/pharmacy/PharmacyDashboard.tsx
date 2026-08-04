import { useState } from 'react';
import {
  Search,
  CheckCircle2,
  Clock,
  RotateCcw,
  Save,
  ChevronLeft,
  ChevronRight,
  UserCheck,
  Calendar,
  Printer,
  Users,
  Activity,
  Plus,
  Download,
  AlertTriangle,
  FileCheck,
  PauseCircle,
  FileText,
  Pill,
  AlertOctagon,
  Phone,
} from 'lucide-react';
import {
  PHARMACY_PENDING_PRESCRIPTIONS,
  PREPARATION_ORDERS_DATA,
  HANDOVER_PATIENTS_DATA,
} from '../../data/pharmacy-mock-data';

interface PharmacyDashboardProps {
  onSwitchRole?: () => void;
}

export default function PharmacyDashboard({ onSwitchRole }: PharmacyDashboardProps) {
  const [activeTab, setActiveTab] = useState<'pending' | 'prep' | 'handover' | 'counseling'>('pending');
  const [collapsed, setCollapsed] = useState(false);

  // Tab 1: Pending Queue State
  const [pendingSearch, setPendingSearch] = useState('');
  const [selectedPendingId, setSelectedPendingId] = useState<string>('rx-021');

  // Tab 2: Preparation State
  const [selectedPrepId, setSelectedPrepId] = useState<string>('prep-021');

  // Tab 3: Handover State
  const [selectedHandoverPatientId, setSelectedHandoverPatientId] = useState<string>('p-021');
  const [selectedRecordId, setSelectedRecordId] = useState<string>('ho-021-1');

  const activePendingRx = PHARMACY_PENDING_PRESCRIPTIONS.find(r => r.id === selectedPendingId) || PHARMACY_PENDING_PRESCRIPTIONS[0];
  const activePrepOrder = PREPARATION_ORDERS_DATA.find(p => p.id === selectedPrepId) || PREPARATION_ORDERS_DATA[0];
  const activeHandoverPatient = HANDOVER_PATIENTS_DATA.find(p => p.id === selectedHandoverPatientId) || HANDOVER_PATIENTS_DATA[0];
  const activeHandoverRecord = activeHandoverPatient.records.find(r => r.id === selectedRecordId) || activeHandoverPatient.records[0] || {
    id: 'empty',
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
    timeline: [{ time: '10:32', action: 'Bàn giao' }],
  };

  return (
    <div style={{ display: 'flex', minHeight: '100vh', background: 'var(--surface-muted)' }}>
      {/* 1. SIDEBAR */}
      <aside
        style={{
          width: collapsed ? 68 : 240,
          minWidth: collapsed ? 68 : 240,
          background: 'var(--surface)',
          borderRight: '1px solid var(--line)',
          display: 'flex',
          flexDirection: 'column',
          height: '100vh',
          position: 'sticky',
          top: 0,
          transition: 'all 0.2s ease',
          zIndex: 20,
        }}
      >
        {/* Logo */}
        <div
          style={{
            padding: collapsed ? '18px 8px' : '18px 16px',
            borderBottom: '1px solid var(--line)',
            display: 'flex',
            alignItems: 'center',
            gap: 10,
            justifyContent: collapsed ? 'center' : 'flex-start',
          }}
        >
          <div
            style={{
              width: 36,
              height: 36,
              borderRadius: 10,
              background: 'linear-gradient(135deg, var(--brand-500), var(--brand-700))',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: 'white',
              fontWeight: 800,
              fontSize: 14,
              flexShrink: 0,
            }}
          >
            CA
          </div>
          {!collapsed && (
            <div>
              <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--ink)' }}>ClinicAI</div>
              <div style={{ fontSize: 9, color: 'var(--ink-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                Connected Clinic Workflow
              </div>
            </div>
          )}
        </div>

        {/* Role title */}
        {!collapsed && (
          <div style={{ padding: '16px 16px 8px', fontSize: 11, fontWeight: 700, color: 'var(--ink-muted)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
            NHÀ THUỐC
          </div>
        )}

        {/* Navigation Tabs */}
        <nav style={{ flex: 1, padding: '4px 8px', display: 'flex', flexDirection: 'column', gap: 2 }}>
          <button
            onClick={() => setActiveTab('pending')}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 10,
              padding: collapsed ? '10px' : '10px 12px',
              borderRadius: 'var(--radius-control)',
              border: 'none',
              background: activeTab === 'pending' ? 'var(--brand-50)' : 'transparent',
              color: activeTab === 'pending' ? 'var(--brand-700)' : 'var(--ink-soft)',
              fontSize: 13,
              fontWeight: activeTab === 'pending' ? 600 : 500,
              cursor: 'pointer',
              textAlign: 'left',
              width: '100%',
            }}
          >
            <FileText size={18} /> {!collapsed && 'Đơn thuốc chờ cấp'}
          </button>

          <button
            onClick={() => setActiveTab('prep')}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 10,
              padding: collapsed ? '10px' : '10px 12px',
              borderRadius: 'var(--radius-control)',
              border: 'none',
              background: activeTab === 'prep' ? 'var(--brand-50)' : 'transparent',
              color: activeTab === 'prep' ? 'var(--brand-700)' : 'var(--ink-soft)',
              fontSize: 13,
              fontWeight: activeTab === 'prep' ? 600 : 500,
              cursor: 'pointer',
              textAlign: 'left',
              width: '100%',
            }}
          >
            <Pill size={18} /> {!collapsed && 'Chuẩn bị thuốc'}
          </button>

          <button
            onClick={() => setActiveTab('handover')}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 10,
              padding: collapsed ? '10px' : '10px 12px',
              borderRadius: 'var(--radius-control)',
              border: 'none',
              background: activeTab === 'handover' ? 'var(--brand-50)' : 'transparent',
              color: activeTab === 'handover' ? 'var(--brand-700)' : 'var(--ink-soft)',
              fontSize: 13,
              fontWeight: activeTab === 'handover' ? 600 : 500,
              cursor: 'pointer',
              textAlign: 'left',
              width: '100%',
            }}
          >
            <FileCheck size={18} /> {!collapsed && 'Đã bàn giao'}
          </button>

          <button
            onClick={() => setActiveTab('counseling')}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 10,
              padding: collapsed ? '10px' : '10px 12px',
              borderRadius: 'var(--radius-control)',
              border: 'none',
              background: activeTab === 'counseling' ? 'var(--brand-50)' : 'transparent',
              color: activeTab === 'counseling' ? 'var(--brand-700)' : 'var(--ink-soft)',
              fontSize: 13,
              fontWeight: activeTab === 'counseling' ? 600 : 500,
              cursor: 'pointer',
              textAlign: 'left',
              width: '100%',
            }}
          >
            <UserCheck size={18} /> {!collapsed && 'Tư vấn dùng thuốc'}
          </button>

          {/* Switch Role Button */}
          {onSwitchRole && (
            <div style={{ marginTop: 'auto', paddingTop: 16 }}>
              <button
                onClick={onSwitchRole}
                className="btn btn-secondary"
                style={{ width: '100%', fontSize: 11, padding: '6px 8px', justifyContent: collapsed ? 'center' : 'flex-start' }}
              >
                <RotateCcw size={13} /> {!collapsed && 'Đổi vai trò'}
              </button>
            </div>
          )}
        </nav>

        {/* Pharmacist Profile */}
        <div style={{ padding: '12px 16px', borderTop: '1px solid var(--line)', display: 'flex', alignItems: 'center', gap: 10 }}>
          <div style={{ width: 32, height: 32, borderRadius: '50%', background: 'var(--brand-100)', color: 'var(--brand-700)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 11, fontWeight: 700 }}>
            LM
          </div>
          {!collapsed && (
            <div>
              <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--ink)' }}>Lê Hoàng Minh</div>
              <div style={{ fontSize: 10, color: 'var(--ink-muted)' }}>Dược sĩ nhà thuốc</div>
            </div>
          )}
        </div>

        {/* Collapse button */}
        <div style={{ padding: '8px', borderTop: '1px solid var(--line)' }}>
          <button
            onClick={() => setCollapsed(!collapsed)}
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: 6,
              width: '100%',
              padding: '6px',
              borderRadius: 'var(--radius-control)',
              border: '1px solid var(--line)',
              background: 'var(--surface-muted)',
              color: 'var(--ink-muted)',
              fontSize: 11,
              cursor: 'pointer',
            }}
          >
            {collapsed ? <ChevronRight size={14} /> : <ChevronLeft size={14} />}
            {!collapsed && 'Thu gọn'}
          </button>
        </div>
      </aside>

      {/* MAIN CONTAINER */}
      <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column' }}>
        {/* HEADER */}
        <header
          style={{
            background: 'var(--surface)',
            borderBottom: '1px solid var(--line)',
            padding: '12px 24px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          <div>
            <h1 style={{ fontSize: 18, fontWeight: 700, color: 'var(--ink)', margin: 0 }}>
              {activeTab === 'pending' && 'Đơn thuốc chờ cấp'}
              {activeTab === 'prep' && 'Chuẩn bị thuốc & Kiểm tra quy cách'}
              {activeTab === 'handover' && 'Lịch sử bàn giao thuốc'}
              {activeTab === 'counseling' && 'Tư vấn dùng thuốc'}
            </h1>
            <p style={{ fontSize: 12, color: 'var(--ink-muted)', margin: '2px 0 0' }}>
              {activeTab === 'pending' && 'Tiếp nhận đơn hợp lệ và xác định đơn đủ điều kiện chuẩn bị.'}
              {activeTab === 'prep' && 'Đối chiếu, soạn và kiểm tra thuốc theo đơn đã được phép cấp.'}
              {activeTab === 'handover' && 'Tra cứu bản ghi thuốc đã thực cấp cho từng bệnh nhân.'}
              {activeTab === 'counseling' && 'Hướng dẫn người bệnh và ghi nhận đã hiểu trước khi bàn giao.'}
            </p>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '6px 12px', background: 'var(--surface-muted)', borderRadius: 'var(--radius-control)', border: '1px solid var(--line)', fontSize: 12 }}>
              <Calendar size={14} color="var(--ink-muted)" />
              <span>Thứ Năm, 14/05/2026</span>
              <span style={{ margin: '0 4px', color: 'var(--line-strong)' }}>|</span>
              <Clock size={14} color="var(--ink-muted)" />
              <strong style={{ fontVariantNumeric: 'tabular-nums' }}>10:20</strong>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <div style={{ width: 34, height: 34, borderRadius: '50%', background: 'var(--brand-600)', color: 'white', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 12, fontWeight: 700 }}>
                LM
              </div>
              <div>
                <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--ink)' }}>Lê Hoàng Minh</div>
                <div style={{ fontSize: 11, color: 'var(--ink-muted)' }}>Dược sĩ</div>
              </div>
            </div>
          </div>
        </header>

        {/* BODY CONTENT */}
        <div style={{ padding: 20, display: 'flex', flexDirection: 'column', gap: 16, flex: 1 }}>

          {/* ========================================================================= */}
          {/* TAB 1: ĐƠN THUỐC CHỜ CẤP (MATCHING IMAGES 4 & 5)                          */}
          {/* ========================================================================= */}
          {activeTab === 'pending' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 16, flex: 1 }}>
              {/* Top 4 KPI Cards */}
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12 }}>
                {[
                  { label: 'Chờ cấp', value: 12, icon: Clock, color: 'var(--warning)', bg: 'var(--warning-bg)' },
                  { label: 'Đủ điều kiện', value: 9, icon: CheckCircle2, color: 'var(--success)', bg: 'var(--success-bg)' },
                  { label: 'Đang bị chặn', value: 3, icon: AlertOctagon, color: 'var(--danger)', bg: 'var(--danger-bg)' },
                  { label: 'Quá SLA', value: 2, icon: AlertTriangle, color: 'var(--danger)', bg: 'var(--danger-bg)' },
                ].map((kpi, idx) => {
                  const Icon = kpi.icon;
                  return (
                    <div key={idx} className="card" style={{ padding: '12px 16px', display: 'flex', alignItems: 'center', gap: 12 }}>
                      <div style={{ width: 36, height: 36, borderRadius: '50%', background: kpi.bg, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                        <Icon size={18} color={kpi.color} />
                      </div>
                      <div>
                        <div style={{ fontSize: 11, color: 'var(--ink-muted)' }}>{kpi.label}</div>
                        <div style={{ fontSize: 20, fontWeight: 700, color: 'var(--ink)', lineHeight: 1.1 }}>{kpi.value}</div>
                      </div>
                    </div>
                  );
                })}
              </div>

              {/* Master Layout: Left Queue, Middle Verification */}
              <div style={{ display: 'grid', gridTemplateColumns: '320px 1fr', gap: 16, flex: 1, alignItems: 'start' }}>
                {/* Left Queue List */}
                <div className="card" style={{ padding: 14, display: 'flex', flexDirection: 'column', gap: 12 }}>
                  <div style={{ display: 'flex', gap: 4, fontSize: 11 }}>
                    <button className="btn btn-primary" style={{ padding: '4px 8px' }}>Tất cả 12</button>
                    <button className="btn btn-secondary" style={{ padding: '4px 8px' }}>Đủ điều kiện 9</button>
                    <button className="btn btn-secondary" style={{ padding: '4px 8px' }}>Bị chặn 3</button>
                  </div>

                  <div style={{ position: 'relative' }}>
                    <Search size={13} style={{ position: 'absolute', left: 8, top: '50%', transform: 'translateY(-50%)', color: 'var(--ink-muted)' }} />
                    <input
                      type="search"
                      placeholder="Tìm bệnh nhân hoặc mã đơn"
                      value={pendingSearch}
                      onChange={(e) => setPendingSearch(e.target.value)}
                      style={{ paddingLeft: 26, width: '100%', fontSize: 11 }}
                    />
                  </div>

                  <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                    {PHARMACY_PENDING_PRESCRIPTIONS.map(rx => {
                      const isSelected = rx.id === activePendingRx.id;
                      return (
                        <div
                          key={rx.id}
                          onClick={() => setSelectedPendingId(rx.id)}
                          style={{
                            padding: 10,
                            borderRadius: 'var(--radius-control)',
                            border: isSelected ? '2px solid var(--brand-500)' : '1px solid var(--line)',
                            background: isSelected ? 'var(--brand-50)' : 'var(--surface)',
                            cursor: 'pointer',
                          }}
                        >
                          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, fontWeight: 700 }}>
                            <span>{rx.patientName}</span>
                            <span style={{ fontSize: 10, color: 'var(--ink-muted)' }}>⏱ {rx.waitTimeMinutes} phút</span>
                          </div>
                          <div style={{ fontSize: 10, color: 'var(--ink-muted)' }}>{rx.patientCode} · {rx.code}</div>
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 6 }}>
                            <span style={{ padding: '2px 6px', borderRadius: 4, background: rx.statusBg, color: rx.statusColor, fontSize: 9, fontWeight: 700 }}>
                              {rx.statusLabel}
                            </span>
                            <span style={{ fontSize: 10, color: 'var(--brand-600)', fontWeight: 600 }}>Hành động &gt;</span>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>

                {/* Middle Prescription Detail & Verification */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
                  <div className="card" style={{ padding: 16, display: 'flex', flexDirection: 'column', gap: 14 }}>
                    {/* Patient Header Banner */}
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid var(--line)', paddingBottom: 10 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                        <div style={{ width: 40, height: 40, borderRadius: '50%', background: 'var(--surface-sunken)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 14, fontWeight: 800 }}>
                          NT
                        </div>
                        <div>
                          <div style={{ fontSize: 15, fontWeight: 700, color: 'var(--ink)' }}>{activePendingRx.patientName}</div>
                          <div style={{ fontSize: 11, color: 'var(--ink-muted)' }}>{activePendingRx.birthYear} · Nữ · {activePendingRx.age} tuổi &nbsp;|&nbsp; Mã BN: {activePendingRx.patientCode}</div>
                        </div>
                      </div>

                      <div style={{ textAlign: 'right', fontSize: 11 }}>
                        <div style={{ color: 'var(--ink-muted)' }}>Bác sĩ kê đơn: <strong style={{ color: 'var(--ink)' }}>{activePendingRx.doctorName}</strong></div>
                        <div style={{ color: 'var(--ink-muted)' }}>Mã đơn: <strong>{activePendingRx.code}</strong> &nbsp;|&nbsp; Ngày: {activePendingRx.prescriptionDate} {activePendingRx.prescriptionTime}</div>
                      </div>
                    </div>

                    {/* Medicines List Table */}
                    <div>
                      <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--ink)', marginBottom: 6 }}>Danh sách thuốc kê đơn ({activePendingRx.items.length} thuốc)</div>
                      <div className="table-wrap">
                        <table>
                          <thead>
                            <tr>
                              <th>Thuốc</th>
                              <th>Cách dùng</th>
                              <th>Số lượng</th>
                              <th>Tồn kho</th>
                            </tr>
                          </thead>
                          <tbody>
                            {activePendingRx.items.map(item => (
                              <tr key={item.id}>
                                <td style={{ fontSize: 12, fontWeight: 700, color: 'var(--brand-700)' }}>{item.drugName}</td>
                                <td style={{ fontSize: 11 }}>{item.usageInstructions}</td>
                                <td style={{ fontSize: 11, fontWeight: 700 }}>{item.prescribedQty} {item.unit}</td>
                                <td style={{ fontSize: 11, color: 'var(--success)', fontWeight: 600 }}>{item.stockQty} hộp</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>

                    {/* Doctor Note */}
                    <div style={{ background: '#dbeafe', padding: 10, borderRadius: 6, fontSize: 11, color: '#1e40af' }}>
                      ℹ <strong>Hướng dẫn của bác sĩ — không được chỉnh sửa:</strong> {activePendingRx.doctorNote}
                    </div>

                    {/* Payment Conflict Banner (Image 5 Variant) */}
                    {activePendingRx.financials && !activePendingRx.financials.medsPaid && (
                      <div style={{ background: '#fef2f2', border: '1px solid #fca5a5', padding: 14, borderRadius: 8 }}>
                        <div style={{ fontSize: 13, fontWeight: 800, color: 'var(--danger)', marginBottom: 6, display: 'flex', alignItems: 'center', gap: 6 }}>
                          <AlertOctagon size={16} /> NGHĨA VỤ THANH TOÁN THUỐC CHƯA HOÀN TẤT
                        </div>
                        <div style={{ fontSize: 11, color: 'var(--ink)', marginBottom: 10 }}>
                          Vui lòng xác nhận thanh toán thuốc tại quầy thu ngân để tiếp tục cấp phát.
                        </div>
                        <button className="btn btn-primary" style={{ fontSize: 11, background: 'var(--brand-600)' }}>
                          <Phone size={13} /> Liên hệ thu ngân
                        </button>
                      </div>
                    )}

                    {/* Eligibility Checklist */}
                    <div style={{ borderTop: '1px solid var(--line)', paddingTop: 10 }}>
                      <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--ink)', marginBottom: 6 }}>Điều kiện cấp thuốc</div>
                      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6, fontSize: 11 }}>
                        <div style={{ color: 'var(--success)', fontWeight: 600 }}>✓ Đơn thuốc hợp lệ (Không có cảnh báo)</div>
                        <div style={{ color: 'var(--success)', fontWeight: 600 }}>✓ Đúng bệnh nhân (Khớp mã hồ sơ)</div>
                        <div style={{ color: 'var(--success)', fontWeight: 600 }}>✓ Đã được phép chuẩn bị</div>
                        <div style={{ color: 'var(--success)', fontWeight: 600 }}>✓ Tồn kho đủ ({activePendingRx.items.length}/{activePendingRx.items.length} mặt hàng)</div>
                      </div>
                    </div>
                  </div>

                  {/* Bottom Action Bar */}
                  <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
                    <button className="btn btn-secondary" style={{ fontSize: 12 }}><PauseCircle size={14} /> Tạm giữ</button>
                    <button
                      onClick={() => setActiveTab('prep')}
                      className="btn btn-primary"
                      style={{ fontSize: 12, padding: '10px 16px', background: 'var(--brand-600)' }}
                    >
                      <Plus size={14} /> Bắt đầu chuẩn bị
                    </button>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* ========================================================================= */}
          {/* TAB 2: CHUẨN BỊ THUỐC (MATCHING IMAGE 3)                                  */}
          {/* ========================================================================= */}
          {activeTab === 'prep' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 16, flex: 1 }}>
              {/* Top 4 KPI Cards */}
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12 }}>
                {[
                  { label: 'Đang chuẩn bị', value: 5, icon: Pill, color: 'var(--brand-600)', bg: 'var(--brand-50)' },
                  { label: 'Chờ kiểm tra', value: 4, icon: Clock, color: 'var(--warning)', bg: 'var(--warning-bg)' },
                  { label: 'Thiếu thuốc', value: 2, icon: AlertOctagon, color: 'var(--danger)', bg: 'var(--danger-bg)' },
                  { label: 'Sắp quá SLA', value: 3, icon: AlertTriangle, color: 'var(--danger)', bg: 'var(--danger-bg)' },
                ].map((kpi, idx) => {
                  const Icon = kpi.icon;
                  return (
                    <div key={idx} className="card" style={{ padding: '12px 16px', display: 'flex', alignItems: 'center', gap: 12 }}>
                      <div style={{ width: 36, height: 36, borderRadius: '50%', background: kpi.bg, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                        <Icon size={18} color={kpi.color} />
                      </div>
                      <div>
                        <div style={{ fontSize: 11, color: 'var(--ink-muted)' }}>{kpi.label}</div>
                        <div style={{ fontSize: 20, fontWeight: 700, color: 'var(--ink)', lineHeight: 1.1 }}>{kpi.value}</div>
                      </div>
                    </div>
                  );
                })}
              </div>

              {/* Master Layout */}
              <div style={{ display: 'grid', gridTemplateColumns: '260px 1fr 300px', gap: 16, flex: 1, alignItems: 'start' }}>
                {/* Left Queue */}
                <div className="card" style={{ padding: 14, display: 'flex', flexDirection: 'column', gap: 10 }}>
                  <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--ink)' }}>Danh sách phiếu</div>
                  <input type="search" placeholder="Tìm tên, mã BN hoặc mã đơn" style={{ width: '100%', fontSize: 11 }} />
                  
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                    {PREPARATION_ORDERS_DATA.map(p => {
                      const isSelected = p.id === activePrepOrder.id;
                      return (
                        <div
                          key={p.id}
                          onClick={() => setSelectedPrepId(p.id)}
                          style={{
                            padding: 8,
                            borderRadius: 'var(--radius-control)',
                            border: isSelected ? '2px solid var(--brand-500)' : '1px solid var(--line)',
                            background: isSelected ? 'var(--brand-50)' : 'var(--surface)',
                            cursor: 'pointer',
                          }}
                        >
                          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, fontWeight: 700 }}>
                            <span>{p.patientName}</span>
                            <span style={{ fontSize: 9, padding: '2px 4px', background: p.statusBg, color: p.statusColor, borderRadius: 4 }}>{p.statusLabel}</span>
                          </div>
                          <div style={{ fontSize: 10, color: 'var(--ink-muted)' }}>{p.prescriptionCode}</div>
                        </div>
                      );
                    })}
                  </div>
                </div>

                {/* Middle Prep Form */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
                  <div className="card" style={{ padding: 16, display: 'flex', flexDirection: 'column', gap: 14 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid var(--line)', paddingBottom: 10 }}>
                      <div>
                        <div style={{ fontSize: 15, fontWeight: 700, color: 'var(--ink)' }}>{activePrepOrder.patientName}</div>
                        <div style={{ fontSize: 11, color: 'var(--ink-muted)' }}>{activePrepOrder.patientCode} · {activePrepOrder.age} tuổi</div>
                      </div>
                      <div style={{ textAlign: 'right', fontSize: 11 }}>
                        <div>Mã đơn: <strong>{activePrepOrder.prescriptionCode}</strong></div>
                        <div>BS kê đơn: <strong>{activePrepOrder.doctorName}</strong></div>
                      </div>
                    </div>

                    <div style={{ background: '#fff7ed', border: '1px solid #ffedd5', padding: 8, borderRadius: 6, fontSize: 10, color: '#c2410c' }}>
                      ℹ Dược sĩ chỉ ghi số lượng thực cấp và chênh lệch; không tự đổi thuốc hoặc liều.
                    </div>

                    {/* Table */}
                    <div className="table-wrap">
                      <table>
                        <thead>
                          <tr>
                            <th>Thuốc theo đơn</th>
                            <th>Quy cách</th>
                            <th>SL kê</th>
                            <th>SL thực cấp</th>
                            <th>Lô/Hạn dùng</th>
                            <th>Kiểm tra</th>
                          </tr>
                        </thead>
                        <tbody>
                          {activePrepOrder.items.map((item, idx) => (
                            <tr key={idx}>
                              <td style={{ fontSize: 11, fontWeight: 700 }}>{item.drugName}</td>
                              <td style={{ fontSize: 10, color: 'var(--ink-muted)' }}>{item.spec}</td>
                              <td style={{ fontSize: 11, fontWeight: 700 }}>{item.prescribedQty} {item.unit}</td>
                              <td>
                                <input type="number" defaultValue={item.dispensedQty} style={{ width: 40, fontSize: 11, padding: 2, textAlign: 'center' }} /> {item.unit}
                              </td>
                              <td style={{ fontSize: 10 }}>{item.lotNumber}<br />{item.expiryDate}</td>
                              <td><span className="badge badge-success">✓ Đã đối chiếu</span></td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>

                  <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
                    <button className="btn btn-secondary" style={{ fontSize: 12, color: 'var(--danger)' }}><AlertTriangle size={14} /> Báo thiếu thuốc</button>
                    <button className="btn btn-secondary" style={{ fontSize: 12 }}><Save size={14} /> Lưu nháp</button>
                    <button
                      onClick={() => setActiveTab('counseling')}
                      className="btn btn-primary"
                      style={{ fontSize: 12, padding: '10px 16px', background: 'var(--brand-600)' }}
                    >
                      <CheckCircle2 size={14} /> Xác nhận đã chuẩn bị
                    </button>
                  </div>
                </div>

                {/* Right Checklist Column */}
                <div className="card" style={{ padding: 14, display: 'flex', flexDirection: 'column', gap: 12 }}>
                  <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--ink)' }}>Kiểm tra trước bàn giao (5/6)</div>
                  
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 6, fontSize: 11 }}>
                    <div style={{ color: 'var(--success)' }}>✓ 1. Đối chiếu bệnh nhân (Nguyễn Thị Mai, 32t)</div>
                    <div style={{ color: 'var(--success)' }}>✓ 2. Đối chiếu thuốc & hàm lượng (3/3 mặt hàng)</div>
                    <div style={{ color: 'var(--success)' }}>✓ 3. Đối chiếu số lượng (SL kê: 4, Thực cấp: 4)</div>
                    <div style={{ color: 'var(--success)' }}>✓ 4. Đối chiếu lô & hạn dùng (3/3 còn hạn)</div>
                    <div style={{ color: 'var(--success)' }}>✓ 5. Nhãn & hướng dẫn sử dụng (In đầy đủ)</div>
                    <div style={{ color: 'var(--ink-muted)' }}>○ 6. Xác nhận hoàn tất</div>
                  </div>

                  <div style={{ fontSize: 10, color: 'var(--ink-muted)', borderTop: '1px solid var(--line)', paddingTop: 8 }}>
                    Dược sĩ thực hiện: <strong>Lê Hoàng Minh</strong><br />
                    Bắt đầu lúc: 10:12 · Thời gian: 08:14
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* ========================================================================= */}
          {/* TAB 3: ĐÃ BÀN GIAO (MATCHING IMAGE 2)                                     */}
          {/* ========================================================================= */}
          {activeTab === 'handover' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 16, flex: 1 }}>
              {/* Top 4 KPI Cards */}
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12 }}>
                {[
                  { label: 'Bàn giao hôm nay', value: 28, icon: Users, color: 'var(--brand-600)', bg: 'var(--brand-50)' },
                  { label: 'Cấp đủ', value: 24, icon: CheckCircle2, color: 'var(--success)', bg: 'var(--success-bg)' },
                  { label: 'Cấp một phần', value: 4, icon: Clock, color: 'var(--warning)', bg: 'var(--warning-bg)' },
                  { label: 'Tổng bản ghi', value: '1.846', icon: FileCheck, color: 'var(--brand-600)', bg: 'var(--brand-50)' },
                ].map((kpi, idx) => {
                  const Icon = kpi.icon;
                  return (
                    <div key={idx} className="card" style={{ padding: '12px 16px', display: 'flex', alignItems: 'center', gap: 12 }}>
                      <div style={{ width: 36, height: 36, borderRadius: '50%', background: kpi.bg, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                        <Icon size={18} color={kpi.color} />
                      </div>
                      <div>
                        <div style={{ fontSize: 11, color: 'var(--ink-muted)' }}>{kpi.label}</div>
                        <div style={{ fontSize: 20, fontWeight: 700, color: 'var(--ink)', lineHeight: 1.1 }}>{kpi.value}</div>
                      </div>
                    </div>
                  );
                })}
              </div>

              {/* Master 3 Column Layout */}
              <div style={{ display: 'grid', gridTemplateColumns: '260px 1fr 340px', gap: 16, flex: 1, alignItems: 'start' }}>
                {/* Left Directory */}
                <div className="card" style={{ padding: 14, display: 'flex', flexDirection: 'column', gap: 10 }}>
                  <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--ink)' }}>Bệnh nhân</div>
                  <input type="search" placeholder="Tên, SĐT hoặc mã BN" style={{ width: '100%', fontSize: 11 }} />

                  <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                    {HANDOVER_PATIENTS_DATA.map(p => {
                      const isSelected = p.id === activeHandoverPatient.id;
                      return (
                        <div
                          key={p.id}
                          onClick={() => {
                            setSelectedHandoverPatientId(p.id);
                            if (p.records.length > 0) setSelectedRecordId(p.records[0].id);
                          }}
                          style={{
                            padding: 8,
                            borderRadius: 'var(--radius-control)',
                            border: isSelected ? '2px solid var(--brand-500)' : '1px solid var(--line)',
                            background: isSelected ? 'var(--brand-50)' : 'var(--surface)',
                            cursor: 'pointer',
                          }}
                        >
                          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, fontWeight: 700 }}>
                            <span>{p.patientName}</span>
                            <span className="badge badge-brand" style={{ fontSize: 9 }}>{p.handoverCount} lần cấp</span>
                          </div>
                          <div style={{ fontSize: 10, color: 'var(--ink-muted)' }}>{p.patientCode}</div>
                        </div>
                      );
                    })}
                  </div>
                </div>

                {/* Middle Patient Dispensing History */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
                  <div className="card" style={{ padding: 14, display: 'flex', flexDirection: 'column', gap: 12 }}>
                    <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--ink)' }}>Lịch sử cấp thuốc của {activeHandoverPatient.patientName}</div>
                    
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                      {activeHandoverPatient.records.map(rec => {
                        const isSelected = rec.id === activeHandoverRecord.id;
                        return (
                          <div
                            key={rec.id}
                            onClick={() => setSelectedRecordId(rec.id)}
                            style={{
                              padding: 12,
                              borderRadius: 8,
                              border: isSelected ? '2px solid var(--brand-500)' : '1px solid var(--line)',
                              background: isSelected ? 'var(--brand-50)' : 'var(--surface)',
                              cursor: 'pointer',
                            }}
                          >
                            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11 }}>
                              <span>{rec.dateStr} · {rec.timeStr}</span>
                              <span className="badge badge-success">{rec.status}</span>
                            </div>
                            <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--ink)', marginTop: 2 }}>Đơn thuốc {rec.prescriptionCode}</div>
                            <div style={{ fontSize: 10, color: 'var(--ink-muted)', marginTop: 2 }}>BS kê đơn: {rec.doctorName} &nbsp;|&nbsp; Dược sĩ: {rec.pharmacistName}</div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                </div>

                {/* Right Details Panel */}
                <div className="card" style={{ padding: 16, display: 'flex', flexDirection: 'column', gap: 12 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid var(--line)', paddingBottom: 10 }}>
                    <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--ink)' }}>Chi tiết bàn giao</div>
                    <span className="badge badge-success">✓ Đã bàn giao</span>
                  </div>

                  <div style={{ fontSize: 11, display: 'flex', flexDirection: 'column', gap: 4 }}>
                    <div><span style={{ color: 'var(--ink-muted)' }}>Bệnh nhân:</span> <strong>{activeHandoverPatient.patientName}</strong></div>
                    <div><span style={{ color: 'var(--ink-muted)' }}>Mã đơn thuốc:</span> <strong>{activeHandoverRecord.prescriptionCode}</strong></div>
                    <div><span style={{ color: 'var(--ink-muted)' }}>Dược sĩ thực cấp:</span> {activeHandoverRecord.pharmacistName}</div>
                    <div><span style={{ color: 'var(--ink-muted)' }}>Bác sĩ kê đơn:</span> {activeHandoverRecord.doctorName}</div>
                    <div><span style={{ color: 'var(--ink-muted)' }}>Thời gian bàn giao:</span> {activeHandoverRecord.dateStr} {activeHandoverRecord.timeStr}</div>
                  </div>

                  <div style={{ borderTop: '1px solid var(--line)', paddingTop: 10 }}>
                    <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--ink)', marginBottom: 6 }}>Danh sách thuốc đã cấp</div>
                    <div className="table-wrap">
                      <table>
                        <thead>
                          <tr>
                            <th>STT</th>
                            <th>Tên thuốc</th>
                            <th>Hàm lượng</th>
                            <th>SL kê</th>
                            <th>SL thực cấp</th>
                          </tr>
                        </thead>
                        <tbody>
                          {activeHandoverRecord.dispensedItems.map(item => (
                            <tr key={item.stt}>
                              <td style={{ fontSize: 10 }}>{item.stt}</td>
                              <td style={{ fontSize: 11, fontWeight: 700 }}>{item.drugName}</td>
                              <td style={{ fontSize: 10 }}>{item.strength}</td>
                              <td style={{ fontSize: 10 }}>{item.prescribedQty}</td>
                              <td style={{ fontSize: 10, fontWeight: 700 }}>{item.dispensedQty}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>

                  <div style={{ background: 'var(--surface-sunken)', padding: 6, borderRadius: 4, fontSize: 10, textAlign: 'center', color: 'var(--ink-muted)' }}>
                    🔒 Bản ghi cấp thuốc — chỉ đọc. Không thể chỉnh sửa, xóa...
                  </div>

                  <div style={{ display: 'flex', gap: 6 }}>
                    <button className="btn btn-secondary" style={{ flex: 1, fontSize: 10 }}><Printer size={12} /> In hướng dẫn</button>
                    <button className="btn btn-secondary" style={{ flex: 1, fontSize: 10 }}><Download size={12} /> Tải biên nhận</button>
                    <button className="btn btn-primary" style={{ flex: 1, fontSize: 10, background: 'var(--brand-600)' }}><FileText size={12} /> Xem chi tiết</button>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* ========================================================================= */}
          {/* TAB 4: TƯ VẤN DÙNG THUỐC (MATCHING IMAGE 1)                               */}
          {/* ========================================================================= */}
          {activeTab === 'counseling' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 16, flex: 1 }}>
              {/* Top 4 KPI Cards */}
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12 }}>
                {[
                  { label: 'Chờ tư vấn', value: 6, icon: Clock, color: 'var(--warning)', bg: 'var(--warning-bg)' },
                  { label: 'Đang tư vấn', value: 2, icon: Activity, color: 'var(--brand-600)', bg: 'var(--brand-50)' },
                  { label: 'Cần lưu ý', value: 3, icon: AlertTriangle, color: 'var(--danger)', bg: 'var(--danger-bg)' },
                  { label: 'Hoàn tất hôm nay', value: 25, icon: CheckCircle2, color: 'var(--success)', bg: 'var(--success-bg)' },
                ].map((kpi, idx) => {
                  const Icon = kpi.icon;
                  return (
                    <div key={idx} className="card" style={{ padding: '12px 16px', display: 'flex', alignItems: 'center', gap: 12 }}>
                      <div style={{ width: 36, height: 36, borderRadius: '50%', background: kpi.bg, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                        <Icon size={18} color={kpi.color} />
                      </div>
                      <div>
                        <div style={{ fontSize: 11, color: 'var(--ink-muted)' }}>{kpi.label}</div>
                        <div style={{ fontSize: 20, fontWeight: 700, color: 'var(--ink)', lineHeight: 1.1 }}>{kpi.value}</div>
                      </div>
                    </div>
                  );
                })}
              </div>

              {/* Master Layout */}
              <div style={{ display: 'grid', gridTemplateColumns: '280px 1fr 300px', gap: 16, flex: 1, alignItems: 'start' }}>
                {/* Left Queue */}
                <div className="card" style={{ padding: 14, display: 'flex', flexDirection: 'column', gap: 10 }}>
                  <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--ink)' }}>Danh sách chờ tư vấn</div>
                  <input type="search" placeholder="Tìm tên bệnh nhân hoặc mã đơn" style={{ width: '100%', fontSize: 11 }} />

                  <div style={{ display: 'flex', gap: 4, fontSize: 10 }}>
                    <button className="btn btn-primary" style={{ padding: '2px 6px' }}>Tất cả 6</button>
                    <button className="btn btn-secondary" style={{ padding: '2px 6px' }}>Ưu tiên 2</button>
                    <button className="btn btn-secondary" style={{ padding: '2px 6px' }}>Thường 4</button>
                  </div>

                  <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                    {PHARMACY_PENDING_PRESCRIPTIONS.map(rx => {
                      const isSelected = rx.id === activePendingRx.id;
                      return (
                        <div
                          key={rx.id}
                          onClick={() => setSelectedPendingId(rx.id)}
                          style={{
                            padding: 8,
                            borderRadius: 'var(--radius-control)',
                            border: isSelected ? '2px solid var(--brand-500)' : '1px solid var(--line)',
                            background: isSelected ? 'var(--brand-50)' : 'var(--surface)',
                            cursor: 'pointer',
                          }}
                        >
                          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, fontWeight: 700 }}>
                            <span>{rx.patientName}</span>
                            <span style={{ fontSize: 9, padding: '2px 4px', background: '#ffedd5', color: '#c2410c', borderRadius: 4 }}>Chờ tư vấn</span>
                          </div>
                          <div style={{ fontSize: 10, color: 'var(--ink-muted)' }}>{rx.code} · {rx.doctorName}</div>
                        </div>
                      );
                    })}
                  </div>
                </div>

                {/* Middle Counseling Form */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
                  <div className="card" style={{ padding: 16, display: 'flex', flexDirection: 'column', gap: 14 }}>
                    <div style={{ background: '#dbeafe', padding: 10, borderRadius: 6, fontSize: 11, color: '#1e40af' }}>
                      ℹ Chỉ định của bác sĩ được khóa; dược sĩ chỉ bổ sung nội dung hướng dẫn và ghi nhận.
                    </div>

                    {/* Detailed Drug Counseling Blocks */}
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                      {activePendingRx.items.map((item) => (
                        <div key={item.id} style={{ border: '1px solid var(--line)', padding: 12, borderRadius: 8, background: 'var(--surface)' }}>
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                            <div>
                              <strong style={{ fontSize: 13, color: 'var(--brand-700)' }}>{item.drugName}</strong>
                              <div style={{ fontSize: 11, color: 'var(--ink-muted)' }}>{item.usageInstructions}</div>
                            </div>
                            <span style={{ fontSize: 10, color: 'var(--ink-muted)', background: 'var(--surface-sunken)', padding: '2px 6px', borderRadius: 4 }}>
                              🔒 Chỉ định bác sĩ
                            </span>
                          </div>

                          {item.counseling && (
                            <div style={{ display: 'flex', flexDirection: 'column', gap: 6, fontSize: 11, background: 'var(--surface-sunken)', padding: 10, borderRadius: 6 }}>
                              <label style={{ display: 'flex', gap: 6 }}><input type="checkbox" defaultChecked /> <strong>Thời điểm dùng:</strong> {item.counseling.timing}</label>
                              <label style={{ display: 'flex', gap: 6 }}><input type="checkbox" defaultChecked /> <strong>Cách dùng:</strong> {item.counseling.method}</label>
                              <label style={{ display: 'flex', gap: 6 }}><input type="checkbox" defaultChecked /> <strong>Quên liều:</strong> {item.counseling.missedDose}</label>
                              <label style={{ display: 'flex', gap: 6 }}><input type="checkbox" defaultChecked /> <strong>Tác dụng KMM:</strong> {item.counseling.sideEffects}</label>
                              <label style={{ display: 'flex', gap: 6 }}><input type="checkbox" defaultChecked /> <strong>Tương tác / lưu ý:</strong> {item.counseling.interactions}</label>
                            </div>
                          )}
                        </div>
                      ))}
                    </div>

                    {/* Patient Confirmation Checklist */}
                    <div style={{ borderTop: '1px solid var(--line)', paddingTop: 10 }}>
                      <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--ink)', marginBottom: 6 }}>Xác nhận người bệnh</div>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: 11 }}>
                        <label style={{ display: 'flex', alignItems: 'center', gap: 6 }}><input type="checkbox" defaultChecked /> Đã nhắc lại đúng cách dùng</label>
                        <label style={{ display: 'flex', alignItems: 'center', gap: 6 }}><input type="checkbox" defaultChecked /> Đã hiểu các lưu ý</label>
                        <label style={{ display: 'flex', alignItems: 'center', gap: 6 }}><input type="checkbox" defaultChecked /> Đã nhận tài liệu hướng dẫn</label>
                      </div>
                    </div>

                    {/* Notes Textarea */}
                    <div>
                      <label style={{ fontSize: 11, fontWeight: 700, color: 'var(--ink)', display: 'block', marginBottom: 4 }}>Ghi chú tư vấn (tùy chọn)</label>
                      <textarea placeholder="Nhập ghi chú về nội dung tư vấn, câu hỏi của người bệnh..." rows={2} style={{ width: '100%', fontSize: 11 }} />
                    </div>
                  </div>

                  <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
                    <button className="btn btn-secondary" style={{ fontSize: 12 }}><Save size={14} /> Lưu nháp</button>
                    <button className="btn btn-secondary" style={{ fontSize: 12 }}><Printer size={14} /> In hướng dẫn</button>
                    <button
                      onClick={() => setActiveTab('handover')}
                      className="btn btn-primary"
                      style={{ fontSize: 12, padding: '10px 16px', background: 'var(--brand-600)' }}
                    >
                      <CheckCircle2 size={14} /> Xác nhận đã tư vấn & bàn giao
                    </button>
                  </div>
                </div>

                {/* Right Info & Progress Column */}
                <div className="card" style={{ padding: 14, display: 'flex', flexDirection: 'column', gap: 12 }}>
                  <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--ink)' }}>Thông tin người bệnh</div>
                  
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                    <div style={{ width: 36, height: 36, borderRadius: '50%', background: 'var(--brand-50)', color: 'var(--brand-700)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 12, fontWeight: 800 }}>
                      NT
                    </div>
                    <div>
                      <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--ink)' }}>{activePendingRx.patientName}</div>
                      <div style={{ fontSize: 10, color: 'var(--ink-muted)' }}>1994 · Nữ · 32 tuổi &nbsp;|&nbsp; {activePendingRx.patientCode}</div>
                    </div>
                  </div>

                  <div style={{ fontSize: 11, display: 'flex', flexDirection: 'column', gap: 4, background: 'var(--surface-sunken)', padding: 8, borderRadius: 6 }}>
                    <div><span style={{ color: 'var(--ink-muted)' }}>Mã đơn thuốc:</span> <strong>{activePendingRx.code}</strong></div>
                    <div><span style={{ color: 'var(--ink-muted)' }}>Bác sĩ kê:</span> {activePendingRx.doctorName}</div>
                  </div>

                  <div>
                    <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--ink)', marginBottom: 2 }}>Dị ứng thuốc</div>
                    <div style={{ fontSize: 11, color: 'var(--success)' }}>Không ghi nhận</div>
                  </div>

                  <div>
                    <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--ink)', marginBottom: 2 }}>Tình trạng chuẩn bị</div>
                    <div style={{ fontSize: 11, color: 'var(--success)', fontWeight: 600 }}>✓ Đã kiểm tra đủ thuốc (3/3 thuốc)</div>
                  </div>

                  <div>
                    <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--ink)', marginBottom: 4 }}>Tiến độ tư vấn</div>
                    <div style={{ height: 6, background: 'var(--line)', borderRadius: 3, overflow: 'hidden' }}>
                      <div style={{ width: '87.5%', height: '100%', background: 'var(--brand-600)' }} />
                    </div>
                    <div style={{ fontSize: 10, color: 'var(--ink-muted)', marginTop: 2, textAlign: 'right' }}>7 / 8 tiêu chí</div>
                  </div>

                  <div style={{ background: '#dbeafe', padding: 8, borderRadius: 6, fontSize: 10, color: '#1e40af' }}>
                    ℹ Dược sĩ không được thay đổi thuốc, liều dùng hoặc chỉ định của bác sĩ.
                  </div>
                </div>
              </div>
            </div>
          )}

        </div>
      </div>
    </div>
  );
}
