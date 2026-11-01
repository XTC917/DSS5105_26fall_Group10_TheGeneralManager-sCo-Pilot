import { cx } from "./cx.js";

const PADDING = {
  none: "p-0",
  sm: "p-3",
  md: "p-5",
  lg: "p-6",
};

/**
 * Surface container. `interactive` adds hover elevation + keyboard affordance
 * and turns the card into a button role when an onClick is provided.
 */
export default function Card({
  as: Tag = "div",
  padding = "md",
  interactive = false,
  className,
  children,
  onClick,
  ...props
}) {
  const clickable = interactive || typeof onClick === "function";
  const handleKeyDown =
    clickable && typeof onClick === "function"
      ? (event) => {
          if (event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            onClick(event);
          }
        }
      : undefined;

  return (
    <Tag
      className={cx(
        "rounded-card border border-line bg-surface shadow-xs",
        PADDING[padding] || PADDING.md,
        clickable &&
          "focus-ring cursor-pointer transition-[transform,box-shadow,background-color] duration-[var(--dur)] hover:-translate-y-0.5 hover:shadow-card active:translate-y-0",
        className,
      )}
      onClick={onClick}
      role={clickable ? "button" : undefined}
      tabIndex={clickable ? 0 : undefined}
      onKeyDown={handleKeyDown}
      {...props}
    >
      {children}
    </Tag>
  );
}

/** Small section wrapper with a title + optional action. */
export function CardSection({ title, description, action, children, className }) {
  return (
    <Card className={className}>
      {(title || action) && (
        <div className="mb-4 flex items-start justify-between gap-3">
          <div>
            {title && <h3 className="type-h3 text-foreground">{title}</h3>}
            {description && <p className="mt-1 type-sm text-muted">{description}</p>}
          </div>
          {action}
        </div>
      )}
      {children}
    </Card>
  );
}
