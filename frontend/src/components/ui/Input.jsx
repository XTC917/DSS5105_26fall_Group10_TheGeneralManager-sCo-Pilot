import { forwardRef, useId } from "react";
import { cx } from "./cx.js";

/**
 * Accessible text input with label / hint / error support. Styled entirely with
 * semantic tokens so it adapts to Light/Dark and the active accent.
 */
const Input = forwardRef(function Input(
  {
    id,
    label,
    hint,
    error,
    leadingIcon = null,
    trailing = null,
    disabled = false,
    className,
    inputClassName,
    ...props
  },
  ref,
) {
  const generatedId = useId();
  const inputId = id || `field-${generatedId}`;
  const describedBy = error ? `${inputId}-error` : hint ? `${inputId}-hint` : undefined;

  return (
    <div className={cx("w-full", className)}>
      {label && (
        <label htmlFor={inputId} className="mb-1.5 block type-sm font-medium text-foreground">
          {label}
        </label>
      )}
      <div className="relative">
        {leadingIcon && (
          <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted">
            {leadingIcon}
          </span>
        )}
        <input
          ref={ref}
          id={inputId}
          disabled={disabled}
          aria-invalid={error ? true : undefined}
          aria-describedby={describedBy}
          className={cx(
            "focus-ring h-10 w-full rounded-control border bg-surface px-3 type-sm text-foreground shadow-xs transition-colors duration-[var(--dur-fast)] placeholder:text-subtle",
            "border-line hover:border-lineStrong focus:border-accentText",
            "disabled:cursor-not-allowed disabled:bg-surfaceMuted disabled:text-muted",
            leadingIcon && "pl-9",
            trailing && "pr-10",
            error && "border-danger focus:border-danger",
            inputClassName,
          )}
          {...props}
        />
        {trailing && (
          <span className="absolute right-2 top-1/2 -translate-y-1/2">{trailing}</span>
        )}
      </div>
      {error ? (
        <p id={`${inputId}-error`} className="mt-1.5 type-caption text-danger">
          {error}
        </p>
      ) : hint ? (
        <p id={`${inputId}-hint`} className="mt-1.5 type-caption text-muted">
          {hint}
        </p>
      ) : null}
    </div>
  );
});

export default Input;
