import React, { useState, useEffect } from "react";
import { apiFetch } from "../api";
import { Calendar, ChevronLeft, ChevronRight, Clock, Send, Loader2, Plus, AlertCircle } from "lucide-react";

const parseUtcDate = (value) => new Date(/(?:Z|[+-]\d{2}:?\d{2})$/.test(value) ? value : `${value}Z`);

export default function ContentCalendar({ onCreateSchedule }) {
  const [currentDate, setCurrentDate] = useState(new Date());
  const [scheduledPosts, setScheduledPosts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");
  const [selectedDay, setSelectedDay] = useState(null);

  const fetchScheduledPosts = async () => {
    setLoading(true);
    setLoadError("");
    try {
      const data = await apiFetch("/api/tg/posts");
      setScheduledPosts(data);
    } catch (e) {
      console.error("Failed to load scheduled posts:", e);
      setLoadError(e.message || "Could not load scheduled posts.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchScheduledPosts(); }, []);

  const year = currentDate.getFullYear();
  const month = currentDate.getMonth();
  const firstDay = new Date(year, month, 1).getDay();
  const daysInMonth = new Date(year, month + 1, 0).getDate();
  const today = new Date();

  const prevMonth = () => setCurrentDate(new Date(year, month - 1, 1));
  const nextMonth = () => setCurrentDate(new Date(year, month + 1, 1));

  const getPostsForDay = (day) => {
    return scheduledPosts.filter(p => {
      const d = parseUtcDate(p.scheduled_at);
      return d.getFullYear() === year && d.getMonth() === month && d.getDate() === day;
    });
  };

  const monthName = currentDate.toLocaleString("default", { month: "long", year: "numeric" });
  const dayNames = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
  const cells = [];
  for (let i = 0; i < firstDay; i++) cells.push(null);
  for (let d = 1; d <= daysInMonth; d++) cells.push(d);

  const selectedPosts = selectedDay ? getPostsForDay(selectedDay) : [];

  const statusColor = (status) => {
    switch (status) {
      case "sent": return "var(--success)";
      case "failed": return "var(--danger)";
      case "cancelled": return "var(--text-muted)";
      default: return "var(--info)";
    }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "20px" }}>
      {/* Calendar Header */}
      <div className="glass-card calendar-toolbar" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <button type="button" className="btn btn-secondary" onClick={prevMonth} aria-label="Previous month"><ChevronLeft size={16} /></button>
        <h3 style={{ fontSize: "18px", fontWeight: "700", display: "flex", alignItems: "center", gap: "8px" }}>
          <Calendar size={20} /> {monthName}
        </h3>
        <div className="calendar-toolbar-actions">
          <button type="button" className="btn btn-secondary" onClick={nextMonth} aria-label="Next month"><ChevronRight size={16} /></button>
          <button type="button" className="btn btn-primary" onClick={onCreateSchedule}><Plus size={15} /> New Schedule</button>
        </div>
      </div>

      {loadError ? (
        <div className="glass-card auth-alert auth-alert-error" role="alert">
          <AlertCircle size={18} />
          <span>{loadError}</span>
          <button type="button" className="btn btn-secondary" onClick={fetchScheduledPosts}>Retry</button>
        </div>
      ) : loading ? (
        <div className="glass-card" style={{ display: "flex", justifyContent: "center", padding: "60px" }}>
          <Loader2 size={32} className="animate-spin" style={{ color: "var(--accent)" }} />
        </div>
      ) : (
        <div className="calendar-layout" style={{ display: "flex", gap: "20px", flexWrap: "wrap" }}>
          {/* Calendar Grid */}
          <div className="glass-card calendar-grid-card" style={{ flex: "2", minWidth: "320px" }}>
            <div className="calendar-grid" style={{ display: "grid", gridTemplateColumns: "repeat(7, 1fr)", gap: "2px" }}>
              {dayNames.map(d => (
                <div key={d} className="calendar-weekday" style={{ textAlign: "center", padding: "8px", fontSize: "12px", fontWeight: "600", color: "var(--text-muted)" }}>
                  {d}
                </div>
              ))}
              {cells.map((day, i) => {
                if (!day) return <div key={`e-${i}`} />;
                const posts = getPostsForDay(day);
                const isToday = day === today.getDate() && month === today.getMonth() && year === today.getFullYear();
                const isSelected = day === selectedDay;
                return (
                  <div
                    key={day}
                    className="calendar-day"
                    onClick={() => setSelectedDay(day === selectedDay ? null : day)}
                    style={{
                      padding: "8px",
                      minHeight: "70px",
                      border: isSelected ? "2px solid var(--accent)" : "1px solid var(--border-color)",
                      borderRadius: "8px",
                      cursor: "pointer",
                      background: isToday ? "rgba(99, 102, 241, 0.08)" : isSelected ? "rgba(99, 102, 241, 0.04)" : "transparent",
                      transition: "all 0.15s",
                    }}
                  >
                    <div style={{ fontSize: "13px", fontWeight: isToday ? "700" : "500", color: isToday ? "var(--accent)" : "var(--text-primary)", marginBottom: "4px" }}>
                      {day}
                    </div>
                    {posts.slice(0, 3).map((p, j) => (
                      <div key={j} style={{ fontSize: "10px", padding: "2px 4px", borderRadius: "3px", background: statusColor(p.status), color: "#fff", marginBottom: "2px", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                        {parseUtcDate(p.scheduled_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                      </div>
                    ))}
                    {posts.length > 3 && (
                      <div style={{ fontSize: "10px", color: "var(--text-muted)" }}>+{posts.length - 3} more</div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>

          {/* Selected Day Detail */}
          <div className="glass-card calendar-detail-card" style={{ flex: "1", minWidth: "260px" }}>
            <h4 style={{ fontSize: "15px", fontWeight: "600", marginBottom: "16px" }}>
              {selectedDay ? `${monthName.split(" ")[0]} ${selectedDay}` : "Select a day"}
            </h4>
            {!selectedDay ? (
              <p style={{ color: "var(--text-muted)", fontSize: "13px" }}>Click a day to see scheduled posts</p>
            ) : selectedPosts.length === 0 ? (
              <p style={{ color: "var(--text-muted)", fontSize: "13px" }}>No posts scheduled for this day</p>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
                {selectedPosts.map(p => (
                  <div key={p.id} className="glass-card" style={{ padding: "12px", borderLeft: `3px solid ${statusColor(p.status)}` }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "6px" }}>
                      <span style={{ display: "flex", alignItems: "center", gap: "4px", fontSize: "12px", color: "var(--text-muted)" }}>
                        <Clock size={12} />
                        {parseUtcDate(p.scheduled_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                      </span>
                      <span className="badge" style={{ background: statusColor(p.status), color: "#fff", fontSize: "10px" }}>
                        {p.status}
                      </span>
                    </div>
                    <p style={{ fontSize: "13px", lineHeight: "1.4", wordBreak: "break-word" }}>
                      {(p.content || "").substring(0, 120)}{(p.content || "").length > 120 ? "..." : ""}
                    </p>
                    {p.channel_title && (
                      <p style={{ fontSize: "11px", color: "var(--text-muted)", marginTop: "4px" }}>
                        <Send size={10} /> {p.channel_title}
                      </p>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
