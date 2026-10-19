import React from 'react';

export interface RobotUnitAvatarProps {
  chassis?: string;
  accentColor?: string;
  isActive?: boolean;
  isArmed?: boolean;
  stage?: 'incubator' | 'certified' | 'live_sealed' | string;
  size?: 'sm' | 'md' | 'lg';
  animate?: boolean;
}

export const RobotUnitAvatar: React.FC<RobotUnitAvatarProps> = ({
  chassis = 'titan_v4',
  accentColor = '#10b981',
  isActive = false,
  isArmed = true,
  stage = 'live_sealed',
  size = 'md',
  animate = true,
}) => {
  const dim = size === 'sm' ? 68 : size === 'lg' ? 124 : 92;
  const coreColor = !isArmed ? '#f43f5e' : isActive ? accentColor : '#6366f1';

  return (
    <div
      className={`relative inline-flex items-center justify-center select-none ${
        animate && isArmed ? 'animate-robot-float' : ''
      }`}
      style={{ width: dim, height: dim }}
    >
      <svg
        viewBox="0 0 120 120"
        className="w-full h-full overflow-visible"
        aria-label={`Robot chassis ${chassis}`}
      >
        <defs>
          <radialGradient id={`coreGlow-${chassis}-${accentColor}`} cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor={coreColor} stopOpacity="0.85" />
            <stop offset="100%" stopColor={coreColor} stopOpacity="0" />
          </radialGradient>
        </defs>

        {/* Ground Telemetry Holo-Ring */}
        <ellipse
          cx="60"
          cy="109"
          rx={isActive ? '36' : '28'}
          ry="5"
          fill="none"
          stroke={coreColor}
          strokeWidth={isActive ? '2' : '1.2'}
          strokeDasharray="6 4"
          opacity={isActive ? 0.9 : 0.45}
        />

        {/* Antenna / Neural Transceiver Array */}
        <line x1="44" y1="18" x2="38" y2="6" stroke="#475569" strokeWidth="2.5" strokeLinecap="round" />
        <circle cx="38" cy="6" r="3" fill={coreColor} />
        <line x1="76" y1="18" x2="82" y2="6" stroke="#475569" strokeWidth="2.5" strokeLinecap="round" />
        <circle cx="82" cy="6" r="3" fill={coreColor} />

        {/* Left Articulated Mechanical Arm */}
        <g
          style={{
            transformOrigin: '28px 56px',
            transform: isActive ? 'rotate(-10deg)' : 'rotate(0deg)',
            transition: 'transform 300ms ease',
          }}
        >
          <rect x="14" y="48" width="12" height="26" rx="5" fill="#1e293b" stroke="#334155" strokeWidth="1.5" />
          <circle cx="20" cy="52" r="2.5" fill={coreColor} />
          <path d="M 16 74 L 14 84 L 24 84 L 22 74 Z" fill="#0f172a" stroke={coreColor} strokeWidth="1.2" />
        </g>

        {/* Right Articulated Mechanical Arm */}
        <g
          style={{
            transformOrigin: '92px 56px',
            transform: isActive ? 'rotate(10deg)' : 'rotate(0deg)',
            transition: 'transform 300ms ease',
          }}
        >
          <rect x="94" y="48" width="12" height="26" rx="5" fill="#1e293b" stroke="#334155" strokeWidth="1.5" />
          <circle cx="100" cy="52" r="2.5" fill={coreColor} />
          <path d="M 98 74 L 96 84 L 106 84 L 104 74 Z" fill="#0f172a" stroke={coreColor} strokeWidth="1.2" />
        </g>

        {/* Robot Head / Sensor Dome */}
        <rect
          x="34"
          y="16"
          width="52"
          height="28"
          rx="9"
          fill="#0f172a"
          stroke={isActive ? coreColor : '#334155'}
          strokeWidth="2"
        />

        {/* Scanning Visor Window */}
        <rect x="40" y="23" width="40" height="12" rx="4" fill="#07090e" stroke="#1e293b" strokeWidth="1" />

        {/* Dual Optical Sensors / Scanning Laser Bar */}
        {chassis === 'synapse_dual' || chassis === 'valkyrie_eth' ? (
          <>
            <circle cx="50" cy="29" r="3.5" fill={coreColor} />
            <circle cx="70" cy="29" r="3.5" fill={coreColor} />
            <line x1="43" y1="29" x2="77" y2="29" stroke={coreColor} strokeWidth="1" opacity="0.6" />
          </>
        ) : (
          <>
            <rect x="44" y="27" width="32" height="4" rx="2" fill={coreColor} opacity="0.85" />
            <circle cx="52" cy="29" r="2" fill="#ffffff" />
            <circle cx="68" cy="29" r="2" fill="#ffffff" />
          </>
        )}

        {/* Neck Gimbal */}
        <rect x="52" y="44" width="16" height="5" rx="2" fill="#334155" />

        {/* Armored Torso Chassis */}
        <path
          d="M 28 49 L 92 49 L 84 86 L 36 86 Z"
          fill="#121621"
          stroke={isActive ? coreColor : '#334155'}
          strokeWidth="2"
        />

        {/* Chest Reactor Core */}
        <circle cx="60" cy="66" r="16" fill={`url(#coreGlow-${chassis}-${accentColor})`} />
        <circle
          cx="60"
          cy="66"
          r="9"
          fill="#0b0d13"
          stroke={coreColor}
          strokeWidth="2"
        />
        <circle cx="60" cy="66" r="4.5" fill={coreColor} />

        {/* Stabilizer Thrusters / Legs */}
        <rect x="41" y="86" width="12" height="16" rx="3" fill="#1e293b" stroke="#334155" strokeWidth="1.5" />
        <rect x="67" y="86" width="12" height="16" rx="3" fill="#1e293b" stroke="#334155" strokeWidth="1.5" />
        <rect x="38" y="101" width="18" height="5" rx="2" fill={coreColor} opacity="0.75" />
        <rect x="64" y="101" width="18" height="5" rx="2" fill={coreColor} opacity="0.75" />

        {/* Seal of Excellence Crown Indicator */}
        {stage === 'live_sealed' && (
          <polygon
            points="60,8 64,14 56,14"
            fill="#10b981"
          />
        )}
      </svg>
    </div>
  );
};
