import React, { useEffect, useId, useRef } from "react";
import { WorkspaceContext } from "./workspace";
const paths: Record<string, React.ReactNode> = {
  home: <path d="m3 10 9-7 9 7v10a1 1 0 0 1-1 1h-5v-7H9v7H4a1 1 0 0 1-1-1Z" />,
  chat: (
    <path d="M21 11.5a8.4 8.4 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.4 8.4 0 0 1-3.8-.9L3 21l1.9-5.7a8.4 8.4 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.4 8.4 0 0 1 3.8-.9h.5a8.5 8.5 0 0 1 8 8Z" />
  ),
  book: (
    <>
      <path d="M12 5C9 3 5 3 2 4v15c3-1 7-1 10 1 3-2 7-2 10-1V4c-3-1-7-1-10 1Z" />
      <path d="M12 5v15M5 8h4M5 12h4m6-4h4m-4 4h4" />
    </>
  ),
  memory: (
    <>
      <path d="M12 3a4 4 0 0 0-7 3 4 4 0 0 0-2 7 4 4 0 0 0 3 7 3 3 0 0 0 6 0V3a4 4 0 0 1 7 3 4 4 0 0 1 2 7 4 4 0 0 1-3 7 3 3 0 0 1-6 0" />
      <path d="M8 8c0 2 1 3 4 3m4-3c0 2-1 3-4 3M6 15c3-1 4 1 4 2m8-2c-3-1-4 1-4 2" />
    </>
  ),
  settings: (
    <>
      <path d="M4 7h16M4 17h16" />
      <circle cx="9" cy="7" r="3" />
      <circle cx="15" cy="17" r="3" />
    </>
  ),
  arrow: <path d="M4 12h15m-5-5 5 5-5 5" />,
  chevron: <path d="m9 5 7 7-7 7" />,
  check: <path d="m5 12 4 4L19 6" />,
  close: <path d="m6 6 12 12M6 18 18 6" />,
  plus: <path d="M12 5v14M5 12h14" />,
  refresh: (
    <>
      <path d="M20 7v5h-5M4 17v-5h5" />
      <path d="M6 7a7 7 0 0 1 12-2l2 3M4 16l2 3a7 7 0 0 0 12-2" />
    </>
  ),
  play: <path d="m8 4 12 8-12 8Z" />,
  pause: <path d="M8 4v16M16 4v16" />,
  stop: <rect x="5" y="5" width="14" height="14" rx="2" />,
  info: (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 11v6m0-10v.2" />
    </>
  ),
  help: (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="M9.5 9a2.5 2.5 0 1 1 4.4 1.6c-1.4.7-1.9 1.1-1.9 2.4m0 3v.1" />
    </>
  ),
  shield: (
    <>
      <path d="m12 3 8 3v6c0 4-4 7-8 9-4-2-8-5-8-9V6Z" />
      <path d="m8 12 3 3 5-6" />
    </>
  ),
  file: (
    <>
      <path d="M13 3H5v18h14V9Z" />
      <path d="M13 3v6h6M8 13h8m-8 4h5" />
    </>
  ),
  upload: <path d="M12 16V3m-5 5 5-5 5 5M4 16v5h16v-5" />,
  search: (
    <>
      <circle cx="10" cy="10" r="6" />
      <path d="m15 15 6 6" />
    </>
  ),
  trash: <path d="M3 6h18M9 6V3h6v3m-10 0 1 15h12l1-15M10 10v7m4-7v7" />,
  spark: <path d="m12 3 2.5 6.5L21 12l-6.5 2.5L12 21l-2.5-6.5L3 12l6.5-2.5Z" />,
  edit: <path d="m15 4 5 5-11 11H4v-5Zm-2 2 5 5" />,
  globe: (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="M3 12h18M12 3c5 5 5 13 0 18-5-5-5-13 0-18Z" />
    </>
  ),
  clock: (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 6v6l4 2" />
    </>
  ),
  copy: (
    <>
      <rect x="8" y="8" width="13" height="13" rx="2" />
      <path d="M16 8V3H3v13h5" />
    </>
  ),
  coffee: (
    <path d="M3 8h14v8a5 5 0 0 1-5 5H8a5 5 0 0 1-5-5Zm14 1h2a3 3 0 0 1 0 6h-2M7 2v3m6-3v3" />
  ),
  eye: (
    <>
      <path d="M2 12c5-9 15-9 20 0-5 9-15 9-20 0Z" />
      <circle cx="12" cy="12" r="3" />
    </>
  ),
};
export function Icon({
  name,
  size = 18,
  className = "",
}: {
  name: string;
  size?: number;
  className?: string;
}) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      className={className}
    >
      {paths[name] || paths.info}
    </svg>
  );
}
export function Empty({
  icon = "chat",
  title,
  children,
  action,
}: {
  icon?: string;
  title: string;
  children?: React.ReactNode;
  action?: React.ReactNode;
}) {
  return (
    <div className="empty-state">
      <div className="empty-symbol">
        <Icon name={icon} size={24} />
      </div>
      <h3>{title}</h3>
      {children && <p>{children}</p>}
      {action}
    </div>
  );
}
export function PageHeading({
  eyebrow,
  title,
  description,
  action,
}: {
  eyebrow?: string;
  title: string;
  description: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="page-heading">
      <div>
        {eyebrow && <span className="eyebrow">{eyebrow}</span>}
        <h1>{title}</h1>
        <p>{description}</p>
      </div>
      {action}
    </div>
  );
}
export function Modal({
  title,
  description,
  children,
  onClose,
  busy = false,
  wide = false,
}: {
  title: string;
  description?: string;
  children: React.ReactNode;
  onClose: () => void;
  busy?: boolean;
  wide?: boolean;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  const workspace = React.useContext(WorkspaceContext);
  const id = useId();
  useEffect(() => {
    const dialog = ref.current;
    dialog?.showModal();
    return () => {
      dialog?.close();
    };
  }, []);
  return (
    <dialog
      ref={ref}
      className={"modal " + (wide ? "modal-wide" : "")}
      aria-labelledby={id}
      aria-describedby={description ? id + "-description" : undefined}
      onCancel={(e) => {
        e.preventDefault();
        if (!busy) onClose();
      }}
      onClick={(e) => {
        if (e.target === ref.current && !busy) onClose();
      }}
    >
      <div className="modal-header">
        <div>
          <h2 id={id}>{title}</h2>
          {description && <p id={id + "-description"}>{description}</p>}
        </div>
        <button
          className="icon-button"
          aria-label="关闭对话框"
          disabled={busy}
          onClick={onClose}
        >
          <Icon name="close" />
        </button>
      </div>
      {workspace?.errorMessage && (
        <div className="feedback feedback-error" role="alert">
          {workspace.errorMessage}
        </div>
      )}
      {children}
    </dialog>
  );
}
export function Skeleton({ rows = 3 }: { rows?: number }) {
  return (
    <div className="skeleton-stack" role="status" aria-label="正在加载">
      {Array.from({ length: rows }, (_, i) => (
        <div className="skeleton" key={i} />
      ))}
    </div>
  );
}
export function Pill({
  children,
  tone = "neutral",
}: {
  children: React.ReactNode;
  tone?: string;
}) {
  return <span className={"pill pill-" + tone}>{children}</span>;
}
export function CopyButton({ value }: { value: string }) {
  const [copied, setCopied] = React.useState(false);
  const [failed, setFailed] = React.useState(false);
  useEffect(() => {
    if (!copied) return;
    const timer = setTimeout(() => setCopied(false), 2200);
    return () => clearTimeout(timer);
  }, [copied]);
  return (
    <button
      className="quiet-button"
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(value);
          setCopied(true);
          setFailed(false);
        } catch {
          setFailed(true);
        }
      }}
    >
      <Icon name={copied ? "check" : "copy"} size={15} />
      {copied ? "已复制" : failed ? "请选中文字复制" : "复制"}
    </button>
  );
}
