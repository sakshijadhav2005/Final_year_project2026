import type { ReactNode } from "react";

type Props = {
  checked: boolean;
  onChange: (next: boolean) => void;
  label?: ReactNode;
  /** Accessible name when there is no visible label. */
  ariaLabel?: string;
  /** Optional icons drawn inside the knob for the off / on states. */
  offIcon?: ReactNode;
  onIcon?: ReactNode;
  className?: string;
};

/**
 * Neumorphic switch: an inset track with a raised knob that slides across
 * when toggled. Keyboard accessible (Space / Enter) via a native button.
 */
export function NeuSwitch({ checked, onChange, label, ariaLabel, offIcon, onIcon, className = "" }: Props) {
  const control = (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label ? undefined : ariaLabel}
      onClick={() => onChange(!checked)}
      className={`neu-switch ${checked ? "is-on" : ""}`}
    >
      <span className="neu-switch-knob" aria-hidden="true">
        {checked ? onIcon : offIcon}
      </span>
    </button>
  );

  if (!label) return <span className={className}>{control}</span>;

  return (
    <label className={`flex cursor-pointer items-start gap-13 ${className}`}>
      {control}
      <span className="pt-[3px]">{label}</span>
    </label>
  );
}
