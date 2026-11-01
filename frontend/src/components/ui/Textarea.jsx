import { forwardRef, useId } from "react";
import { cx } from "./cx.js";

const Textarea = forwardRef(function Textarea(
  { id, label, hint, error, rows = 4, disabled = false, className, textareaClassName, ...props },
  ref,
) {
  const generatedId = useId();
  const textareaId = id || `textarea-${generatedId}`;
  const describedBy = error ? `${textareaId}-error` : hint ? `${textareaId}-hint` : undefined;

  return (
    <div className={cx("w-full", className)}>
      {label && (
        <label htmlFor={textareaId} className="mb-1.5 block type-sm font-medium text-foreground">
          {label}
        </label>
      )}
      <textarea
        ref={ref}
        id={textareaId}
        rows={rows}
        disabled={disabled}
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy}
        className={cx(
          "focus-ring w-full resize-y rounded-control border bg-surface px-3 py-2 type-sm text-foreground shadow-xs transition-colors duration-[var(--dur-fast)] placeholder:text-subtle",
          "border-line hover:border-lineStrong focus:border-accentText",
          "disabled:cursor-not-allowed disabled:bg-surfaceMuted disabled:text-muted",
          error && "border-danger focus:border-danger",
          textareaClassName,
        )}
        {...props}
      />
      {error ? (
        <p id={`${textareaId}-error`} className="mt-1.5 type-caption text-danger">
          {error}
        </p>
      ) : hint ? (
        <p id={`${textareaId}-hint`} className="mt-1.5 type-caption text-muted">
          {hint}
        </p>
      ) : null}
    </div>
  );
});

export default Textarea;
