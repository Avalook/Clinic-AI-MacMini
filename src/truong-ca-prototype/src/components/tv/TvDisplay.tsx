import { useState, useEffect } from 'react';
import { Clock, Heart, Volume2, Info, Settings, Eye, EyeOff, Stethoscope, Monitor, FlaskConical, Pill } from 'lucide-react';
import { TV_STATIONS, type TvStation } from '../../data/mock-data';

const stationIcons: Record<string, typeof Stethoscope> = {
  doctor: Stethoscope,
  sa1: Monitor,
  sa2: Monitor,
  sa3: Monitor,
  lab: FlaskConical,
  pharmacy: Pill,
};

export default function TvDisplay() {
  const [time, setTime] = useState(new Date());
  const [showSettings, setShowSettings] = useState(false);
  const [visibleFields, setVisibleFields] = useState({
    queueCode: true,
    room: true,
    waiting: true,
    instructions: true,
  });

  useEffect(() => {
    const interval = setInterval(() => setTime(new Date()), 1000);
    return () => clearInterval(interval);
  }, []);

  const days = ['Chủ nhật', 'Thứ hai', 'Thứ ba', 'Thứ tư', 'Thứ năm', 'Thứ sáu', 'Thứ bảy'];
  const dayOfWeek = days[time.getDay()];
  const dateStr = time.toLocaleDateString('vi-VN', { day: '2-digit', month: '2-digit', year: 'numeric' });
  const timeStr = time.toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' });

  return (
    <div
      style={{
        width: '100%',
        minHeight: '100vh',
        background: 'linear-gradient(180deg, #f0f6fa 0%, #e6f0f7 100%)',
        padding: 28,
        display: 'flex',
        flexDirection: 'column',
        gap: 20,
        fontFamily: "'Inter', sans-serif",
        position: 'relative',
      }}
    >
      {/* Settings toggle (admin only — not visible on actual TV) */}
      <button
        onClick={() => setShowSettings(!showSettings)}
        style={{
          position: 'absolute',
          top: 12,
          right: 12,
          background: 'rgba(0,0,0,0.05)',
          border: 'none',
          borderRadius: 8,
          padding: '6px 10px',
          cursor: 'pointer',
          fontSize: 11,
          color: 'var(--ink-muted)',
          display: 'flex',
          alignItems: 'center',
          gap: 4,
          zIndex: 10,
        }}
      >
        <Settings size={14} /> Quản lý nội dung TV
      </button>

      {/* Settings panel */}
      {showSettings && (
        <div
          className="card scale-in"
          style={{
            position: 'absolute',
            top: 44,
            right: 12,
            padding: 16,
            zIndex: 20,
            width: 260,
            boxShadow: 'var(--shadow-lg)',
          }}
        >
          <h3 style={{ fontSize: 13, fontWeight: 700, color: 'var(--ink)', marginBottom: 12 }}>
            Chế độ hiển thị TV
          </h3>
          {[
            { key: 'queueCode', label: 'Số thứ tự' },
            { key: 'room', label: 'Số phòng' },
            { key: 'waiting', label: 'Danh sách chờ' },
            { key: 'instructions', label: 'Hướng dẫn BN' },
          ].map(({ key, label }) => (
            <label
              key={key}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 8,
                padding: '6px 0',
                fontSize: 12,
                cursor: 'pointer',
              }}
            >
              <input
                type="checkbox"
                checked={visibleFields[key as keyof typeof visibleFields]}
                onChange={() =>
                  setVisibleFields(prev => ({ ...prev, [key]: !prev[key as keyof typeof visibleFields] }))
                }
              />
              {visibleFields[key as keyof typeof visibleFields] ? <Eye size={13} /> : <EyeOff size={13} />}
              {label}
            </label>
          ))}
          <div style={{ marginTop: 8, fontSize: 10, color: 'var(--ink-muted)', borderTop: '1px solid var(--line)', paddingTop: 8 }}>
            ⚠ Tên đầy đủ BN luôn bị ẩn trên TV để bảo vệ quyền riêng tư
          </div>
        </div>
      )}

      {/* Header */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '0 8px',
        }}
      >
        {/* Logo */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
          <div
            style={{
              width: 48,
              height: 48,
              borderRadius: 14,
              background: 'linear-gradient(135deg, var(--brand-500), var(--brand-700))',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              boxShadow: '0 2px 8px rgba(15, 139, 141, 0.3)',
            }}
          >
            <Heart size={24} color="white" fill="white" />
          </div>
          <div>
            <div style={{ fontSize: 18, fontWeight: 800, color: 'var(--brand-700)', letterSpacing: '0.02em' }}>
              ClinicAI
            </div>
            <div style={{ fontSize: 10, fontWeight: 600, color: 'var(--ink-muted)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>
              Connected Clinic Workflow
            </div>
          </div>
        </div>

        {/* Title */}
        <div style={{ textAlign: 'center' }}>
          <h1 style={{ fontSize: 26, fontWeight: 800, color: 'var(--ink)', margin: 0, letterSpacing: '0.04em' }}>
            PHÒNG CHỜ — THÔNG BÁO LƯỢT KHÁM
          </h1>
          <p style={{ fontSize: 13, color: 'var(--ink-muted)', margin: '4px 0 0' }}>
            Kính chào Quý khách! ClinicAI luôn đồng hành cùng sức khỏe của bạn.
          </p>
        </div>

        {/* Clock */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <Clock size={22} color="var(--ink-muted)" />
            <span style={{ fontSize: 32, fontWeight: 800, color: 'var(--ink)', fontVariantNumeric: 'tabular-nums' }}>
              {timeStr}
            </span>
          </div>
          <div style={{ textAlign: 'right' }}>
            <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--ink)' }}>{dayOfWeek}</div>
            <div style={{ fontSize: 12, color: 'var(--ink-muted)' }}>{dateStr}</div>
          </div>
        </div>
      </div>

      {/* Station grid */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: `repeat(${TV_STATIONS.length}, 1fr)`,
          gap: 14,
          flex: 1,
        }}
      >
        {TV_STATIONS.map(station => (
          <TvStationCard
            key={station.id}
            station={station}
            visibleFields={visibleFields}
          />
        ))}
      </div>

      {/* Instructions */}
      {visibleFields.instructions && (
        <div
          style={{
            background: 'var(--surface)',
            borderRadius: 14,
            padding: '14px 28px',
            display: 'flex',
            alignItems: 'center',
            gap: 24,
            border: '1px solid var(--line)',
            boxShadow: 'var(--shadow-card)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: 'var(--brand-600)', fontWeight: 700, fontSize: 13, whiteSpace: 'nowrap' }}>
            <Info size={18} />
            HƯỚNG DẪN DÀNH CHO QUÝ KHÁCH
          </div>
          <div style={{ display: 'flex', gap: 24, flex: 1, justifyContent: 'space-evenly' }}>
            <InstructionItem icon={<Eye size={15} />} text="Vui lòng theo dõi số thứ tự trên màn hình và giữ trật tự trong khu vực chờ." />
            <InstructionItem icon={<Volume2 size={15} />} text="Khi đến lượt, vui lòng di chuyển đến đúng khu vực được gọi." />
            <InstructionItem icon={<Volume2 size={15} />} text="Quý khách có thể lắng nghe thông báo và kiểm tra số thứ tự." />
          </div>
        </div>
      )}

      {/* Footer */}
      <div style={{ textAlign: 'center', padding: '4px 0' }}>
        <span style={{ fontSize: 12, color: 'var(--ink-muted)', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6 }}>
          <Heart size={12} color="var(--brand-500)" fill="var(--brand-500)" />
          ClinicAI / Dr4Women — Đồng hành cùng sức khỏe phụ nữ Việt
        </span>
      </div>
    </div>
  );
}

function InstructionItem({ icon, text }: { icon: React.ReactNode; text: string }) {
  return (
    <div style={{ display: 'flex', alignItems: 'flex-start', gap: 8, fontSize: 11, color: 'var(--ink-soft)', maxWidth: 260 }}>
      <span style={{ color: 'var(--brand-600)', marginTop: 1, flexShrink: 0 }}>{icon}</span>
      {text}
    </div>
  );
}

function TvStationCard({ station, visibleFields }: { station: TvStation; visibleFields: Record<string, boolean> }) {
  const Icon = stationIcons[station.id] || Monitor;

  return (
    <div
      style={{
        background: 'var(--surface)',
        borderRadius: 16,
        border: '1px solid var(--line)',
        boxShadow: 'var(--shadow-card)',
        overflow: 'hidden',
        display: 'flex',
        flexDirection: 'column',
        animation: 'tv-glow 4s ease-in-out infinite',
      }}
    >
      {/* Station header */}
      <div
        style={{
          padding: '12px 0',
          textAlign: 'center',
          borderBottom: `3px solid ${station.color}`,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8, marginBottom: 2 }}>
          <Icon size={18} color={station.color} />
          <span style={{ fontSize: 14, fontWeight: 800, color: station.color, whiteSpace: 'pre-line', lineHeight: 1.2 }}>
            {station.name}
          </span>
        </div>
      </div>

      {/* Currently serving */}
      <div
        style={{
          padding: '14px 12px',
          textAlign: 'center',
          background: `${station.color}08`,
        }}
      >
        <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--ink-muted)', textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: 4 }}>
          ĐANG GỌI
        </div>
        {visibleFields.queueCode && (
          <div style={{ fontSize: 38, fontWeight: 900, color: station.color, lineHeight: 1 }}>
            {station.currentlyServing.queueCode}
          </div>
        )}
        {visibleFields.room && station.currentlyServing.room && (
          <div style={{ fontSize: 10, fontWeight: 600, color: station.color, marginTop: 4, opacity: 0.8 }}>
            {station.currentlyServing.room}
          </div>
        )}
      </div>

      {/* Next up */}
      <div style={{ padding: '8px 12px', textAlign: 'center', borderTop: '1px solid var(--surface-sunken)' }}>
        <div style={{ fontSize: 9, fontWeight: 700, color: 'var(--ink-muted)', textTransform: 'uppercase', letterSpacing: '0.1em' }}>
          TIẾP THEO
        </div>
        {visibleFields.queueCode && (
          <div style={{ fontSize: 18, fontWeight: 800, color: 'var(--ink)' }}>
            {station.nextUp.queueCode}
          </div>
        )}
      </div>

      {/* Waiting list */}
      {visibleFields.waiting && (
        <div style={{ padding: '8px 10px', borderTop: '1px solid var(--surface-sunken)', flex: 1 }}>
          <div style={{ fontSize: 9, fontWeight: 700, color: 'var(--ink-muted)', textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: 6, textAlign: 'center' }}>
            ĐANG CHỜ
          </div>
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(3, 1fr)',
              gap: 3,
            }}
          >
            {station.waiting.map((item, i) => (
              <div
                key={i}
                style={{
                  padding: '4px 2px',
                  textAlign: 'center',
                  fontSize: 12,
                  fontWeight: 600,
                  color: 'var(--ink-soft)',
                  background: i < 3 ? 'var(--surface-sunken)' : 'transparent',
                  borderRadius: 4,
                }}
              >
                {item.queueCode}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
