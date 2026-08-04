import { useState } from 'react';
import {
  Search,
  CheckCircle2,
  AlertTriangle,
  Clock,
  RotateCcw,
  Save,
  ArrowRight,
  Bell,
  SlidersHorizontal,
  ChevronLeft,
  ChevronRight,
  Activity,
  History,
  Filter,
  User,
  AlertOctagon,
} from 'lucide-react';
import {
  NURSE_KPI,
  NURSE_PATIENTS,
  INITIAL_VITALS,
  NURSE_VITALS_HISTORY,
  type VitalSignItem,
} from '../../data/nurse-mock-data';

interface NurseVitalsDashboardProps {
  onSwitchRole?: () => void;
}

export default function NurseVitalsDashboard({ onSwitchRole }: NurseVitalsDashboardProps) {
  const [activeTab, setActiveTab] = useState<'measure' | 'history'>('measure');
  const [queueFilter, setQueueFilter] = useState<'pending' | 'priority' | 'remeasure'>('pending');
  const [search, setSearch] = useState('');
  const [historySearch, setHistorySearch] = useState('');
  const [historyStatusFilter, setHistoryStatusFilter] = useState<string>('all');
  const [selectedPatientId, setSelectedPatientId] = useState<string>('p-021');
  const [selectedHistoryId, setSelectedHistoryId] = useState<string>('h-019');
  const [vitals, setVitals] = useState<VitalSignItem[]>(INITIAL_VITALS);
  const [collapsed, setCollapsed] = useState(false);
  const [nurseNotes, setNurseNotes] = useState('BN tỉnh, tiếp xúc tốt, không khó thở.');

  // Form selections
  const [bpPosition, setBpPosition] = useState('Ngồi');
  const [bpLocation, setBpLocation] = useState('Cánh tay trái');
  const [eatingState, setEatingState] = useState('Chưa ăn sáng');
  const [pregnancyState, setPregnancyState] = useState('Không ghi nhận');

  // Checklist states
  const [checklist, setChecklist] = useState({
    correctPatient: true,
    allVitalsInputted: true,
    validDevice: true,
    alertHandled: true,
  });

  const selectedPatient = NURSE_PATIENTS.find(p => p.id === selectedPatientId) || NURSE_PATIENTS[0];

  const handleVitalChange = (id: string, field: 'value' | 'secondaryValue', newValue: string | number) => {
    setVitals(prev => prev.map(item => {
      if (item.id === id) {
        return { ...item, [field]: newValue };
      }
      return item;
    }));
  };

  // Filter history records
  const filteredHistory = NURSE_VITALS_HISTORY.filter(h => {
    if (historySearch) {
      const q = historySearch.toLowerCase();
      const matchName = h.patientName.toLowerCase().includes(q) || h.patientCode.toLowerCase().includes(q) || h.visitCode.toLowerCase().includes(q);
      if (!matchName) return false;
    }
    if (historyStatusFilter !== 'all') {
      if (h.status !== historyStatusFilter) return false;
    }
    return true;
  });

  const activeHistoryRecord = NURSE_VITALS_HISTORY.find(h => h.id === selectedHistoryId) || NURSE_VITALS_HISTORY[0];

  return (
    <div style={{ display: 'flex', minHeight: '100vh', background: 'var(--surface-muted)' }}>
      {/* 1. SIDEBAR (COMPACT 2 TABS AS REQUESTED BY USER) */}
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

        {/* Role header */}
        {!collapsed && (
          <div style={{ padding: '16px 16px 8px', fontSize: 11, fontWeight: 700, color: 'var(--ink-muted)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
            ĐIỀU DƯỠNG
          </div>
        )}

        {/* Nav Links — ONLY 2 TABS BASED ON USER FEEDBACK */}
        <nav style={{ flex: 1, padding: '4px 8px', display: 'flex', flexDirection: 'column', gap: 2 }}>
          {[
            { id: 'measure', label: 'Đo & ghi sinh hiệu', icon: Activity },
            { id: 'history', label: 'Lịch sử sinh hiệu', icon: History },
          ].map(tab => {
            const active = activeTab === tab.id;
            const Icon = tab.icon;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id as any)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 10,
                  padding: collapsed ? '10px' : '10px 12px',
                  borderRadius: 'var(--radius-control)',
                  border: 'none',
                  background: active ? 'var(--brand-50)' : 'transparent',
                  color: active ? 'var(--brand-700)' : 'var(--ink-soft)',
                  fontSize: 13,
                  fontWeight: active ? 600 : 500,
                  cursor: 'pointer',
                  textAlign: 'left',
                  width: '100%',
                  justifyContent: collapsed ? 'center' : 'flex-start',
                  borderLeft: active ? '3px solid var(--brand-600)' : '3px solid transparent',
                }}
              >
                <Icon size={18} />
                {!collapsed && <span>{tab.label}</span>}
              </button>
            );
          })}

          {/* Switch Role Button */}
          {onSwitchRole && (
            <div style={{ marginTop: 'auto', paddingTop: 16 }}>
              <button
                onClick={onSwitchRole}
                className="btn btn-secondary"
                style={{ width: '100%', fontSize: 11, padding: '6px 8px', justifyContent: collapsed ? 'center' : 'flex-start' }}
                title="Đổi sang màn hình Trưởng Ca"
              >
                <RotateCcw size={13} />
                {!collapsed && <span>Đổi sang Trưởng Ca</span>}
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
            padding: '14px 24px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          <div>
            <h1 style={{ fontSize: 18, fontWeight: 700, color: 'var(--ink)', margin: 0 }}>
              {activeTab === 'measure' ? 'Đo & ghi sinh hiệu' : 'Lịch sử sinh hiệu & Cảnh báo'}
            </h1>
            <p style={{ fontSize: 12, color: 'var(--ink-muted)', margin: '2px 0 0' }}>
              {activeTab === 'measure'
                ? 'Ghi nhận chỉ số ban đầu, phát hiện bất thường và chuyển người bệnh sang bước khám.'
                : 'Tra cứu lịch sử các lượt đo sinh hiệu, chi tiết thời gian đo/xác nhận và nhật ký xử lý cảnh báo.'}
            </p>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
            <div style={{ position: 'relative', cursor: 'pointer' }}>
              <Bell size={18} color="var(--ink-muted)" />
              <span style={{ position: 'absolute', top: -4, right: -4, background: 'var(--danger)', color: 'white', borderRadius: 999, fontSize: 9, fontWeight: 700, width: 15, height: 15, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                3
              </span>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <div style={{ width: 34, height: 34, borderRadius: '50%', background: 'var(--surface-sunken)', color: 'var(--ink)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 12, fontWeight: 700 }}>
                NT
              </div>
              <div>
                <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--ink)' }}>Nguyễn Thị Tâm</div>
                <div style={{ fontSize: 11, color: 'var(--ink-muted)' }}>Điều dưỡng</div>
              </div>
            </div>
          </div>
        </header>

        {/* TAB 1: ĐO & GHI SINH HIỆU */}
        {activeTab === 'measure' && (
          <div style={{ padding: 20, display: 'flex', flexDirection: 'column', gap: 16, flex: 1 }}>
            {/* 2. TOP KPI ROW */}
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(5, 1fr)',
                gap: 12,
              }}
            >
              {[
                { label: 'Chờ đo sinh hiệu', value: NURSE_KPI.waiting, icon: Activity, color: 'var(--brand-600)', bg: 'var(--brand-50)' },
                { label: 'Đang thực hiện', value: NURSE_KPI.inProgress, icon: SlidersHorizontal, color: 'var(--brand-600)', bg: 'var(--brand-50)' },
                { label: 'Có cảnh báo', value: NURSE_KPI.alertAbnormal, icon: AlertTriangle, color: 'var(--danger)', bg: 'var(--danger-bg)' },
                { label: 'Có cảnh báo', value: NURSE_KPI.alertLongWait, icon: Clock, color: 'var(--warning)', bg: 'var(--warning-bg)' },
                { label: 'Hoàn tất hôm nay', value: NURSE_KPI.completedToday, icon: CheckCircle2, color: 'var(--success)', bg: 'var(--success-bg)' },
              ].map((kpi, idx) => {
                const Icon = kpi.icon;
                return (
                  <div
                    key={idx}
                    className="card"
                    style={{
                      padding: '12px 16px',
                      display: 'flex',
                      alignItems: 'center',
                      gap: 12,
                    }}
                  >
                    <div
                      style={{
                        width: 36,
                        height: 36,
                        borderRadius: '50%',
                        background: kpi.bg,
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        flexShrink: 0,
                      }}
                    >
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

            {/* 3 COLUMNS WORKSPACE GRID */}
            <div style={{ display: 'grid', gridTemplateColumns: '260px 1fr 340px', gap: 16, flex: 1, alignItems: 'start' }}>
              {/* 3. LEFT COLUMN: DANH SÁCH CHỜ SINH HIỆU */}
              <div className="card" style={{ padding: 14, display: 'flex', flexDirection: 'column', gap: 12 }}>
                <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--ink)' }}>Danh sách chờ sinh hiệu</div>
                
                <div style={{ position: 'relative' }}>
                  <Search size={13} style={{ position: 'absolute', left: 8, top: '50%', transform: 'translateY(-50%)', color: 'var(--ink-muted)' }} />
                  <input
                    type="search"
                    placeholder="Tên, số thứ tự hoặc mã bệnh nhân"
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                    style={{ paddingLeft: 26, width: '100%', fontSize: 11 }}
                  />
                </div>

                {/* Filter tabs */}
                <div style={{ display: 'flex', gap: 4 }}>
                  {[
                    { id: 'pending', label: 'Chờ đo', count: 9 },
                    { id: 'priority', label: 'Ưu tiên', count: 2 },
                    { id: 'remeasure', label: 'Cần đo lại', count: 1 },
                  ].map(tab => (
                    <button
                      key={tab.id}
                      onClick={() => setQueueFilter(tab.id as any)}
                      className={queueFilter === tab.id ? 'btn btn-primary' : 'btn btn-secondary'}
                      style={{ padding: '4px 6px', fontSize: 10, flex: 1, whiteSpace: 'nowrap' }}
                    >
                      {tab.label} <span style={{ opacity: 0.8 }}>{tab.count}</span>
                    </button>
                  ))}
                </div>

                {/* Patient List Cards */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8, maxHeight: 600, overflowY: 'auto' }}>
                  {NURSE_PATIENTS.map(p => {
                    const isSelected = p.id === selectedPatientId;
                    return (
                      <div
                        key={p.id}
                        onClick={() => setSelectedPatientId(p.id)}
                        style={{
                          padding: 10,
                          borderRadius: 'var(--radius-control)',
                          border: isSelected ? '2px solid var(--brand-500)' : '1px solid var(--line)',
                          background: isSelected ? 'var(--brand-50)' : 'var(--surface)',
                          cursor: 'pointer',
                          transition: 'all 0.15s ease',
                        }}
                      >
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 4 }}>
                          <span style={{ fontSize: 14, fontWeight: 800, color: 'var(--brand-700)' }}>{p.stt}</span>
                          <span style={{ fontSize: 11, fontWeight: 500, color: 'var(--ink-muted)' }}>{String(p.waitTimeMinutes).padStart(2, '0')} phút chờ</span>
                        </div>
                        
                        <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--ink)', marginBottom: 2 }}>{p.name}</div>
                        <div style={{ fontSize: 10, color: 'var(--ink-muted)', marginBottom: 6 }}>
                          {p.birthYear} · {p.gender} · {p.age} tuổi
                          <br />
                          {p.patientCode} · {p.visitCode}
                        </div>

                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          {p.statusTag ? (
                            <span
                              className="badge"
                              style={{
                                fontSize: 9,
                                background: p.statusTag === 'Đang đo' ? 'var(--brand-50)' : p.statusTag === 'Ưu tiên' ? 'var(--warning-bg)' : 'var(--danger-bg)',
                                color: p.statusTag === 'Đang đo' ? 'var(--brand-700)' : p.statusTag === 'Ưu tiên' ? 'var(--warning)' : 'var(--danger)',
                              }}
                            >
                              {p.statusTag}
                            </span>
                          ) : <span />}
                          <span style={{ fontSize: 10, color: 'var(--ink-muted)' }}>Tiếp theo: <strong style={{ color: 'var(--ink-soft)' }}>{p.nextStep}</strong></span>
                        </div>
                      </div>
                    );
                  })}
                </div>

                <div style={{ fontSize: 10, color: 'var(--ink-muted)', textAlign: 'center', marginTop: 4 }}>
                  Hiển thị 1–5 trong 9 <span style={{ color: 'var(--brand-600)', cursor: 'pointer', fontWeight: 600 }}>Xem tất cả</span>
                </div>
              </div>

              {/* 4. MIDDLE COLUMN: CHỈ SỐ SINH HIỆU */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
                {/* Active Patient Header */}
                <div className="card" style={{ padding: '12px 16px', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                    <div style={{ width: 40, height: 40, borderRadius: '50%', background: 'var(--surface-sunken)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 700, fontSize: 14, color: 'var(--ink)' }}>
                      NT
                    </div>
                    <div>
                      <div style={{ fontSize: 15, fontWeight: 700, color: 'var(--ink)' }}>{selectedPatient.name}</div>
                      <div style={{ fontSize: 11, color: 'var(--ink-muted)' }}>
                        {selectedPatient.birthYear} · {selectedPatient.gender} · {selectedPatient.age} tuổi &nbsp;|&nbsp; {selectedPatient.patientCode} · {selectedPatient.visitCode}
                      </div>
                    </div>
                  </div>

                  <div style={{ display: 'flex', gap: 24, alignItems: 'center' }}>
                    <div style={{ textAlign: 'center' }}>
                      <div style={{ fontSize: 10, color: 'var(--ink-muted)', textTransform: 'uppercase' }}>Số thứ tự</div>
                      <div style={{ fontSize: 16, fontWeight: 800, color: 'var(--ink)' }}>{selectedPatient.stt}</div>
                    </div>
                    <div style={{ textAlign: 'center' }}>
                      <div style={{ fontSize: 10, color: 'var(--ink-muted)', textTransform: 'uppercase' }}>Lượt khám hiện tại</div>
                      <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--brand-600)' }}>Khám bác sĩ</div>
                    </div>
                    <div style={{ textAlign: 'center' }}>
                      <div style={{ fontSize: 10, color: 'var(--ink-muted)', textTransform: 'uppercase' }}>Đối chiếu danh tính</div>
                      <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--success)', display: 'flex', alignItems: 'center', gap: 3 }}>
                        <CheckCircle2 size={13} /> Khớp
                      </div>
                    </div>
                  </div>
                </div>

                {/* 9 VITAL SIGNS CARDS GRID */}
                <div>
                  <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--ink)', marginBottom: 8 }}>Chỉ số sinh hiệu</div>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12 }}>
                    <VitalCard
                      title="Mạch"
                      unit="lần/phút"
                      value={vitals[0].value}
                      onChange={(v) => handleVitalChange('pulse', 'value', v)}
                      source="Monitor M3"
                      time="10:19"
                      statusText="Trong giới hạn"
                      range="60 - 100"
                    />

                    <VitalCardBP
                      title="Huyết áp"
                      unit="mmHg"
                      systolic={vitals[1].value}
                      diastolic={vitals[1].secondaryValue || 78}
                      onSysChange={(v) => handleVitalChange('bp', 'value', v)}
                      onDiaChange={(v) => handleVitalChange('bp', 'secondaryValue', v)}
                      source="BP-02"
                      time="10:19"
                      statusText="Trong giới hạn"
                      range="90/60 - 140/90"
                    />

                    <VitalCard
                      title="Nhịp thở"
                      unit="lần/phút"
                      value={vitals[2].value}
                      onChange={(v) => handleVitalChange('respiration', 'value', v)}
                      source="Quan sát"
                      time="10:19"
                      statusText="Trong giới hạn"
                      range="12 - 20"
                    />

                    <VitalCard
                      title="SpO2"
                      unit="%"
                      value={vitals[3].value}
                      onChange={(v) => handleVitalChange('spo2', 'value', v)}
                      source="SpO2-01"
                      time="10:18"
                      statusText="Trong giới hạn"
                      range="95 - 100"
                    />

                    <VitalCard
                      title="Nhiệt độ"
                      unit="°C"
                      value={vitals[4].value}
                      onChange={(v) => handleVitalChange('temp', 'value', v)}
                      source="Nhiệt kế TM-01"
                      time="10:18"
                      statusText="Trong giới hạn"
                      range="36,0 - 37,5"
                    />

                    <VitalCard
                      title="Cân nặng"
                      unit="kg"
                      value={vitals[5].value}
                      onChange={(v) => handleVitalChange('weight', 'value', v)}
                      source="Cân điện tử"
                      time="10:18"
                      statusText="Trong giới hạn"
                      range="40 - 100"
                    />

                    <VitalCard
                      title="Chiều cao"
                      unit="cm"
                      value={vitals[6].value}
                      onChange={(v) => handleVitalChange('height', 'value', v)}
                      source="Thước đo"
                      time="10:18"
                      statusText="Trong giới hạn"
                      range="140 - 200"
                    />

                    <VitalCard
                      title="BMI"
                      unit="kg/m²"
                      value={vitals[7].value}
                      onChange={(v) => handleVitalChange('bmi', 'value', v)}
                      source="Tự động tính toán"
                      time="10:19"
                      statusText="Trong giới hạn"
                      range="18,5 - 24,9"
                      readOnly
                    />

                    <VitalCard
                      title="Mức độ đau"
                      unit="/ 10"
                      value={vitals[8].value}
                      onChange={(v) => handleVitalChange('pain', 'value', v)}
                      source="Hỏi bệnh nhân"
                      time="10:20"
                      statusText="Trong giới hạn"
                      range="0 - 10"
                    />
                  </div>
                </div>

                {/* Alert Notice Banner */}
                <div style={{ padding: '8px 12px', background: '#fffbeb', border: '1px solid #fef3c7', borderRadius: 'var(--radius-chip)', fontSize: 11, color: '#b45309', display: 'flex', alignItems: 'center', gap: 6 }}>
                  <span>ⓘ Nếu giá trị ngoài ngưỡng, hệ thống yêu cầu đo lại hoặc báo bác sĩ.</span>
                </div>

                {/* Additional Information Section */}
                <div className="card" style={{ padding: 14 }}>
                  <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--ink)', marginBottom: 10 }}>Thông tin bổ sung</div>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12, marginBottom: 12 }}>
                    <div>
                      <label style={{ fontSize: 10, color: 'var(--ink-muted)', display: 'block', marginBottom: 4 }}>Tư thế đo huyết áp</label>
                      <select value={bpPosition} onChange={(e) => setBpPosition(e.target.value)} style={{ width: '100%', fontSize: 11 }}>
                        <option value="Ngồi">Ngồi</option>
                        <option value="Nằm">Nằm</option>
                        <option value="Đứng">Đứng</option>
                      </select>
                    </div>
                    <div>
                      <label style={{ fontSize: 10, color: 'var(--ink-muted)', display: 'block', marginBottom: 4 }}>Vị trí đo</label>
                      <select value={bpLocation} onChange={(e) => setBpLocation(e.target.value)} style={{ width: '100%', fontSize: 11 }}>
                        <option value="Cánh tay trái">Cánh tay trái</option>
                        <option value="Cánh tay phải">Cánh tay phải</option>
                        <option value="Cổ tay">Cổ tay</option>
                      </select>
                    </div>
                    <div>
                      <label style={{ fontSize: 10, color: 'var(--ink-muted)', display: 'block', marginBottom: 4 }}>Trạng thái ăn uống</label>
                      <select value={eatingState} onChange={(e) => setEatingState(e.target.value)} style={{ width: '100%', fontSize: 11 }}>
                        <option value="Chưa ăn sáng">Chưa ăn sáng</option>
                        <option value="Đã ăn sáng">Đã ăn sáng</option>
                        <option value="Sau ăn 2h">Sau ăn 2h</option>
                      </select>
                    </div>
                    <div>
                      <label style={{ fontSize: 10, color: 'var(--ink-muted)', display: 'block', marginBottom: 4 }}>Thai kỳ</label>
                      <select value={pregnancyState} onChange={(e) => setPregnancyState(e.target.value)} style={{ width: '100%', fontSize: 11 }}>
                        <option value="Không ghi nhận">Không ghi nhận</option>
                        <option value="Có thai">Có thai</option>
                      </select>
                    </div>
                  </div>

                  <div style={{ position: 'relative' }}>
                    <label style={{ fontSize: 10, color: 'var(--ink-muted)', display: 'block', marginBottom: 4 }}>Ghi chú của điều dưỡng (tùy chọn)</label>
                    <textarea
                      value={nurseNotes}
                      onChange={(e) => setNurseNotes(e.target.value)}
                      rows={2}
                      style={{ width: '100%', fontSize: 11, resize: 'none' }}
                    />
                    <span style={{ position: 'absolute', right: 8, bottom: 6, fontSize: 9, color: 'var(--ink-muted)' }}>41/200</span>
                  </div>
                </div>

                {/* Checklist before confirmation */}
                <div className="card" style={{ padding: 14 }}>
                  <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--ink)', marginBottom: 8 }}>Kiểm tra trước xác nhận</div>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
                    {[
                      { key: 'correctPatient', label: 'Đúng bệnh nhân' },
                      { key: 'allVitalsInputted', label: 'Đủ 9 chỉ số bắt buộc' },
                      { key: 'validDevice', label: 'Thiết bị/nguồn đo hợp lệ' },
                      { key: 'alertHandled', label: 'Đã xử lý cảnh báo' },
                    ].map(item => (
                      <label key={item.key} style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 11, color: 'var(--ink-soft)', cursor: 'pointer' }}>
                        <input
                          type="checkbox"
                          checked={checklist[item.key as keyof typeof checklist]}
                          onChange={(e) => setChecklist(prev => ({ ...prev, [item.key]: e.target.checked }))}
                        />
                        <span style={{ color: 'var(--success)', fontWeight: 600 }}>✓</span> {item.label}
                      </label>
                    ))}
                  </div>
                </div>
              </div>

              {/* 5. RIGHT COLUMN: THÔNG TIN LƯỢT KHÁM & ĐÁNH GIÁ */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                {/* Encounter Info */}
                <div className="card" style={{ padding: 14 }}>
                  <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--ink)', marginBottom: 8 }}>Thông tin lượt khám</div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: 11 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                      <span style={{ color: 'var(--ink-muted)' }}>Bệnh nhân</span>
                      <strong style={{ color: 'var(--ink)' }}>{selectedPatient.name}</strong>
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                      <span style={{ color: 'var(--ink-muted)' }}>Mã lượt khám</span>
                      <span>{selectedPatient.visitCode}</span>
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                      <span style={{ color: 'var(--ink-muted)' }}>Lý do khám</span>
                      <span>Khám phụ khoa định kỳ</span>
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                      <span style={{ color: 'var(--ink-muted)' }}>Bác sĩ chỉ định</span>
                      <strong style={{ color: 'var(--ink)' }}>BS. Trần Văn Dũng</strong>
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                      <span style={{ color: 'var(--ink-muted)' }}>Phòng khám</span>
                      <span>Phòng khám số 2</span>
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                      <span style={{ color: 'var(--ink-muted)' }}>Thời gian đến</span>
                      <span>09:18, 14/05/2026</span>
                    </div>
                  </div>
                </div>

                {/* Automatic Assessment Card */}
                <div className="card" style={{ padding: 14, background: 'var(--success-bg)', border: '1px solid #bbf7d0' }}>
                  <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--success)', marginBottom: 4 }}>Đánh giá tự động</div>
                  <div style={{ display: 'flex', alignItems: 'flex-start', gap: 8 }}>
                    <CheckCircle2 size={22} color="var(--success)" style={{ flexShrink: 0, marginTop: 2 }} />
                    <div>
                      <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--success)' }}>
                        Không có chỉ số vượt ngưỡng
                      </div>
                      <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--ink)' }}>
                        Đủ điều kiện chuyển bước
                      </div>
                      <div style={{ fontSize: 10, color: 'var(--ink-muted)', marginTop: 4 }}>
                        Điều dưỡng ghi nhận và cảnh báo; không chẩn đoán.
                      </div>
                    </div>
                  </div>
                </div>

                {/* Service Journey Timeline */}
                <div className="card" style={{ padding: 14 }}>
                  <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--ink)', marginBottom: 10 }}>Hành trình dịch vụ</div>
                  
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 12, position: 'relative', paddingLeft: 16 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: 11 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                        <span style={{ width: 10, height: 10, borderRadius: '50%', background: 'var(--success)' }} />
                        <span style={{ fontWeight: 600, color: 'var(--ink)' }}>Check-in</span>
                      </div>
                      <span style={{ color: 'var(--success)', fontWeight: 600 }}>Hoàn tất 09:18</span>
                    </div>

                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: 11 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                        <span style={{ width: 10, height: 10, borderRadius: '50%', background: 'var(--brand-600)', border: '2px solid var(--brand-100)' }} />
                        <span style={{ fontWeight: 700, color: 'var(--brand-700)' }}>Đo sinh hiệu</span>
                      </div>
                      <span style={{ color: 'var(--brand-600)', fontWeight: 600 }}>Đang thực hiện 10:17</span>
                    </div>

                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: 11 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                        <span style={{ width: 10, height: 10, borderRadius: '50%', background: 'var(--line-strong)' }} />
                        <span style={{ color: 'var(--ink-muted)' }}>Khám bác sĩ</span>
                      </div>
                      <span style={{ color: 'var(--ink-faint)' }}>Chưa bắt đầu —</span>
                    </div>

                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: 11 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                        <span style={{ width: 10, height: 10, borderRadius: '50%', background: 'var(--line-strong)' }} />
                        <span style={{ color: 'var(--ink-muted)' }}>Siêu âm</span>
                      </div>
                      <span style={{ color: 'var(--ink-faint)' }}>Chưa bắt đầu —</span>
                    </div>
                  </div>

                  <div style={{ marginTop: 12, paddingTop: 10, borderTop: '1px solid var(--line)', display: 'grid', gridTemplateColumns: '1fr 1fr 1fr 1fr', gap: 4, fontSize: 10, textAlign: 'center' }}>
                    <div>
                      <div style={{ color: 'var(--ink-muted)' }}>Điều dưỡng</div>
                      <div style={{ fontWeight: 600, color: 'var(--ink)' }}>NT Tâm</div>
                    </div>
                    <div>
                      <div style={{ color: 'var(--ink-muted)' }}>Bắt đầu</div>
                      <div style={{ fontWeight: 600, color: 'var(--ink)' }}>10:17</div>
                    </div>
                    <div>
                      <div style={{ color: 'var(--ink-muted)' }}>Đã trôi qua</div>
                      <div style={{ fontWeight: 600, color: 'var(--ink)' }}>03:12</div>
                    </div>
                    <div>
                      <div style={{ color: 'var(--ink-muted)' }}>SLA</div>
                      <div style={{ fontWeight: 700, color: 'var(--danger)' }}>10 phút</div>
                    </div>
                  </div>
                </div>

                {/* Activity Log */}
                <div className="card" style={{ padding: 14 }}>
                  <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--ink)', marginBottom: 8 }}>Nhật ký thao tác</div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: 10, color: 'var(--ink-muted)' }}>
                    <div><strong>10:18</strong> Thiết bị BP-02 đồng bộ huyết áp</div>
                    <div><strong>10:20</strong> Điều dưỡng nhập mức độ đau</div>
                  </div>
                  <div style={{ fontSize: 10, color: 'var(--brand-600)', fontWeight: 600, cursor: 'pointer', marginTop: 6 }}>Xem tất cả nhật ký</div>
                </div>

                {/* ACTION BUTTONS */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginTop: 4 }}>
                  <div style={{ display: 'flex', gap: 8 }}>
                    <button className="btn btn-secondary" style={{ flex: 1, fontSize: 12 }}>
                      <RotateCcw size={13} /> Đo lại
                    </button>
                    <button className="btn btn-secondary" style={{ flex: 1, fontSize: 12 }}>
                      <Save size={13} /> Lưu nháp
                    </button>
                  </div>
                  
                  <button
                    className="btn btn-primary"
                    style={{
                      width: '100%',
                      padding: '12px 16px',
                      fontSize: 13,
                      fontWeight: 700,
                      borderRadius: 'var(--radius-control)',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      gap: 8,
                      background: 'var(--brand-600)',
                    }}
                  >
                    <ArrowRight size={16} /> Xác nhận sinh hiệu & chuyển khám
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* TAB 2: LỊCH SỬ SINH HIỆU & CẢNH BÁO CHUYÊN SÂU (ENHANCED BASED ON USER REQUEST) */}
        {activeTab === 'history' && (
          <div style={{ padding: 20, display: 'flex', flexDirection: 'column', gap: 16, flex: 1 }}>
            {/* Header & Filter Bar */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 16 }}>
              <div style={{ position: 'relative', flex: 1, maxWidth: 360 }}>
                <Search size={14} style={{ position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)', color: 'var(--ink-muted)' }} />
                <input
                  type="search"
                  placeholder="Tìm theo tên bệnh nhân, mã BN, mã lượt khám..."
                  value={historySearch}
                  onChange={(e) => setHistorySearch(e.target.value)}
                  style={{ paddingLeft: 32, width: '100%', fontSize: 12 }}
                />
              </div>

              <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                <Filter size={14} color="var(--ink-muted)" />
                {[
                  { id: 'all', label: 'Tất cả trạng thái' },
                  { id: 'completed', label: 'Hoàn tất' },
                  { id: 'warning', label: 'Có cảnh báo' },
                  { id: 'remeasured', label: 'Đã đo lại' },
                ].map(f => (
                  <button
                    key={f.id}
                    onClick={() => setHistoryStatusFilter(f.id)}
                    className={historyStatusFilter === f.id ? 'btn btn-primary' : 'btn btn-secondary'}
                    style={{ padding: '5px 12px', fontSize: 11 }}
                  >
                    {f.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Split layout: History List Left, Full History Detail Right */}
            <div style={{ display: 'grid', gridTemplateColumns: '380px 1fr', gap: 16, flex: 1, alignItems: 'start' }}>
              {/* History List Left */}
              <div className="card" style={{ padding: 14, display: 'flex', flexDirection: 'column', gap: 10 }}>
                <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--ink)', marginBottom: 4 }}>
                  Danh sách lượt đo đã ghi nhận ({filteredHistory.length})
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: 8, maxHeight: 680, overflowY: 'auto' }}>
                  {filteredHistory.map(rec => {
                    const isSelected = rec.id === activeHistoryRecord.id;
                    return (
                      <div
                        key={rec.id}
                        onClick={() => setSelectedHistoryId(rec.id)}
                        style={{
                          padding: 12,
                          borderRadius: 'var(--radius-control)',
                          border: isSelected ? '2px solid var(--brand-500)' : '1px solid var(--line)',
                          background: isSelected ? 'var(--brand-50)' : 'var(--surface)',
                          cursor: 'pointer',
                          transition: 'all 0.15s ease',
                        }}
                      >
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
                          <span style={{ fontSize: 14, fontWeight: 800, color: 'var(--brand-700)' }}>{rec.stt}</span>
                          <span
                            className="badge"
                            style={{
                              fontSize: 9,
                              background: rec.status === 'completed' ? 'var(--success-bg)' : rec.status === 'warning' ? 'var(--danger-bg)' : 'var(--warning-bg)',
                              color: rec.status === 'completed' ? 'var(--success)' : rec.status === 'warning' ? 'var(--danger)' : 'var(--warning)',
                            }}
                          >
                            {rec.statusLabel}
                          </span>
                        </div>

                        <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--ink)', marginBottom: 2 }}>{rec.patientName}</div>
                        <div style={{ fontSize: 11, color: 'var(--ink-muted)', marginBottom: 6 }}>
                          {rec.patientCode} · {rec.visitCode} · {rec.age} tuổi
                        </div>

                        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, color: 'var(--ink-muted)', borderTop: '1px solid var(--surface-sunken)', paddingTop: 6 }}>
                          <span>⏱ Bắt đầu: <strong>{rec.startTime}</strong> → <strong>{rec.endTime}</strong></span>
                          <span>{rec.duration}</span>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* History Record Detail Right */}
              <div className="card" style={{ padding: 20, display: 'flex', flexDirection: 'column', gap: 16 }}>
                {/* Record Header */}
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', borderBottom: '1px solid var(--line)', paddingBottom: 14 }}>
                  <div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 4 }}>
                      <span style={{ fontSize: 20, fontWeight: 800, color: 'var(--brand-700)' }}>{activeHistoryRecord.stt}</span>
                      <span style={{ fontSize: 18, fontWeight: 700, color: 'var(--ink)' }}>{activeHistoryRecord.patientName}</span>
                      <span
                        className="badge"
                        style={{
                          fontSize: 11,
                          padding: '4px 10px',
                          background: activeHistoryRecord.status === 'completed' ? 'var(--success-bg)' : activeHistoryRecord.status === 'warning' ? 'var(--danger-bg)' : 'var(--warning-bg)',
                          color: activeHistoryRecord.status === 'completed' ? 'var(--success)' : activeHistoryRecord.status === 'warning' ? 'var(--danger)' : 'var(--warning)',
                        }}
                      >
                        {activeHistoryRecord.statusLabel}
                      </span>
                    </div>
                    <div style={{ fontSize: 12, color: 'var(--ink-muted)' }}>
                      Mã bệnh nhân: <strong>{activeHistoryRecord.patientCode}</strong> &nbsp;·&nbsp; Mã lượt khám: <strong>{activeHistoryRecord.visitCode}</strong> &nbsp;·&nbsp; {activeHistoryRecord.age} tuổi ({activeHistoryRecord.gender})
                    </div>
                  </div>

                  <div style={{ textAlign: 'right' }}>
                    <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--ink)' }}>{activeHistoryRecord.doctorName}</div>
                    <div style={{ fontSize: 11, color: 'var(--ink-muted)' }}>{activeHistoryRecord.room}</div>
                  </div>
                </div>

                {/* Timing & Performer Bar */}
                <div style={{ padding: '12px 16px', background: 'var(--surface-sunken)', borderRadius: 'var(--radius-card)', display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12, fontSize: 12 }}>
                  <div>
                    <div style={{ fontSize: 10, color: 'var(--ink-muted)' }}>Bắt đầu đo</div>
                    <div style={{ fontWeight: 700, color: 'var(--ink)', display: 'flex', alignItems: 'center', gap: 4 }}>
                      <Clock size={13} color="var(--brand-600)" /> {activeHistoryRecord.startTime}
                    </div>
                  </div>
                  <div>
                    <div style={{ fontSize: 10, color: 'var(--ink-muted)' }}>Hoàn tất / Xác nhận</div>
                    <div style={{ fontWeight: 700, color: 'var(--ink)', display: 'flex', alignItems: 'center', gap: 4 }}>
                      <CheckCircle2 size={13} color="var(--success)" /> {activeHistoryRecord.endTime}
                    </div>
                  </div>
                  <div>
                    <div style={{ fontSize: 10, color: 'var(--ink-muted)' }}>Tổng thời gian đo</div>
                    <div style={{ fontWeight: 700, color: 'var(--ink)' }}>{activeHistoryRecord.duration}</div>
                  </div>
                  <div>
                    <div style={{ fontSize: 10, color: 'var(--ink-muted)' }}>Điều dưỡng thực hiện</div>
                    <div style={{ fontWeight: 700, color: 'var(--ink)', display: 'flex', alignItems: 'center', gap: 4 }}>
                      <User size={13} /> {activeHistoryRecord.nurseName}
                    </div>
                  </div>
                </div>

                {/* Alert History Log Section */}
                {activeHistoryRecord.alertsHistory.length > 0 ? (
                  <div style={{ padding: 14, background: '#fffbeb', border: '1px solid #fef3c7', borderRadius: 'var(--radius-card)' }}>
                    <div style={{ fontSize: 13, fontWeight: 700, color: '#b45309', marginBottom: 8, display: 'flex', alignItems: 'center', gap: 6 }}>
                      <AlertOctagon size={16} /> Lịch sử cảnh báo & Xử lý vượt ngưỡng ({activeHistoryRecord.alertsHistory.length})
                    </div>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                      {activeHistoryRecord.alertsHistory.map((item, idx) => (
                        <div key={idx} style={{ display: 'flex', alignItems: 'flex-start', gap: 8, fontSize: 12 }}>
                          <span style={{ fontSize: 11, fontWeight: 700, color: '#b45309', whiteSpace: 'nowrap', fontVariantNumeric: 'tabular-nums' }}>
                            {item.time}
                          </span>
                          <span style={{ color: item.severity === 'warning' ? 'var(--danger)' : 'var(--ink)' }}>
                            {item.text}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                ) : (
                  <div style={{ padding: '10px 14px', background: 'var(--success-bg)', border: '1px solid #bbf7d0', borderRadius: 'var(--radius-card)', fontSize: 12, color: 'var(--success)', display: 'flex', alignItems: 'center', gap: 6 }}>
                    <CheckCircle2 size={16} /> Không có bất kỳ cảnh báo hoặc chỉ số vượt ngưỡng nào trong lượt đo này.
                  </div>
                )}

                {/* Vitals Summary Grid */}
                <div>
                  <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--ink)', marginBottom: 10 }}>Kết quả 9 chỉ số sinh hiệu đã ghi nhận</div>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12 }}>
                    {[
                      { label: 'Mạch', val: activeHistoryRecord.vitalsSummary.pulse },
                      { label: 'Huyết áp', val: activeHistoryRecord.vitalsSummary.bp },
                      { label: 'Nhịp thở', val: activeHistoryRecord.vitalsSummary.respiration },
                      { label: 'SpO2', val: activeHistoryRecord.vitalsSummary.spo2 },
                      { label: 'Nhiệt độ', val: activeHistoryRecord.vitalsSummary.temp },
                      { label: 'Cân nặng', val: activeHistoryRecord.vitalsSummary.weight },
                      { label: 'Chiều cao', val: activeHistoryRecord.vitalsSummary.height },
                      { label: 'BMI', val: activeHistoryRecord.vitalsSummary.bmi },
                      { label: 'Mức độ đau', val: activeHistoryRecord.vitalsSummary.pain },
                    ].map((v, i) => (
                      <div key={i} style={{ padding: '10px 12px', background: 'var(--surface-sunken)', borderRadius: 'var(--radius-chip)' }}>
                        <div style={{ fontSize: 10, color: 'var(--ink-muted)' }}>{v.label}</div>
                        <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--ink)' }}>{v.val}</div>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Nurse Note */}
                <div style={{ padding: 12, background: 'var(--surface-sunken)', borderRadius: 'var(--radius-chip)' }}>
                  <div style={{ fontSize: 10, color: 'var(--ink-muted)', marginBottom: 2 }}>Ghi chú của Điều dưỡng</div>
                  <div style={{ fontSize: 12, color: 'var(--ink)', fontStyle: 'italic' }}>
                    "{activeHistoryRecord.notes}"
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

{/* SUB COMPONENTS FOR VITAL CARDS */}

function VitalCard({
  title,
  unit,
  value,
  onChange,
  source,
  time,
  statusText,
  range,
  readOnly = false,
}: {
  title: string;
  unit: string;
  value: string | number;
  onChange: (val: string) => void;
  source: string;
  time: string;
  statusText: string;
  range: string;
  readOnly?: boolean;
}) {
  return (
    <div className="card" style={{ padding: 12, display: 'flex', flexDirection: 'column', justifyContent: 'space-between', minHeight: 115 }}>
      <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--ink)', marginBottom: 4 }}>{title}</div>
      
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 4, marginBottom: 6 }}>
        {readOnly ? (
          <div style={{ fontSize: 24, fontWeight: 800, color: 'var(--ink)' }}>{value}</div>
        ) : (
          <input
            type="text"
            value={value}
            onChange={(e) => onChange(e.target.value)}
            style={{
              fontSize: 22,
              fontWeight: 800,
              color: 'var(--ink)',
              width: 80,
              padding: '2px 6px',
              height: 36,
              textAlign: 'left',
            }}
          />
        )}
        <span style={{ fontSize: 11, color: 'var(--ink-muted)' }}>{unit}</span>
      </div>

      <div style={{ fontSize: 9, color: 'var(--ink-muted)', display: 'flex', alignItems: 'center', gap: 4, marginBottom: 6 }}>
        <span>⚙ Nguồn: {source}</span>
        <span>⏱ {time}</span>
      </div>

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderTop: '1px solid var(--surface-sunken)', paddingTop: 4, fontSize: 10 }}>
        <span style={{ color: 'var(--success)', fontWeight: 600, display: 'flex', alignItems: 'center', gap: 2 }}>
          ✓ {statusText}
        </span>
        <span style={{ color: 'var(--ink-muted)' }}>{range}</span>
      </div>
    </div>
  );
}

function VitalCardBP({
  title,
  unit,
  systolic,
  diastolic,
  onSysChange,
  onDiaChange,
  source,
  time,
  statusText,
  range,
}: {
  title: string;
  unit: string;
  systolic: string | number;
  diastolic: string | number;
  onSysChange: (val: string) => void;
  onDiaChange: (val: string) => void;
  source: string;
  time: string;
  statusText: string;
  range: string;
}) {
  return (
    <div className="card" style={{ padding: 12, display: 'flex', flexDirection: 'column', justifyContent: 'space-between', minHeight: 115 }}>
      <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--ink)', marginBottom: 4 }}>{title}</div>
      
      <div style={{ display: 'flex', alignItems: 'center', gap: 4, marginBottom: 6 }}>
        <input
          type="text"
          value={systolic}
          onChange={(e) => onSysChange(e.target.value)}
          style={{
            fontSize: 20,
            fontWeight: 800,
            color: 'var(--ink)',
            width: 55,
            padding: '2px 4px',
            height: 36,
            textAlign: 'center',
          }}
        />
        <span style={{ fontSize: 18, fontWeight: 700, color: 'var(--ink-muted)' }}>/</span>
        <input
          type="text"
          value={diastolic}
          onChange={(e) => onDiaChange(e.target.value)}
          style={{
            fontSize: 20,
            fontWeight: 800,
            color: 'var(--ink)',
            width: 55,
            padding: '2px 4px',
            height: 36,
            textAlign: 'center',
          }}
        />
        <span style={{ fontSize: 11, color: 'var(--ink-muted)', marginLeft: 2 }}>{unit}</span>
      </div>

      <div style={{ fontSize: 9, color: 'var(--ink-muted)', display: 'flex', alignItems: 'center', gap: 4, marginBottom: 6 }}>
        <span>⚙ Nguồn: {source}</span>
        <span>⏱ {time}</span>
      </div>

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderTop: '1px solid var(--surface-sunken)', paddingTop: 4, fontSize: 10 }}>
        <span style={{ color: 'var(--success)', fontWeight: 600, display: 'flex', alignItems: 'center', gap: 2 }}>
          ✓ {statusText}
        </span>
        <span style={{ color: 'var(--ink-muted)' }}>{range}</span>
      </div>
    </div>
  );
}
