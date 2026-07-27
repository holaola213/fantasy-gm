import {
  type ButtonHTMLAttributes,
  type HTMLAttributes,
  type ReactNode,
  useCallback,
  useEffect,
  useId,
  useRef,
  useState,
} from "react";
import { createPortal } from "react-dom";

type BaseProps = {
  children: ReactNode;
  className?: string;
  text: string;
};

type SpanProps = BaseProps &
  Omit<HTMLAttributes<HTMLSpanElement>, "children" | "className"> & {
    as?: "span";
  };

type ButtonProps = BaseProps &
  Omit<ButtonHTMLAttributes<HTMLButtonElement>, "children" | "className"> & {
    as: "button";
  };

type TooltipPosition = {
  left: number;
  top: number;
  placement: "above" | "below";
};

const TOOLTIP_WIDTH = 280;
const VIEWPORT_PADDING = 12;
const TRIGGER_GAP = 8;

export function ExplainedTerm(props: SpanProps | ButtonProps) {
  const { children, className, text } = props;
  const id = useId();
  const triggerRef = useRef<HTMLSpanElement | HTMLButtonElement | null>(null);
  const tooltipRef = useRef<HTMLDivElement | null>(null);
  const [isHovering, setIsHovering] = useState(false);
  const [isFocused, setIsFocused] = useState(false);
  const [position, setPosition] = useState<TooltipPosition | null>(null);
  const isOpen = isHovering || isFocused;

  const updatePosition = useCallback(() => {
    const trigger = triggerRef.current;
    if (!trigger) {
      return;
    }
    const rect = trigger.getBoundingClientRect();
    if (
      rect.bottom < 0 ||
      rect.top > window.innerHeight ||
      rect.right < 0 ||
      rect.left > window.innerWidth
    ) {
      setPosition(null);
      return;
    }

    const tooltipHeight = tooltipRef.current?.offsetHeight ?? 72;
    const width = Math.min(TOOLTIP_WIDTH, window.innerWidth - VIEWPORT_PADDING * 2);
    const preferredTop = rect.top - tooltipHeight - TRIGGER_GAP;
    const hasRoomAbove = preferredTop >= VIEWPORT_PADDING;
    const top = hasRoomAbove
      ? preferredTop
      : Math.min(rect.bottom + TRIGGER_GAP, window.innerHeight - tooltipHeight - VIEWPORT_PADDING);
    const idealLeft = rect.left + rect.width / 2 - width / 2;
    const left = Math.min(
      Math.max(idealLeft, VIEWPORT_PADDING),
      window.innerWidth - width - VIEWPORT_PADDING,
    );
    setPosition({
      left,
      top: Math.max(top, VIEWPORT_PADDING),
      placement: hasRoomAbove ? "above" : "below",
    });
  }, []);

  useEffect(() => {
    if (!isOpen) {
      setPosition(null);
      return;
    }
    updatePosition();
    window.addEventListener("resize", updatePosition);
    window.addEventListener("scroll", updatePosition, true);
    return () => {
      window.removeEventListener("resize", updatePosition);
      window.removeEventListener("scroll", updatePosition, true);
    };
  }, [isOpen, updatePosition]);

  useEffect(() => {
    if (isOpen) {
      updatePosition();
    }
  }, [isOpen, position?.placement, updatePosition]);

  useEffect(() => {
    if (!isOpen) {
      return;
    }
    function closeOnEscape(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setIsFocused(false);
        setIsHovering(false);
        triggerRef.current?.blur();
      }
    }
    document.addEventListener("keydown", closeOnEscape);
    return () => document.removeEventListener("keydown", closeOnEscape);
  }, [isOpen]);

  const sharedProps = {
    "aria-describedby": isOpen ? id : undefined,
    className: ["explained-term", className].filter(Boolean).join(" "),
    onBlur: () => setIsFocused(false),
    onFocus: () => setIsFocused(true),
    onMouseEnter: () => setIsHovering(true),
    onMouseLeave: () => setIsHovering(false),
  };

  if (props.as === "button") {
    const { as: _as, children: _children, className: _className, text: _text, ...buttonProps } = props;
    return (
      <>
      <button
        {...buttonProps}
        {...sharedProps}
        ref={(node) => {
          triggerRef.current = node;
        }}
      >
        {children}
      </button>
        {isOpen && position
          ? createPortal(
              <div
                className={`explained-term-tooltip ${position.placement}`}
                id={id}
                ref={tooltipRef}
                role="tooltip"
                style={{
                  left: position.left,
                  top: position.top,
                  width: Math.min(
                    TOOLTIP_WIDTH,
                    window.innerWidth - VIEWPORT_PADDING * 2,
                  ),
                }}
              >
                {text}
              </div>,
              document.body,
            )
          : null}
      </>
    );
  }

  const {
    as: _as,
    children: _children,
    className: _className,
    text: _text,
    ...spanProps
  } = props;

  return (
    <>
      <span
        {...spanProps}
        {...sharedProps}
        ref={(node) => {
          triggerRef.current = node;
        }}
        tabIndex={props.tabIndex ?? 0}
      >
        {children}
      </span>
      {isOpen && position
        ? createPortal(
            <div
              className={`explained-term-tooltip ${position.placement}`}
              id={id}
              ref={tooltipRef}
              role="tooltip"
              style={{
                left: position.left,
                top: position.top,
                width: Math.min(
                  TOOLTIP_WIDTH,
                  window.innerWidth - VIEWPORT_PADDING * 2,
                ),
              }}
            >
              {text}
            </div>,
            document.body,
          )
        : null}
    </>
  );
}
