import React from "react";

export type LogoSize = "xs" | "sm" | "md" | "lg" | "xl";

interface LogoProps {
  size?: LogoSize;
  variant?: "full" | "icon";
  className?: string;
}

const sizeConfig = {
  xs: { height: 24, width: 100, iconSize: 32 },
  sm: { height: 32, width: 133, iconSize: 48 },
  md: { height: 48, width: 200, iconSize: 64 },
  lg: { height: 64, width: 267, iconSize: 96 },
  xl: { height: 80, width: 333, iconSize: 128 },
};

/**
 * ModuFlow Logo component
 *
 * @param size - Size variant: xs (24h), sm (32h), md (48h), lg (64h), xl (80h)
 * @param variant - Display variant: "full" (icon + wordmark) or "icon" (icon only)
 * @param className - Additional CSS classes
 *
 * @example
 * ```tsx
 * <Logo size="md" variant="full" />
 * <Logo size="sm" variant="icon" />
 * ```
 */
export function Logo({ size = "md", variant = "full", className = "" }: LogoProps) {
  const config = sizeConfig[size];

  if (variant === "icon") {
    return (
      <svg
        width={config.iconSize}
        height={config.iconSize}
        viewBox="0 0 64 64"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        className={className}
      >
        <rect width="64" height="64" fill="transparent" rx="8" />

        {/* Left hexagon */}
        <path d="M12 32L18 22L30 22L36 32L30 42L18 42L12 32Z" fill="#6366f1" />

        {/* Middle hexagon with gradient */}
        <path d="M28 32L34 22L46 22L52 32L46 42L34 42L28 32Z" fill="url(#iconGradient)" />

        {/* Connection line */}
        <line x1="30" y1="32" x2="34" y2="32" stroke="#818cf8" strokeWidth="3" strokeLinecap="round" />

        <defs>
          <linearGradient id="iconGradient" x1="28" y1="22" x2="52" y2="42" gradientUnits="userSpaceOnUse">
            <stop offset="0%" stopColor="#6366f1" />
            <stop offset="100%" stopColor="#06b6d4" />
          </linearGradient>
        </defs>
      </svg>
    );
  }

  return (
    <svg
      width={config.width}
      height={config.height}
      viewBox="0 0 200 48"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
    >
      {/* Icon: Connected modular hexagons */}
      <g id="icon">
        {/* Left hexagon */}
        <path d="M10 24L16 14L28 14L34 24L28 34L16 34L10 24Z" fill="#6366f1" fillOpacity="0.9" />

        {/* Middle hexagon */}
        <path d="M26 24L32 14L44 14L50 24L44 34L32 34L26 24Z" fill="url(#gradient1)" />

        {/* Right hexagon */}
        <path d="M42 24L48 14L60 14L66 24L60 34L48 34L42 24Z" fill="#06b6d4" fillOpacity="0.8" />

        {/* Connection lines */}
        <line x1="28" y1="24" x2="32" y2="24" stroke="#818cf8" strokeWidth="2" />
        <line x1="44" y1="24" x2="48" y2="24" stroke="#818cf8" strokeWidth="2" />
      </g>

      {/* Wordmark: ModuFlow */}
      <text
        x="78"
        y="32"
        fontFamily="Inter, sans-serif"
        fontSize="24"
        fontWeight="700"
        fill="#f1f5f9"
      >
        ModuFlow
      </text>

      {/* Gradient definition */}
      <defs>
        <linearGradient id="gradient1" x1="26" y1="14" x2="50" y2="34" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stopColor="#6366f1" />
          <stop offset="100%" stopColor="#06b6d4" />
        </linearGradient>
      </defs>
    </svg>
  );
}
