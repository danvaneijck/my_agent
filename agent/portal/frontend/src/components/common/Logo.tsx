interface LogoProps {
  size?: "sm" | "md" | "lg";
  withText?: boolean;
  className?: string;
}

export default function Logo({ size = "md", withText = true, className = "" }: LogoProps) {
  const sizeMap = {
    sm: { box: 24, rect: 6, spacing: 13, center: 9, fontSize: "text-lg" },
    md: { box: 40, rect: 10, spacing: 22, center: 15, fontSize: "text-2xl" },
    lg: { box: 64, rect: 12, spacing: 35, center: 26, fontSize: "text-4xl" },
  };

  const s = sizeMap[size];

  return (
    <div className={`flex items-center gap-3 ${className}`}>
      {/* SVG Logo */}
      <svg
        width={s.box}
        height={s.box}
        viewBox={`0 0 ${s.box} ${s.box}`}
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        className="flex-shrink-0"
      >
        {/* Top-left module */}
        <rect x="2" y="2" width={s.rect} height={s.rect} rx="2" fill="#6366f1" opacity="0.9" />

        {/* Top-right module */}
        <rect x={s.box - s.rect - 2} y="2" width={s.rect} height={s.rect} rx="2" fill="#06b6d4" opacity="0.9" />

        {/* Bottom-left module */}
        <rect x="2" y={s.box - s.rect - 2} width={s.rect} height={s.rect} rx="2" fill="#06b6d4" opacity="0.9" />

        {/* Center module (accent) */}
        <rect x={s.center} y={s.center} width={s.rect} height={s.rect} rx="2" fill="#818cf8" opacity="1" />

        {/* Connection lines (flow) */}
        <line x1={s.rect + 2} y1="7" x2={s.box - s.rect - 2} y2="7" stroke="#818cf8" strokeWidth="2" opacity="0.5" />
        <line x1="7" y1={s.rect + 2} x2="7" y2={s.box - s.rect - 2} stroke="#818cf8" strokeWidth="2" opacity="0.5" />
        <line x1={s.center + s.rect / 2} y1={s.center + s.rect} x2={s.center + s.rect / 2} y2={s.box - s.rect - 2} stroke="#818cf8" strokeWidth="2" opacity="0.5" />
        <line x1={s.center + s.rect} y1={s.center + s.rect / 2} x2={s.box - s.rect - 2} y2={s.center + s.rect / 2} stroke="#818cf8" strokeWidth="2" opacity="0.5" />
      </svg>

      {/* Text */}
      {withText && (
        <div className="flex flex-col">
          <span className={`font-bold text-white leading-tight ${s.fontSize}`}>ModuFlow</span>
          {size !== "sm" && (
            <span className="text-xs text-gray-400 leading-tight">Modular AI Agent Framework</span>
          )}
        </div>
      )}
    </div>
  );
}
