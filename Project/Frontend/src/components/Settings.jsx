import React, { useState, useEffect } from "react";
import { apiFetch } from "../api";
import { Save, AlertCircle, Shield, Trash2, Plus, Key, CheckCircle, Link2, Unplug, Bot, Lock, Building2, User } from "lucide-react";


export default function Settings() {
  // Base settings
  const [dailyLimit, setDailyLimit] = useState(30);
  const [minDelay, setMinDelay] = useState(45);
  const [maxDelay, setMaxDelay] = useState(120);
  const [workingHoursStart, setWorkingHoursStart] = useState("08:00");
  const [workingHoursEnd, setWorkingHoursEnd] = useState("22:00");
  const [tunnelUrl] = useState(import.meta.env.VITE_API_URL || "http://localhost:8000");
  
  // Compliance Settings
  const [apiMode, setApiMode] = useState("sandbox"); // sandbox or official
  const [optOutKeywords, setOptOutKeywords] = useState("stop, unsubscribe, optout, stopdm");
  const consentEnforce = true;
  const [metaInstagramUserId, setMetaInstagramUserId] = useState("");
  const [metaAccessToken, setMetaAccessToken] = useState("");
  const [metaConnection, setMetaConnection] = useState(null);
  const [metaPlatformConfigured, setMetaPlatformConfigured] = useState(false);
  const [showMetaForm, setShowMetaForm] = useState(true);
  const [metaLoading, setMetaLoading] = useState(false);
  const [saveNotice, setSaveNotice] = useState(null);
  const [runtimeStatus, setRuntimeStatus] = useState(null);

  // Blocklist states
  const [blocklist, setBlocklist] = useState([]);
  const [newBlockedUser, setNewBlockedUser] = useState("");
  const [loading, setLoading] = useState(false);
  const [blocklistLoading, setBlocklistLoading] = useState(false);

  const fetchSettings = async () => {
    try {
      const data = await apiFetch("/api/settings");
      if (data.daily_limit) setDailyLimit(parseInt(data.daily_limit));
      if (data.min_delay) setMinDelay(parseInt(data.min_delay));
      if (data.max_delay) setMaxDelay(parseInt(data.max_delay));
      if (data.working_hours_start) setWorkingHoursStart(data.working_hours_start);
      if (data.working_hours_end) setWorkingHoursEnd(data.working_hours_end);
      
      if (data.api_mode) setApiMode(data.api_mode);
      if (data.opt_out_keywords) setOptOutKeywords(data.opt_out_keywords);
      const connected = Boolean(data.meta_connection_configured);
      setMetaConnection(connected ? {
        connected,
        active: Boolean(data.meta_connection_active),
        status: data.meta_connection_status,
        instagram_user_id: data.meta_instagram_user_id,
        instagram_username: data.meta_instagram_username,
        access_token_masked: data.meta_access_token_masked,
      } : null);
      setMetaInstagramUserId(data.meta_instagram_user_id || "");
      setMetaPlatformConfigured(Boolean(data.meta_platform_configured));
      setShowMetaForm(!connected);
    } catch (e) {
      console.error("Failed to load settings:", e);
    }
  };

  const fetchBlocklist = async () => {
    try {
      const data = await apiFetch("/api/optouts");
      setBlocklist(data);
    } catch (e) {
      console.error("Failed to load blocklist:", e);
    }
  };

  const fetchRuntimeStatus = async () => {
    try {
      setRuntimeStatus(await apiFetch("/api/status"));
    } catch (e) {
      console.error("Failed to load automation status:", e);
    }
  };

  useEffect(() => {
    fetchSettings();
    fetchBlocklist();
    fetchRuntimeStatus();
  }, []);

  const handleSaveSettings = async (e) => {
    e.preventDefault();
    setSaveNotice(null);
    if (maxDelay < minDelay) {
      setSaveNotice({ type: "error", text: "Max delay must be greater than or equal to min delay." });
      return;
    }
    setLoading(true);
    try {
      // Save backend settings
      await apiFetch("/api/settings", {
        method: "POST",
        body: JSON.stringify({
          daily_limit: dailyLimit,
          min_delay: minDelay,
          max_delay: maxDelay,
          working_hours_start: workingHoursStart,
          working_hours_end: workingHoursEnd,
          api_mode: apiMode,
          opt_out_keywords: optOutKeywords,
          consent_enforce: consentEnforce
        }),
      });

      // Tunnel URL is configured via .env — no local update needed
      
      setSaveNotice({
        type: "success",
        text: runtimeStatus?.system_running && runtimeStatus?.user_automation_active
          ? "Configuration saved and active."
          : "Configuration saved. It will apply when automation is started.",
      });
      await fetchSettings();
      await fetchRuntimeStatus();
    } catch (e) {
      setSaveNotice({ type: "error", text: e.message || "Failed to save settings." });
    } finally {
      setLoading(false);
    }
  };

  const handleConnectMeta = async (e) => {
    e.preventDefault();
    setSaveNotice(null);
    setMetaLoading(true);
    try {
      const connection = await apiFetch("/api/meta/connection", {
        method: "POST",
        body: JSON.stringify({
          instagram_user_id: metaInstagramUserId.trim(),
          access_token: metaAccessToken.trim(),
        }),
      });
      setMetaConnection(connection);
      setMetaInstagramUserId(connection.instagram_user_id || "");
      setMetaAccessToken("");
      setShowMetaForm(false);
      setSaveNotice({ type: "success", text: `Meta account @${connection.instagram_username || connection.instagram_user_id} connected securely.` });
      await fetchSettings();
    } catch (e) {
      setSaveNotice({ type: "error", text: e.message || "Could not connect the Meta account." });
    } finally {
      setMetaLoading(false);
    }
  };

  const handleDisconnectMeta = async () => {
    if (!confirm("Disconnect this Meta account and permanently remove its stored access token?")) return;
    setMetaLoading(true);
    setSaveNotice(null);
    try {
      await apiFetch("/api/meta/connection", { method: "DELETE" });
      setMetaConnection(null);
      setMetaInstagramUserId("");
      setMetaAccessToken("");
      setApiMode("sandbox");
      setShowMetaForm(true);
      setSaveNotice({ type: "success", text: "Meta account disconnected and its token was removed." });
      await fetchSettings();
    } catch (e) {
      setSaveNotice({ type: "error", text: e.message || "Could not disconnect the Meta account." });
    } finally {
      setMetaLoading(false);
    }
  };

  const handleAddBlocklist = async (e) => {
    e.preventDefault();
    if (!newBlockedUser.trim()) return;
    setBlocklistLoading(true);
    try {
      await apiFetch("/api/optouts", {
        method: "POST",
        body: JSON.stringify({ username: newBlockedUser.trim() })
      });
      setNewBlockedUser("");
      fetchBlocklist();
    } catch (e) {
      alert(e.message || "Failed to block user.");
    } finally {
      setBlocklistLoading(false);
    }
  };

  const handleDeleteBlocklist = async (id) => {
    if (!confirm("Remove this username from blocklist? They will receive automated messages if triggered.")) return;
    try {
      await apiFetch(`/api/optouts/${id}`, { method: "DELETE" });
      fetchBlocklist();
    } catch (e) {
      alert(e.message || "Failed to remove user from blocklist.");
    }
  };

  // The Official Meta path only unlocks once an administrator has configured
  // META_APP_SECRET and the webhook verify token on the backend. Until then it
  // is a dead end, so it stays hidden rather than showing customers a blocked
  // flow. A workspace that is already connected keeps seeing it either way, so
  // an unset platform variable can never strand an existing connection.
  const showMetaFlow = metaPlatformConfigured || Boolean(metaConnection?.connected);

  return (
    <div className="content-grid cols-2-wide">
      {/* Column 1: Settings Form */}
      <div className="glass-card" style={{ display: "flex", flexDirection: "column", gap: "24px" }}>
        <div>
          <h3 style={{ fontSize: "18px", fontWeight: "700", display: "flex", gap: "8px", alignItems: "center" }}>
            <Shield size={20} style={{ color: "var(--accent)" }} /> Lyvora Configurations
          </h3>
          <p style={{ color: "var(--text-muted)", fontSize: "12px", marginTop: "4px" }}>
            Configure delivery rules, security compliance, and messaging adapters.
          </p>
          <div className={`settings-runtime-status ${runtimeStatus?.system_running && runtimeStatus?.user_automation_active ? "running" : "paused"}`}>
            <span />
            {runtimeStatus?.system_running && runtimeStatus?.user_automation_active
              ? "Automation running — configuration is active"
              : "Automation paused — configuration is saved but not executing"}
          </div>
        </div>

        <form onSubmit={handleSaveSettings} style={{ display: "flex", flexDirection: "column", gap: "20px" }}>
          
          <section className="integration-panel" aria-labelledby="messaging-engine-title">
            <div className="integration-panel-heading">
              <div>
                <span className="section-eyebrow">Delivery channel</span>
                <h4 id="messaging-engine-title">Messaging engine</h4>
                <p>Choose how this workspace sends Instagram messages.</p>
              </div>
              <span className={`engine-current-badge ${apiMode === "official" ? "official" : "sandbox"}`}>
                {apiMode === "official" ? "Official active" : "Sandbox active"}
              </span>
            </div>

            <div className="engine-options" role="radiogroup" aria-label="Messaging engine">
              <label className={`engine-option ${apiMode === "sandbox" ? "selected" : ""}`}>
                <input
                  type="radio"
                  name="apiMode"
                  value="sandbox"
                  checked={apiMode === "sandbox"}
                  onChange={() => setApiMode("sandbox")}
                />
                <span className="engine-option-icon"><Bot size={18} /></span>
                <span className="engine-option-copy">
                  <span className="engine-option-title">Playwright Sandbox <small>Testing</small></span>
                  <span>Browser-based automation for internal testing and development.</span>
                </span>
              </label>

              {showMetaFlow && (
                <label className={`engine-option ${apiMode === "official" ? "selected" : ""} ${!metaConnection?.connected ? "disabled" : ""}`}>
                  <input
                    type="radio"
                    name="apiMode"
                    value="official"
                    checked={apiMode === "official"}
                    onChange={() => setApiMode("official")}
                    disabled={!metaConnection?.connected}
                  />
                  <span className="engine-option-icon meta"><Shield size={18} /></span>
                  <span className="engine-option-copy">
                    <span className="engine-option-title">Official Meta API <small>Production</small></span>
                    <span>Meta Graph API and webhooks for approved Professional accounts.</span>
                  </span>
                </label>
              )}
            </div>

            {showMetaFlow && (
              <div className={`platform-readiness ${metaPlatformConfigured ? "ready" : "pending"}`}>
                <span className="platform-readiness-icon"><Building2 size={17} /></span>
                <span>
                  <strong>Lyvora Meta platform</strong>
                  <small>{metaPlatformConfigured ? "Configured once by Lyvora and ready for customer connections." : "Administrator setup is pending. Customers never enter the Lyvora App Secret."}</small>
                </span>
                <b>{metaPlatformConfigured ? "Ready" : "Admin setup"}</b>
              </div>
            )}
          </section>

          {showMetaFlow && (
          <div className="meta-connection-card">
            <div className="meta-connection-heading">
              <span className="meta-heading-icon"><Key size={19} /></span>
              <div className="meta-heading-copy">
                <span className="section-eyebrow">Workspace account</span>
                <h4>Connect Instagram Professional</h4>
                <p>Connect one account securely to enable Official Meta automation.</p>
              </div>
              <span className={`meta-connected-badge ${metaConnection?.connected ? "connected" : "not-connected"}`}>
                {metaConnection?.connected ? <CheckCircle size={14} /> : <AlertCircle size={14} />}
                {metaConnection?.connected ? "Connected" : "Not connected"}
              </span>
            </div>

            <div className="meta-setup-path" aria-label="Official Meta setup progress">
              <div className={metaPlatformConfigured ? "complete" : "current"}>
                <span>{metaPlatformConfigured ? <CheckCircle size={14} /> : "1"}</span>
                <p><strong>Platform</strong><small>Managed by Lyvora</small></p>
              </div>
              <i />
              <div className={metaConnection?.connected ? "complete" : metaPlatformConfigured ? "current" : ""}>
                <span>{metaConnection?.connected ? <CheckCircle size={14} /> : "2"}</span>
                <p><strong>Instagram</strong><small>Connect workspace</small></p>
              </div>
              <i />
              <div className={apiMode === "official" ? "complete" : metaConnection?.connected && metaPlatformConfigured ? "current" : ""}>
                <span>{apiMode === "official" ? <CheckCircle size={14} /> : "3"}</span>
                <p><strong>Activate</strong><small>Enable Official mode</small></p>
              </div>
            </div>

            {metaConnection?.connected && !showMetaForm ? (
              <div className="meta-connection-summary">
                <span className="meta-account-avatar"><User size={19} /></span>
                <div className="meta-account-identity">
                  <strong>@{metaConnection.instagram_username || "Instagram account"}</strong>
                  <span>Professional account · ID {metaConnection.instagram_user_id}</span>
                  <span className="meta-token-state"><Lock size={12} /> Token {metaConnection.access_token_masked || "encrypted"}</span>
                </div>
                <div className="meta-connection-actions">
                  <button type="button" className="btn btn-secondary" onClick={() => setShowMetaForm(true)} disabled={metaLoading}>
                    <Link2 size={14} /> Replace
                  </button>
                  <button type="button" className="btn btn-danger" onClick={handleDisconnectMeta} disabled={metaLoading}>
                    <Unplug size={14} /> Disconnect
                  </button>
                </div>
              </div>
            ) : (
              <div className="meta-connect-form">
                {!metaPlatformConfigured && (
                  <div className="meta-admin-notice" role="status">
                    <Building2 size={17} />
                    <span><strong>Waiting for Lyvora platform setup</strong><small>You may prepare your workspace connection now. Official mode unlocks after the administrator completes the platform setup.</small></span>
                  </div>
                )}
                <div className="meta-credential-grid">
                  <div>
                  <label className="form-label">Instagram Professional Account ID</label>
                  <input
                    type="text"
                    inputMode="numeric"
                    className="form-input"
                    placeholder="e.g. 17841400000000000"
                    value={metaInstagramUserId}
                    onChange={(e) => setMetaInstagramUserId(e.target.value.replace(/\D/g, ""))}
                    autoComplete="off"
                  />
                    <small className="field-help">Numeric ID for the Professional account.</small>
                  </div>
                  <div>
                    <label className="form-label">Instagram User Access Token</label>
                    <input
                      type="password"
                      className="form-input"
                      placeholder={metaConnection?.connected ? "Paste a replacement token" : "Paste the token generated by Meta"}
                      value={metaAccessToken}
                      onChange={(e) => setMetaAccessToken(e.target.value)}
                      autoComplete="new-password"
                    />
                    <small className="field-help">Use a token with the required Meta permissions.</small>
                  </div>
                </div>
                <div className="meta-security-copy">
                  <Lock size={16} />
                  <span><strong>Encrypted and workspace-isolated</strong><small>Lyvora validates this token with Meta, encrypts it before storage, and never returns the full value to your browser.</small></span>
                </div>
                <div className="meta-connection-actions">
                  {metaConnection?.connected && (
                    <button type="button" className="btn btn-secondary" onClick={() => { setShowMetaForm(false); setMetaAccessToken(""); }} disabled={metaLoading}>Cancel</button>
                  )}
                  <button
                    type="button"
                    className="btn btn-primary"
                    onClick={handleConnectMeta}
                    disabled={metaLoading || !metaInstagramUserId || metaAccessToken.trim().length < 20}
                  >
                    <Link2 size={14} /> {metaLoading ? "Validating..." : "Validate & Connect"}
                  </button>
                </div>
              </div>
            )}

            <details className="meta-technical-details">
              <summary>Technical connection details</summary>
              <span className="meta-webhook-copy">
                Webhook callback: <code>{tunnelUrl ? `${tunnelUrl}/api/webhooks/instagram` : "Not configured"}</code>
              </span>
            </details>
          </div>
          )}

          {/* Base limits & delays */}
          <div className="settings-2col-grid" style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16px" }}>
            <div className="form-group">
              <label className="form-label">Daily Message Limit</label>
              <input 
                type="number" 
                className="form-input" 
                min="1" 
                max="100" 
                value={dailyLimit}
                onChange={(e) => setDailyLimit(parseInt(e.target.value))}
                required
              />
            </div>
            <div className="form-group">
              <label className="form-label">Min Delay (Seconds)</label>
              <input 
                type="number" 
                className="form-input" 
                min="10" 
                value={minDelay}
                onChange={(e) => setMinDelay(parseInt(e.target.value))}
                disabled={apiMode === "official"}
                required
              />
            </div>
          </div>

          <div className="settings-2col-grid" style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16px" }}>
            <div className="form-group">
              <label className="form-label">Max Delay (Seconds)</label>
              <input 
                type="number" 
                className="form-input" 
                min={minDelay}
                value={maxDelay}
                onChange={(e) => setMaxDelay(parseInt(e.target.value))}
                disabled={apiMode === "official"}
                required
              />
            </div>
            <div className="form-group" style={{ display: "flex", flexDirection: "column" }}>
              <label className="form-label">Enforce Consent Keyword</label>
              <div style={{ display: "flex", alignItems: "center", gap: "10px", marginTop: "10px" }}>
                <input
                  type="checkbox" 
                  checked={consentEnforce}
                  readOnly
                  disabled
                  style={{ width: "16px", height: "16px" }}
                />
                <span style={{ fontSize: "12px", color: "var(--text-secondary)" }}>Required: only DM on exact comment keyword match</span>
              </div>
            </div>
          </div>

          <div className="settings-2col-grid" style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16px" }}>
            <div className="form-group">
              <label className="form-label">Start Work Hour</label>
              <input 
                type="time"
                className="form-input" 
                placeholder="08:00"
                value={workingHoursStart}
                onChange={(e) => setWorkingHoursStart(e.target.value)}
                disabled={apiMode === "official"}
                required
              />
            </div>
            <div className="form-group">
              <label className="form-label">End Work Hour</label>
              <input 
                type="time"
                className="form-input" 
                placeholder="22:00"
                value={workingHoursEnd}
                onChange={(e) => setWorkingHoursEnd(e.target.value)}
                disabled={apiMode === "official"}
                required
              />
            </div>
          </div>

          {/* Compliance Opt-Out Keywords */}
          <div className="form-group">
            <label className="form-label">Auto Opt-Out / Unsubscribe Keywords</label>
            <input 
              type="text" 
              className="form-input" 
              placeholder="e.g. stop, unsubscribe, block, optout" 
              value={optOutKeywords}
              onChange={(e) => setOptOutKeywords(e.target.value)}
              required
            />
            <span style={{ fontSize: "11px", color: "var(--text-muted)", marginTop: "4px" }}>
              Comma-separated list. Exact matching comments are automatically added to the blocklist.
            </span>
          </div>
          {saveNotice && (
            <div className={`auth-alert auth-alert-${saveNotice.type}`} role="status">
              {saveNotice.type === "success" ? <CheckCircle size={16} /> : <AlertCircle size={16} />}
              {saveNotice.text}
            </div>
          )}

          <button 
            type="submit" 
            className="btn btn-primary" 
            style={{ marginTop: "8px" }}
            disabled={loading}
          >
            <Save size={16} /> Save Configuration
          </button>
        </form>
      </div>

      {/* Column 2: Blocklist & Compliance Notices */}
      <div style={{ display: "flex", flexDirection: "column", gap: "24px" }}>
        
        {/* Blocklist Manager */}
        <div className="glass-card">
          <h3 style={{ fontSize: "16px", fontWeight: "700", marginBottom: "8px" }}>Manage Opt-Out Blocklist</h3>
          <p style={{ color: "var(--text-muted)", fontSize: "12px", marginBottom: "16px" }}>
            Usernames listed here will be skipped automatically from all outbound automated DMs.
          </p>

          <form onSubmit={handleAddBlocklist} style={{ display: "flex", gap: "8px", marginBottom: "20px" }}>
            <input 
              type="text" 
              className="form-input" 
              placeholder="Instagram Username..." 
              value={newBlockedUser}
              onChange={(e) => setNewBlockedUser(e.target.value)}
              disabled={blocklistLoading}
              required
            />
            <button 
              type="submit" 
              className="btn btn-secondary" 
              style={{ display: "flex", gap: "6px", alignItems: "center" }}
              disabled={blocklistLoading}
            >
              <Plus size={14} /> Add Block
            </button>
          </form>

          {blocklist.length === 0 ? (
            <div style={{ padding: "30px", textAlign: "center", color: "var(--text-secondary)", fontSize: "13px", border: "1px dashed var(--border-color)", borderRadius: "8px" }}>
              No users opted-out currently.
            </div>
          ) : (
            <div className="table-container" style={{ maxHeight: "250px", overflowY: "auto", border: "1px solid var(--border-color)", borderRadius: "8px" }}>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "13px" }}>
                <thead>
                  <tr style={{ background: "rgba(255,255,255,0.03)", textAlign: "left" }}>
                    <th style={{ padding: "10px 16px", fontWeight: "600", color: "var(--text-secondary)" }}>Username</th>
                    <th style={{ padding: "10px 16px", fontWeight: "600", color: "var(--text-secondary)" }}>Blocked Date</th>
                    <th style={{ padding: "10px 16px", textAlign: "right" }}></th>
                  </tr>
                </thead>
                <tbody>
                  {blocklist.map((u) => (
                    <tr key={u.id} style={{ borderTop: "1px solid var(--border-color)" }}>
                      <td style={{ padding: "10px 16px", fontWeight: "500", color: "var(--text-primary)" }}>@{u.username}</td>
                      <td style={{ padding: "10px 16px", color: "var(--text-muted)" }}>
                        {new Date(u.created_at).toLocaleDateString()}
                      </td>
                      <td style={{ padding: "10px 16px", textAlign: "right" }}>
                        <button 
                          className="btn btn-danger" 
                          style={{ padding: "6px 8px" }}
                          onClick={() => handleDeleteBlocklist(u.id)}
                        >
                          <Trash2 size={12} />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Safety Notice Panel */}
        <div className="glass-card" style={{ height: "fit-content" }}>
          <h4 style={{ fontSize: "15px", fontWeight: "600", color: "var(--text-primary)", display: "flex", gap: "8px", alignItems: "center" }}>
            <AlertCircle size={18} style={{ color: "#64748B" }} /> GDPR & Compliance Recommendations
          </h4>
          <div style={{ color: "var(--text-secondary)", fontSize: "13px", marginTop: "12px", display: "flex", flexDirection: "column", gap: "14px", lineHeight: "1.6" }}>
            <p>
              To maintain legal compliance under digital privacy frameworks:
            </p>
            <ul style={{ paddingLeft: "16px", display: "flex", flexDirection: "column", gap: "8px" }}>
              <li>
                • <strong>Consent Validation:</strong> Enable the <em>Enforce Consent Keyword</em> setting to ensure DMs are only triggered by explicit follower comments.
              </li>
              <li>
                • <strong>Opt-Out Transparency:</strong> Always include unsubscribe instructions inside your message templates (e.g. <em>"Reply STOP to unsubscribe"</em>).
              </li>
              <li>
                • <strong>Official API:</strong> For approved use cases, connect a Professional account and follow Meta's messaging permissions, limits, and response-window rules.
              </li>
            </ul>
            <div style={{ marginTop: "6px", display: "flex", gap: "8px", background: "rgba(16, 185, 129, 0.05)", border: "1px solid rgba(16, 185, 129, 0.2)", padding: "10px 14px", borderRadius: "6px", alignItems: "center" }}>
              <CheckCircle size={16} style={{ color: "var(--success)" }} />
              <span style={{ fontSize: "12px", color: "var(--success)", fontWeight: "500" }}>Exact-trigger and blocklist protection are configured.</span>
            </div>
          </div>
        </div>

      </div>
    </div>
  );
}
