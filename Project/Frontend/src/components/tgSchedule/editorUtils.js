import { MessageSquare, FileUp, Layers } from "lucide-react";

export const STATUS_COLORS = {
  pending: "var(--warning)", processing: "var(--info)", sent: "var(--success)", failed: "var(--danger)", cancelled: "var(--text-muted)",
};

export const MSG_TYPES = [
  { value: "text", label: "Text", icon: MessageSquare },
  { value: "media", label: "Media / File", icon: FileUp },
  { value: "multi", label: "Multi", icon: Layers },
];

export const labelStyle = { fontSize: "12px", fontWeight: 600, color: "var(--text-muted)", marginBottom: "6px", display: "block" };

/** Uploads are stored as `<uuid>__<original name>` — show only the readable part. */
export const displayMediaName = (path = "") => {
  const storedName = path.split("/").pop() || "attachment";
  return storedName.includes("__") ? storedName.split("__").slice(1).join("__") : storedName;
};

export function insertTag(textareaRef, openTag, closeTag, setContent) {
  const el = textareaRef.current;
  if (!el) return;
  const start = el.selectionStart;
  const end = el.selectionEnd;
  const text = el.value;
  const selected = text.substring(start, end);
  const replacement = `${openTag}${selected}${closeTag}`;
  const newText = text.substring(0, start) + replacement + text.substring(end);
  setContent(newText);
  setTimeout(() => {
    el.focus();
    const cursorPos = selected ? start + replacement.length : start + openTag.length;
    el.setSelectionRange(cursorPos, cursorPos);
  }, 0);
}

export function plainTextToHtml(text) {
  if (!text) return text;
  if (/<[a-z][\s\S]*>/i.test(text)) return text;
  let html = text
    .replace(/\*\*(.+?)\*\*/g, "<b>$1</b>")
    .replace(/\*(.+?)\*/g, "<i>$1</i>")
    .replace(/__(.+?)__/g, "<u>$1</u>")
    .replace(/~~(.+?)~~/g, "<s>$1</s>")
    .replace(/`(.+?)`/g, "<code>$1</code>");
  return html;
}

export const toLocalInputValue = (date) => {
  const pad = (value) => String(value).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
};

export const defaultScheduleTime = () => toLocalInputValue(new Date(Date.now() + 10 * 60 * 1000));
