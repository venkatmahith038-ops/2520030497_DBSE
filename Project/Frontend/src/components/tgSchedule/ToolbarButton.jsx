import React from "react";

export default function ToolbarButton({ icon: Icon, title, onClick, size = 14 }) {
  return (
    <button type="button" title={title} onClick={onClick} style={{
      background: "none", border: "1px solid transparent", borderRadius: "4px",
      padding: "4px 6px", cursor: "pointer", color: "var(--text-secondary)",
      display: "flex", alignItems: "center", justifyContent: "center",
      transition: "all 0.15s",
    }}
    onMouseEnter={(e) => { e.currentTarget.style.background = "var(--bg-tertiary)"; e.currentTarget.style.borderColor = "var(--border-color)"; }}
    onMouseLeave={(e) => { e.currentTarget.style.background = "none"; e.currentTarget.style.borderColor = "transparent"; }}
    >
      <Icon size={size} />
    </button>
  );
}
