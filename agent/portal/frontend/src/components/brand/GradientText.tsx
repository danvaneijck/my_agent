import React from "react";

type GradientVariant = "brand" | "primary" | "secondary";

interface GradientTextProps {
  children: React.ReactNode;
  variant?: GradientVariant;
  className?: string;
  as?: "span" | "h1" | "h2" | "h3" | "h4" | "h5" | "h6" | "p";
}

const gradientClasses: Record<GradientVariant, string> = {
  brand: "bg-gradient-brand",
  primary: "bg-gradient-primary",
  secondary: "bg-gradient-secondary",
};

/**
 * GradientText component - applies brand gradient to text
 *
 * Uses CSS background-clip and text-transparent to create gradient text effect.
 *
 * @param variant - Gradient variant: "brand" (primary → secondary), "primary" (indigo), "secondary" (teal)
 * @param as - HTML element to render as (default: "span")
 * @param className - Additional CSS classes
 *
 * @example
 * ```tsx
 * <GradientText variant="brand" as="h1" className="text-4xl font-bold">
 *   ModuFlow
 * </GradientText>
 *
 * <GradientText variant="primary">
 *   Highlighted text
 * </GradientText>
 * ```
 */
export function GradientText({
  children,
  variant = "brand",
  className = "",
  as: Component = "span",
}: GradientTextProps) {
  const gradientClass = gradientClasses[variant];

  return (
    <Component className={`${gradientClass} bg-clip-text text-transparent ${className}`}>
      {children}
    </Component>
  );
}
