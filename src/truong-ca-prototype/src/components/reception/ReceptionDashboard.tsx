import { useState } from 'react';
import {
  Search,
  CheckCircle2,
  Clock,
  RotateCcw,
  ArrowRight,
  ChevronLeft,
  ChevronRight,
  UserCheck,
  Calendar,
  FileText,
  AlertOctagon,
  Printer,
  Send,
  Volume2,
  Copy,
  QrCode,
  FileCheck,
  User,
  Users,
  ShieldAlert,
} from 'lucide-react';
import {
  CHECKIN_PATIENTS,
  RECEPTION_QUEUE_ITEMS,
  CHECKOUT_PATIENTS,
} from '../../data/reception-mock-data';

interface ReceptionDashboardProps {
  onSwitchRole?: () => void;
}

export default function ReceptionDashboard({ onSwitchRole }: ReceptionDashboardProps) {
  const [activeTab, setActiveTab] = useState<'checkin' | 'queue' | 'checkout'>('checkin');
  const [collapsed, setCollapsed] = useState(false);

  // Tab 1 state (Checkin)
  const [checkinFilter, setCheckinFilter] = useState<string>('upcoming');
  const [checkinSearch, setCheckinSearch] = useState('');
  const [selectedCheckinId, setSelectedCheckinId] = useState<string>('ck-021');

  // Tab 2 state (Queue)
  const [queueSearch, setQueueSearch] = useState('');
  const [selectedQueueStt, setSelectedQueueStt] = useState<string>('A021');
  const [exceptionReason, setExceptionReason] = useState('');

  // Tab 3 state (Checkout)
  const [checkoutFilter, setCheckoutFilter] = useState<string>('all');
  const [checkoutSearch, setCheckoutSearch] = useState('');
  const [selectedCheckoutId, setSelectedCheckoutId] = useState<string>('co-021');
  const [handoverTarget, setHandoverTarget] = useState<'patient' | 'family' | 'app'>('patient');

  const activeCheckin = CHECKIN_PATIENTS.find(p => p.id === selectedCheckinId) || CHECKIN_PATIENTS[0];
  const activeQueue = RECEPTION_QUEUE_ITEMS.find(p => p.stt === selectedQueueStt) || RECEPTION_QUEUE_ITEMS[0];
  const activeCheckout = CHECKOUT_PATIENTS.find(p => p.id === selectedCheckoutId) || CHECKOUT_PATIENTS[0];

  return (
    <div style={{ display: 'flex', minHeight: '100vh', background: 'var(--surface-muted)' }}>
      {/* 1. SIDEBAR (LỄ TÂN) */}
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
            LỄ TÂN
          </div>
        )}

        {/* Nav Links */}
        <nav style={{ flex: 1, padding: '4px 8px', display: 'flex', flexDirection: 'column', gap: 2 }}>
          {[
            { id: 'checkin', label: 'Check-in & tiếp nhận', icon: UserCheck },
            { id: 'queue', label: 'Hàng đợi', icon: Calendar },
            { id: 'checkout', label: 'Check-out lượt khám', icon: FileCheck },
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
                title="Đổi vai trò"
              >
                <RotateCcw size={13} />
                {!collapsed && <span>Đổi vai trò</span>}
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
              {activeTab === 'checkin' && 'Check-in & tiếp nhận'}
              {activeTab === 'queue' && 'Hàng đợi tiếp nhận'}
              {activeTab === 'checkout' && 'Check-out lượt khám'}
            </h1>
            <p style={{ fontSize: 12, color: 'var(--ink-muted)', margin: '2px 0 0' }}>
              {activeTab === 'checkin' && 'Xác nhận người bệnh đến, tạo lượt khám và đưa vào hàng đợi.'}
              {activeTab === 'queue' && 'Gọi người bệnh và xử lý hàng chờ tại khu vực tiếp nhận.'}
              {activeTab === 'checkout' && 'Đối soát điều kiện, trả hồ sơ và xác nhận kết thúc lượt khám.'}
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
              <div style={{ width: 34, height: 34, borderRadius: '50%', background: 'var(--brand-50)', color: 'var(--brand-700)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 12, fontWeight: 700 }}>
                TM
              </div>
              <div>
                <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--ink)' }}>Trần Ngọc Mai</div>
                <div style={{ fontSize: 11, color: 'var(--ink-muted)' }}>Lễ tân</div>
              </div>
            </div>
          </div>
        </header>

        {/* CONTENT BODY */}
        <div style={{ padding: 20, display: 'flex', flexDirection: 'column', gap: 16, flex: 1 }}>

          {/* ========================================================================= */}
          {/* TAB 1: CHECK-IN & TIẾP NHẬN (MATCHING IMAGE 3)                           */}
          {/* ========================================================================= */}
          {activeTab === 'checkin' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 16, flex: 1 }}>
              {/* KPI Cards */}
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12 }}>
                {[
                  { label: 'Lịch hẹn hôm nay', value: 86, icon: Calendar, color: 'var(--brand-600)', bg: 'var(--brand-50)' },
                  { label: 'Đã check-in', value: 42, icon: CheckCircle2, color: 'var(--success)', bg: 'var(--success-bg)' },
                  { label: 'Walk-in', value: 8, icon: User, color: 'var(--brand-600)', bg: 'var(--brand-50)' },
                  { label: 'Đến muộn', value: 5, icon: Clock, color: 'var(--warning)', bg: 'var(--warning-bg)' },
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

              {/* Grid 3 Columns Workspace */}
              <div style={{ display: 'grid', gridTemplateColumns: '260px 1fr 340px', gap: 16, flex: 1, alignItems: 'start' }}>
                {/* Left List */}
                <div className="card" style={{ padding: 14, display: 'flex', flexDirection: 'column', gap: 12 }}>
                  <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--ink)' }}>Danh sách người bệnh đến</div>

                  {/* Filter tabs */}
                  <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                    {[
                      { id: 'upcoming', label: 'Sắp đến (23)' },
                      { id: 'arrived', label: 'Đã đến (42)' },
                      { id: 'walkin', label: 'Walk-in (8)' },
                      { id: 'verify', label: 'Cần xác minh (3)' },
                    ].map(f => (
                      <button
                        key={f.id}
                        onClick={() => setCheckinFilter(f.id)}
                        className={checkinFilter === f.id ? 'btn btn-primary' : 'btn btn-secondary'}
                        style={{ padding: '3px 6px', fontSize: 10, flex: 1 }}
                      >
                        {f.label}
                      </button>
                    ))}
                  </div>

                  <div style={{ position: 'relative' }}>
                    <Search size={13} style={{ position: 'absolute', left: 8, top: '50%', transform: 'translateY(-50%)', color: 'var(--ink-muted)' }} />
                    <input
                      type="search"
                      placeholder="Tìm lịch hẹn, SĐT hoặc mã bệnh nhân"
                      value={checkinSearch}
                      onChange={(e) => setCheckinSearch(e.target.value)}
                      style={{ paddingLeft: 26, width: '100%', fontSize: 11 }}
                    />
                  </div>

                  <div style={{ display: 'flex', flexDirection: 'column', gap: 8, maxHeight: 580, overflowY: 'auto' }}>
                    {CHECKIN_PATIENTS.map(p => {
                      const isSelected = p.id === activeCheckin.id;
                      return (
                        <div
                          key={p.id}
                          onClick={() => setSelectedCheckinId(p.id)}
                          style={{
                            padding: 10,
                            borderRadius: 'var(--radius-control)',
                            border: isSelected ? '2px solid var(--brand-500)' : '1px solid var(--line)',
                            background: isSelected ? 'var(--brand-50)' : 'var(--surface)',
                            cursor: 'pointer',
                          }}
                        >
                          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                            <span style={{ fontSize: 12, fontWeight: 700, color: 'var(--ink)' }}>{p.name}</span>
                            <span style={{ fontSize: 11, fontWeight: 600, color: 'var(--ink-muted)' }}>{p.arrivalTime}</span>
                          </div>
                          <div style={{ fontSize: 10, color: 'var(--ink-muted)', marginBottom: 6 }}>
                            {p.birthYear} · {p.gender} · {p.age} tuổi
                            <br />
                            {p.appointmentTime} · {p.specialty}
                          </div>
                          <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
                            <span
                              className="badge"
                              style={{
                                fontSize: 9,
                                background: p.statusTag === 'Có hẹn' ? 'var(--brand-50)' : p.statusTag === 'Đến sớm' ? 'var(--success-bg)' : p.statusTag === 'No-show' ? 'var(--danger-bg)' : 'var(--warning-bg)',
                                color: p.statusTag === 'Có hẹn' ? 'var(--brand-700)' : p.statusTag === 'Đến sớm' ? 'var(--success)' : p.statusTag === 'No-show' ? 'var(--danger)' : 'var(--warning)',
                              }}
                            >
                              {p.statusTag}
                            </span>
                          </div>
                        </div>
                      );
                    })}
                  </div>

                  <div style={{ fontSize: 10, color: 'var(--ink-muted)', textAlign: 'center' }}>
                    Hiển thị 1–6 trong 23 người bệnh <span style={{ color: 'var(--brand-600)', fontWeight: 600, cursor: 'pointer' }}>Xem tất cả</span>
                  </div>
                </div>

                {/* Middle Verification */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
                  <div className="card" style={{ padding: 16 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12, borderBottom: '1px solid var(--line)', paddingBottom: 10 }}>
                      <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--ink)' }}>
                        Xác minh người bệnh & dịch vụ hôm nay
                      </div>
                      <span style={{ fontSize: 11, fontWeight: 600, color: 'var(--success)', display: 'flex', alignItems: 'center', gap: 4 }}>
                        <CheckCircle2 size={14} /> Đã khớp hồ sơ
                      </span>
                    </div>

                    {/* Identity Info */}
                    <div style={{ marginBottom: 14 }}>
                      <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--ink-muted)', textTransform: 'uppercase', marginBottom: 8 }}>Thông tin định danh</div>
                      <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: 16 }}>
                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, fontSize: 11 }}>
                          <div><span style={{ color: 'var(--ink-muted)' }}>Họ và tên:</span> <strong style={{ color: 'var(--ink)' }}>{activeCheckin.name}</strong></div>
                          <div><span style={{ color: 'var(--ink-muted)' }}>Số điện thoại:</span> {activeCheckin.phone}</div>
                          <div><span style={{ color: 'var(--ink-muted)' }}>Ngày sinh:</span> 14/03/1994 ({activeCheckin.age} tuổi)</div>
                          <div><span style={{ color: 'var(--ink-muted)' }}>Email:</span> {activeCheckin.email}</div>
                          <div><span style={{ color: 'var(--ink-muted)' }}>Giới tính:</span> {activeCheckin.gender}</div>
                          <div><span style={{ color: 'var(--ink-muted)' }}>Địa chỉ:</span> {activeCheckin.address}</div>
                          <div><span style={{ color: 'var(--ink-muted)' }}>Mã bệnh nhân:</span> {activeCheckin.patientCode}</div>
                          <div><span style={{ color: 'var(--ink-muted)' }}>CMND/CCCD:</span> {activeCheckin.cmnd}</div>
                        </div>

                        {/* QR / CCCD Scan Box */}
                        <div style={{ border: '1px dashed var(--brand-300)', borderRadius: 'var(--radius-card)', padding: 12, background: 'var(--brand-50)', textAlign: 'center', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 6 }}>
                          <QrCode size={32} color="var(--brand-600)" />
                          <div style={{ fontSize: 10, fontWeight: 600, color: 'var(--brand-700)' }}>Quét CCCD / QR code</div>
                          <button className="btn btn-primary" style={{ padding: '3px 8px', fontSize: 10 }}>Quét mã</button>
                        </div>
                      </div>
                    </div>

                    {/* Appointment Info & Reason */}
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14, borderTop: '1px solid var(--surface-sunken)', paddingTop: 12, marginBottom: 12 }}>
                      <div>
                        <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--ink-muted)', marginBottom: 6 }}>Thông tin lịch hẹn</div>
                        <div style={{ fontSize: 11, display: 'flex', flexDirection: 'column', gap: 4 }}>
                          <div><span style={{ color: 'var(--ink-muted)' }}>Thời gian hẹn:</span> <strong>{activeCheckin.appointmentTime} - 14/05/2026</strong></div>
                          <div><span style={{ color: 'var(--ink-muted)' }}>Giờ đến:</span> {activeCheckin.arrivalTime}</div>
                          <div><span style={{ color: 'var(--ink-muted)' }}>Chuyên khoa:</span> {activeCheckin.specialty}</div>
                          <div><span style={{ color: 'var(--ink-muted)' }}>Bác sĩ:</span> {activeCheckin.doctorName}</div>
                          <div><span style={{ color: 'var(--ink-muted)' }}>Phòng khám:</span> {activeCheckin.roomName}</div>
                        </div>
                      </div>

                      <div>
                        <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--ink-muted)', marginBottom: 6 }}>Lý do khám</div>
                        <div style={{ fontSize: 11, color: 'var(--ink)', background: 'var(--surface-sunken)', padding: 8, borderRadius: 6, marginBottom: 10 }}>
                          {activeCheckin.reason}
                        </div>

                        <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--ink-muted)', marginBottom: 4 }}>Dịch vụ đăng ký</div>
                        <div style={{ fontSize: 11, display: 'flex', justifyContent: 'space-between', background: 'var(--surface-sunken)', padding: '6px 8px', borderRadius: 6 }}>
                          <span>{activeCheckin.registeredService} x1</span>
                          <strong>{(activeCheckin.servicePrice).toLocaleString()}đ</strong>
                        </div>
                      </div>
                    </div>

                    {/* Insurance & Admin Check */}
                    <div style={{ borderTop: '1px solid var(--surface-sunken)', paddingTop: 12 }}>
                      <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--ink-muted)', marginBottom: 8 }}>Thông tin bảo hiểm & hành chính</div>
                      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 10, fontSize: 11 }}>
                        <div style={{ background: 'var(--surface-sunken)', padding: 8, borderRadius: 6 }}>
                          <div style={{ color: 'var(--ink-muted)', fontSize: 10 }}>Bảo hiểm y tế</div>
                          <div style={{ fontWeight: 600, color: 'var(--success)' }}>Có BHYT</div>
                          <div style={{ fontSize: 9, color: 'var(--ink-muted)' }}>{activeCheckin.bhytCode || 'Chưa cập nhật'}</div>
                        </div>
                        <div style={{ background: 'var(--surface-sunken)', padding: 8, borderRadius: 6 }}>
                          <div style={{ color: 'var(--ink-muted)', fontSize: 10 }}>Bảo hiểm khác</div>
                          <div style={{ color: 'var(--ink-muted)' }}>Không có thông tin</div>
                        </div>
                        <div style={{ background: 'var(--surface-sunken)', padding: 8, borderRadius: 6 }}>
                          <div style={{ color: 'var(--ink-muted)', fontSize: 10 }}>Hồ sơ hành chính</div>
                          <div style={{ color: 'var(--success)', fontWeight: 600 }}>✓ Đã đầy đủ</div>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Right Form: Create Encounter */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                  <div className="card" style={{ padding: 14 }}>
                    <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--ink)', marginBottom: 10 }}>Tạo lượt khám</div>

                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginBottom: 12 }}>
                      <div>
                        <label style={{ fontSize: 10, color: 'var(--ink-muted)', display: 'block', marginBottom: 2 }}>Mã lượt khám (dự kiến)</label>
                        <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--ink)', background: 'var(--surface-sunken)', padding: '6px 8px', borderRadius: 6, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <span>LK250514-021</span>
                          <Copy size={12} style={{ cursor: 'pointer' }} />
                        </div>
                      </div>
                      <div>
                        <label style={{ fontSize: 10, color: 'var(--ink-muted)', display: 'block', marginBottom: 2 }}>Số thứ tự hàng đợi</label>
                        <div style={{ fontSize: 14, fontWeight: 800, color: 'var(--brand-700)', background: 'var(--brand-50)', padding: '4px 8px', borderRadius: 6, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <span>{activeCheckin.stt}</span>
                          <RotateCcw size={12} style={{ cursor: 'pointer' }} />
                        </div>
                      </div>
                    </div>

                    <div style={{ display: 'flex', flexDirection: 'column', gap: 8, fontSize: 11, marginBottom: 14 }}>
                      <div>
                        <label style={{ fontSize: 10, color: 'var(--ink-muted)', display: 'block', marginBottom: 2 }}>Loại đến</label>
                        <select style={{ width: '100%', fontSize: 11 }}>
                          <option>Có hẹn</option>
                          <option>Walk-in (Không hẹn)</option>
                          <option>Cấp cứu</option>
                        </select>
                      </div>

                      <div>
                        <label style={{ fontSize: 10, color: 'var(--ink-muted)', display: 'block', marginBottom: 2 }}>Điểm đến ban đầu</label>
                        <select style={{ width: '100%', fontSize: 11 }}>
                          <option>Chờ đo sinh hiệu</option>
                          <option>Khám bác sĩ trực tiếp</option>
                          <option>Xét nghiệm thẳng</option>
                        </select>
                      </div>

                      <div>
                        <label style={{ fontSize: 10, color: 'var(--ink-muted)', display: 'block', marginBottom: 2 }}>Ưu tiên</label>
                        <select style={{ width: '100%', fontSize: 11 }}>
                          <option>Bình thường</option>
                          <option>Ưu tiên cao</option>
                          <option>Khẩn cấp</option>
                        </select>
                      </div>

                      <div>
                        <label style={{ fontSize: 10, color: 'var(--ink-muted)', display: 'block', marginBottom: 2 }}>Nhân viên tiếp nhận</label>
                        <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--ink)', padding: '6px 8px', background: 'var(--surface-sunken)', borderRadius: 6 }}>
                          TM Trần Ngọc Mai
                        </div>
                      </div>

                      <div>
                        <label style={{ fontSize: 10, color: 'var(--ink-muted)', display: 'block', marginBottom: 2 }}>Thời gian tiếp nhận</label>
                        <div style={{ fontSize: 11, color: 'var(--ink)', padding: '6px 8px', background: 'var(--surface-sunken)', borderRadius: 6 }}>
                          14/05/2026 · 09:18
                        </div>
                      </div>
                    </div>

                    {/* Next Steps Journey */}
                    <div style={{ borderTop: '1px solid var(--line)', paddingTop: 10, marginBottom: 14 }}>
                      <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--ink)', marginBottom: 8 }}>Hành trình tiếp theo</div>
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: 10, textAlign: 'center' }}>
                        <div style={{ textAlign: 'center' }}>
                          <div style={{ width: 28, height: 28, borderRadius: '50%', background: 'var(--brand-600)', color: 'white', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 4px' }}>📱</div>
                          <span style={{ fontWeight: 600 }}>Tiếp nhận</span>
                          <div style={{ fontSize: 9, color: 'var(--brand-600)' }}>Hiện tại</div>
                        </div>
                        <ArrowRight size={14} color="var(--line-strong)" />
                        <div style={{ textAlign: 'center' }}>
                          <div style={{ width: 28, height: 28, borderRadius: '50%', background: 'var(--brand-50)', color: 'var(--brand-700)', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 4px' }}>🩺</div>
                          <span style={{ fontWeight: 600 }}>Sinh hiệu</span>
                          <div style={{ fontSize: 9, color: 'var(--ink-muted)' }}>Tiếp theo</div>
                        </div>
                        <ArrowRight size={14} color="var(--line-strong)" />
                        <div style={{ textAlign: 'center' }}>
                          <div style={{ width: 28, height: 28, borderRadius: '50%', background: 'var(--surface-sunken)', color: 'var(--ink-muted)', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 4px' }}>👨‍⚕️</div>
                          <span>Khám BS</span>
                          <div style={{ fontSize: 9, color: 'var(--ink-muted)' }}>Sau đó</div>
                        </div>
                      </div>
                    </div>

                    {/* Bottom Action Bar */}
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                      <div style={{ display: 'flex', gap: 6 }}>
                        <button className="btn btn-secondary" style={{ flex: 1, fontSize: 11 }}>
                          Lưu chờ xác minh
                        </button>
                        <button className="btn btn-secondary" style={{ flex: 1, fontSize: 11 }}>
                          <Printer size={12} /> In số thứ tự
                        </button>
                      </div>
                      <button className="btn btn-primary" style={{ width: '100%', fontSize: 12, padding: '10px 14px', background: 'var(--brand-600)' }}>
                        <CheckCircle2 size={15} /> Xác nhận check-in & vào hàng đợi
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* ========================================================================= */}
          {/* TAB 2: HÀNG ĐỢI TIẾP NHẬN (MATCHING IMAGE 2)                              */}
          {/* ========================================================================= */}
          {activeTab === 'queue' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 16, flex: 1 }}>
              {/* KPI Cards */}
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12 }}>
                {[
                  { label: 'Đang chờ tiếp nhận', value: 18, icon: Users, color: 'var(--brand-600)', bg: 'var(--brand-50)' },
                  { label: 'Đã gọi', value: 3, icon: Volume2, color: 'var(--brand-600)', bg: 'var(--brand-50)' },
                  { label: 'Cần xác minh', value: 4, icon: ShieldAlert, color: 'var(--warning)', bg: 'var(--warning-bg)' },
                  { label: 'Quá SLA', value: 2, icon: Clock, color: 'var(--danger)', bg: 'var(--danger-bg)' },
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

              {/* Grid 3 Columns Workspace */}
              <div style={{ display: 'grid', gridTemplateColumns: '320px 1fr 300px', gap: 16, flex: 1, alignItems: 'start' }}>
                {/* Left Table Queue */}
                <div className="card" style={{ padding: 14, display: 'flex', flexDirection: 'column', gap: 10 }}>
                  <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--ink)' }}>Danh sách hàng đợi</div>
                  
                  <div style={{ position: 'relative' }}>
                    <Search size={13} style={{ position: 'absolute', left: 8, top: '50%', transform: 'translateY(-50%)', color: 'var(--ink-muted)' }} />
                    <input
                      type="search"
                      placeholder="Tìm theo tên, SĐT hoặc mã bệnh nhân"
                      value={queueSearch}
                      onChange={(e) => setQueueSearch(e.target.value)}
                      style={{ paddingLeft: 26, width: '100%', fontSize: 11 }}
                    />
                  </div>

                  <div className="table-wrap" style={{ maxHeight: 580, overflowY: 'auto' }}>
                    <table>
                      <thead>
                        <tr>
                          <th>STT</th>
                          <th>Người bệnh</th>
                          <th>Đến</th>
                          <th>Chờ</th>
                        </tr>
                      </thead>
                      <tbody>
                        {RECEPTION_QUEUE_ITEMS.map(item => {
                          const isSelected = item.stt === activeQueue.stt;
                          return (
                            <tr
                              key={item.stt}
                              onClick={() => setSelectedQueueStt(item.stt)}
                              style={{ cursor: 'pointer', background: isSelected ? 'var(--brand-50)' : undefined }}
                            >
                              <td>
                                <span style={{ fontSize: 13, fontWeight: 800, color: 'var(--brand-700)' }}>{item.stt}</span>
                              </td>
                              <td>
                                <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--ink)' }}>{item.name}</div>
                                <div style={{ fontSize: 10, color: 'var(--ink-muted)' }}>{item.type}</div>
                              </td>
                              <td style={{ fontSize: 11 }}>{item.arrivalTime}</td>
                              <td style={{ fontSize: 11, fontWeight: 700, color: 'var(--danger)' }}>{item.waitTimeStr}</td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                </div>

                {/* Middle Detail Banner */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
                  <div className="card" style={{ padding: 16 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', borderBottom: '1px solid var(--line)', paddingBottom: 12, marginBottom: 12 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                        <div style={{ width: 44, height: 44, borderRadius: '50%', background: 'var(--surface-sunken)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 800, fontSize: 16, color: 'var(--ink)' }}>
                          NT
                        </div>
                        <div>
                          <div style={{ fontSize: 16, fontWeight: 700, color: 'var(--ink)' }}>{activeQueue.name}</div>
                          <div style={{ fontSize: 11, color: 'var(--ink-muted)' }}>
                            1994 · Nữ · 32 tuổi &nbsp;|&nbsp; SĐT: 0987 654 321 &nbsp;|&nbsp; Mã NB: BN250514-021
                          </div>
                        </div>
                      </div>

                      <div style={{ textAlign: 'right' }}>
                        <span className="badge badge-brand" style={{ fontSize: 11, padding: '4px 10px' }}>QUEUED</span>
                        <div style={{ fontSize: 11, color: 'var(--ink-muted)', marginTop: 4 }}>Mã số: <strong>{activeQueue.stt}</strong></div>
                      </div>
                    </div>

                    {/* 3 Grid Boxes */}
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 10, fontSize: 11, marginBottom: 14 }}>
                      <div style={{ background: 'var(--surface-sunken)', padding: 10, borderRadius: 6 }}>
                        <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--ink-muted)', textTransform: 'uppercase', marginBottom: 4 }}>Lịch hẹn</div>
                        <div>14/05/2026 · 10:00</div>
                        <div>Nội tổng quát</div>
                        <strong style={{ color: 'var(--ink)' }}>BS. Trần Văn Dũng</strong>
                      </div>

                      <div style={{ background: 'var(--surface-sunken)', padding: 10, borderRadius: 6 }}>
                        <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--ink-muted)', textTransform: 'uppercase', marginBottom: 4 }}>Thông tin hàng đợi</div>
                        <div>Thời điểm đến: 10:10</div>
                        <div>Vào hàng đợi lúc: 10:10</div>
                        <div>Được gán quầy: 10:10</div>
                      </div>

                      <div style={{ background: 'var(--surface-sunken)', padding: 10, borderRadius: 6 }}>
                        <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--ink-muted)', textTransform: 'uppercase', marginBottom: 4 }}>Bảo hiểm y tế</div>
                        <div>BHYT: HS4567890123456</div>
                        <div>Nơi ĐK KCB BĐ: BV Quận 3</div>
                        <div style={{ color: 'var(--success)', fontWeight: 600 }}>✓ Hợp lệ</div>
                      </div>
                    </div>

                    {/* Handling Timeline */}
                    <div style={{ borderTop: '1px solid var(--line)', paddingTop: 12, marginBottom: 14 }}>
                      <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--ink)', marginBottom: 8 }}>Trạng thái xử lý</div>
                      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, textAlign: 'center' }}>
                        <div>
                          <div style={{ color: 'var(--success)', fontWeight: 700 }}>✓ Vào hàng đợi</div>
                          <div style={{ color: 'var(--ink-muted)' }}>10:10</div>
                        </div>
                        <span>→</span>
                        <div>
                          <div style={{ color: 'var(--brand-600)', fontWeight: 700 }}>👤 Đã gán quầy 2</div>
                          <div style={{ color: 'var(--ink-muted)' }}>10:10</div>
                        </div>
                        <span>→</span>
                        <div>
                          <div style={{ color: 'var(--ink-muted)' }}>💬 Gọi bệnh nhân</div>
                          <div style={{ color: 'var(--ink-faint)' }}>Chưa gọi</div>
                        </div>
                        <span>→</span>
                        <div>
                          <div style={{ color: 'var(--ink-muted)' }}>📋 Xác nhận có mặt</div>
                          <div style={{ color: 'var(--ink-faint)' }}>Chưa xác nhận</div>
                        </div>
                      </div>
                    </div>

                    {/* Exception handling */}
                    <div style={{ borderTop: '1px solid var(--line)', paddingTop: 12 }}>
                      <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--ink)', marginBottom: 8 }}>Xử lý ngoại lệ (bắt buộc chọn lý do)</div>
                      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 8, marginBottom: 10 }}>
                        {[
                          { icon: '❌', label: 'Vắng mặt', sub: 'No-show' },
                          { icon: '🔀', label: 'Sai chuyên khoa', sub: 'Wrong branch' },
                          { icon: '📑', label: 'Trùng hồ sơ', sub: 'Duplicate' },
                          { icon: '📄', label: 'Thiếu giấy tờ', sub: 'Missing docs' },
                        ].map((btn, i) => (
                          <button key={i} className="btn btn-secondary" style={{ flexDirection: 'column', padding: '8px 4px', fontSize: 10, gap: 2 }}>
                            <span>{btn.icon}</span>
                            <strong>{btn.label}</strong>
                            <span style={{ fontSize: 8, color: 'var(--ink-muted)' }}>{btn.sub}</span>
                          </button>
                        ))}
                      </div>

                      <input
                        type="text"
                        placeholder="Nhập ghi chú hoặc lý do ngoại lệ..."
                        value={exceptionReason}
                        onChange={(e) => setExceptionReason(e.target.value)}
                        style={{ width: '100%', fontSize: 11 }}
                      />
                    </div>
                  </div>
                </div>

                {/* Right Counter Control */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                  <div className="card" style={{ padding: 14 }}>
                    <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--ink)', marginBottom: 8 }}>Điều phối tại quầy</div>
                    
                    <div style={{ background: 'var(--surface-sunken)', padding: 10, borderRadius: 6, marginBottom: 10, fontSize: 11 }}>
                      <div style={{ fontWeight: 600, color: 'var(--ink)', marginBottom: 4 }}>Hiện trạng quầy 2</div>
                      <div style={{ display: 'flex', justifyContent: 'space-between', color: 'var(--ink-muted)', fontSize: 10 }}>
                        <span>Sức chứa: <strong>4</strong></span>
                        <span>Đang phục vụ: <strong>1</strong></span>
                        <span>Đang chờ: <strong>2</strong></span>
                        <span>Trống: <strong>1</strong></span>
                      </div>
                    </div>

                    {/* TV Counter Preview */}
                    <div style={{ background: 'var(--brand-700)', color: 'white', padding: 14, borderRadius: 'var(--radius-card)', textAlign: 'center', marginBottom: 12 }}>
                      <div style={{ fontSize: 10, textTransform: 'uppercase', letterSpacing: '0.08em', opacity: 0.8 }}>MÀN HÌNH HIỂN THỊ (TV QUẦY 2)</div>
                      <div style={{ fontSize: 12, fontWeight: 600, marginTop: 4 }}>QUẦY 2 &nbsp;|&nbsp; MỜI SỐ</div>
                      <div style={{ fontSize: 36, fontWeight: 900, color: 'white', margin: '4px 0' }}>{activeQueue.stt}</div>
                      <div style={{ fontSize: 11, opacity: 0.8 }}>CHỜ {activeQueue.waitTimeStr}</div>
                    </div>

                    {/* Action Buttons */}
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                      <div style={{ display: 'flex', gap: 6 }}>
                        <button className="btn btn-secondary" style={{ flex: 1, fontSize: 10 }}>⏸ Tạm giữ</button>
                        <button className="btn btn-secondary" style={{ flex: 1, fontSize: 10 }}>👤 Vắng mặt</button>
                        <button className="btn btn-secondary" style={{ flex: 1, fontSize: 10 }}>🔊 Gọi số {activeQueue.stt}</button>
                      </div>

                      <button className="btn btn-primary" style={{ width: '100%', fontSize: 12, padding: '10px 14px', background: 'var(--brand-600)' }}>
                        <CheckCircle2 size={15} /> Xác nhận có mặt & hoàn tất
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* ========================================================================= */}
          {/* TAB 3: CHECK-OUT LƯỢT KHÁM (MATCHING IMAGE 1)                            */}
          {/* ========================================================================= */}
          {activeTab === 'checkout' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 16, flex: 1 }}>
              {/* KPI Cards */}
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12 }}>
                {[
                  { label: 'Chờ check-out', value: 12, icon: FileCheck, color: 'var(--brand-600)', bg: 'var(--brand-50)' },
                  { label: 'Đủ điều kiện đóng', value: 8, icon: CheckCircle2, color: 'var(--success)', bg: 'var(--success-bg)' },
                  { label: 'Đang bị chặn', value: 4, icon: AlertOctagon, color: 'var(--danger)', bg: 'var(--danger-bg)' },
                  { label: 'Kết quả trả sau', value: 3, icon: Clock, color: 'var(--warning)', bg: 'var(--warning-bg)' },
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

              {/* Grid 3 Columns Workspace */}
              <div style={{ display: 'grid', gridTemplateColumns: '280px 1fr 320px', gap: 16, flex: 1, alignItems: 'start' }}>
                {/* Left List */}
                <div className="card" style={{ padding: 14, display: 'flex', flexDirection: 'column', gap: 12 }}>
                  <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--ink)' }}>Danh sách lượt khám</div>

                  <div style={{ display: 'flex', gap: 4 }}>
                    {[
                      { id: 'all', label: 'Tất cả (12)' },
                      { id: 'ready', label: 'Đủ điều kiện (8)' },
                      { id: 'blocked', label: 'Bị chặn (4)' },
                    ].map(f => (
                      <button
                        key={f.id}
                        onClick={() => setCheckoutFilter(f.id)}
                        className={checkoutFilter === f.id ? 'btn btn-primary' : 'btn btn-secondary'}
                        style={{ padding: '3px 6px', fontSize: 10, flex: 1 }}
                      >
                        {f.label}
                      </button>
                    ))}
                  </div>

                  <div style={{ position: 'relative' }}>
                    <Search size={13} style={{ position: 'absolute', left: 8, top: '50%', transform: 'translateY(-50%)', color: 'var(--ink-muted)' }} />
                    <input
                      type="search"
                      placeholder="Tìm tên, mã BN, mã lượt khám"
                      value={checkoutSearch}
                      onChange={(e) => setCheckoutSearch(e.target.value)}
                      style={{ paddingLeft: 26, width: '100%', fontSize: 11 }}
                    />
                  </div>

                  <div style={{ display: 'flex', flexDirection: 'column', gap: 8, maxHeight: 580, overflowY: 'auto' }}>
                    {CHECKOUT_PATIENTS.map(p => {
                      const isSelected = p.id === activeCheckout.id;
                      return (
                        <div
                          key={p.id}
                          onClick={() => setSelectedCheckoutId(p.id)}
                          style={{
                            padding: 10,
                            borderRadius: 'var(--radius-control)',
                            border: isSelected ? '2px solid var(--brand-500)' : '1px solid var(--line)',
                            background: isSelected ? 'var(--brand-50)' : 'var(--surface)',
                            cursor: 'pointer',
                          }}
                        >
                          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                            <span style={{ fontSize: 12, fontWeight: 700, color: 'var(--ink)' }}>{p.name}</span>
                            <span style={{ fontSize: 10, color: 'var(--ink-muted)' }}>{p.checkinTime}</span>
                          </div>
                          <div style={{ fontSize: 10, color: 'var(--ink-muted)', marginBottom: 6 }}>
                            {p.birthYear} · {p.gender} · {p.age} tuổi
                            <br />
                            {p.patientCode} · {p.visitCode}
                          </div>
                          <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
                            <span
                              className="badge"
                              style={{
                                fontSize: 9,
                                background: p.statusType === 'ready' ? 'var(--success-bg)' : p.statusType === 'finance_pending' ? 'var(--warning-bg)' : 'var(--danger-bg)',
                                color: p.statusType === 'ready' ? 'var(--success)' : p.statusType === 'finance_pending' ? 'var(--warning)' : 'var(--danger)',
                              }}
                            >
                              {p.statusTag}
                            </span>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>

                {/* Middle Reconciliation Checklist */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
                  <div className="card" style={{ padding: 16 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid var(--line)', paddingBottom: 12, marginBottom: 14 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                        <div style={{ width: 40, height: 40, borderRadius: '50%', background: 'var(--surface-sunken)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 800, fontSize: 14, color: 'var(--ink)' }}>
                          NT
                        </div>
                        <div>
                          <div style={{ fontSize: 15, fontWeight: 700, color: 'var(--ink)' }}>{activeCheckout.name}</div>
                          <div style={{ fontSize: 11, color: 'var(--ink-muted)' }}>
                            1994 · Nữ · 32 tuổi &nbsp;|&nbsp; {activeCheckout.patientCode} · {activeCheckout.visitCode}
                          </div>
                        </div>
                      </div>

                      <span className="badge badge-success" style={{ fontSize: 11, padding: '4px 10px' }}>
                        {activeCheckout.statusTag}
                      </span>
                    </div>

                    {/* 4 Reconciliation Groups */}
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
                      {/* Group 1: Dịch vụ */}
                      <div style={{ border: '1px solid var(--line)', borderRadius: 'var(--radius-card)', overflow: 'hidden' }}>
                        <div style={{ background: 'var(--surface-sunken)', padding: '8px 12px', fontSize: 12, fontWeight: 700, color: 'var(--ink)', display: 'flex', justifyContent: 'space-between' }}>
                          <span>1. Dịch vụ</span>
                          <span style={{ fontSize: 11, color: 'var(--ink-muted)' }}>2/3 hoàn tất</span>
                        </div>
                        <div style={{ padding: 12, display: 'flex', flexDirection: 'column', gap: 8, fontSize: 11 }}>
                          {activeCheckout.services.map((s, idx) => (
                            <div key={idx} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                              <div>
                                <strong>{s.name}</strong> &nbsp;·&nbsp; <span style={{ color: 'var(--ink-muted)' }}>{s.doctor}</span>
                                {s.note && <div style={{ fontSize: 10, color: 'var(--warning)' }}>{s.note}</div>}
                              </div>
                              {s.status === 'completed' ? (
                                <span style={{ color: 'var(--success)', fontWeight: 600, display: 'flex', alignItems: 'center', gap: 2 }}>Hoàn tất ✓</span>
                              ) : (
                                <span style={{ color: 'var(--warning)', fontWeight: 600 }}>Chờ kết quả</span>
                              )}
                            </div>
                          ))}
                        </div>
                      </div>

                      {/* Group 2: Tài chính */}
                      <div style={{ border: '1px solid var(--line)', borderRadius: 'var(--radius-card)', overflow: 'hidden' }}>
                        <div style={{ background: 'var(--surface-sunken)', padding: '8px 12px', fontSize: 12, fontWeight: 700, color: 'var(--ink)', display: 'flex', justifyContent: 'space-between' }}>
                          <span>2. Tài chính</span>
                          <span style={{ fontSize: 11, color: 'var(--ink-muted)' }}>3/3 hoàn tất</span>
                        </div>
                        <div style={{ padding: 12, display: 'flex', flexDirection: 'column', gap: 8, fontSize: 11 }}>
                          {activeCheckout.finances.map((f, idx) => (
                            <div key={idx} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                              <span>{f.name}</span>
                              <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
                                <span style={{ color: 'var(--ink-muted)' }}>{f.status === 'paid' ? 'Đã thanh toán' : 'Chưa thanh toán'}</span>
                                <strong style={{ color: 'var(--ink)' }}>{f.amount.toLocaleString()}đ</strong>
                                {f.status === 'paid' && <span style={{ color: 'var(--success)' }}>✓</span>}
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>

                      {/* Group 3: Hồ sơ trả bệnh nhân */}
                      <div style={{ border: '1px solid var(--line)', borderRadius: 'var(--radius-card)', overflow: 'hidden' }}>
                        <div style={{ background: 'var(--surface-sunken)', padding: '8px 12px', fontSize: 12, fontWeight: 700, color: 'var(--ink)', display: 'flex', justifyContent: 'space-between' }}>
                          <span>3. Hồ sơ trả bệnh nhân</span>
                          <span style={{ fontSize: 11, color: 'var(--ink-muted)' }}>4/4 hoàn tất</span>
                        </div>
                        <div style={{ padding: 12, display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, fontSize: 11 }}>
                          {activeCheckout.documents.map((d, idx) => (
                            <div key={idx} style={{ display: 'flex', alignItems: 'center', gap: 6, background: 'var(--surface-sunken)', padding: 6, borderRadius: 6 }}>
                              <FileText size={14} color="var(--brand-600)" />
                              <div>
                                <div style={{ fontWeight: 600, fontSize: 10 }}>{d.name}</div>
                                <div style={{ fontSize: 9, color: 'var(--success)' }}>Sẵn sàng ({d.type})</div>
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>

                      {/* Group 4: Theo dõi sau khám */}
                      {activeCheckout.followup && (
                        <div style={{ border: '1px solid var(--line)', borderRadius: 'var(--radius-card)', overflow: 'hidden' }}>
                          <div style={{ background: 'var(--surface-sunken)', padding: '8px 12px', fontSize: 12, fontWeight: 700, color: 'var(--ink)', display: 'flex', justifyContent: 'space-between' }}>
                            <span>4. Theo dõi sau khám</span>
                            <span style={{ fontSize: 11, color: 'var(--ink-muted)' }}>1/1 hoàn tất</span>
                          </div>
                          <div style={{ padding: 12, fontSize: 11, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                            <div>
                              <strong>{activeCheckout.followup.code}</strong> &nbsp;·&nbsp; {activeCheckout.followup.note}
                              <div style={{ fontSize: 10, color: 'var(--ink-muted)' }}>Chủ sở hữu: {activeCheckout.followup.owner} | Hạn: {activeCheckout.followup.dueDate}</div>
                            </div>
                            <span style={{ color: 'var(--success)', fontWeight: 600 }}>✓</span>
                          </div>
                        </div>
                      )}
                    </div>

                    {/* Bottom Summary Banner */}
                    <div style={{ marginTop: 14, padding: '10px 12px', background: 'var(--success-bg)', border: '1px solid #bbf7d0', borderRadius: 'var(--radius-chip)', fontSize: 11, color: 'var(--success)', display: 'flex', alignItems: 'center', gap: 6 }}>
                      <CheckCircle2 size={16} />
                      <span><strong>Đối soát điều kiện hoàn tất:</strong> Không có chặn. Có thể trả hồ sơ và đóng lượt.</span>
                    </div>
                  </div>
                </div>

                {/* Right Encounter Details & Handover */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                  <div className="card" style={{ padding: 14 }}>
                    <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--ink)', marginBottom: 8 }}>Thông tin lượt khám</div>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: 11, marginBottom: 12 }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between' }}><span style={{ color: 'var(--ink-muted)' }}>Bệnh nhân</span><strong>{activeCheckout.name}</strong></div>
                      <div style={{ display: 'flex', justifyContent: 'space-between' }}><span style={{ color: 'var(--ink-muted)' }}>Mã bệnh nhân</span><span>{activeCheckout.patientCode}</span></div>
                      <div style={{ display: 'flex', justifyContent: 'space-between' }}><span style={{ color: 'var(--ink-muted)' }}>Mã lượt khám</span><span>{activeCheckout.visitCode}</span></div>
                      <div style={{ display: 'flex', justifyContent: 'space-between' }}><span style={{ color: 'var(--ink-muted)' }}>Bác sĩ phụ trách</span><strong>{activeCheckout.doctorName}</strong></div>
                      <div style={{ display: 'flex', justifyContent: 'space-between' }}><span style={{ color: 'var(--ink-muted)' }}>Thời gian</span><span>14/05/2026 · {activeCheckout.checkinTime}</span></div>
                      <div style={{ display: 'flex', justifyContent: 'space-between' }}><span style={{ color: 'var(--ink-muted)' }}>Phòng khám</span><span>{activeCheckout.roomName}</span></div>
                    </div>

                    {/* Timeline */}
                    <div style={{ borderTop: '1px solid var(--line)', paddingTop: 10, marginBottom: 12 }}>
                      <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--ink)', marginBottom: 8 }}>Timeline lượt khám</div>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: 6, fontSize: 10, paddingLeft: 12, borderLeft: '2px solid var(--line)' }}>
                        <div><strong>10:18</strong> Check-in & tiếp nhận</div>
                        <div><strong>10:22</strong> Khám bác sĩ</div>
                        <div><strong>10:35</strong> Siêu âm</div>
                        <div><strong>10:50</strong> Lấy mẫu xét nghiệm</div>
                        <div><strong>10:55</strong> Kết thúc khám</div>
                      </div>
                    </div>

                    {/* Handover Target Selection */}
                    <div style={{ borderTop: '1px solid var(--line)', paddingTop: 10, marginBottom: 12 }}>
                      <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--ink)', marginBottom: 6 }}>Bàn giao cho</div>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: 11 }}>
                        <label style={{ display: 'flex', alignItems: 'center', gap: 6, cursor: 'pointer' }}>
                          <input type="radio" name="handover" checked={handoverTarget === 'patient'} onChange={() => setHandoverTarget('patient')} />
                          <span>Bệnh nhân</span>
                        </label>
                        <label style={{ display: 'flex', alignItems: 'center', gap: 6, cursor: 'pointer' }}>
                          <input type="radio" name="handover" checked={handoverTarget === 'family'} onChange={() => setHandoverTarget('family')} />
                          <span>Người nhà</span>
                        </label>
                        <label style={{ display: 'flex', alignItems: 'center', gap: 6, cursor: 'pointer' }}>
                          <input type="radio" name="handover" checked={handoverTarget === 'app'} onChange={() => setHandoverTarget('app')} />
                          <span>Ứng dụng (ClinicAI)</span>
                        </label>
                      </div>
                    </div>

                    {/* Audit Check Note */}
                    <div style={{ fontSize: 10, color: 'var(--ink-muted)', background: 'var(--surface-sunken)', padding: 8, borderRadius: 6, marginBottom: 12 }}>
                      Đã đối soát đầy đủ điều kiện. Hồ sơ sẵn sàng trả bệnh nhân.
                      <br />
                      <strong>Trần Ngọc Mai</strong> · 14/05/2026 10:20
                    </div>

                    {/* Bottom Action Bar */}
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                      <div style={{ display: 'flex', gap: 6 }}>
                        <button className="btn btn-secondary" style={{ flex: 1, fontSize: 11 }}>
                          <Printer size={12} /> In bộ hồ sơ
                        </button>
                        <button className="btn btn-secondary" style={{ flex: 1, fontSize: 11 }}>
                          <Send size={12} /> Gửi app
                        </button>
                      </div>
                      <button className="btn btn-primary" style={{ width: '100%', fontSize: 12, padding: '10px 14px', background: 'var(--brand-600)' }}>
                        <CheckCircle2 size={15} /> Xác nhận trả hồ sơ & đóng lượt
                      </button>
                    </div>
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
