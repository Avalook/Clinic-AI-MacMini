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
  Zap,
  SlidersHorizontal,
  ArrowRight,
  ExternalLink,
  PauseCircle,
  RefreshCw,
  Send,
  FileText,
  Building,
  X
} from 'lucide-react';
import {
  ULTRASOUND_MASTER_QUEUE,
  ROOM_DISPATCH_DATA,
  ULTRASOUND_RESULT_DRAFTS,
  ULTRASOUND_SIGNED_PATIENTS,
} from '../../data/ultrasound-mock-data';

interface UltrasoundDashboardProps {
  onSwitchRole?: () => void;
}

export default function UltrasoundDashboard({ onSwitchRole }: UltrasoundDashboardProps) {
  const [activeTab, setActiveTab] = useState<'queue' | 'dispatch' | 'results' | 'signed_reports'>('queue');
  const [collapsed, setCollapsed] = useState(false);

  // Tab 1: Queue State
  const [queueSearch, setQueueSearch] = useState('');
  const [selectedQueueId, setSelectedQueueId] = useState<string>('us-001');

  // Tab 3: Results State
  const [resultsSearch, setResultsSearch] = useState('');
  const [selectedResultId, setSelectedResultId] = useState<string>('res-021');

  // Tab 4: Signed Reports State
  const [signedSearch, setSignedSearch] = useState('');
  const [selectedSignedPatientId, setSelectedSignedPatientId] = useState<string>('p-021');
  const [selectedReportId, setSelectedReportId] = useState<string>('r-021-1');

  const activeQueuePatient = ULTRASOUND_MASTER_QUEUE.find(q => q.id === selectedQueueId) || ULTRASOUND_MASTER_QUEUE[0];
  const activeResultDraft = ULTRASOUND_RESULT_DRAFTS.find(r => r.id === selectedResultId) || ULTRASOUND_RESULT_DRAFTS[0];
  const activeSignedPatient = ULTRASOUND_SIGNED_PATIENTS.find(p => p.id === selectedSignedPatientId) || ULTRASOUND_SIGNED_PATIENTS[0];
  const activeReport = activeSignedPatient.reports.find(r => r.id === selectedReportId) || activeSignedPatient.reports[0] || {
    id: 'empty',
    code: 'US250514-021',
    serviceName: 'Siêu âm thai đầu dò',
    dateStr: '14/05/2026',
    timeStr: '10:18',
    doctorName: 'BS. Trần Văn Dũng',
    signedStatus: 'Đã ký',
    publishStatus: 'Đã phát hành',
    conclusion: 'Thai trong tử cung, hình ảnh phù hợp tuổi thai.',
    imageDescription: 'Thai trong tử cung rõ nét. Tim thai 165 lần/phút.',
    imageUrl: 'https://images.unsplash.com/photo-1579684385127-1ef15d508118?auto=format&fit=crop&w=400&q=80',
    timeline: [{ time: '10:18', action: 'Bác sĩ ký báo cáo' }],
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
            SIÊU ÂM
          </div>
        )}

        {/* Navigation Tabs */}
        <nav style={{ flex: 1, padding: '4px 8px', display: 'flex', flexDirection: 'column', gap: 2 }}>
          <button
            onClick={() => setActiveTab('queue')}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 10,
              padding: collapsed ? '10px' : '10px 12px',
              borderRadius: 'var(--radius-control)',
              border: 'none',
              background: activeTab === 'queue' ? 'var(--brand-50)' : 'transparent',
              color: activeTab === 'queue' ? 'var(--brand-700)' : 'var(--ink-soft)',
              fontSize: 13,
              fontWeight: activeTab === 'queue' ? 600 : 500,
              cursor: 'pointer',
              textAlign: 'left',
              width: '100%',
            }}
          >
            <Clock size={18} /> {!collapsed && 'Danh sách chờ siêu âm'}
          </button>

          <button
            onClick={() => setActiveTab('dispatch')}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 10,
              padding: collapsed ? '10px' : '10px 12px',
              borderRadius: 'var(--radius-control)',
              border: 'none',
              background: activeTab === 'dispatch' ? 'var(--brand-50)' : 'transparent',
              color: activeTab === 'dispatch' ? 'var(--brand-700)' : 'var(--ink-soft)',
              fontSize: 13,
              fontWeight: activeTab === 'dispatch' ? 600 : 500,
              cursor: 'pointer',
              textAlign: 'left',
              width: '100%',
            }}
          >
            <Activity size={18} /> {!collapsed && 'Điều phối phòng SA'}
          </button>

          <button
            onClick={() => setActiveTab('results')}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 10,
              padding: collapsed ? '10px' : '10px 12px',
              borderRadius: 'var(--radius-control)',
              border: 'none',
              background: activeTab === 'results' ? 'var(--brand-50)' : 'transparent',
              color: activeTab === 'results' ? 'var(--brand-700)' : 'var(--ink-soft)',
              fontSize: 13,
              fontWeight: activeTab === 'results' ? 600 : 500,
              cursor: 'pointer',
              textAlign: 'left',
              width: '100%',
            }}
          >
            <Zap size={18} /> {!collapsed && 'Kết quả siêu âm'}
          </button>

          <button
            onClick={() => setActiveTab('signed_reports')}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 10,
              padding: collapsed ? '10px' : '10px 12px',
              borderRadius: 'var(--radius-control)',
              border: 'none',
              background: activeTab === 'signed_reports' ? 'var(--brand-50)' : 'transparent',
              color: activeTab === 'signed_reports' ? 'var(--brand-700)' : 'var(--ink-soft)',
              fontSize: 13,
              fontWeight: activeTab === 'signed_reports' ? 600 : 500,
              cursor: 'pointer',
              textAlign: 'left',
              width: '100%',
            }}
          >
            <FileCheck size={18} /> {!collapsed && 'Báo cáo đã ký'}
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

        {/* User profile at bottom */}
        <div style={{ padding: '12px 16px', borderTop: '1px solid var(--line)', display: 'flex', alignItems: 'center', gap: 10 }}>
          <div style={{ width: 32, height: 32, borderRadius: '50%', background: 'var(--brand-100)', color: 'var(--brand-700)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 11, fontWeight: 700 }}>
            NP
          </div>
          {!collapsed && (
            <div>
              <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--ink)' }}>Nguyễn Phương Anh</div>
              <div style={{ fontSize: 10, color: 'var(--ink-muted)' }}>Thư ký siêu âm</div>
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

      {/* MAIN CONTENT AREA */}
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
              {activeTab === 'queue' && 'Danh sách chờ siêu âm'}
              {activeTab === 'dispatch' && 'Điều phối phòng siêu âm (SA1–SA3)'}
              {activeTab === 'results' && 'Kết quả siêu âm & Hoàn thiện báo cáo'}
              {activeTab === 'signed_reports' && 'Báo cáo siêu âm đã ký'}
            </h1>
            <p style={{ fontSize: 12, color: 'var(--ink-muted)', margin: '2px 0 0' }}>
              {activeTab === 'queue' && 'Tiếp nhận yêu cầu, kiểm tra sẵn sàng và theo dõi thời gian chờ.'}
              {activeTab === 'dispatch' && 'Theo dõi SA1–SA3, hàng đợi và xử lý thay đổi phòng.'}
              {activeTab === 'results' && 'Hoàn thiện mô tả, đính kèm hình ảnh và gửi bác sĩ rà soát.'}
              {activeTab === 'signed_reports' && 'Tra cứu lịch sử kết quả đã ký và phát hành theo từng bệnh nhân.'}
            </p>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, color: 'var(--brand-600)' }}>
              <span style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--success)', animation: 'pulse-dot 1.5s ease-in-out infinite' }} />
              Tự động cập nhật
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
                NP
              </div>
              <div>
                <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--ink)' }}>Nguyễn Phương Anh</div>
                <div style={{ fontSize: 11, color: 'var(--ink-muted)' }}>Thư ký siêu âm</div>
              </div>
            </div>
          </div>
        </header>

        {/* BODY TAB CONTENT */}
        <div style={{ padding: 20, display: 'flex', flexDirection: 'column', gap: 16, flex: 1 }}>

          {/* ========================================================================= */}
          {/* TAB 1: DANH SÁCH CHỜ SIÊU ÂM (MATCHING IMAGE 4)                           */}
          {/* ========================================================================= */}
          {activeTab === 'queue' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 16, flex: 1 }}>
              {/* Top 4 KPI Cards */}
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12 }}>
                {[
                  { label: 'Tổng yêu cầu hôm nay', value: 146, icon: Users, color: 'var(--brand-600)', bg: 'var(--brand-50)' },
                  { label: 'Chờ tiếp nhận', value: 12, icon: Clock, color: 'var(--warning)', bg: 'var(--warning-bg)' },
                  { label: 'Chờ phòng', value: 31, icon: Building, color: 'var(--brand-600)', bg: 'var(--brand-50)' },
                  { label: 'Quá SLA', value: 4, icon: AlertTriangle, color: 'var(--danger)', bg: 'var(--danger-bg)' },
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

              {/* Master Queue Grid */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 340px', gap: 16, flex: 1, alignItems: 'start' }}>
                {/* Left Queue Table */}
                <div className="card" style={{ padding: 14, display: 'flex', flexDirection: 'column', gap: 12 }}>
                  <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
                    <div style={{ position: 'relative', flex: 1 }}>
                      <Search size={14} style={{ position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)', color: 'var(--ink-muted)' }} />
                      <input
                        type="search"
                        placeholder="Tìm bệnh nhân, mã yêu cầu hoặc dịch vụ"
                        value={queueSearch}
                        onChange={(e) => setQueueSearch(e.target.value)}
                        style={{ paddingLeft: 32, width: '100%', fontSize: 12 }}
                      />
                    </div>
                    <select style={{ fontSize: 12, padding: '6px 10px' }}><option>Tất cả dịch vụ</option></select>
                    <select style={{ fontSize: 12, padding: '6px 10px' }}><option>Ưu tiên & SLA</option></select>
                    <button className="btn btn-secondary" style={{ fontSize: 12 }}><SlidersHorizontal size={14} /> Bộ lọc</button>
                  </div>

                  <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--ink)' }}>Hàng đợi siêu âm <span style={{ color: 'var(--ink-muted)', fontWeight: 400 }}>(38 bệnh nhân đang chờ)</span></div>

                  <div className="table-wrap">
                    <table>
                      <thead>
                        <tr>
                          <th>STT</th>
                          <th>Bệnh nhân</th>
                          <th>Chỉ định</th>
                          <th>Hẹn lúc</th>
                          <th>Đã chờ</th>
                          <th>Ưu tiên</th>
                          <th>Trạng thái</th>
                        </tr>
                      </thead>
                      <tbody>
                        {ULTRASOUND_MASTER_QUEUE.map(item => {
                          const isSelected = item.id === activeQueuePatient.id;
                          return (
                            <tr
                              key={item.id}
                              onClick={() => setSelectedQueueId(item.id)}
                              style={{ cursor: 'pointer', background: isSelected ? 'var(--brand-50)' : undefined }}
                            >
                              <td style={{ fontSize: 12, fontWeight: 700, color: 'var(--brand-700)' }}>{item.stt}</td>
                              <td>
                                <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--ink)' }}>{item.patientName}</div>
                                <div style={{ fontSize: 10, color: 'var(--ink-muted)' }}>{item.code} · {item.birthYear} · {item.gender} · {item.age} tuổi</div>
                              </td>
                              <td style={{ fontSize: 11, fontWeight: 600 }}>{item.serviceName}</td>
                              <td style={{ fontSize: 11 }}>{item.appointmentTime}</td>
                              <td style={{ fontSize: 11, color: item.status === 'overdue' ? 'var(--danger)' : 'var(--ink)' }}>{item.waitTimeStr}</td>
                              <td>
                                <span className={item.priority === 'Ưu tiên' ? 'badge badge-warning' : 'badge badge-secondary'} style={{ fontSize: 10 }}>
                                  {item.priority}
                                </span>
                              </td>
                              <td>
                                <span style={{ padding: '3px 8px', borderRadius: 4, background: item.statusBg, color: item.statusColor, fontSize: 10, fontWeight: 700 }}>
                                  {item.statusLabel}
                                </span>
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                </div>

                {/* Right Details Panel */}
                <div className="card" style={{ padding: 16, display: 'flex', flexDirection: 'column', gap: 14 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid var(--line)', paddingBottom: 10 }}>
                    <div>
                      <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--ink-muted)', textTransform: 'uppercase' }}>Chi tiết yêu cầu</div>
                      <div style={{ fontSize: 14, fontWeight: 800, color: 'var(--brand-700)' }}>{activeQueuePatient.code}</div>
                    </div>
                    <button className="btn btn-secondary" style={{ padding: 4 }}><X size={14} /></button>
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                    <div style={{ width: 38, height: 38, borderRadius: '50%', background: 'var(--surface-sunken)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 12, fontWeight: 800 }}>
                      LC
                    </div>
                    <div>
                      <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--ink)' }}>{activeQueuePatient.patientName}</div>
                      <div style={{ fontSize: 10, color: 'var(--ink-muted)' }}>{activeQueuePatient.birthYear} · Nữ · {activeQueuePatient.age} tuổi</div>
                      <a href="#" style={{ fontSize: 10, color: 'var(--brand-600)', textDecoration: 'none', display: 'inline-flex', alignItems: 'center', gap: 2 }}>
                        Mở hồ sơ bệnh nhân <ExternalLink size={10} />
                      </a>
                    </div>
                  </div>

                  <div style={{ fontSize: 11, display: 'flex', flexDirection: 'column', gap: 6, background: 'var(--surface-sunken)', padding: 10, borderRadius: 6 }}>
                    <div style={{ fontWeight: 700, color: 'var(--ink)' }}>Thông tin yêu cầu</div>
                    <div><span style={{ color: 'var(--ink-muted)' }}>Dịch vụ:</span> <strong>{activeQueuePatient.serviceName}</strong></div>
                    <div><span style={{ color: 'var(--ink-muted)' }}>Chỉ định:</span> {activeQueuePatient.indication}</div>
                    <div><span style={{ color: 'var(--ink-muted)' }}>Bác sĩ chỉ định:</span> {activeQueuePatient.indicationDoctor}</div>
                    <div><span style={{ color: 'var(--ink-muted)' }}>Thời gian chỉ định:</span> {activeQueuePatient.indicationTime}</div>
                    <div><span style={{ color: 'var(--ink-muted)' }}>Ghi chú:</span> <span style={{ color: 'var(--danger)', fontWeight: 600 }}>{activeQueuePatient.notes}</span></div>
                  </div>

                  {/* Readiness Checklist */}
                  <div style={{ borderTop: '1px solid var(--line)', paddingTop: 10 }}>
                    <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--ink)', marginBottom: 6 }}>Sẵn sàng thực hiện</div>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: 11 }}>
                      <div style={{ color: activeQueuePatient.readiness.checkedIn ? 'var(--success)' : 'var(--ink-muted)' }}>
                        {activeQueuePatient.readiness.checkedIn ? '✓' : '○'} Đã check-in
                      </div>
                      <div style={{ color: activeQueuePatient.readiness.identityVerified ? 'var(--success)' : 'var(--ink-muted)' }}>
                        {activeQueuePatient.readiness.identityVerified ? '✓' : '○'} Đã xác nhận danh tính
                      </div>
                      <div style={{ color: activeQueuePatient.readiness.indicationValid ? 'var(--success)' : 'var(--ink-muted)' }}>
                        {activeQueuePatient.readiness.indicationValid ? '✓' : '○'} Chỉ định hợp lệ
                      </div>
                      <div style={{ color: activeQueuePatient.readiness.allowedPerform ? 'var(--success)' : 'var(--ink-muted)' }}>
                        {activeQueuePatient.readiness.allowedPerform ? '✓' : '○'} Đã được phép thực hiện
                      </div>
                    </div>
                  </div>

                  <div style={{ background: '#dcfce7', padding: 8, borderRadius: 6, fontSize: 11, fontWeight: 700, color: '#15803d', textAlign: 'center' }}>
                    Sẵn sàng chờ phòng
                  </div>

                  <div style={{ padding: 10, background: '#fffbeb', border: '1px solid #fef3c7', borderRadius: 6, fontSize: 10, color: '#b45309' }}>
                    ℹ SA2 đang bảo trì; hệ thống sẽ tránh chuyển bệnh nhân vào SA2.
                  </div>

                  <div style={{ display: 'flex', gap: 8 }}>
                    <button className="btn btn-secondary" style={{ fontSize: 11 }}><FileText size={13} /> Ghi chú</button>
                    <button
                      onClick={() => setActiveTab('dispatch')}
                      className="btn btn-primary"
                      style={{ flex: 1, fontSize: 11, background: 'var(--brand-600)' }}
                    >
                      Chuyển sang điều phối phòng <ArrowRight size={13} />
                    </button>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* ========================================================================= */}
          {/* TAB 2: ĐIỀU PHỐI PHÒNG SA (MATCHING IMAGES 3 & 5)                         */}
          {/* ========================================================================= */}
          {activeTab === 'dispatch' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 16, flex: 1 }}>
              {/* Top 5 KPI Cards */}
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 10 }}>
                {[
                  { label: 'Tổng yêu cầu hôm nay', value: 146, icon: Users, color: 'var(--brand-600)', bg: 'var(--brand-50)' },
                  { label: 'Chờ phòng', value: 31, icon: Clock, color: 'var(--warning)', bg: 'var(--warning-bg)', sub: 'TB chờ 27 phút' },
                  { label: 'Đang thực hiện', value: 3, icon: Activity, color: 'var(--brand-600)', bg: 'var(--brand-50)', sub: 'Đang thực hiện' },
                  { label: 'Chờ thư ký hoàn thiện', value: 7, icon: FileText, color: 'var(--brand-600)', bg: 'var(--brand-50)', sub: 'TB chờ 18 phút' },
                  { label: 'Chờ bác sĩ ký', value: 14, icon: UserCheck, color: 'var(--warning)', bg: 'var(--warning-bg)', sub: 'TB chờ 15 phút' },
                ].map((kpi, idx) => {
                  const Icon = kpi.icon;
                  return (
                    <div key={idx} className="card" style={{ padding: '10px 12px', display: 'flex', alignItems: 'center', gap: 10 }}>
                      <div style={{ width: 32, height: 32, borderRadius: '50%', background: kpi.bg, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                        <Icon size={16} color={kpi.color} />
                      </div>
                      <div>
                        <div style={{ fontSize: 10, color: 'var(--ink-muted)' }}>{kpi.label}</div>
                        <div style={{ fontSize: 18, fontWeight: 700, color: 'var(--ink)', lineHeight: 1.1 }}>{kpi.value}</div>
                        {kpi.sub && <div style={{ fontSize: 9, color: 'var(--ink-muted)' }}>{kpi.sub}</div>}
                      </div>
                    </div>
                  );
                })}
              </div>

              {/* 3 Room Grid & Details Split */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 340px', gap: 16, flex: 1, alignItems: 'start' }}>
                {/* 3 Room Columns */}
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 14 }}>
                  {/* ROOM SA1 */}
                  <div className="card" style={{ padding: 14, display: 'flex', flexDirection: 'column', gap: 12 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <span style={{ fontSize: 15, fontWeight: 800, color: 'var(--ink)' }}>SA1</span>
                      <span className="badge badge-success">Đang hoạt động</span>
                    </div>

                    <div style={{ border: '1px solid var(--brand-200)', background: 'var(--brand-50)', padding: 10, borderRadius: 8 }}>
                      <div style={{ fontSize: 10, color: 'var(--ink-muted)', marginBottom: 2 }}>Bệnh nhân hiện tại</div>
                      <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--ink)' }}>Nguyễn Thị Mai</div>
                      <div style={{ fontSize: 10, color: 'var(--ink-muted)' }}>US250514-021 · Siêu âm thai đầu dò</div>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 6, fontSize: 10 }}>
                        <span>10:05 ─── 10:25</span>
                        <span style={{ color: 'var(--brand-600)', fontWeight: 700 }}>Đang thực hiện</span>
                      </div>
                    </div>

                    <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--ink)' }}>Danh sách chờ (5)</div>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                      {ROOM_DISPATCH_DATA.SA1.waitingList.map((item, idx) => (
                        <div key={idx} style={{ padding: 8, background: 'var(--surface-sunken)', borderRadius: 6, fontSize: 11 }}>
                          <div style={{ display: 'flex', justifyContent: 'space-between', fontWeight: 700 }}>
                            <span>{item.stt}. {item.patientName}</span>
                            <span style={{ fontSize: 10, color: 'var(--ink-muted)' }}>{item.code}</span>
                          </div>
                          <div style={{ fontSize: 10, color: 'var(--ink-muted)' }}>{item.serviceName}</div>
                          <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 4, fontSize: 10 }}>
                            <span>{item.waitTime}</span>
                            <span style={{ padding: '2px 6px', borderRadius: 4, background: item.badgeBg, color: item.badgeColor, fontWeight: 700 }}>{item.badgeLabel}</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* ROOM SA2 (MAINTENANCE) */}
                  <div className="card" style={{ padding: 14, display: 'flex', flexDirection: 'column', gap: 12, border: '1px solid #fed7aa' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <span style={{ fontSize: 15, fontWeight: 800, color: 'var(--ink)' }}>SA2</span>
                      <span style={{ padding: '2px 6px', background: '#ffedd5', color: '#c2410c', borderRadius: 4, fontSize: 10, fontWeight: 700 }}>Tạm dừng bảo trì</span>
                    </div>

                    <div style={{ background: '#fff7ed', border: '1px solid #ffedd5', padding: 14, borderRadius: 8, textAlign: 'center' }}>
                      <PauseCircle size={28} color="#c2410c" style={{ marginBottom: 6 }} />
                      <div style={{ fontSize: 13, fontWeight: 800, color: '#c2410c' }}>Phòng SA2 đang bảo trì</div>
                      <div style={{ fontSize: 10, color: '#9a3412', marginTop: 2 }}>Dự kiến hoàn tất lúc 12:30</div>
                      <div style={{ fontSize: 10, color: 'var(--ink-muted)', marginTop: 6 }}>Cần người điều phối chọn phòng khác; hệ thống không tự động chuyển.</div>
                    </div>

                    <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--ink)' }}>Chờ điều phối lại (4)</div>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                      {ROOM_DISPATCH_DATA.SA2.waitingList.map((item, idx) => (
                        <div key={idx} style={{ padding: 8, background: 'var(--surface-sunken)', borderRadius: 6, fontSize: 11, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <div>
                            <div style={{ fontWeight: 700 }}>{item.stt}. {item.patientName}</div>
                            <div style={{ fontSize: 10, color: 'var(--ink-muted)' }}>{item.serviceName}</div>
                          </div>
                          <button className="btn btn-secondary" style={{ padding: '2px 6px', fontSize: 9 }}>Chờ chọn phòng</button>
                        </div>
                      ))}
                    </div>

                    <button className="btn btn-secondary" style={{ width: '100%', fontSize: 11, color: '#c2410c', borderColor: '#fed7aa' }}>
                      <RefreshCw size={12} /> Điều phối 4 bệnh nhân
                    </button>
                  </div>

                  {/* ROOM SA3 */}
                  <div className="card" style={{ padding: 14, display: 'flex', flexDirection: 'column', gap: 12 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <span style={{ fontSize: 15, fontWeight: 800, color: 'var(--ink)' }}>SA3</span>
                      <span className="badge badge-success">Đang hoạt động</span>
                    </div>

                    <div style={{ border: '1px solid var(--brand-200)', background: 'var(--brand-50)', padding: 10, borderRadius: 8 }}>
                      <div style={{ fontSize: 10, color: 'var(--ink-muted)', marginBottom: 2 }}>Bệnh nhân hiện tại</div>
                      <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--ink)' }}>Phạm Thị Lan</div>
                      <div style={{ fontSize: 10, color: 'var(--ink-muted)' }}>US250514-015 · Siêu âm ổ bụng tổng quát</div>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 6, fontSize: 10 }}>
                        <span>09:55 ─── 10:25</span>
                        <span style={{ color: 'var(--brand-600)', fontWeight: 700 }}>Đang thực hiện</span>
                      </div>
                    </div>

                    <div style={{ background: '#dbeafe', padding: 8, borderRadius: 6, fontSize: 10, color: '#1e40af' }}>
                      ℹ Đã nhận 4 bệnh nhân chuyển từ SA2 · thời gian chờ có thể lâu hơn
                    </div>

                    <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--ink)' }}>Danh sách chờ (7)</div>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                      {ROOM_DISPATCH_DATA.SA3.waitingList.map((item, idx) => (
                        <div key={idx} style={{ padding: 8, background: 'var(--surface-sunken)', borderRadius: 6, fontSize: 11 }}>
                          <div style={{ display: 'flex', justifyContent: 'space-between', fontWeight: 700 }}>
                            <span>{item.stt}. {item.patientName}</span>
                            <span style={{ fontSize: 9, padding: '1px 4px', background: '#dbeafe', color: '#1d4ed8', borderRadius: 3 }}>{item.fromRoom}</span>
                          </div>
                          <div style={{ fontSize: 10, color: 'var(--ink-muted)' }}>{item.serviceName}</div>
                          <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 4, fontSize: 10 }}>
                            <span>{item.waitTime}</span>
                            <span style={{ padding: '2px 6px', borderRadius: 4, background: item.badgeBg, color: item.badgeColor, fontWeight: 700 }}>{item.badgeLabel}</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>

                {/* Right Side Details Panel */}
                <div className="card" style={{ padding: 16, display: 'flex', flexDirection: 'column', gap: 12 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid var(--line)', paddingBottom: 10 }}>
                    <div>
                      <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--ink-muted)', textTransform: 'uppercase' }}>Chi tiết yêu cầu</div>
                      <div style={{ fontSize: 14, fontWeight: 800, color: 'var(--brand-700)' }}>US250514-021</div>
                    </div>
                    <button className="btn btn-secondary" style={{ padding: 4 }}><X size={14} /></button>
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                    <div style={{ width: 36, height: 36, borderRadius: '50%', background: 'var(--brand-50)', color: 'var(--brand-700)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 12, fontWeight: 800 }}>
                      NT
                    </div>
                    <div>
                      <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--ink)' }}>Nguyễn Thị Mai</div>
                      <div style={{ fontSize: 10, color: 'var(--ink-muted)' }}>1994 · Nữ · 32 tuổi</div>
                    </div>
                  </div>

                  <div style={{ fontSize: 11, display: 'flex', flexDirection: 'column', gap: 4, background: 'var(--surface-sunken)', padding: 10, borderRadius: 6 }}>
                    <div><span style={{ color: 'var(--ink-muted)' }}>Dịch vụ:</span> <strong>Siêu âm thai đầu dò</strong></div>
                    <div><span style={{ color: 'var(--ink-muted)' }}>Chỉ định:</span> Theo dõi thai kỳ</div>
                    <div><span style={{ color: 'var(--ink-muted)' }}>Bác sĩ chỉ định:</span> BS. Trần Văn Dũng</div>
                    <div><span style={{ color: 'var(--ink-muted)' }}>Thời gian chỉ định:</span> 14/05/2026 09:30</div>
                  </div>

                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span style={{ fontSize: 11, color: 'var(--ink-muted)' }}>Phòng thực hiện:</span>
                    <select style={{ fontSize: 11, padding: '4px 8px' }}><option>SA1</option></select>
                  </div>

                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span style={{ fontSize: 11, color: 'var(--ink-muted)' }}>Trạng thái hiện tại:</span>
                    <span className="badge badge-brand">Đang thực hiện</span>
                  </div>

                  {/* Countdown Timer */}
                  <div style={{ background: 'var(--surface-sunken)', padding: 10, borderRadius: 6, textAlign: 'center' }}>
                    <div style={{ fontSize: 10, color: 'var(--ink-muted)' }}>Đếm ngược thời gian làm SA</div>
                    <div style={{ fontSize: 20, fontWeight: 800, color: 'var(--brand-700)', fontVariantNumeric: 'tabular-nums' }}>01:39:40</div>
                  </div>

                  <button
                    onClick={() => setActiveTab('results')}
                    className="btn btn-primary"
                    style={{ width: '100%', fontSize: 12, padding: '10px', background: 'var(--brand-600)' }}
                  >
                    📂 Mở kết quả siêu âm
                  </button>
                </div>
              </div>

              {/* Bottom Process Bar (Matching Image 5) */}
              <div className="card" style={{ padding: 12, display: 'flex', alignItems: 'center', justifyContent: 'space-around', fontSize: 11 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, color: 'var(--brand-700)', fontWeight: 700 }}>
                  <Clock size={16} /> 1. Đang thực hiện (Bác sĩ tiến hành)
                </div>
                <ArrowRight size={14} color="var(--ink-muted)" />
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, color: 'var(--ink-muted)' }}>
                  <FileText size={16} /> 2. Chờ thư ký hoàn thiện (Mô tả & kết luận)
                </div>
                <ArrowRight size={14} color="var(--ink-muted)" />
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, color: 'var(--ink-muted)' }}>
                  <UserCheck size={16} /> 3. Chờ bác sĩ ký (Rà soát & ký phát hành)
                </div>
                <ArrowRight size={14} color="var(--ink-muted)" />
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, color: 'var(--success)' }}>
                  <CheckCircle2 size={16} /> 4. Hoàn tất (Sẵn sàng trả bệnh nhân)
                </div>
              </div>
            </div>
          )}

          {/* ========================================================================= */}
          {/* TAB 3: KẾT QUẢ SIÊU ÂM (MATCHING IMAGE 2)                                 */}
          {/* ========================================================================= */}
          {activeTab === 'results' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 16, flex: 1 }}>
              {/* Top 4 KPI Cards */}
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12 }}>
                {[
                  { label: 'Chờ nhập kết quả', value: 6, icon: Users, color: 'var(--brand-600)', bg: 'var(--brand-50)' },
                  { label: 'Bản nháp', value: 4, icon: Clock, color: 'var(--warning)', bg: 'var(--warning-bg)' },
                  { label: 'Chờ thư ký hoàn thiện', value: 7, icon: FileText, color: 'var(--brand-600)', bg: 'var(--brand-50)' },
                  { label: 'Chờ bác sĩ ký', value: 14, icon: UserCheck, color: 'var(--warning)', bg: 'var(--warning-bg)' },
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

              {/* Master Workspace Grid */}
              <div style={{ display: 'grid', gridTemplateColumns: '280px 1fr 300px', gap: 16, flex: 1, alignItems: 'start' }}>
                {/* Left Patient List */}
                <div className="card" style={{ padding: 14, display: 'flex', flexDirection: 'column', gap: 10 }}>
                  <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--ink)' }}>Danh sách kết quả</div>
                  
                  <div style={{ position: 'relative' }}>
                    <Search size={13} style={{ position: 'absolute', left: 8, top: '50%', transform: 'translateY(-50%)', color: 'var(--ink-muted)' }} />
                    <input
                      type="search"
                      placeholder="Tìm bệnh nhân hoặc mã yêu cầu"
                      value={resultsSearch}
                      onChange={(e) => setResultsSearch(e.target.value)}
                      style={{ paddingLeft: 26, width: '100%', fontSize: 11 }}
                    />
                  </div>

                  <div style={{ display: 'flex', gap: 4, fontSize: 10 }}>
                    <button className="btn btn-primary" style={{ padding: '2px 6px' }}>Chờ hoàn thiện (7)</button>
                    <button className="btn btn-secondary" style={{ padding: '2px 6px' }}>Bản nháp (4)</button>
                    <button className="btn btn-secondary" style={{ padding: '2px 6px' }}>Chờ ký (14)</button>
                  </div>

                  <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                    {ULTRASOUND_RESULT_DRAFTS.map(item => {
                      const isSelected = item.id === activeResultDraft.id;
                      return (
                        <div
                          key={item.id}
                          onClick={() => setSelectedResultId(item.id)}
                          style={{
                            padding: 8,
                            borderRadius: 'var(--radius-control)',
                            border: isSelected ? '2px solid var(--brand-500)' : '1px solid var(--line)',
                            background: isSelected ? 'var(--brand-50)' : 'var(--surface)',
                            cursor: 'pointer',
                          }}
                        >
                          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, fontWeight: 700 }}>
                            <span>{item.patientName}</span>
                            <span style={{ fontSize: 9, padding: '2px 4px', background: item.statusBg, color: item.statusColor, borderRadius: 4 }}>{item.statusLabel}</span>
                          </div>
                          <div style={{ fontSize: 10, color: 'var(--ink-muted)' }}>{item.code} · {item.serviceName}</div>
                          <div style={{ fontSize: 9, color: 'var(--ink-muted)', marginTop: 2 }}>{item.room} · {item.finishTime}</div>
                        </div>
                      );
                    })}
                  </div>
                </div>

                {/* Middle Editing Form */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
                  <div className="card" style={{ padding: 16, display: 'flex', flexDirection: 'column', gap: 14 }}>
                    {/* Patient Header Banner */}
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid var(--line)', paddingBottom: 10 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                        <div style={{ width: 36, height: 36, borderRadius: '50%', background: 'var(--brand-50)', color: 'var(--brand-700)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 12, fontWeight: 800 }}>
                          NT
                        </div>
                        <div>
                          <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--ink)' }}>{activeResultDraft.patientName}</div>
                          <div style={{ fontSize: 11, color: 'var(--ink-muted)' }}>{activeResultDraft.code} · {activeResultDraft.birthYear} · Nữ · {activeResultDraft.age} tuổi</div>
                        </div>
                      </div>

                      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <span className="badge badge-brand">{activeResultDraft.room}</span>
                        <span style={{ fontSize: 11, color: 'var(--ink-muted)' }}>{activeResultDraft.serviceName}</span>
                        <a href="#" style={{ fontSize: 11, color: 'var(--brand-600)', textDecoration: 'none' }}>Mở hồ sơ bệnh nhân ↗</a>
                      </div>
                    </div>

                    {/* Template Selector */}
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <span style={{ fontSize: 11, fontWeight: 600, color: 'var(--ink)' }}>Mẫu báo cáo:</span>
                      <select style={{ flex: 1, fontSize: 11, padding: '6px 8px' }}><option>{activeResultDraft.templateName}</option></select>
                      <button className="btn btn-secondary" style={{ fontSize: 11 }}><FileText size={13} /> Áp dụng mẫu</button>
                    </div>

                    {/* Image Thumbnails */}
                    <div>
                      <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--ink)', marginBottom: 6 }}>Hình ảnh siêu âm</div>
                      <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
                        {activeResultDraft.images.map(img => (
                          <div key={img.id} style={{ border: '1px solid var(--line)', borderRadius: 6, overflow: 'hidden', width: 120 }}>
                            <img src={img.url} alt={img.name} style={{ width: '100%', height: 80, objectFit: 'cover' }} />
                            <div style={{ fontSize: 10, padding: 4, textAlign: 'center', color: 'var(--ink-muted)' }}>{img.name}</div>
                          </div>
                        ))}
                        <button
                          style={{
                            width: 120,
                            height: 100,
                            borderRadius: 6,
                            border: '2px dashed var(--line)',
                            background: 'var(--surface-sunken)',
                            display: 'flex',
                            flexDirection: 'column',
                            alignItems: 'center',
                            justifyContent: 'center',
                            gap: 4,
                            cursor: 'pointer',
                            color: 'var(--brand-600)',
                            fontSize: 11,
                          }}
                        >
                          <Plus size={18} /> Thêm hình ảnh
                        </button>
                      </div>
                      <div style={{ fontSize: 9, color: 'var(--ink-muted)', marginTop: 4 }}>Đã đồng bộ 3 hình từ máy SA1</div>
                    </div>

                    {/* Form Input Textareas */}
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                      <div>
                        <label style={{ fontSize: 11, fontWeight: 700, color: 'var(--ink)', display: 'block', marginBottom: 4 }}>Mô tả hình ảnh</label>
                        <textarea
                          defaultValue={activeResultDraft.imageDescription}
                          rows={3}
                          style={{ width: '100%', fontSize: 11, resize: 'none' }}
                        />
                      </div>

                      <div>
                        <label style={{ fontSize: 11, fontWeight: 700, color: 'var(--ink)', display: 'block', marginBottom: 4 }}>Kết luận sơ bộ</label>
                        <textarea
                          defaultValue={activeResultDraft.preliminaryConclusion}
                          rows={2}
                          style={{ width: '100%', fontSize: 11, resize: 'none' }}
                        />
                      </div>

                      <div>
                        <label style={{ fontSize: 11, fontWeight: 700, color: 'var(--ink)', display: 'block', marginBottom: 4 }}>Khuyến nghị</label>
                        <textarea
                          defaultValue={activeResultDraft.recommendations}
                          rows={2}
                          style={{ width: '100%', fontSize: 11, resize: 'none' }}
                        />
                      </div>
                    </div>

                    <div style={{ fontSize: 10, color: 'var(--ink-muted)', textAlign: 'right' }}>
                      Người cập nhật gần nhất: {activeResultDraft.lastUpdated}
                    </div>
                  </div>

                  {/* Bottom Actions */}
                  <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
                    <button className="btn btn-secondary" style={{ fontSize: 12 }}><Save size={14} /> Lưu nháp</button>
                    <button className="btn btn-primary" style={{ fontSize: 12, padding: '10px 16px', background: 'var(--brand-600)' }}>
                      <Send size={14} /> Gửi bác sĩ rà soát
                    </button>
                  </div>
                </div>

                {/* Right Verification & Audit Log Panel */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                  <div className="card" style={{ padding: 14 }}>
                    <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--ink)', marginBottom: 8 }}>Thông tin chỉ định</div>
                    <div style={{ fontSize: 11, display: 'flex', flexDirection: 'column', gap: 4 }}>
                      <div><span style={{ color: 'var(--ink-muted)' }}>Dịch vụ:</span> <strong>{activeResultDraft.serviceName}</strong></div>
                      <div><span style={{ color: 'var(--ink-muted)' }}>Chỉ định:</span> Theo dõi thai kỳ</div>
                      <div><span style={{ color: 'var(--ink-muted)' }}>Bác sĩ chỉ định:</span> {activeResultDraft.indicationDoctor}</div>
                      <div><span style={{ color: 'var(--ink-muted)' }}>Bác sĩ thực hiện:</span> {activeResultDraft.doctorPerformer}</div>
                      <div><span style={{ color: 'var(--ink-muted)' }}>Phòng thực hiện:</span> {activeResultDraft.room}</div>
                      <div><span style={{ color: 'var(--ink-muted)' }}>Hoàn tất lúc:</span> 10:25 · 14/05/2026</div>
                    </div>
                  </div>

                  <div className="card" style={{ padding: 14 }}>
                    <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--ink)', marginBottom: 8 }}>Kiểm tra trước khi gửi</div>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 6, fontSize: 11 }}>
                      <label style={{ display: 'flex', alignItems: 'center', gap: 6 }}><input type="checkbox" defaultChecked /> Đúng bệnh nhân và chỉ định</label>
                      <label style={{ display: 'flex', alignItems: 'center', gap: 6 }}><input type="checkbox" defaultChecked /> Đã đính kèm hình ảnh</label>
                      <label style={{ display: 'flex', alignItems: 'center', gap: 6 }}><input type="checkbox" defaultChecked /> Đã hoàn thiện mô tả</label>
                      <label style={{ display: 'flex', alignItems: 'center', gap: 6 }}><input type="checkbox" /> Bác sĩ đã nhập kết luận</label>
                    </div>
                  </div>

                  <div style={{ padding: 10, background: '#dbeafe', borderRadius: 6, fontSize: 10, color: '#1e40af' }}>
                    ℹ Thư ký có thể lưu nháp và gửi rà soát. Chỉ bác sĩ được ký và phát hành báo cáo.
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* ========================================================================= */}
          {/* TAB 4: BÁO CÁO ĐÃ KÝ (MATCHING IMAGE 1)                                   */}
          {/* ========================================================================= */}
          {activeTab === 'signed_reports' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 16, flex: 1 }}>
              {/* Top 4 KPI Cards */}
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12 }}>
                {[
                  { label: 'Đã ký hôm nay', value: 18, icon: CheckCircle2, color: 'var(--brand-600)', bg: 'var(--brand-50)' },
                  { label: 'Đã phát hành', value: 14, icon: Send, color: 'var(--success)', bg: 'var(--success-bg)' },
                  { label: 'Chưa gửi bệnh nhân', value: 4, icon: Clock, color: 'var(--warning)', bg: 'var(--warning-bg)' },
                  { label: 'Tổng báo cáo lưu trữ', value: '1.286', icon: FileCheck, color: 'var(--brand-600)', bg: 'var(--brand-50)' },
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
                {/* Left Patient List */}
                <div className="card" style={{ padding: 14, display: 'flex', flexDirection: 'column', gap: 10 }}>
                  <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--ink)' }}>Bệnh nhân</div>
                  
                  <div style={{ position: 'relative' }}>
                    <Search size={13} style={{ position: 'absolute', left: 8, top: '50%', transform: 'translateY(-50%)', color: 'var(--ink-muted)' }} />
                    <input
                      type="search"
                      placeholder="Tên, SĐT hoặc mã bệnh nhân"
                      value={signedSearch}
                      onChange={(e) => setSignedSearch(e.target.value)}
                      style={{ paddingLeft: 26, width: '100%', fontSize: 11 }}
                    />
                  </div>

                  <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                    {ULTRASOUND_SIGNED_PATIENTS.map(p => {
                      const isSelected = p.id === activeSignedPatient.id;
                      return (
                        <div
                          key={p.id}
                          onClick={() => {
                            setSelectedSignedPatientId(p.id);
                            if (p.reports.length > 0) setSelectedReportId(p.reports[0].id);
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
                            <span className="badge badge-brand" style={{ fontSize: 9 }}>{p.reportCount} báo cáo</span>
                          </div>
                          <div style={{ fontSize: 10, color: 'var(--ink-muted)' }}>{p.birthYear} · Nữ · {p.age} tuổi</div>
                          <div style={{ fontSize: 10, color: 'var(--ink-muted)' }}>{p.patientCode}</div>
                        </div>
                      );
                    })}
                  </div>
                </div>

                {/* Middle Patient Reports History */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
                  <div className="card" style={{ padding: 14, display: 'flex', flexDirection: 'column', gap: 12 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--ink)' }}>
                        Lịch sử báo cáo của {activeSignedPatient.patientName}
                      </div>
                      <span style={{ fontSize: 11, color: 'var(--ink-muted)' }}>{activeSignedPatient.reports.length} kết quả đã ký</span>
                    </div>

                    <div style={{ display: 'flex', gap: 8 }}>
                      <input type="text" defaultValue="01/01/2026 – 14/05/2026" style={{ fontSize: 11, padding: '4px 8px' }} />
                      <select style={{ fontSize: 11, padding: '4px 8px' }}><option>Tất cả dịch vụ</option></select>
                      <button className="btn btn-secondary" style={{ padding: '4px 8px' }}><Search size={13} /></button>
                    </div>

                    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                      {activeSignedPatient.reports.map(rep => {
                        const isSelected = rep.id === activeReport.id;
                        return (
                          <div
                            key={rep.id}
                            onClick={() => setSelectedReportId(rep.id)}
                            style={{
                              padding: 12,
                              borderRadius: 8,
                              border: isSelected ? '2px solid var(--brand-500)' : '1px solid var(--line)',
                              background: isSelected ? 'var(--brand-50)' : 'var(--surface)',
                              cursor: 'pointer',
                              display: 'flex',
                              flexDirection: 'column',
                              gap: 6,
                            }}
                          >
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                              <div style={{ fontSize: 11, color: 'var(--ink-muted)' }}>{rep.dateStr} · {rep.timeStr}</div>
                              <div style={{ display: 'flex', gap: 4 }}>
                                <span className="badge badge-success" style={{ fontSize: 9 }}>{rep.signedStatus}</span>
                                <span className="badge badge-brand" style={{ fontSize: 9 }}>{rep.publishStatus}</span>
                              </div>
                            </div>

                            <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--ink)' }}>{rep.serviceName}</div>
                            <div style={{ fontSize: 11, color: 'var(--ink-muted)' }}>Mã báo cáo: {rep.code} &nbsp;·&nbsp; Bác sĩ ký: <strong>{rep.doctorName}</strong></div>
                            <div style={{ fontSize: 11, color: 'var(--ink)' }}><strong>Kết luận:</strong> {rep.conclusion}</div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                </div>

                {/* Right Details Panel */}
                <div className="card" style={{ padding: 16, display: 'flex', flexDirection: 'column', gap: 12 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid var(--line)', paddingBottom: 10 }}>
                    <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--ink)' }}>Chi tiết báo cáo đã ký</div>
                    <button className="btn btn-secondary" style={{ padding: 4 }}><X size={14} /></button>
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                    <div style={{ width: 36, height: 36, borderRadius: '50%', background: 'var(--brand-50)', color: 'var(--brand-700)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 12, fontWeight: 800 }}>
                      NT
                    </div>
                    <div>
                      <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--ink)' }}>{activeSignedPatient.patientName}</div>
                      <div style={{ fontSize: 10, color: 'var(--ink-muted)' }}>{activeSignedPatient.birthYear} · Nữ · {activeSignedPatient.age} tuổi &nbsp;|&nbsp; {activeReport.code}</div>
                    </div>
                  </div>

                  {/* Signature Card */}
                  <div style={{ background: '#dcfce7', border: '1px solid #86efac', padding: 10, borderRadius: 8, textAlign: 'center' }}>
                    <div style={{ fontSize: 12, fontWeight: 800, color: '#15803d', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6 }}>
                      <CheckCircle2 size={16} /> Báo cáo đã ký số
                    </div>
                    <div style={{ fontSize: 10, color: '#166534', marginTop: 2 }}>Chữ ký hợp lệ</div>
                  </div>

                  <div style={{ fontSize: 11, display: 'flex', flexDirection: 'column', gap: 4 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between' }}><span style={{ color: 'var(--ink-muted)' }}>Bác sĩ ký</span><strong>{activeReport.doctorName}</strong></div>
                    <div style={{ display: 'flex', justifyContent: 'space-between' }}><span style={{ color: 'var(--ink-muted)' }}>Thời gian ký</span><span>{activeReport.dateStr} {activeReport.timeStr}</span></div>
                    <div style={{ display: 'flex', justifyContent: 'space-between' }}><span style={{ color: 'var(--ink-muted)' }}>Phiên bản</span><span>v1.0</span></div>
                  </div>

                  <div style={{ borderTop: '1px solid var(--line)', paddingTop: 10 }}>
                    <div style={{ fontSize: 11, fontWeight: 800, color: 'var(--ink)', textTransform: 'uppercase', marginBottom: 6 }}>KẾT QUẢ SIÊU ÂM</div>
                    <div style={{ fontSize: 11, marginBottom: 4 }}><span style={{ color: 'var(--ink-muted)' }}>Dịch vụ:</span> <strong>{activeReport.serviceName}</strong></div>
                    <div style={{ fontSize: 11, marginBottom: 6 }}><strong>Mô tả hình ảnh:</strong><br />{activeReport.imageDescription}</div>
                    <img src={activeReport.imageUrl} alt="Ultrasound" style={{ width: '100%', height: 120, objectFit: 'cover', borderRadius: 6, marginBottom: 6 }} />
                    <div style={{ fontSize: 11 }}><strong>Kết luận:</strong><br />{activeReport.conclusion}</div>
                  </div>

                  <div style={{ borderTop: '1px solid var(--line)', paddingTop: 10, fontSize: 10, color: 'var(--ink-muted)' }}>
                    <div style={{ fontWeight: 700, color: 'var(--ink)', marginBottom: 4 }}>Lịch sử phát hành</div>
                    {activeReport.timeline.map((tl, i) => (
                      <div key={i}>🟢 {tl.time} - {tl.action}</div>
                    ))}
                  </div>

                  <div style={{ background: 'var(--surface-sunken)', padding: 6, borderRadius: 4, fontSize: 10, textAlign: 'center', color: 'var(--ink-muted)' }}>
                    🔒 Báo cáo đã ký — chỉ đọc
                  </div>

                  <div style={{ display: 'flex', gap: 6 }}>
                    <button className="btn btn-secondary" style={{ flex: 1, fontSize: 10 }}><Printer size={12} /> In báo cáo</button>
                    <button className="btn btn-secondary" style={{ flex: 1, fontSize: 10 }}><Download size={12} /> Tải xuống</button>
                    <button className="btn btn-primary" style={{ flex: 1, fontSize: 10, background: 'var(--brand-600)' }}><FileText size={12} /> Xem bản PDF</button>
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
