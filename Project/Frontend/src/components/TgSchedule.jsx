import React, { useState, useEffect, useRef } from "react";
import { apiFetch, apiUpload, getApiUrl } from "../api";
import QuickMediaPicker from "./QuickMediaPicker";
import ToolbarButton from "./tgSchedule/ToolbarButton";
import FileUploadArea from "./tgSchedule/FileUploadArea";
import SophieAssistant from "./tgSchedule/SophieAssistant";
import {
  STATUS_COLORS, MSG_TYPES, labelStyle, displayMediaName,
  insertTag, plainTextToHtml, defaultScheduleTime,
} from "./tgSchedule/editorUtils";
import {
  CalendarClock, Plus, Send, Trash2, Edit2,
  CheckCircle, XCircle, Clock, Repeat, X,
  Image, FileText,
  Bold, Italic, Code, Link2, Strikethrough, Underline,
  Eye, EyeOff, Library,
  RefreshCw,
} from "lucide-react";

export default function TgSchedule({ onOpenBots }) {
  const [posts, setPosts] = useState([]);
  const [channels, setChannels] = useState([]);
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [form, setForm] = useState({
    channel_id: "", content: "", scheduled_at: defaultScheduleTime(), message_type: "text",
    is_recurring: false, recurrence_rule: "",
  });
  const [mediaFiles, setMediaFiles] = useState([]);
  const [batchMessages, setBatchMessages] = useState([{ content: "", media_type: "text", file: null, filePreview: null }]);
  const [error, setError] = useState("");
  const [dataError, setDataError] = useState("");
  const [saving, setSaving] = useState(false);
  const [showPreview, setShowPreview] = useState(false);
  const [selectedIds, setSelectedIds] = useState([]);
  const [showLibrary, setShowLibrary] = useState(false);
  const [templates, setTemplates] = useState([]);
  const contentRef = useRef(null);

  const toggleSelect = (id) => {
    if (selectedIds.includes(id)) {
      setSelectedIds(selectedIds.filter(x => x !== id));
    } else {
      setSelectedIds([...selectedIds, id]);
    }
  };

  const selectAll = () => {
    if (selectedIds.length === posts.length) {
      setSelectedIds([]);
    } else {
      setSelectedIds(posts.map(p => p.id));
    }
  };

  const handleBulkDelete = async () => {
    if (!selectedIds.length) return;
    if (!window.confirm(`Delete ${selectedIds.length} scheduled item(s)?`)) return;
    try {
      await Promise.all(selectedIds.map(id => apiFetch(`/api/tg/posts/${id}`, { method: "DELETE" })));
      setSelectedIds([]);
      fetchData();
    } catch (e) {
      alert(e.message || "Failed to delete selected items.");
    }
  };

  const fetchData = async () => {
    setDataError("");
    try {
      const [p, ch, tpl] = await Promise.all([apiFetch("/api/tg/posts"), apiFetch("/api/tg/channels"), apiFetch("/api/tg/templates")]);
      setPosts(p);
      setChannels(ch);
      setTemplates(tpl);
      setForm((current) => ({ ...current, channel_id: current.channel_id || (ch[0] ? String(ch[0].id) : "") }));
    } catch (fetchError) {
      setDataError(fetchError.message || "Could not load scheduling data.");
    }
  };

  useEffect(() => { fetchData(); }, []);

  const resetForm = () => {
    setForm({ channel_id: channels[0] ? String(channels[0].id) : "", content: "", scheduled_at: defaultScheduleTime(), message_type: "text", is_recurring: false, recurrence_rule: "" });
    setMediaFiles([]);
    setBatchMessages([{ content: "", media_type: "text", file: null, filePreview: null }]);
    setError("");
    setShowPreview(false);
    setEditingId(null);
    setSelectedIds([]);
  };

  const handleFileSelect = (file) => {
    if (!file) return;
    // Guard against extremely large files (>500 MB) before touching the browser
    const MAX_MB = 500;
    if (file.size > MAX_MB * 1024 * 1024) {
      setError(`File is too large (${(file.size / 1024 / 1024).toFixed(0)} MB). Maximum allowed is ${MAX_MB} MB.`);
      return;
    }
    const newId = Date.now() + Math.random();
    // Use createObjectURL — instant and non-blocking (no base64 encoding)
    const preview = file.type.startsWith("image/") ? URL.createObjectURL(file) : null;
    const newAttachment = {
      id: newId,
      file: file,
      name: file.name,
      preview,
      media_type: file.type.startsWith("image/") ? "photo" : "document",
    };
    setMediaFiles(prev => [...prev, newAttachment]);
  };

  const uploadFile = async (file) => {
    const result = await apiUpload("/api/tg/upload", file);
    return result.filename;
  };

  const useLibraryMedia = async (files) => {
    try {
      const attachments = await Promise.all(files.map(async (file) => {
        const result = await apiFetch(`/api/media/${file.id}/use/telegram`, { method: "POST" });
        return {
          id: `library-${file.id}-${Date.now()}`,
          name: file.original_name,
          preview: file.file_type === "image" ? `${getApiUrl()}/api/tg/uploads/${result.filename}` : null,
          media_path: result.filename,
          media_type: file.file_type === "image" ? "photo" : "document",
        };
      }));
      setMediaFiles((items) => [...items, ...attachments]);
      setShowLibrary(false);
    } catch (error) {
      setError(error.message || "Could not use library media.");
    }
  };

  const handleEdit = (post) => {
    const scheduledUtc = post.scheduled_at.endsWith("Z") ? post.scheduled_at : post.scheduled_at + "Z";
    const localDate = new Date(scheduledUtc);
    const pad = (n) => String(n).padStart(2, "0");
    const localStr = `${localDate.getFullYear()}-${pad(localDate.getMonth() + 1)}-${pad(localDate.getDate())}T${pad(localDate.getHours())}:${pad(localDate.getMinutes())}`;
    setForm({
      channel_id: String(post.channel_id),
      content: post.content,
      scheduled_at: localStr,
      message_type: (post.message_type === "photo" || post.message_type === "document") ? "media" : (post.message_type || "text"),
      is_recurring: post.is_recurring,
      recurrence_rule: post.recurrence_rule || "",
    });
    setEditingId(post.id);
    setShowForm(true);

    const loadedFiles = [];
    if (post.media_path) {
      loadedFiles.push({
        id: "main",
        name: displayMediaName(post.media_path),
        preview: post.media_type === "photo" ? `${getApiUrl()}/api/tg/uploads/${post.media_path}` : null,
        media_path: post.media_path,
        media_type: post.media_type,
      });
    }
    // If it's a media post (i.e. message_type is photo or document), all batch messages with content === "" or content is empty are just additional files!
    const isMediaPost = post.message_type === "photo" || post.message_type === "document";
    const otherBatchMsgs = [];

    if (post.batch_messages) {
      post.batch_messages.forEach((bm, idx) => {
        if (isMediaPost && !bm.content && bm.media_path) {
          loadedFiles.push({
            id: `batch-media-${idx}`,
            name: displayMediaName(bm.media_path),
            preview: bm.media_type === "photo" ? `${getApiUrl()}/api/tg/uploads/${bm.media_path}` : null,
            media_path: bm.media_path,
            media_type: bm.media_type,
          });
        } else {
          otherBatchMsgs.push(bm);
        }
      });
    }
    setMediaFiles(loadedFiles);

    if (post.batch_messages && post.batch_messages.length > 0 && !isMediaPost) {
      setBatchMessages(post.batch_messages.map(bm => ({
        content: bm.content || "",
        media_type: (bm.media_type === "photo" || bm.media_type === "document") ? "media" : (bm.media_type || "text"),
        file: null,
        filePreview: (bm.media_path && bm.media_type === "photo") ? `${getApiUrl()}/api/tg/uploads/${bm.media_path}` : null,
        media_path: bm.media_path || null,
        actual_media_type: bm.media_type || null,
      })));
    } else {
      setBatchMessages([{ content: "", media_type: "text", file: null, filePreview: null }]);
    }
  };

  const handleCreate = async (e) => {
    e.preventDefault();
    setError("");
    if (!form.channel_id) {
      setError("Connect a Telegram bot and add a channel before creating a schedule.");
      return;
    }
    const localDate = new Date(form.scheduled_at);
    if (Number.isNaN(localDate.getTime())) {
      setError("Choose a valid schedule date and time.");
      return;
    }
    if (!editingId && localDate.getTime() <= Date.now()) {
      setError("Schedule time must be in the future.");
      return;
    }
    setSaving(true);
    try {
      const utcScheduledAt = localDate.toISOString();
      const processedContent = plainTextToHtml(form.content);

      const payload = {
        channel_id: parseInt(form.channel_id),
        content: processedContent,
        scheduled_at: utcScheduledAt,
        is_recurring: form.is_recurring,
        recurrence_rule: form.is_recurring ? form.recurrence_rule : null,
      };

      if (form.message_type === "media") {
        if (mediaFiles.length === 0) {
          payload.message_type = "text";
          payload.media_type = null;
          payload.media_path = null;
        } else {
          const uploadedPaths = [];
          for (const item of mediaFiles) {
            if (item.file) {
              const path = await uploadFile(item.file);
              uploadedPaths.push({ path, media_type: item.media_type });
            } else {
              uploadedPaths.push({ path: item.media_path, media_type: item.media_type });
            }
          }

          // Main post media:
          payload.message_type = uploadedPaths[0].media_type;
          payload.media_type = uploadedPaths[0].media_type;
          payload.media_path = uploadedPaths[0].path;

          // Subsequent media files:
          if (uploadedPaths.length > 1) {
            payload.batch_messages = uploadedPaths.slice(1).map(item => ({
              content: "",
              media_type: item.media_type,
              media_path: item.path,
            }));
          }
        }
      } else if (form.message_type === "multi") {
        payload.message_type = "multi";
        const processedBatch = [];
        for (const msg of batchMessages) {
          if (!msg.content.trim()) continue;
          let batchMediaPath = msg.media_path || null;
          let actualMediaType = null;
          if (msg.media_type === "media") {
            if (msg.file) {
              batchMediaPath = await uploadFile(msg.file);
              actualMediaType = msg.file.type.startsWith("image/") ? "photo" : "document";
            } else if (msg.media_path) {
              if (msg.filePreview) {
                actualMediaType = "photo";
              } else {
                actualMediaType = msg.actual_media_type || "document";
              }
            }
          }
          processedBatch.push({
            content: plainTextToHtml(msg.content),
            media_type: actualMediaType,
            media_path: batchMediaPath,
          });
        }
        payload.batch_messages = processedBatch;
      } else {
        payload.message_type = "text";
        payload.media_type = null;
        payload.media_path = null;
      }

      if (editingId) {
        await apiFetch(`/api/tg/posts/${editingId}`, { method: "PATCH", body: JSON.stringify(payload) });
      } else {
        await apiFetch("/api/tg/posts/schedule", { method: "POST", body: JSON.stringify(payload) });
      }
      setShowForm(false);
      resetForm();
      fetchData();
    } catch (e) { setError(e.message); }
    finally { setSaving(false); }
  };

  const handleDelete = async (id) => {
    if (!window.confirm("Delete this scheduled item?")) return;
    try { await apiFetch(`/api/tg/posts/${id}`, { method: "DELETE" }); fetchData(); }
    catch (e) { alert(e.message); }
  };

  const handleSendNow = async (id) => {
    if (!window.confirm("Send now?")) return;
    try { await apiFetch(`/api/tg/posts/${id}/send-now`, { method: "POST" }); fetchData(); }
    catch (e) { alert(e.message); }
  };

  const addBatchMsg = () => setBatchMessages([...batchMessages, { content: "", media_type: "text", file: null, filePreview: null }]);
  const removeBatchMsg = (i) => setBatchMessages(batchMessages.filter((_, idx) => idx !== i));
  const updateBatchMsg = (i, field, val) => {
    const copy = [...batchMessages];
    copy[i] = { ...copy[i], [field]: val };
    setBatchMessages(copy);
  };
  const setBatchFile = (i, file) => {
    const copy = [...batchMessages];
    if (file) {
      const MAX_MB = 500;
      if (file.size > MAX_MB * 1024 * 1024) {
        setError(`File is too large (${(file.size / 1024 / 1024).toFixed(0)} MB). Maximum allowed is ${MAX_MB} MB.`);
        return;
      }
      // Use createObjectURL — instant and non-blocking
      const filePreview = file.type.startsWith("image/") ? URL.createObjectURL(file) : null;
      copy[i] = { ...copy[i], file, filePreview };
      setBatchMessages(copy);
    } else {
      copy[i] = { ...copy[i], file: null, filePreview: null, media_path: null, actual_media_type: null };
      setBatchMessages(copy);
    }
  };

  const doInsert = (open, close) => insertTag(contentRef, open, close, (val) => setForm({ ...form, content: val }));


  const previewHtml = plainTextToHtml(form.content);

  return (
    <div className="tg-section">
      <div className="tg-section-header">
        <h3 className="tg-section-title"><CalendarClock size={18} /> Scheduled Messages</h3>
        <button className="btn btn-primary" style={{ padding: "6px 14px", fontSize: "12px" }} onClick={() => {
          if (channels.length === 0) { onOpenBots?.(); return; }
          if (showForm) { resetForm(); setShowForm(false); } else { resetForm(); setShowForm(true); }
        }}>
          {showForm ? <><X size={13} /> Cancel</> : <><Plus size={13} /> New</>}
        </button>
      </div>

      {dataError && (
        <div className="auth-alert auth-alert-error" role="alert" style={{ marginBottom: "16px" }}>
          {dataError}
          <button type="button" className="btn btn-secondary" onClick={fetchData}>Retry</button>
        </div>
      )}

      {!dataError && channels.length === 0 && (
        <div className="glass-card schedule-setup-card">
          <div>
            <h4>Connect a destination first</h4>
            <p>Scheduling needs an active Telegram bot and at least one channel or group.</p>
          </div>
          <button type="button" className="btn btn-primary" onClick={onOpenBots}>Set Up Bot &amp; Channel</button>
        </div>
      )}

      {showForm && (
        <div className="glass-card" style={{ marginBottom: "16px", padding: "20px" }}>
          {error && <div className="auth-alert auth-alert-error" style={{ marginBottom: "12px" }}>{error}</div>}
          <form onSubmit={handleCreate}>
            <div className="tg-template-select">
              <label style={labelStyle}>Start from a template</label>
              <select defaultValue="" onChange={(e) => { const template = templates.find((item) => String(item.id) === e.target.value); if (template) setForm((current) => ({ ...current, content: template.content })); }}>
                <option value="">Choose a saved template…</option>
                {templates.map((template) => <option value={template.id} key={template.id}>{template.name}</option>)}
              </select>
            </div>

            {/* ── Row 1: Type + Channel + Time ── */}
            <div style={{ display: "flex", gap: "10px", marginBottom: "16px", flexWrap: "wrap" }}>
              {/* Message type tabs */}
              <div style={{ display: "flex", background: "var(--bg-tertiary)", borderRadius: "8px", padding: "3px", gap: "2px" }}>
                {MSG_TYPES.map((t) => {
                  const Icon = t.icon;
                  const active = form.message_type === t.value;
                  return (
                    <button key={t.value} type="button" onClick={() => setForm({ ...form, message_type: t.value })}
                      style={{
                        padding: "6px 12px", borderRadius: "6px", fontSize: "12px", fontWeight: 600,
                        border: "none",
                        background: active ? "var(--bg-primary)" : "transparent",
                        color: active ? "#6366F1" : "var(--text-muted)",
                        cursor: "pointer", display: "flex", alignItems: "center", gap: "4px", transition: "all 0.15s",
                        boxShadow: active ? "0 1px 3px rgba(0,0,0,0.08)" : "none",
                      }}>
                      <Icon size={12} /> {t.label}
                    </button>
                  );
                })}
              </div>
            </div>

            <div style={{ display: "flex", gap: "12px", marginBottom: "16px", flexWrap: "wrap" }}>
              <div style={{ flex: 1, minWidth: "160px" }}>
                <label style={labelStyle}>Channel</label>
                <select value={form.channel_id} onChange={(e) => setForm({ ...form, channel_id: e.target.value })} required
                  style={{ width: "100%", padding: "8px 12px", borderRadius: "8px", border: "1px solid var(--border-color)", background: "var(--bg-primary)", fontSize: "13px", color: "var(--text-primary)" }}>
                  <option value="">Select channel...</option>
                  {channels.map((ch) => <option key={ch.id} value={ch.id}>{ch.title}</option>)}
                </select>
              </div>
              <div style={{ flex: 1, minWidth: "180px" }}>
                <label style={labelStyle}>Schedule</label>
                <input type="datetime-local" value={form.scheduled_at} onChange={(e) => setForm({ ...form, scheduled_at: e.target.value })} required
                  style={{ width: "100%", padding: "8px 12px", borderRadius: "8px", border: "1px solid var(--border-color)", background: "var(--bg-primary)", fontSize: "13px", color: "var(--text-primary)" }} />
              </div>
            </div>

            <SophieAssistant onApply={(text) => setForm((prev) => ({ ...prev, content: text }))} />

            {/* ── Rich text editor ── */}
            <div style={{ marginBottom: "16px" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "6px" }}>
                <label style={{ ...labelStyle, marginBottom: 0 }}>
                  {form.message_type === "multi" ? "First Message" : "Message"}
                </label>
                <button type="button" onClick={() => setShowPreview(!showPreview)}
                  style={{ display: "flex", alignItems: "center", gap: "4px", background: "none", border: "none", fontSize: "11px", color: "var(--text-muted)", cursor: "pointer", fontWeight: 600 }}>
                  {showPreview ? <EyeOff size={12} /> : <Eye size={12} />} {showPreview ? "Edit" : "Preview"}
                </button>
              </div>
              {/* Toolbar */}
              <div style={{
                display: "flex", gap: "2px", padding: "4px 6px",
                borderRadius: "8px 8px 0 0", border: "1px solid var(--border-color)", borderBottom: "none",
                background: "var(--bg-tertiary)",
              }}>
                <ToolbarButton icon={Bold} title="Bold (Ctrl+B)" onClick={() => doInsert("<b>", "</b>")} />
                <ToolbarButton icon={Italic} title="Italic" onClick={() => doInsert("<i>", "</i>")} />
                <ToolbarButton icon={Underline} title="Underline" onClick={() => doInsert("<u>", "</u>")} />
                <ToolbarButton icon={Strikethrough} title="Strikethrough" onClick={() => doInsert("<s>", "</s>")} />
                <ToolbarButton icon={Code} title="Code" onClick={() => doInsert("<code>", "</code>")} />
                <ToolbarButton icon={Link2} title="Link" onClick={() => doInsert('<a href="URL">', "</a>")} />
                <div style={{ flex: 1 }} />
                <span style={{ fontSize: "10px", color: "var(--text-muted)", display: "flex", alignItems: "center", padding: "0 6px" }}>
                  Use **bold**, *italic*, or HTML tags
                </span>
              </div>
              {showPreview ? (
                <div style={{
                  minHeight: "100px", padding: "12px", borderRadius: "0 0 8px 8px",
                  border: "1px solid var(--border-color)", background: "var(--bg-primary)",
                  fontSize: "14px", lineHeight: "1.5", color: "var(--text-primary)",
                  whiteSpace: "pre-wrap",
                }} dangerouslySetInnerHTML={{ __html: previewHtml || '<span style="color: var(--text-muted)">Nothing to preview</span>' }} />
              ) : (
                <textarea ref={contentRef} value={form.content} onChange={(e) => setForm({ ...form, content: e.target.value })}
                  rows={4} placeholder="Type your message... Use **bold** or *italic* — we auto-convert to HTML"
                  required
                  style={{
                    width: "100%", resize: "vertical", borderRadius: "0 0 8px 8px",
                    border: "1px solid var(--border-color)", borderTop: "none", padding: "12px",
                    fontSize: "14px", lineHeight: "1.5", fontFamily: "inherit",
                    background: "var(--bg-primary)", color: "var(--text-primary)",
                  }} />
              )}
            </div>

            {/* ── File upload for unified media/file ── */}
            {form.message_type === "media" && (
              <div style={{ marginBottom: "16px" }}>
                <label style={labelStyle}>Attach Photos / Documents</label>
                <button type="button" className="quick-media-button" onClick={() => setShowLibrary(true)}>
                  <Library size={16} /><span><strong>Choose from Media Library</strong><small>No re-upload needed</small></span>
                </button>
                <FileUploadArea
                  accept="*"
                  label="Select photo or document to add"
                  file={null}
                  preview={null}
                  onFileSelect={handleFileSelect}
                  onClear={() => {}}
                />
                {mediaFiles.length > 0 && (
                  <div style={{ display: "flex", flexDirection: "column", gap: "8px", marginTop: "12px" }}>
                    {mediaFiles.map((item, idx) => (
                      <div key={item.id} className="file-upload-row" style={{
                        display: "flex", alignItems: "center", gap: "12px", padding: "10px 14px",
                        border: "1px solid var(--border-color)", borderRadius: "8px", background: "var(--bg-secondary)"
                      }}>
                        {item.preview ? (
                          <img src={item.preview} alt="" style={{ width: "36px", height: "36px", borderRadius: "6px", objectFit: "cover" }} />
                        ) : (
                          <div style={{ width: "36px", height: "36px", borderRadius: "6px", background: "rgba(14,165,233,0.08)", display: "flex", alignItems: "center", justifyContent: "center", color: "#0EA5E9" }}>
                            <FileText size={18} />
                          </div>
                        )}
                        <div style={{ flex: 1, minWidth: 0 }}>
                          <p style={{ fontWeight: 600, fontSize: "12px", marginBottom: "2px", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                            {item.name}
                          </p>
                          <p style={{ fontSize: "10px", color: "var(--text-muted)" }}>
                            {item.media_type === "photo" ? "Photo" : "Document"} {idx === 0 && <span style={{ color: "#6366F1", fontWeight: 700, marginLeft: "4px" }}>(Main Post File)</span>}
                          </p>
                        </div>
                        <button type="button" onClick={() => setMediaFiles(prev => prev.filter(f => f.id !== item.id))}
                          style={{ background: "rgba(239,68,68,0.08)", border: "none", borderRadius: "4px", padding: "4px", cursor: "pointer", color: "var(--danger)", display: "flex", alignItems: "center" }}>
                          <X size={14} />
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* ── Multi-message batch builder ── */}
            {form.message_type === "multi" && (
              <div style={{ marginBottom: "16px", padding: "16px", borderRadius: "10px", background: "var(--bg-tertiary)", border: "1px solid var(--border-color)" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "12px" }}>
                  <label style={{ ...labelStyle, marginBottom: 0 }}>Additional Messages</label>
                  <button type="button" onClick={addBatchMsg} className="btn btn-secondary" style={{ padding: "4px 10px", fontSize: "11px" }}>
                    <Plus size={12} /> Add
                  </button>
                </div>
                {batchMessages.map((msg, i) => (
                  <div key={i} style={{ padding: "12px", background: "var(--bg-primary)", borderRadius: "8px", marginBottom: "8px", border: "1px solid var(--border-color)" }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" }}>
                      <span style={{ fontSize: "11px", fontWeight: 700, color: "var(--text-muted)" }}>Message {i + 2}</span>
                      <div style={{ display: "flex", gap: "6px", alignItems: "center" }}>
                        <select value={msg.media_type} onChange={(e) => updateBatchMsg(i, "media_type", e.target.value)}
                          style={{ fontSize: "11px", padding: "3px 8px", borderRadius: "6px", border: "1px solid var(--border-color)", background: "var(--bg-tertiary)" }}>
                          <option value="text">Text</option>
                          <option value="media">Media / File</option>
                        </select>
                        {batchMessages.length > 1 && (
                          <button type="button" onClick={() => removeBatchMsg(i)} style={{
                            background: "rgba(239,68,68,0.08)", border: "none", borderRadius: "4px",
                            padding: "3px 6px", cursor: "pointer", color: "var(--danger)",
                          }}><X size={12} /></button>
                        )}
                      </div>
                    </div>
                    <textarea value={msg.content} onChange={(e) => updateBatchMsg(i, "content", e.target.value)}
                      rows={2} placeholder={`Message content...`}
                      style={{ width: "100%", fontSize: "13px", resize: "vertical", borderRadius: "6px", border: "1px solid var(--border-color)", padding: "8px", fontFamily: "inherit" }} />
                    {msg.media_type !== "text" && (
                      <div style={{ marginTop: "8px" }}>
                        <FileUploadArea
                          accept="*"
                          label="Select a photo or document to send"
                          file={msg.file || (msg.media_path ? { name: displayMediaName(msg.media_path) } : null)}
                          preview={msg.filePreview}
                          onFileSelect={(f) => setBatchFile(i, f)}
                          onClear={() => { 
                            updateBatchMsg(i, "file", null); 
                            updateBatchMsg(i, "filePreview", null); 
                            updateBatchMsg(i, "media_path", null);
                            updateBatchMsg(i, "actual_media_type", null);
                          }}
                        />
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}

            {/* ── Recurring ── */}
            <div style={{ display: "flex", gap: "12px", marginBottom: "16px", alignItems: "center", flexWrap: "wrap" }}>
              <label style={{ fontSize: "13px", fontWeight: 600, display: "flex", alignItems: "center", gap: "6px", cursor: "pointer", color: "var(--text-secondary)" }}>
                <input type="checkbox" checked={form.is_recurring} onChange={(e) => setForm({ ...form, is_recurring: e.target.checked })} />
                <Repeat size={14} /> Recurring
              </label>
              {form.is_recurring && (
                <select value={form.recurrence_rule} onChange={(e) => setForm({ ...form, recurrence_rule: e.target.value })}
                  style={{ fontSize: "13px", minWidth: "120px", padding: "6px 10px", borderRadius: "6px", border: "1px solid var(--border-color)" }} required>
                  <option value="">Select...</option>
                  <option value="hourly">Every Hour</option>
                  <option value="daily">Every Day</option>
                  <option value="weekly">Every Week</option>
                  <option value="monthly">Every Month</option>
                </select>
              )}
            </div>

            {/* ── Submit ── */}
            <button type="submit" className="btn btn-primary" disabled={saving} style={{ padding: "10px 24px", fontSize: "13px", fontWeight: 700 }}>
              <Send size={14} /> {saving ? (editingId ? "Saving..." : "Uploading & Scheduling...") : (editingId ? "Update Message" : "Schedule Message")}
            </button>
          </form>
        </div>
      )}
      <QuickMediaPicker open={showLibrary} onClose={() => setShowLibrary(false)} onSelect={useLibraryMedia} />

      {posts.length > 0 && (
        <div style={{ display: "flex", alignItems: "center", gap: "12px", background: "rgba(255,255,255,0.02)", border: "1px solid var(--border-color)", padding: "10px 16px", borderRadius: "10px", marginBottom: "16px" }}>
          <label style={{ display: "flex", alignItems: "center", gap: "8px", fontSize: "13px", fontWeight: "600", cursor: "pointer", color: "var(--text-secondary)" }}>
            <input 
              type="checkbox" 
              checked={selectedIds.length === posts.length && posts.length > 0} 
              onChange={selectAll}
              style={{ width: "16px", height: "16px", accentColor: "#6366F1", cursor: "pointer" }}
            />
            Select All
          </label>
          <span style={{ fontSize: "12px", color: "var(--text-muted)" }}>
            ({selectedIds.length} selected)
          </span>
          {selectedIds.length > 0 && (
            <button 
              type="button" 
              className="btn btn-danger" 
              style={{ padding: "6px 14px", fontSize: "12px", marginLeft: "auto", display: "flex", gap: "6px", alignItems: "center" }}
              onClick={handleBulkDelete}
            >
              <Trash2 size={13} /> Delete Selected
            </button>
          )}
        </div>
      )}

      {/* ── Post list ── */}
      {posts.length === 0 ? (
        <p style={{ color: "var(--text-muted)", textAlign: "center", padding: "24px", fontSize: "14px" }}>
          No scheduled messages yet.
        </p>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
          {posts.map((post) => {
            let typeInfo = MSG_TYPES.find(t => t.value === (post.message_type || "text"));
            if (!typeInfo) {
              if (post.message_type === "photo" || post.message_type === "document") {
                typeInfo = { 
                  value: "media", 
                  label: post.message_type === "photo" ? "Photo" : "Document", 
                  icon: post.message_type === "photo" ? Image : FileText 
                };
              } else {
                typeInfo = MSG_TYPES[0];
              }
            }
            const TypeIcon = typeInfo.icon;
            return (
              <div key={post.id} className="glass-card" style={{ padding: "14px 18px", display: "flex", gap: "14px", alignItems: "flex-start" }}>
                <input 
                  type="checkbox" 
                  checked={selectedIds.includes(post.id)}
                  onChange={() => toggleSelect(post.id)}
                  style={{ width: "16px", height: "16px", marginTop: "12px", cursor: "pointer", accentColor: "#6366F1" }}
                />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: "8px", flexWrap: "wrap" }}>
                      <span style={{ fontSize: "11px", fontWeight: 700, color: "#0EA5E9", background: "rgba(14, 165, 233, 0.08)", padding: "2px 10px", borderRadius: "12px" }}>
                        {post.channel_title}
                      </span>
                      <span style={{ fontSize: "11px", fontWeight: 600, color: "var(--text-muted)", background: "var(--bg-tertiary)", padding: "2px 8px", borderRadius: "10px", display: "flex", alignItems: "center", gap: "3px" }}>
                        <TypeIcon size={10} /> {typeInfo.label}
                      </span>
                      {post.batch_messages && (
                        <span style={{ fontSize: "11px", fontWeight: 600, color: "#8B5CF6", background: "rgba(139, 92, 246, 0.08)", padding: "2px 8px", borderRadius: "10px" }}>
                          +{post.batch_messages.length} msgs
                        </span>
                      )}
                    </div>
                    <span style={{ fontSize: "11px", fontWeight: 700, color: STATUS_COLORS[post.status], display: "flex", alignItems: "center", gap: "4px", textTransform: "uppercase" }}>
                      {post.status === "sent" && <CheckCircle size={12} />}
                      {post.status === "failed" && <XCircle size={12} />}
                      {post.status === "pending" && <Clock size={12} />}
                      {post.status === "processing" && <RefreshCw size={12} className="animate-spin" />}
                      {post.status}
                    </span>
                  </div>
                  <p style={{ fontSize: "14px", color: "var(--text-secondary)", marginBottom: "8px", whiteSpace: "pre-wrap", maxHeight: "80px", overflow: "hidden" }}>
                    {post.content}
                  </p>
                  <div style={{ display: "flex", alignItems: "center", gap: "12px", flexWrap: "wrap", fontSize: "12px", color: "var(--text-muted)" }}>
                    <span style={{ display: "flex", alignItems: "center", gap: "4px" }}>
                      <CalendarClock size={11} /> {new Date(post.scheduled_at.endsWith("Z") ? post.scheduled_at : post.scheduled_at + "Z").toLocaleString()}
                    </span>
                    {post.is_recurring && (
                      <span style={{ display: "flex", alignItems: "center", gap: "4px", color: "var(--warning)" }}>
                        <Repeat size={11} /> {post.recurrence_rule}
                      </span>
                    )}
                    <div style={{ marginLeft: "auto", display: "flex", gap: "6px" }}>
                      {post.status === "pending" && (
                        <>
                          <button className="btn btn-secondary" style={{ padding: "4px 10px", fontSize: "11px" }} onClick={() => handleEdit(post)}>
                            <Edit2 size={11} /> Edit
                          </button>
                          <button className="btn btn-primary" style={{ padding: "4px 10px", fontSize: "11px" }} onClick={() => handleSendNow(post.id)}>
                            <Send size={11} /> Send Now
                          </button>
                        </>
                      )}
                      {post.status === "failed" && (
                        <button className="btn btn-primary" style={{ padding: "4px 10px", fontSize: "11px" }} onClick={() => handleSendNow(post.id)}>
                          <RefreshCw size={11} /> Retry
                        </button>
                      )}
                      <button className="btn btn-danger" style={{ padding: "4px 10px", fontSize: "11px" }} onClick={() => handleDelete(post.id)}>
                        <Trash2 size={11} />
                      </button>
                    </div>
                  </div>
                  {post.error_message && (
                    <p style={{ marginTop: "6px", fontSize: "12px", color: "var(--danger)", padding: "4px 8px", background: "rgba(239,68,68,0.06)", borderRadius: "6px" }}>
                      {post.error_message}
                    </p>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
