import React, { useState, useEffect } from "react";
import { apiFetch } from "../api";
import { Send as SendIcon, Bot, Hash, FileText } from "lucide-react";
import TgBots from "./TgBots";
import TgSchedule from "./TgSchedule";
import TgModeration from "./TgModeration";
import TgTemplates from "./TgTemplates";

export default function TelegramPanel({ initialTab = "bots" }) {
  const [activeTab, setActiveTab] = useState(initialTab);
  const [channels, setChannels] = useState([]);

  const fetchChannels = async () => {
    try {
      const ch = await apiFetch("/api/tg/channels");
      setChannels(ch);
    } catch {}
  };

  useEffect(() => {
    fetchChannels();
  }, []);

  useEffect(() => {
    setActiveTab(initialTab);
  }, [initialTab]);

  const tabs = [
    { id: "bots", label: "Bots & Channels", icon: Bot },
    { id: "schedule", label: "Schedule", icon: SendIcon },
    { id: "templates", label: "Templates", icon: FileText },
    { id: "moderation", label: "Moderation", icon: Hash },
  ];

  return (
    <div className="telegram-workspace">
      <div className="glass-card tg-overview-card">
        <div className="tg-overview-icon">
          <SendIcon size={18} />
        </div>
        <div>
          <p>Telegram Automation</p>
          <span>
            {channels.length} channel(s) connected — service controlled by admin
          </span>
        </div>
      </div>

      <div className="tg-tab-bar">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            type="button"
            className={`tg-tab ${activeTab === tab.id ? "active" : ""}`}
            onClick={() => setActiveTab(tab.id)}
          >
            <tab.icon size={14} /> {tab.label}
          </button>
        ))}
      </div>

      {activeTab === "bots" && <TgBots />}
      {activeTab === "schedule" && <TgSchedule onOpenBots={() => setActiveTab("bots")} />}
      {activeTab === "templates" && <TgTemplates />}
      {activeTab === "moderation" && <TgModeration />}
    </div>
  );
}
