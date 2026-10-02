import React, { useState, useRef, useCallback } from "react";
import { Upload, FileText, X } from "lucide-react";

export default function FileUploadArea({ accept, label, file, onFileSelect, onClear, preview }) {
  const inputRef = useRef(null);
  const [dragOver, setDragOver] = useState(false);

  const handleDrop = useCallback((e) => {
    e.preventDefault();
    setDragOver(false);
    const dropped = e.dataTransfer.files[0];
    if (dropped) onFileSelect(dropped);
  }, [onFileSelect]);

  return (
    <div
      onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
      onDragLeave={() => setDragOver(false)}
      onDrop={handleDrop}
      onClick={() => !file && inputRef.current?.click()}
      style={{
        border: `2px dashed ${dragOver ? "#6366F1" : file ? "var(--success)" : "var(--border-color)"}`,
        borderRadius: "12px",
        padding: file ? "12px" : "24px",
        textAlign: "center",
        cursor: file ? "default" : "pointer",
        background: dragOver ? "rgba(99, 102, 241,0.04)" : file ? "rgba(34,197,94,0.04)" : "var(--bg-tertiary)",
        transition: "all 0.2s",
      }}
    >
      <input
        ref={inputRef}
        type="file"
        accept={accept}
        onChange={(e) => e.target.files[0] && onFileSelect(e.target.files[0])}
        style={{ display: "none" }}
      />
      {file ? (
        <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
          {preview ? (
            <img src={preview} alt="" style={{ width: "48px", height: "48px", borderRadius: "8px", objectFit: "cover" }} />
          ) : (
            <div style={{ width: "48px", height: "48px", borderRadius: "8px", background: "rgba(14,165,233,0.08)", display: "flex", alignItems: "center", justifyContent: "center", color: "#0EA5E9" }}>
              <FileText size={20} />
            </div>
          )}
          <div style={{ flex: 1, textAlign: "left" }}>
            <p style={{ fontWeight: 600, fontSize: "13px", marginBottom: "2px" }}>{file.name}</p>
            <p style={{ fontSize: "11px", color: "var(--text-muted)" }}>{(file.size / 1024).toFixed(1)} KB</p>
          </div>
          <button type="button" onClick={(e) => { e.stopPropagation(); onClear(); }}
            style={{ background: "rgba(239,68,68,0.08)", border: "none", borderRadius: "6px", padding: "6px", cursor: "pointer", color: "var(--danger)" }}>
            <X size={14} />
          </button>
        </div>
      ) : (
        <>
          <Upload size={24} style={{ color: "var(--text-muted)", marginBottom: "8px" }} />
          <p style={{ fontSize: "13px", fontWeight: 600, color: "var(--text-secondary)", marginBottom: "4px" }}>{label}</p>
          <p style={{ fontSize: "11px", color: "var(--text-muted)" }}>Drag & drop or click to browse</p>
        </>
      )}
    </div>
  );
}
