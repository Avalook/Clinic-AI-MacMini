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
  AlertOctagon,
  Printer,
  User,
  Users,
  Sparkles,
  Stethoscope,
  Activity,
  Plus,
  Lock,
  Download,
  Eye,
  AlertTriangle,
  Phone,
  FileCheck,
  Zap,
  Image as ImageIcon
} from 'lucide-react';
import {
  DOCTOR_PROFILES,
  GENERAL_PATIENTS,
  SIGNED_RESULTS,
  OBGYN_EXAM_DATA,
  ULTRASOUND_ITEMS,
  type DoctorType,
} from '../../data/doctor-mock-data';

interface DoctorDashboardProps {
  onSwitchRole?: () => void;
}

export default function DoctorDashboard({ onSwitchRole }: DoctorDashboardProps) {
  // Doctor specialty switcher state ('general' | 'obgyn' | 'ultrasound')
  const [doctorSpecialty, setDoctorSpecialty] = useState<DoctorType>('general');
  const [activeTab, setActiveTab] = useState<string>('today_encounters');
  const [collapsed, setCollapsed] = useState(false);

  // General Doctor state
  const [generalSearch, setGeneralSearch] = useState('');
  const [selectedGeneralId, setSelectedGeneralId] = useState<string>('dr-021');
  const [emrTab, setEmrTab] = useState<'exam' | 'orders' | 'results' | 'prescription' | 'payment'>('exam');

  // Signed Results Registry state
  const [signedSearch, setSignedSearch] = useState('');
  const [selectedSignedId, setSelectedSignedId] = useState<string>('sr-021');

  // OB-GYN Specialist state
  const [obgynOrders, setObgynOrders] = useState(OBGYN_EXAM_DATA.selectedOrders);
  const [costBlocked, setCostBlocked] = useState(OBGYN_EXAM_DATA.costConflictBlocked);

  // Ultrasound Specialist state
  const [selectedUsId, setSelectedUsId] = useState<string>('us-101');
  const [usFindings, setUsFindings] = useState(ULTRASOUND_ITEMS[0].findings);
  const [usConclusion, setUsConclusion] = useState(ULTRASOUND_ITEMS[0].conclusion);

  const activeDoctor = DOCTOR_PROFILES[doctorSpecialty];
  const activeGeneralPatient = GENERAL_PATIENTS.find(p => p.id === selectedGeneralId) || GENERAL_PATIENTS[0];
  const activeSignedRecord = SIGNED_RESULTS.find(r => r.id === selectedSignedId) || SIGNED_RESULTS[0];
  const activeUsItem = ULTRASOUND_ITEMS.find(u => u.id === selectedUsId) || ULTRASOUND_ITEMS[0];

  const totalObgynPrice = obgynOrders.filter(o => o.checked).reduce((acc, curr) => acc + curr.price, 0);

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
            {doctorSpecialty === 'general' && 'KHÁM BÁC SĨ'}
            {doctorSpecialty === 'obgyn' && 'BÁC SĨ PHỤ KHOA'}
            {doctorSpecialty === 'ultrasound' && 'BÁC SĨ SIÊU ÂM'}
          </div>
        )}

        {/* Nav Links based on Specialty */}
        <nav style={{ flex: 1, padding: '4px 8px', display: 'flex', flexDirection: 'column', gap: 2 }}>
          {doctorSpecialty === 'general' && (
            <>
              <button
                onClick={() => setActiveTab('patient_list')}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 10,
                  padding: collapsed ? '10px' : '10px 12px',
                  borderRadius: 'var(--radius-control)',
                  border: 'none',
                  background: activeTab === 'patient_list' ? 'var(--brand-50)' : 'transparent',
                  color: activeTab === 'patient_list' ? 'var(--brand-700)' : 'var(--ink-soft)',
                  fontSize: 13,
                  fontWeight: activeTab === 'patient_list' ? 600 : 500,
                  cursor: 'pointer',
                  textAlign: 'left',
                  width: '100%',
                }}
              >
                <User size={18} /> {!collapsed && 'Danh sách bệnh nhân'}
              </button>
              <button
                onClick={() => setActiveTab('today_encounters')}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 10,
                  padding: collapsed ? '10px' : '10px 12px',
                  borderRadius: 'var(--radius-control)',
                  border: 'none',
                  background: activeTab === 'today_encounters' ? 'var(--brand-50)' : 'transparent',
                  color: activeTab === 'today_encounters' ? 'var(--brand-700)' : 'var(--ink-soft)',
                  fontSize: 13,
                  fontWeight: activeTab === 'today_encounters' ? 600 : 500,
                  cursor: 'pointer',
                  textAlign: 'left',
                  width: '100%',
                }}
              >
                <Stethoscope size={18} /> {!collapsed && 'Danh sách khám hôm nay'}
              </button>
              <button
                onClick={() => setActiveTab('signed_results')}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 10,
                  padding: collapsed ? '10px' : '10px 12px',
                  borderRadius: 'var(--radius-control)',
                  border: 'none',
                  background: activeTab === 'signed_results' ? 'var(--brand-50)' : 'transparent',
                  color: activeTab === 'signed_results' ? 'var(--brand-700)' : 'var(--ink-soft)',
                  fontSize: 13,
                  fontWeight: activeTab === 'signed_results' ? 600 : 500,
                  cursor: 'pointer',
                  textAlign: 'left',
                  width: '100%',
                }}
              >
                <FileCheck size={18} /> {!collapsed && 'Kết quả đã ký'}
              </button>
            </>
          )}

          {doctorSpecialty === 'obgyn' && (
            <>
              <button
                onClick={() => setActiveTab('gyn_exam')}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 10,
                  padding: collapsed ? '10px' : '10px 12px',
                  borderRadius: 'var(--radius-control)',
                  border: 'none',
                  background: activeTab === 'gyn_exam' ? 'var(--brand-50)' : 'transparent',
                  color: activeTab === 'gyn_exam' ? 'var(--brand-700)' : 'var(--ink-soft)',
                  fontSize: 13,
                  fontWeight: activeTab === 'gyn_exam' ? 600 : 500,
                  cursor: 'pointer',
                  textAlign: 'left',
                  width: '100%',
                }}
              >
                <Stethoscope size={18} /> {!collapsed && 'Khám phụ khoa & Order'}
              </button>
              <button
                onClick={() => setActiveTab('signed_results')}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 10,
                  padding: collapsed ? '10px' : '10px 12px',
                  borderRadius: 'var(--radius-control)',
                  border: 'none',
                  background: activeTab === 'signed_results' ? 'var(--brand-50)' : 'transparent',
                  color: activeTab === 'signed_results' ? 'var(--brand-700)' : 'var(--ink-soft)',
                  fontSize: 13,
                  fontWeight: activeTab === 'signed_results' ? 600 : 500,
                  cursor: 'pointer',
                  textAlign: 'left',
                  width: '100%',
                }}
              >
                <FileCheck size={18} /> {!collapsed && 'Kết quả đã ký'}
              </button>
            </>
          )}

          {doctorSpecialty === 'ultrasound' && (
            <>
              <button
                onClick={() => setActiveTab('ultrasound_work')}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 10,
                  padding: collapsed ? '10px' : '10px 12px',
                  borderRadius: 'var(--radius-control)',
                  border: 'none',
                  background: activeTab === 'ultrasound_work' ? 'var(--brand-50)' : 'transparent',
                  color: activeTab === 'ultrasound_work' ? 'var(--brand-700)' : 'var(--ink-soft)',
                  fontSize: 13,
                  fontWeight: activeTab === 'ultrasound_work' ? 600 : 500,
                  cursor: 'pointer',
                  textAlign: 'left',
                  width: '100%',
                }}
              >
                <Activity size={18} /> {!collapsed && 'Phòng siêu âm CĐHA'}
              </button>
              <button
                onClick={() => setActiveTab('signed_results')}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 10,
                  padding: collapsed ? '10px' : '10px 12px',
                  borderRadius: 'var(--radius-control)',
                  border: 'none',
                  background: activeTab === 'signed_results' ? 'var(--brand-50)' : 'transparent',
                  color: activeTab === 'signed_results' ? 'var(--brand-700)' : 'var(--ink-soft)',
                  fontSize: 13,
                  fontWeight: activeTab === 'signed_results' ? 600 : 500,
                  cursor: 'pointer',
                  textAlign: 'left',
                  width: '100%',
                }}
              >
                <FileCheck size={18} /> {!collapsed && 'Phiếu siêu âm đã ký'}
              </button>
            </>
          )}

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

        {/* Collapse button */}
        <div style={{ padding: '12px 8px', borderTop: '1px solid var(--line)' }}>
          <button
            onClick={() => setCollapsed(!collapsed)}
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: 6,
              width: '100%',
              padding: '8px',
              borderRadius: 'var(--radius-control)',
              border: '1px solid var(--line)',
              background: 'var(--surface-muted)',
              color: 'var(--ink-muted)',
              fontSize: 12,
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
              {doctorSpecialty === 'general' && activeTab === 'today_encounters' && 'Danh sách khám bệnh hôm nay'}
              {doctorSpecialty === 'general' && activeTab === 'patient_list' && 'Danh sách bệnh nhân'}
              {doctorSpecialty === 'general' && activeTab === 'signed_results' && 'Kết quả đã ký'}
              {doctorSpecialty === 'obgyn' && 'Khám phụ khoa & Order composer'}
              {doctorSpecialty === 'ultrasound' && 'Phòng siêu âm — Chẩn đoán hình ảnh'}
            </h1>
            <p style={{ fontSize: 12, color: 'var(--ink-muted)', margin: '2px 0 0' }}>
              {activeDoctor.description}
            </p>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
            {/* Specialty Sub-switcher */}
            <div style={{ display: 'flex', gap: 4, background: 'var(--surface-sunken)', padding: 3, borderRadius: 'var(--radius-control)' }}>
              {[
                { id: 'general' as const, label: 'Đa khoa', doc: 'BS. Dũng' },
                { id: 'obgyn' as const, label: 'Phụ khoa', doc: 'BS. Lan' },
                { id: 'ultrasound' as const, label: 'Siêu âm', doc: 'BS. Nam' },
              ].map(s => (
                <button
                  key={s.id}
                  onClick={() => {
                    setDoctorSpecialty(s.id);
                    if (s.id === 'obgyn') setActiveTab('gyn_exam');
                    else if (s.id === 'ultrasound') setActiveTab('ultrasound_work');
                    else setActiveTab('today_encounters');
                  }}
                  style={{
                    padding: '4px 10px',
                    fontSize: 11,
                    fontWeight: doctorSpecialty === s.id ? 700 : 500,
                    borderRadius: 6,
                    border: 'none',
                    background: doctorSpecialty === s.id ? 'var(--surface)' : 'transparent',
                    color: doctorSpecialty === s.id ? 'var(--brand-700)' : 'var(--ink-muted)',
                    boxShadow: doctorSpecialty === s.id ? 'var(--shadow-panel)' : 'none',
                    cursor: 'pointer',
                  }}
                >
                  {s.label} ({s.doc})
                </button>
              ))}
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '6px 12px', background: 'var(--surface-muted)', borderRadius: 'var(--radius-control)', border: '1px solid var(--line)', fontSize: 12 }}>
              <Calendar size={14} color="var(--ink-muted)" />
              <span>Thứ Năm, 14/05/2026</span>
              <span style={{ margin: '0 4px', color: 'var(--line-strong)' }}>|</span>
              <Clock size={14} color="var(--ink-muted)" />
              <strong style={{ fontVariantNumeric: 'tabular-nums' }}>10:20</strong>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <div style={{ width: 34, height: 34, borderRadius: '50%', background: 'var(--brand-600)', color: 'white', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 12, fontWeight: 700 }}>
                {activeDoctor.avatarText}
              </div>
              <div>
                <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--ink)' }}>{activeDoctor.name}</div>
                <div style={{ fontSize: 11, color: 'var(--ink-muted)' }}>{activeDoctor.title}</div>
              </div>
            </div>
          </div>
        </header>

        {/* CONTENT BODY */}
        <div style={{ padding: 20, display: 'flex', flexDirection: 'column', gap: 16, flex: 1 }}>

          {/* ========================================================================= */}
          {/* VIEW 1: BÁC SĨ ĐA KHOA — DANH SÁCH KHÁM HÔM NAY (MATCHING IMAGE 2)          */}
          {/* ========================================================================= */}
          {doctorSpecialty === 'general' && activeTab === 'today_encounters' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 16, flex: 1 }}>
              {/* KPI Cards */}
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12 }}>
                {[
                  { label: 'Lịch hôm nay', value: 24, icon: Calendar, color: 'var(--brand-600)', bg: 'var(--brand-50)' },
                  { label: 'Chờ khám', value: 7, icon: Clock, color: 'var(--warning)', bg: 'var(--warning-bg)' },
                  { label: 'Đang khám', value: 3, icon: UserCheck, color: 'var(--brand-600)', bg: 'var(--brand-50)' },
                  { label: 'Chờ kết quả', value: 5, icon: Activity, color: 'var(--brand-600)', bg: 'var(--brand-50)' },
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

              {/* 3 Columns Workspace */}
              <div style={{ display: 'grid', gridTemplateColumns: '260px 1fr 280px', gap: 16, flex: 1, alignItems: 'start' }}>
                {/* Left Queue */}
                <div className="card" style={{ padding: 14, display: 'flex', flexDirection: 'column', gap: 12 }}>
                  <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--ink)' }}>Hàng đợi hôm nay</div>
                  
                  <div style={{ position: 'relative' }}>
                    <Search size={13} style={{ position: 'absolute', left: 8, top: '50%', transform: 'translateY(-50%)', color: 'var(--ink-muted)' }} />
                    <input
                      type="search"
                      placeholder="Tìm bệnh nhân hoặc mã hồ sơ"
                      value={generalSearch}
                      onChange={(e) => setGeneralSearch(e.target.value)}
                      style={{ paddingLeft: 26, width: '100%', fontSize: 11 }}
                    />
                  </div>

                  <div style={{ display: 'flex', flexDirection: 'column', gap: 10, maxHeight: 600, overflowY: 'auto' }}>
                    {/* Waiting */}
                    <div>
                      <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--ink-muted)', textTransform: 'uppercase', marginBottom: 4 }}>Chờ khám (7)</div>
                      {GENERAL_PATIENTS.map(p => (
                        <div
                          key={p.id}
                          onClick={() => setSelectedGeneralId(p.id)}
                          style={{
                            padding: 8,
                            borderRadius: 'var(--radius-control)',
                            border: p.id === selectedGeneralId ? '2px solid var(--brand-500)' : '1px solid var(--line)',
                            background: p.id === selectedGeneralId ? 'var(--brand-50)' : 'var(--surface)',
                            marginBottom: 4,
                            cursor: 'pointer',
                          }}
                        >
                          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, fontWeight: 700 }}>
                            <span>{p.name}</span>
                            <span style={{ fontSize: 10, color: 'var(--ink-muted)' }}>{p.appointmentTime}</span>
                          </div>
                          <div style={{ fontSize: 10, color: 'var(--ink-muted)' }}>{p.patientCode} · {p.age} tuổi</div>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>

                {/* Middle EMR Form */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
                  <div className="card" style={{ padding: 16 }}>
                    {/* Patient Header Banner */}
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid var(--line)', paddingBottom: 12, marginBottom: 12 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                        <div style={{ width: 40, height: 40, borderRadius: '50%', background: 'var(--surface-sunken)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 800, fontSize: 14, color: 'var(--ink)' }}>
                          NT
                        </div>
                        <div>
                          <div style={{ fontSize: 15, fontWeight: 700, color: 'var(--ink)' }}>{activeGeneralPatient.name}</div>
                          <div style={{ fontSize: 11, color: 'var(--ink-muted)' }}>
                            1994 · Nữ · 32 tuổi &nbsp;|&nbsp; {activeGeneralPatient.patientCode} · {activeGeneralPatient.visitCode}
                          </div>
                        </div>
                      </div>

                      {/* Vitals Summary Bar */}
                      <div style={{ display: 'flex', gap: 12, fontSize: 11, background: 'var(--surface-sunken)', padding: '6px 12px', borderRadius: 8 }}>
                        <div><span style={{ color: 'var(--ink-muted)' }}>Mạch</span> <strong style={{ color: 'var(--ink)' }}>{activeGeneralPatient.vitals.pulse}</strong> lần/p</div>
                        <div><span style={{ color: 'var(--ink-muted)' }}>HA</span> <strong style={{ color: 'var(--ink)' }}>{activeGeneralPatient.vitals.bp}</strong> mmHg</div>
                        <div><span style={{ color: 'var(--ink-muted)' }}>Nhiệt độ</span> <strong style={{ color: 'var(--ink)' }}>{activeGeneralPatient.vitals.temp}</strong> °C</div>
                        <div><span style={{ color: 'var(--ink-muted)' }}>Cân nặng</span> <strong style={{ color: 'var(--ink)' }}>{activeGeneralPatient.vitals.weight}</strong> kg</div>
                        <div style={{ color: 'var(--danger)', fontWeight: 600 }}>⚠ Dị ứng: {activeGeneralPatient.vitals.allergy}</div>
                      </div>
                    </div>

                    {/* EMR Tabs */}
                    <div style={{ display: 'flex', gap: 4, borderBottom: '1px solid var(--line)', paddingBottom: 8, marginBottom: 12 }}>
                      {[
                        { id: 'exam', label: 'Khám bác sĩ' },
                        { id: 'orders', label: 'Chỉ định' },
                        { id: 'results', label: 'Kết quả' },
                        { id: 'prescription', label: 'Đơn thuốc' },
                        { id: 'payment', label: 'Thuốc & thanh toán' },
                      ].map(t => (
                        <button
                          key={t.id}
                          onClick={() => setEmrTab(t.id as any)}
                          className={emrTab === t.id ? 'btn btn-primary' : 'btn btn-secondary'}
                          style={{ padding: '4px 12px', fontSize: 11 }}
                        >
                          {t.label}
                        </button>
                      ))}
                    </div>

                    {/* 5 EMR Form Blocks Grid */}
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14, marginBottom: 14 }}>
                      {/* Block 1: Lý do khám */}
                      <div style={{ background: 'var(--surface-sunken)', padding: 12, borderRadius: 8 }}>
                        <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--ink)', marginBottom: 6 }}>1. Lý do khám</div>
                        <div style={{ fontSize: 11, color: 'var(--ink)', marginBottom: 8 }}>{activeGeneralPatient.clinicalReason}</div>
                        <div style={{ fontSize: 10, color: 'var(--brand-600)', fontWeight: 600, display: 'flex', alignItems: 'center', gap: 4, cursor: 'pointer' }}>
                          <Sparkles size={12} /> Gợi ý AI — bản nháp
                        </div>
                      </div>

                      {/* Block 3: Khám lâm sàng */}
                      <div style={{ background: 'var(--surface-sunken)', padding: 12, borderRadius: 8 }}>
                        <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--ink)', marginBottom: 6 }}>3. Khám lâm sàng</div>
                        <div style={{ fontSize: 11, color: 'var(--ink)', whiteSpace: 'pre-line', marginBottom: 8 }}>{activeGeneralPatient.physicalExam}</div>
                        <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--brand-700)' }}>Kết luận khám: Viêm âm đạo mức độ nhẹ, nghi do nấm.</div>
                      </div>

                      {/* Block 2: Bệnh sử */}
                      <div style={{ background: 'var(--surface-sunken)', padding: 12, borderRadius: 8 }}>
                        <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--ink)', marginBottom: 6 }}>2. Bệnh sử</div>
                        <div style={{ fontSize: 11, color: 'var(--ink)', whiteSpace: 'pre-line', marginBottom: 8 }}>{activeGeneralPatient.medicalHistory}</div>
                        <div style={{ fontSize: 10, color: 'var(--brand-600)', fontWeight: 600, display: 'flex', alignItems: 'center', gap: 4, cursor: 'pointer' }}>
                          <Sparkles size={12} /> Gợi ý AI — bản nháp
                        </div>
                      </div>

                      {/* Block 4: Chẩn đoán */}
                      <div style={{ background: 'var(--surface-sunken)', padding: 12, borderRadius: 8 }}>
                        <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--ink)', marginBottom: 6 }}>4. Chẩn đoán</div>
                        <div style={{ fontSize: 11, color: 'var(--ink)', marginBottom: 4 }}><strong>Chẩn đoán chính:</strong> {activeGeneralPatient.diagnosisMain}</div>
                        <div style={{ fontSize: 11, color: 'var(--ink-muted)', marginBottom: 8 }}><strong>Chẩn đoán kèm theo:</strong> {activeGeneralPatient.diagnosisSub}</div>
                      </div>
                    </div>

                    {/* Block 5: Kế hoạch điều trị */}
                    <div style={{ background: 'var(--surface-sunken)', padding: 12, borderRadius: 8, marginBottom: 14 }}>
                      <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--ink)', marginBottom: 6 }}>5. Kế hoạch điều trị</div>
                      <div style={{ fontSize: 11, color: 'var(--ink)', whiteSpace: 'pre-line' }}>{activeGeneralPatient.treatmentPlan}</div>
                    </div>

                    {/* Related Orders Sub-panel */}
                    <div style={{ borderTop: '1px solid var(--line)', paddingTop: 10 }}>
                      <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--ink)', marginBottom: 8 }}>Chỉ định & kết quả liên quan</div>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                        {activeGeneralPatient.relatedOrders.map((ord, idx) => (
                          <div key={idx} style={{ padding: 10, background: 'var(--surface-muted)', borderRadius: 6, display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: 11 }}>
                            <div>
                              <strong style={{ color: 'var(--brand-700)' }}>{ord.name}</strong> &nbsp;·&nbsp; <span style={{ color: 'var(--ink-muted)' }}>{ord.doctor}</span>
                              <div style={{ fontSize: 10, color: 'var(--ink-soft)', marginTop: 2 }}>{ord.resultText}</div>
                            </div>
                            <span className="badge badge-success">{ord.status === 'completed' ? 'Đã hoàn tất' : ord.status === 'received' ? 'Đã có kết quả' : 'Chờ duyệt'}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>

                  {/* Bottom Action Bar */}
                  <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
                    <button className="btn btn-secondary" style={{ fontSize: 12 }}><Save size={14} /> Lưu nháp</button>
                    <button className="btn btn-secondary" style={{ fontSize: 12 }}><Plus size={14} /> Tạo chỉ định</button>
                    <button className="btn btn-primary" style={{ fontSize: 12, padding: '10px 16px', background: 'var(--brand-600)' }}>
                      <CheckCircle2 size={15} /> Ký duyệt & hoàn tất hồ sơ
                    </button>
                  </div>
                </div>

                {/* Right Panel: Checklist & Summary */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                  <div className="card" style={{ padding: 14 }}>
                    <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--ink)', marginBottom: 8 }}>Việc cần hoàn tất</div>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 6, fontSize: 11 }}>
                      <label style={{ display: 'flex', alignItems: 'center', gap: 6 }}><input type="checkbox" defaultChecked /> Hoàn tất khám lâm sàng</label>
                      <label style={{ display: 'flex', alignItems: 'center', gap: 6 }}><input type="checkbox" defaultChecked /> Xem & duyệt kết quả</label>
                      <label style={{ display: 'flex', alignItems: 'center', gap: 6 }}><input type="checkbox" /> Kê đơn thuốc</label>
                      <label style={{ display: 'flex', alignItems: 'center', gap: 6 }}><input type="checkbox" /> Ký duyệt & hoàn tất hồ sơ</label>
                    </div>
                  </div>

                  <div className="card" style={{ padding: 14 }}>
                    <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--ink)', marginBottom: 8 }}>Dịch vụ song song</div>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 6, fontSize: 11 }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between' }}><span>Siêu âm phụ khoa</span> <span style={{ color: 'var(--success)' }}>Đã hoàn tất</span></div>
                      <div style={{ display: 'flex', justifyContent: 'space-between' }}><span>Xét nghiệm dịch âm đạo</span> <span style={{ color: 'var(--success)' }}>Đã có kết quả</span></div>
                    </div>
                  </div>

                  <div className="card" style={{ padding: 14 }}>
                    <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--ink)', marginBottom: 8 }}>Tóm tắt đơn thuốc</div>
                    <div style={{ fontSize: 11, color: 'var(--ink-muted)' }}>
                      Clotrimazole 500mg đặt âm đạo (1 viên)
                      <br />
                      Clotrimazole 1% bôi ngoài (1 tuýp)
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* ========================================================================= */}
          {/* VIEW 2: BÁC SĨ PHỤ KHOA — KHÁM & ORDER COMPOSER (MATCHING IMAGE 4)          */}
          {/* ========================================================================= */}
          {doctorSpecialty === 'obgyn' && activeTab === 'gyn_exam' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 16, flex: 1 }}>
              {/* Patient Banner */}
              <div className="card" style={{ padding: '12px 16px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                  <div style={{ width: 40, height: 40, borderRadius: '50%', background: 'var(--brand-50)', color: 'var(--brand-700)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 800, fontSize: 14 }}>
                    NH
                  </div>
                  <div>
                    <div style={{ fontSize: 16, fontWeight: 700, color: 'var(--ink)' }}>
                      {OBGYN_EXAM_DATA.patientName} <span style={{ fontSize: 12, color: 'var(--brand-600)' }}>♀</span>
                    </div>
                    <div style={{ fontSize: 11, color: 'var(--ink-muted)' }}>
                      1990 · Nữ · 35 tuổi &nbsp;|&nbsp; SĐT: {OBGYN_EXAM_DATA.phone} &nbsp;|&nbsp; Mã bệnh nhân: {OBGYN_EXAM_DATA.patientCode} &nbsp;|&nbsp; Ngày khám: {OBGYN_EXAM_DATA.visitDate}
                    </div>
                  </div>
                </div>

                <button className="btn btn-secondary" style={{ fontSize: 11 }}>
                  <User size={13} /> Xem hồ sơ bệnh nhân
                </button>
              </div>

              {/* 4 Columns Ob/Gyn Specialist Workspace */}
              <div style={{ display: 'grid', gridTemplateColumns: '280px 300px 1fr 300px', gap: 14, flex: 1, alignItems: 'start' }}>
                {/* Column 1: Thông tin lượt khám & Tiền sử */}
                <div className="card" style={{ padding: 14, display: 'flex', flexDirection: 'column', gap: 12 }}>
                  <div>
                    <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--ink)', marginBottom: 4 }}>Thông tin lượt khám</div>
                    <div style={{ fontSize: 11, color: 'var(--ink-muted)' }}>
                      Số thứ tự: <strong>{OBGYN_EXAM_DATA.stt}</strong> &nbsp;·&nbsp; Trạng thái: <span style={{ color: 'var(--brand-600)', fontWeight: 600 }}>● Đang khám</span>
                    </div>
                  </div>

                  <div style={{ background: '#fef2f2', padding: 10, borderRadius: 6, border: '1px solid #fee2e2' }}>
                    <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--danger)', marginBottom: 2 }}>Lý do đến khám</div>
                    <div style={{ fontSize: 11, color: 'var(--ink)' }}>{OBGYN_EXAM_DATA.reason}</div>
                  </div>

                  <div>
                    <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--ink)', marginBottom: 4 }}>Tiền sử kinh nguyệt</div>
                    <div style={{ fontSize: 10, color: 'var(--ink-soft)', display: 'flex', flexDirection: 'column', gap: 2 }}>
                      <div>• {OBGYN_EXAM_DATA.menstrualHistory.cycle}</div>
                      <div>• {OBGYN_EXAM_DATA.menstrualHistory.flow}</div>
                      <div>• {OBGYN_EXAM_DATA.menstrualHistory.duration}</div>
                      <div>• {OBGYN_EXAM_DATA.menstrualHistory.dysmenorrhea}</div>
                    </div>
                  </div>

                  <div>
                    <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--ink)', marginBottom: 4 }}>Tiền sử sản khoa</div>
                    <div style={{ fontSize: 10, color: 'var(--ink-soft)', display: 'flex', flexDirection: 'column', gap: 2 }}>
                      <div>• {OBGYN_EXAM_DATA.obHistory.para}</div>
                      <div>• {OBGYN_EXAM_DATA.obHistory.birthYear}</div>
                      <div>• {OBGYN_EXAM_DATA.obHistory.notes}</div>
                    </div>
                  </div>

                  <div>
                    <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--ink)', marginBottom: 4 }}>Tiền sử phụ khoa</div>
                    <div style={{ fontSize: 10, color: 'var(--ink-soft)', display: 'flex', flexDirection: 'column', gap: 2 }}>
                      <div>• {OBGYN_EXAM_DATA.gynHistory.fibroid}</div>
                      <div>• {OBGYN_EXAM_DATA.gynHistory.papSmear}</div>
                      <div>• {OBGYN_EXAM_DATA.gynHistory.hpvVaccine}</div>
                    </div>
                  </div>

                  {/* Vitals widget */}
                  <div style={{ borderTop: '1px solid var(--line)', paddingTop: 10 }}>
                    <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--ink)', marginBottom: 6 }}>Dấu hiệu sinh tồn</div>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6, fontSize: 10 }}>
                      <div style={{ background: 'var(--surface-sunken)', padding: 6, borderRadius: 4 }}>HA: <strong>{OBGYN_EXAM_DATA.vitals.bp}</strong> mmHg</div>
                      <div style={{ background: 'var(--surface-sunken)', padding: 6, borderRadius: 4 }}>Mạch: <strong>{OBGYN_EXAM_DATA.vitals.pulse}</strong>/p</div>
                      <div style={{ background: 'var(--surface-sunken)', padding: 6, borderRadius: 4 }}>Nhiệt độ: <strong>{OBGYN_EXAM_DATA.vitals.temp}</strong>°C</div>
                      <div style={{ background: 'var(--surface-sunken)', padding: 6, borderRadius: 4 }}>BMI: <strong>{OBGYN_EXAM_DATA.vitals.bmi}</strong></div>
                    </div>
                  </div>
                </div>

                {/* Column 2: Kết quả khám phụ khoa */}
                <div className="card" style={{ padding: 14, display: 'flex', flexDirection: 'column', gap: 12 }}>
                  <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--ink)', borderBottom: '1px solid var(--line)', paddingBottom: 8 }}>
                    Kết quả khám phụ khoa
                  </div>

                  <div>
                    <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--ink)', marginBottom: 2 }}>Khám ngoài</div>
                    <div style={{ fontSize: 11, color: 'var(--ink-soft)', background: 'var(--surface-sunken)', padding: 6, borderRadius: 4 }}>
                      {OBGYN_EXAM_DATA.examExternal}
                    </div>
                  </div>

                  <div>
                    <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--ink)', marginBottom: 2 }}>Khám mỏ vịt</div>
                    <div style={{ fontSize: 11, color: 'var(--ink-soft)', background: 'var(--surface-sunken)', padding: 6, borderRadius: 4 }}>
                      {OBGYN_EXAM_DATA.examSpeculum}
                    </div>
                  </div>

                  <div>
                    <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--ink)', marginBottom: 2 }}>Khám tay</div>
                    <div style={{ fontSize: 11, color: 'var(--ink-soft)', background: 'var(--surface-sunken)', padding: 6, borderRadius: 4 }}>
                      {OBGYN_EXAM_DATA.examBimanual}
                    </div>
                  </div>

                  <div>
                    <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--ink)', marginBottom: 2 }}>Chẩn đoán sơ bộ</div>
                    <div style={{ fontSize: 11, color: 'var(--brand-700)', fontWeight: 600, background: 'var(--brand-50)', padding: 6, borderRadius: 4 }}>
                      {OBGYN_EXAM_DATA.diagnosisPre}
                    </div>
                  </div>

                  <div>
                    <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--ink)', marginBottom: 2 }}>Hướng xử trí</div>
                    <div style={{ fontSize: 11, color: 'var(--ink-soft)', background: 'var(--surface-sunken)', padding: 6, borderRadius: 4 }}>
                      {OBGYN_EXAM_DATA.treatmentDirection}
                    </div>
                  </div>
                </div>

                {/* Column 3: Order Composer */}
                <div className="card" style={{ padding: 14, display: 'flex', flexDirection: 'column', gap: 12 }}>
                  <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--ink)' }}>Chỉ định dịch vụ</div>

                  {/* Preset Order Cards */}
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
                    {OBGYN_EXAM_DATA.presetOrders.map(p => (
                      <div key={p.id} style={{ border: '1px solid var(--brand-200)', background: 'var(--brand-50)', padding: 8, borderRadius: 6, cursor: 'pointer' }}>
                        <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--brand-700)' }}>{p.name}</div>
                        <div style={{ fontSize: 9, color: 'var(--ink-muted)', margin: '2px 0' }}>{p.desc}</div>
                        <div style={{ fontSize: 10, fontWeight: 800, color: 'var(--brand-600)' }}>{p.price.toLocaleString()}đ</div>
                      </div>
                    ))}
                  </div>

                  {/* Order List */}
                  <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--ink)' }}>Dịch vụ thường dùng (6 dịch vụ đã chọn)</div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 6, maxHeight: 320, overflowY: 'auto' }}>
                    {obgynOrders.map(o => (
                      <div key={o.id} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '6px 8px', background: 'var(--surface-sunken)', borderRadius: 6, fontSize: 11 }}>
                        <label style={{ display: 'flex', alignItems: 'center', gap: 6, cursor: 'pointer' }}>
                          <input type="checkbox" checked={o.checked} onChange={() => {
                            setObgynOrders(prev => prev.map(item => item.id === o.id ? { ...item, checked: !item.checked } : item));
                          }} />
                          <span style={{ fontWeight: 600 }}>{o.name}</span>
                        </label>
                        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                          <span style={{ fontSize: 10, color: 'var(--ink-muted)' }}>{o.price.toLocaleString()}đ</span>
                          <span className="badge badge-warning" style={{ fontSize: 8 }}>{o.priority}</span>
                        </div>
                      </div>
                    ))}
                  </div>

                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderTop: '1px solid var(--line)', paddingTop: 10 }}>
                    <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--ink)' }}>Tạm tính ({obgynOrders.filter(o => o.checked).length} dịch vụ):</span>
                    <strong style={{ fontSize: 16, color: 'var(--brand-600)' }}>{totalObgynPrice.toLocaleString()} đ</strong>
                  </div>

                  <button className="btn btn-primary" style={{ width: '100%', fontSize: 12, padding: '10px', background: 'var(--brand-600)' }}>
                    <Zap size={14} /> Xem và gửi chỉ định
                  </button>
                </div>

                {/* Column 4: Cost Conflict & Warning Panel */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                  {/* COST CONFLICT BLOCK BANNER */}
                  {costBlocked && (
                    <div style={{ padding: 14, background: '#fef2f2', border: '1px solid #fca5a5', borderRadius: 'var(--radius-card)' }}>
                      <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--danger)', marginBottom: 6, display: 'flex', alignItems: 'center', gap: 6 }}>
                        <AlertOctagon size={16} /> ĐANG BỊ CHẶN
                      </div>
                      <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--ink)', marginBottom: 4 }}>Lý do chặn:</div>
                      <div style={{ fontSize: 10, color: 'var(--ink-soft)', marginBottom: 10 }}>{OBGYN_EXAM_DATA.costConflictReason}</div>
                      
                      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                        <button className="btn btn-primary" style={{ padding: '6px', fontSize: 10, background: 'var(--brand-600)' }}>
                          <Phone size={12} /> Gọi CSKH giải thích chi phí
                        </button>
                        <button className="btn btn-secondary" style={{ padding: '6px', fontSize: 10 }}>
                          Ghi nhận từ chối
                        </button>
                        <button className="btn btn-secondary" style={{ padding: '6px', fontSize: 10 }} onClick={() => setCostBlocked(false)}>
                          Điều chỉnh chỉ định (mở chặn)
                        </button>
                      </div>
                    </div>
                  )}

                  {/* Order Summary */}
                  <div className="card" style={{ padding: 14 }}>
                    <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--ink)', marginBottom: 8 }}>Tóm tắt đơn hàng</div>
                    <div style={{ fontSize: 11, display: 'flex', flexDirection: 'column', gap: 4 }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between' }}><span>Tổng dịch vụ</span><strong>6</strong></div>
                      <div style={{ display: 'flex', justifyContent: 'space-between' }}><span>Tạm tính</span><span>2.950.000đ</span></div>
                      <div style={{ display: 'flex', justifyContent: 'space-between' }}><span>Giảm giá</span><span>0đ</span></div>
                      <div style={{ display: 'flex', justifyContent: 'space-between', borderTop: '1px solid var(--line)', paddingTop: 4, fontWeight: 700, color: 'var(--brand-600)' }}>
                        <span>Tổng dự kiến</span><span>2.950.000đ</span>
                      </div>
                    </div>
                  </div>

                  {/* Duplicate Order Warning */}
                  <div style={{ padding: 12, background: '#fffbeb', border: '1px solid #fef3c7', borderRadius: 'var(--radius-card)', fontSize: 10, color: '#b45309' }}>
                    <strong style={{ display: 'flex', alignItems: 'center', gap: 4, marginBottom: 4 }}><AlertTriangle size={12} /> Cảnh báo trùng lặp</strong>
                    Phát hiện chỉ định trùng dịch vụ trong 30 ngày gần nhất: Pap smear/ThinPrep, XN nội tiết tố. <span style={{ color: 'var(--brand-600)', cursor: 'pointer', fontWeight: 600 }}>Xem chi tiết</span>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* ========================================================================= */}
          {/* VIEW 3: BÁC SĨ SIÊU ÂM / CĐHA (BS. Lê Hoàng Nam)                          */}
          {/* ========================================================================= */}
          {doctorSpecialty === 'ultrasound' && activeTab === 'ultrasound_work' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 16, flex: 1 }}>
              <div style={{ display: 'grid', gridTemplateColumns: '280px 1fr 320px', gap: 16, flex: 1, alignItems: 'start' }}>
                {/* Column 1: Ultrasound Queue */}
                <div className="card" style={{ padding: 14, display: 'flex', flexDirection: 'column', gap: 10 }}>
                  <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--ink)' }}>Hàng đợi siêu âm (3 trạm)</div>
                  
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                    {ULTRASOUND_ITEMS.map(u => (
                      <div
                        key={u.id}
                        onClick={() => {
                          setSelectedUsId(u.id);
                          setUsFindings(u.findings);
                          setUsConclusion(u.conclusion);
                        }}
                        style={{
                          padding: 10,
                          borderRadius: 'var(--radius-control)',
                          border: u.id === activeUsItem.id ? '2px solid var(--brand-500)' : '1px solid var(--line)',
                          background: u.id === activeUsItem.id ? 'var(--brand-50)' : 'var(--surface)',
                          cursor: 'pointer',
                        }}
                      >
                        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                          <span style={{ fontSize: 13, fontWeight: 800, color: 'var(--brand-700)' }}>{u.stt}</span>
                          <span className="badge badge-brand">{u.room}</span>
                        </div>
                        <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--ink)' }}>{u.patientName}</div>
                        <div style={{ fontSize: 10, color: 'var(--ink-muted)' }}>{u.type}</div>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Column 2: Ultrasound Findings & Measurements */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
                  <div className="card" style={{ padding: 16 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid var(--line)', paddingBottom: 10, marginBottom: 12 }}>
                      <div>
                        <div style={{ fontSize: 15, fontWeight: 700, color: 'var(--ink)' }}>{activeUsItem.patientName}</div>
                        <div style={{ fontSize: 11, color: 'var(--ink-muted)' }}>
                          {activeUsItem.patientCode} · {activeUsItem.type} · BS chỉ định: {activeUsItem.indicationDoctor}
                        </div>
                      </div>
                      <span className="badge badge-success">{activeUsItem.room}</span>
                    </div>

                    {/* Measurements Table */}
                    <div style={{ marginBottom: 14 }}>
                      <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--ink)', marginBottom: 6 }}>Bảng thông số đo đạc siêu âm</div>
                      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
                        {activeUsItem.measurements.map((m, idx) => (
                          <div key={idx} style={{ display: 'flex', justifyContent: 'space-between', padding: '6px 8px', background: 'var(--surface-sunken)', borderRadius: 6, fontSize: 11 }}>
                            <span>{m.name}</span>
                            <strong>{m.val} {m.unit}</strong>
                          </div>
                        ))}
                      </div>
                    </div>

                    {/* Findings Input */}
                    <div style={{ marginBottom: 14 }}>
                      <label style={{ fontSize: 11, fontWeight: 700, color: 'var(--ink)', display: 'block', marginBottom: 4 }}>Mô tả hình ảnh tổn thương & siêu âm</label>
                      <textarea
                        value={usFindings}
                        onChange={(e) => setUsFindings(e.target.value)}
                        rows={5}
                        style={{ width: '100%', fontSize: 12, resize: 'none' }}
                      />
                    </div>

                    {/* Conclusion Input */}
                    <div>
                      <label style={{ fontSize: 11, fontWeight: 700, color: 'var(--ink)', display: 'block', marginBottom: 4 }}>Kết luận siêu âm</label>
                      <textarea
                        value={usConclusion}
                        onChange={(e) => setUsConclusion(e.target.value)}
                        rows={3}
                        style={{ width: '100%', fontSize: 12, resize: 'none', fontWeight: 600, color: 'var(--brand-700)' }}
                      />
                    </div>
                  </div>

                  <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
                    <button className="btn btn-secondary"><Save size={14} /> Lưu nháp phiếu</button>
                    <button className="btn btn-primary" style={{ padding: '10px 16px', background: 'var(--brand-600)' }}>
                      <CheckCircle2 size={15} /> Ký duyệt & phát hành phiếu siêu âm
                    </button>
                  </div>
                </div>

                {/* Column 3: Attached Images */}
                <div className="card" style={{ padding: 14, display: 'flex', flexDirection: 'column', gap: 12 }}>
                  <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--ink)' }}>Hình ảnh siêu âm đính kèm</div>
                  
                  <div style={{ border: '2px dashed var(--line)', borderRadius: 'var(--radius-card)', padding: 20, textAlign: 'center', background: 'var(--surface-sunken)', cursor: 'pointer' }}>
                    <ImageIcon size={32} color="var(--brand-600)" style={{ marginBottom: 6 }} />
                    <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--brand-700)' }}>Kéo thả hoặc bấm để kết nối máy siêu âm</div>
                    <div style={{ fontSize: 9, color: 'var(--ink-muted)', marginTop: 4 }}>Đồng bộ DICOM / JPG tự động</div>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* ========================================================================= */}
          {/* TAB: KẾT QUẢ ĐÃ KÝ (MATCHING IMAGE 1)                                    */}
          {/* ========================================================================= */}
          {activeTab === 'signed_results' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 16, flex: 1 }}>
              {/* KPI Cards */}
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12 }}>
                {[
                  { label: 'Đã ký hôm nay', value: 16, icon: FileCheck, color: 'var(--brand-600)', bg: 'var(--brand-50)' },
                  { label: 'Đã phát hành', value: 14, icon: CheckCircle2, color: 'var(--success)', bg: 'var(--success-bg)' },
                  { label: 'Có bản điều chỉnh', value: 2, icon: RotateCcw, color: 'var(--warning)', bg: 'var(--warning-bg)' },
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

              {/* Table & Detail Split Workspace */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 360px', gap: 16, flex: 1, alignItems: 'start' }}>
                {/* Left Table */}
                <div className="card" style={{ padding: 14, display: 'flex', flexDirection: 'column', gap: 12 }}>
                  <div style={{ display: 'flex', gap: 10 }}>
                    <div style={{ position: 'relative', flex: 1 }}>
                      <Search size={14} style={{ position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)', color: 'var(--ink-muted)' }} />
                      <input
                        type="search"
                        placeholder="Tìm bệnh nhân, mã kết quả, tên báo cáo..."
                        value={signedSearch}
                        onChange={(e) => setSignedSearch(e.target.value)}
                        style={{ paddingLeft: 32, width: '100%', fontSize: 12 }}
                      />
                    </div>
                  </div>

                  <div className="table-wrap">
                    <table>
                      <thead>
                        <tr>
                          <th>Thời gian ký</th>
                          <th>Mã kết quả</th>
                          <th>Bệnh nhân</th>
                          <th>Loại kết quả</th>
                          <th>Phiên bản</th>
                          <th>Trạng thái</th>
                          <th>Phát hành</th>
                        </tr>
                      </thead>
                      <tbody>
                        {SIGNED_RESULTS.map(rec => {
                          const isSelected = rec.id === activeSignedRecord.id;
                          return (
                            <tr
                              key={rec.id}
                              onClick={() => setSelectedSignedId(rec.id)}
                              style={{ cursor: 'pointer', background: isSelected ? 'var(--brand-50)' : undefined }}
                            >
                              <td style={{ fontSize: 11 }}>{rec.signedTime}</td>
                              <td style={{ fontSize: 11, fontWeight: 700 }}>{rec.code}</td>
                              <td>
                                <div style={{ fontSize: 12, fontWeight: 700 }}>{rec.patientName}</div>
                                <div style={{ fontSize: 10, color: 'var(--ink-muted)' }}>{rec.patientCode}</div>
                              </td>
                              <td style={{ fontSize: 11 }}>{rec.resultType}</td>
                              <td style={{ fontSize: 11, fontWeight: 600 }}>{rec.version}</td>
                              <td><span className="badge badge-success">Đã ký</span></td>
                              <td><span className="badge badge-brand">Đã phát hành</span></td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                </div>

                {/* Right Signed Record Detail */}
                <div className="card" style={{ padding: 16, display: 'flex', flexDirection: 'column', gap: 14 }}>
                  <div style={{ background: 'var(--brand-50)', padding: 10, borderRadius: 6, border: '1px solid var(--brand-200)', fontSize: 11, color: 'var(--brand-700)', display: 'flex', alignItems: 'center', gap: 6 }}>
                    <Lock size={14} /> Bản đã ký — chỉ đọc. Chỉnh sửa phải tạo bản điều chỉnh mới.
                  </div>

                  <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid var(--line)', paddingBottom: 10 }}>
                    <div>
                      <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--ink)' }}>{activeSignedRecord.patientName}</div>
                      <div style={{ fontSize: 10, color: 'var(--ink-muted)' }}>{activeSignedRecord.patientCode} · {activeSignedRecord.age} tuổi ({activeSignedRecord.gender})</div>
                    </div>
                    <div style={{ textAlign: 'right', fontSize: 10, color: 'var(--ink-muted)' }}>
                      Mã khám (LK):<br /><strong style={{ color: 'var(--ink)' }}>{activeSignedRecord.visitCode}</strong>
                    </div>
                  </div>

                  <div style={{ fontSize: 11, display: 'flex', flexDirection: 'column', gap: 4 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between' }}><span style={{ color: 'var(--ink-muted)' }}>Mã kết quả</span><strong>{activeSignedRecord.code}</strong></div>
                    <div style={{ display: 'flex', justifyContent: 'space-between' }}><span style={{ color: 'var(--ink-muted)' }}>Loại kết quả</span><span>{activeSignedRecord.resultType}</span></div>
                    <div style={{ display: 'flex', justifyContent: 'space-between' }}><span style={{ color: 'var(--ink-muted)' }}>Bác sĩ ký</span><strong>{activeSignedRecord.doctorName}</strong></div>
                    <div style={{ display: 'flex', justifyContent: 'space-between' }}><span style={{ color: 'var(--ink-muted)' }}>Thời gian ký</span><span>{activeSignedRecord.signedTime}</span></div>
                    <div style={{ display: 'flex', justifyContent: 'space-between' }}><span style={{ color: 'var(--ink-muted)' }}>Chữ ký số</span><span style={{ color: 'var(--success)', fontWeight: 600 }}>✓ Hợp lệ</span></div>
                  </div>

                  {/* Summary Content */}
                  <div style={{ borderTop: '1px solid var(--line)', paddingTop: 10 }}>
                    <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--ink)', marginBottom: 6 }}>Nội dung tóm tắt</div>
                    <div style={{ fontSize: 11, display: 'flex', flexDirection: 'column', gap: 6 }}>
                      <div><strong style={{ color: 'var(--ink-muted)' }}>Kết luận:</strong><br />{activeSignedRecord.summary.conclusion}</div>
                      <div><strong style={{ color: 'var(--ink-muted)' }}>Chẩn đoán:</strong><br />{activeSignedRecord.summary.diagnosis}</div>
                      <div><strong style={{ color: 'var(--ink-muted)' }}>Kế hoạch:</strong><br />{activeSignedRecord.summary.plan}</div>
                    </div>
                  </div>

                  {/* Action Buttons */}
                  <div style={{ display: 'flex', gap: 6, borderTop: '1px solid var(--line)', paddingTop: 10 }}>
                    <button className="btn btn-secondary" style={{ flex: 1, fontSize: 10 }}><Printer size={12} /> In kết quả</button>
                    <button className="btn btn-secondary" style={{ flex: 1, fontSize: 10 }}><Download size={12} /> Tải PDF</button>
                    <button className="btn btn-secondary" style={{ flex: 1, fontSize: 10 }}><Eye size={12} /> Xem phiên bản</button>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* ========================================================================= */}
          {/* VIEW: DANH SÁCH BỆNH NHÂN (MATCHING IMAGE 3)                              */}
          {/* ========================================================================= */}
          {doctorSpecialty === 'general' && activeTab === 'patient_list' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 16, flex: 1 }}>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12 }}>
                {[
                  { label: 'Tổng bệnh nhân', value: '3.842', icon: Users, color: 'var(--brand-600)', bg: 'var(--brand-50)' },
                  { label: 'Có lượt đang mở', value: 28, icon: Activity, color: 'var(--success)', bg: 'var(--success-bg)' },
                  { label: 'Chờ bác sĩ xử lý', value: 9, icon: UserCheck, color: 'var(--warning)', bg: 'var(--warning-bg)' },
                  { label: 'Cần theo dõi', value: 14, icon: Clock, color: 'var(--danger)', bg: 'var(--danger-bg)' },
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

              <div className="card" style={{ padding: 20, textAlign: 'center' }}>
                <User size={32} color="var(--brand-600)" style={{ marginBottom: 8 }} />
                <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--ink)' }}>Danh mục hồ sơ tổng & Lịch sử khám bệnh nhân</div>
                <div style={{ fontSize: 12, color: 'var(--ink-muted)', marginTop: 4 }}>
                  Hiển thị chi tiết tiền sử sản phụ khoa, dị ứng, bệnh lý mãn tính và file kết quả xét nghiệm ngoài (đúng theo ảnh 3).
                </div>
              </div>
            </div>
          )}

        </div>
      </div>
    </div>
  );
}
