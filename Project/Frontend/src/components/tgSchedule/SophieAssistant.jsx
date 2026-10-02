import React, { useState } from "react";
import { Sparkles, RefreshCw, Wand2 } from "lucide-react";
import { apiFetch } from "../../api";
import { labelStyle } from "./editorUtils";

/**
 * Collapsible AI copywriter panel.
 *
 * Owns all of its own request state; the composer only receives the finished
 * text through `onApply`.
 */
export default function SophieAssistant({ onApply }) {
  const [open, setOpen] = useState(false);
  const [prompt, setPrompt] = useState("");
  const [platform, setPlatform] = useState("telegram");
  const [tone, setTone] = useState("friendly");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState("");
  const [error, setError] = useState("");

  const handleGenerate = async (e) => {
    e?.preventDefault?.();
    if (!prompt.trim()) return;
    setLoading(true);
    setError("");
    setResult("");
    try {
      const data = await apiFetch("/api/ai/sophie", {
        method: "POST",
        body: JSON.stringify({
          prompt: prompt.trim(),
          platform,
          tone,
        }),
      });
      setResult(data.text);
    } catch (err) {
      setError(err.message || "Sophie AI failed to generate a message.");
    } finally {
      setLoading(false);
    }
  };

  const handleApply = () => {
    if (!result) return;
    onApply(result);
    setOpen(false);
    setPrompt("");
    setResult("");
  };

  const selectStyle = {
    width: "100%", padding: "6px 10px", borderRadius: "7px",
    border: "1px solid var(--border-color)", fontSize: "12px",
    background: "var(--bg-primary)", color: "var(--text-primary)",
  };

  const primaryButtonStyle = {
    height: "34px", borderRadius: "7px", border: "none", cursor: "pointer",
    fontWeight: "600", fontSize: "12px", color: "#fff",
    background: "linear-gradient(135deg, #a855f7 0%, #ec4899 100%)",
    display: "flex", alignItems: "center", gap: "6px",
  };

  const secondaryButtonStyle = {
    height: "34px", padding: "0 12px", borderRadius: "7px",
    border: "1px solid var(--border-color)", cursor: "pointer",
    fontWeight: "600", fontSize: "12px", background: "var(--bg-secondary)",
    display: "flex", alignItems: "center", gap: "5px",
  };

  return (
    <>
      <style>{`
        @keyframes tg-sophie-spin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
        .tg-sophie-spin { animation: tg-sophie-spin 1.2s linear infinite; }
      `}</style>
      <button
        type="button"
        onClick={() => setOpen(!open)}
        style={{
          width: "100%",
          padding: "11px 16px",
          marginBottom: "16px",
          background: "linear-gradient(135deg, rgba(168,85,247,0.15) 0%, rgba(236,72,153,0.15) 100%)",
          border: "1px solid rgba(168,85,247,0.3)",
          borderRadius: "10px",
          color: "var(--text-primary)",
          fontWeight: "600",
          fontSize: "13px",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          cursor: "pointer",
          transition: "all 0.2s",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <Sparkles size={15} style={{ color: "#d946ef" }} />
          <span>Ask Sophie AI Copywriter</span>
        </div>
        <span style={{ fontSize: "11px", opacity: 0.8 }}>
          {open ? "Hide Assistant" : "Need ideas? Ask Sophie"}
        </span>
      </button>

      {open && (
        <div style={{
          padding: "16px",
          borderRadius: "10px",
          background: "rgba(168,85,247,0.04)",
          border: "1px solid rgba(168,85,247,0.25)",
          marginBottom: "16px",
          display: "flex",
          flexDirection: "column",
          gap: "12px",
        }}>
          <div style={{ fontSize: "12px", color: "var(--text-secondary)", lineHeight: "1.4" }}>
            Tell Sophie what kind of Telegram message you want. She'll write it automatically using NVIDIA NIM GPU models.
          </div>

          <div>
            <label style={{ ...labelStyle, marginBottom: "5px" }}>What should this message say?</label>
            <textarea
              style={{
                width: "100%", height: "64px", fontSize: "12.5px", resize: "none",
                borderRadius: "8px", border: "1px solid var(--border-color)",
                padding: "8px 12px", fontFamily: "inherit",
                background: "var(--bg-primary)", color: "var(--text-primary)",
              }}
              placeholder="e.g. A friendly announcement about our new Telegram channel with a CTA to join..."
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              disabled={loading}
            />
          </div>

          <div style={{ display: "flex", gap: "10px" }}>
            <div style={{ flex: 1 }}>
              <label style={labelStyle}>Platform</label>
              <select
                style={selectStyle}
                value={platform}
                onChange={(e) => setPlatform(e.target.value)}
                disabled={loading}
              >
                <option value="telegram">Telegram Post</option>
                <option value="instagram">Instagram DM</option>
              </select>
            </div>
            <div style={{ flex: 1 }}>
              <label style={labelStyle}>Tone of Voice</label>
              <select
                style={selectStyle}
                value={tone}
                onChange={(e) => setTone(e.target.value)}
                disabled={loading}
              >
                <option value="friendly">Friendly &amp; Warm</option>
                <option value="professional">Professional &amp; Direct</option>
                <option value="casual">Casual &amp; Conversational</option>
                <option value="urgent">Direct &amp; Urgent</option>
                <option value="educational">Educational &amp; Value-focused</option>
              </select>
            </div>
          </div>

          {error && (
            <div style={{ color: "#ef4444", fontSize: "12px", background: "rgba(239,68,68,0.05)", padding: "8px 10px", borderRadius: "6px", border: "1px solid rgba(239,68,68,0.15)" }}>
              {error}
            </div>
          )}

          {result && (
            <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
              <label style={{ ...labelStyle, marginBottom: 0 }}>Sophie's Output:</label>
              <div style={{
                padding: "12px", background: "var(--bg-secondary)",
                border: "1px solid rgba(168,85,247,0.25)", borderRadius: "8px",
                fontFamily: "monospace", fontSize: "12.5px", lineHeight: "1.5",
                color: "var(--text-primary)", whiteSpace: "pre-wrap", wordBreak: "break-word",
              }}>
                {result}
              </div>
              <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
                <button
                  type="button"
                  onClick={handleApply}
                  disabled={loading}
                  style={{ ...primaryButtonStyle, padding: "0 14px", gap: "5px" }}
                >
                  <Sparkles size={12} /> Use this Message
                </button>
                <button
                  type="button"
                  onClick={() => handleGenerate()}
                  disabled={loading || !prompt.trim()}
                  style={{ ...secondaryButtonStyle, color: "var(--text-secondary)" }}
                >
                  {loading ? <RefreshCw size={12} className="tg-sophie-spin" /> : <Wand2 size={12} />}
                  {loading ? "Generating..." : "Regenerate"}
                </button>
                <button
                  type="button"
                  onClick={() => setResult("")}
                  disabled={loading}
                  style={{ ...secondaryButtonStyle, color: "var(--text-muted)" }}
                >
                  Clear
                </button>
              </div>
            </div>
          )}

          {!result && (
            <button
              type="button"
              onClick={handleGenerate}
              disabled={loading || !prompt.trim()}
              style={{
                ...primaryButtonStyle,
                padding: "0 16px",
                alignSelf: "flex-start",
                opacity: loading || !prompt.trim() ? 0.6 : 1,
              }}
            >
              {loading ? <RefreshCw size={12} className="tg-sophie-spin" /> : <Sparkles size={12} />}
              {loading ? "Generating..." : "Generate Message"}
            </button>
          )}
        </div>
      )}
    </>
  );
}
