import React, { lazy, Suspense, useState, useEffect } from "react";
import AuthPage from "./components/AuthPage";
import LandingPage from "./components/LandingPage";
import LegalPrivacy from "./components/LegalPrivacy";
import TermsConditions from "./components/TermsConditions";
import LegalDisclaimer from "./components/LegalDisclaimer";
import ErrorBoundary from "./components/ErrorBoundary";
import {
  LayoutDashboard, UserCheck, Mail,
  Settings as SettingsIcon, MessageSquare, Menu, X,
  Shield, LogOut, ChevronDown, Send,
  Image, Bell, Calendar, ChevronRight, Wifi, WifiOff, LoaderCircle
} from "lucide-react";
import { getToken, getAuthUser, logout, apiFetch, getApiUrl, setApiUrl } from "./api";

const Dashboard = lazy(() => import("./components/Dashboard"));
const Accounts = lazy(() => import("./components/Accounts"));
const Messages = lazy(() => import("./components/Messages"));
const Settings = lazy(() => import("./components/Settings"));
const CommentTriggers = lazy(() => import("./components/CommentTriggers"));
const AdminPanel = lazy(() => import("./components/AdminPanel"));
const TelegramPanel = lazy(() => import("./components/TelegramPanel"));
const MediaLibrary = lazy(() => import("./components/MediaLibrary"));
const NotificationCenter = lazy(() => import("./components/NotificationCenter"));
const ContentCalendar = lazy(() => import("./components/ContentCalendar"));

export default function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [currentUser, setCurrentUser] = useState(null);
  const [activeTab, setActiveTab] = useState("dashboard");
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [connectionStatus, setConnectionStatus] = useState("checking");
  const [telegramInitialTab, setTelegramInitialTab] = useState("bots");
  const [userMenuOpen, setUserMenuOpen] = useState(false);
  const [showAuth, setShowAuth] = useState(false);
  const [legalPage, setLegalPage] = useState(null);

  // ── Check existing session on mount ──────────────────────────────────────────
  useEffect(() => {
    const token = getToken();
    const user = getAuthUser();
    if (token && user) {
      setIsAuthenticated(true);
      setCurrentUser(user);
      verifyConnection();
    }
  }, []);

  useEffect(() => {
    if (!sidebarOpen) return undefined;

    const previousOverflow = document.body.style.overflow;
    const closeOnEscape = (event) => {
      if (event.key === "Escape") setSidebarOpen(false);
    };

    document.body.style.overflow = "hidden";
    window.addEventListener("keydown", closeOnEscape);

    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener("keydown", closeOnEscape);
    };
  }, [sidebarOpen]);

  const verifyConnection = async () => {
    setConnectionStatus("checking");
    try {
      await apiFetch("/");
      setConnectionStatus("active");
    } catch {
      setConnectionStatus("error");
    }
  };

  const handleAuthSuccess = (data) => {
    setCurrentUser({ username: data.username, is_admin: data.is_admin });
    setIsAuthenticated(true);
    verifyConnection();
    setActiveTab("dashboard");
  };

  const handleLogout = () => {
    setUserMenuOpen(false);
    logout();         // clears localStorage + reloads
  };

  const handleNavClick = (tab) => {
    setActiveTab(tab);
    setSidebarOpen(false);
    setUserMenuOpen(false);
  };

  // ── Auth gate ────────────────────────────────────────────────────────────────
  if (!isAuthenticated) {
    if (legalPage === "privacy") return <LegalPrivacy onBack={() => setLegalPage(null)} />;
    if (legalPage === "terms") return <TermsConditions onBack={() => setLegalPage(null)} />;
    if (legalPage === "disclaimer") return <LegalDisclaimer onBack={() => setLegalPage(null)} />;
    if (showAuth) {
      return (
        <AuthPage
          onAuthSuccess={handleAuthSuccess}
          onBackToHome={() => setShowAuth(false)}
        />
      );
    }
    return <LandingPage onGetStarted={() => setShowAuth(true)} onNavigateLegal={setLegalPage} />;
  }

  // ── Nav items ────────────────────────────────────────────────────────────────
  const navSections = [
    {
      label: "Overview",
      items: [
        { id: "dashboard", label: "Dashboard", icon: LayoutDashboard },
        { id: "notifications", label: "Notifications", icon: Bell },
      ],
    },
    {
      label: "Instagram",
      items: [
        { id: "accounts", label: "Accounts", icon: UserCheck },
        { id: "messages", label: "DM Templates", icon: Mail },
        { id: "comment-triggers", label: "Comment Triggers", icon: MessageSquare },
      ],
    },
    {
      label: "Content",
      items: [
        { id: "media", label: "Media Library", icon: Image },
        { id: "calendar", label: "Content Calendar", icon: Calendar },
        { id: "telegram", label: "Telegram", icon: Send, isTelegram: true },
      ],
    },
    {
      label: "Workspace",
      items: [
        { id: "settings", label: "Settings", icon: SettingsIcon },
        ...(currentUser?.is_admin
          ? [{ id: "admin", label: "Admin Console", icon: Shield, isAdmin: true }]
          : []),
      ],
    },
  ];

  const renderActiveComponent = () => {
    switch (activeTab) {
      case "dashboard":        return <Dashboard />;
      case "accounts":         return <Accounts />;
      case "messages":         return <Messages />;
      case "comment-triggers": return <CommentTriggers />;
      case "media":            return <MediaLibrary />;
      case "calendar":         return <ContentCalendar onCreateSchedule={() => { setTelegramInitialTab("schedule"); handleNavClick("telegram"); }} />;
      case "notifications":    return <NotificationCenter />;
      case "telegram":         return <TelegramPanel initialTab={telegramInitialTab} />;
      case "settings":         return <Settings />;
      case "admin":            return currentUser?.is_admin ? <AdminPanel /> : <Dashboard />;
      default:                 return <Dashboard />;
    }
  };

  const pageTitle = () => {
    const map = {
      dashboard: "Dashboard",
      accounts: "Instagram Accounts",
      messages: "DM Templates",
      "comment-triggers": "Comment Triggers",
      media: "Media Library",
      calendar: "Content Calendar",
      notifications: "Notifications",
      telegram: "Telegram Automation",
      settings: "Settings",
      admin: "Admin Panel",
    };
    return map[activeTab] || activeTab;
  };

  const pageSubtitle = () => {
    const map = {
      dashboard: "Overview of your automation activity",
      accounts: "Manage connected Instagram accounts",
      messages: "Create and manage message templates",
      "comment-triggers": "Auto-DM users who comment on posts",
      media: "Upload and organize media assets",
      calendar: "View and create scheduled Telegram content",
      notifications: "Stay updated on platform activity",
      telegram: "Manage bots, schedule posts & moderate channels",
      settings: "Configure bot behavior and limits",
      admin: "System management & monitoring",
    };
    return map[activeTab] || "";
  };

  return (
    <div className="app-container">
      {/* SVG gradient helper (must stay for brand icon) */}
      <svg width="0" height="0" style={{ position: "absolute" }}>
        <defs>
          <linearGradient id="brand-grad" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#2563EB" />
            <stop offset="100%" stopColor="#60A5FA" />
          </linearGradient>
        </defs>
      </svg>

      {/* ── Mobile header ─────────────────────────────────────────────────────── */}
      <div className="mobile-header">
        <div className="mobile-brand">
          <span className="mobile-brand-mark"><Mail size={18} /></span>
          <span>Lyvora</span>
        </div>
        <button
          type="button"
          className="hamburger-btn"
          onClick={() => setSidebarOpen(!sidebarOpen)}
          aria-label={sidebarOpen ? "Close navigation" : "Open navigation"}
          aria-expanded={sidebarOpen}
          aria-controls="primary-sidebar"
        >
          {sidebarOpen ? <X size={24} /> : <Menu size={24} />}
        </button>
      </div>

      {/* ── Sidebar overlay (mobile) ───────────────────────────────────────────── */}
      <div
        className={`sidebar-overlay ${sidebarOpen ? "open" : ""}`}
        onClick={() => setSidebarOpen(false)}
        aria-hidden="true"
      />

      {/* ── Sidebar ───────────────────────────────────────────────────────────── */}
      <aside id="primary-sidebar" className={`sidebar ${sidebarOpen ? "open" : ""}`} aria-label="Primary navigation">
        <div className="brand brand-lockup">
          <div className="brand-mark"><Mail size={21} /></div>
          <div className="brand-copy"><span>Lyvora</span><small>Growth workspace</small></div>
        </div>

        <nav className="nav-menu">
          {navSections.map((section) => (
            <div className="nav-group" key={section.label}>
              <div className="nav-section-label">{section.label}</div>
              {section.items.map(({ id, label, icon: Icon, isAdmin, isTelegram }) => (
                <button
                  type="button"
                  id={`nav-${id}`}
                  key={id}
                  className={`nav-item ${activeTab === id ? "active" : ""} ${isAdmin ? "nav-item-admin" : ""} ${isTelegram ? "nav-item-telegram" : ""}`}
                  onClick={() => {
                    if (id === "telegram") setTelegramInitialTab("bots");
                    handleNavClick(id);
                  }}
                  aria-current={activeTab === id ? "page" : undefined}
                >
                  <Icon size={17} />
                  <span>{label}</span>
                  {isAdmin && <span className="nav-admin-badge">ADMIN</span>}
                </button>
              ))}
            </div>
          ))}
        </nav>

        {/* ── Sidebar footer ────────────────────────────────────────────────── */}
        <div className="sidebar-footer">
          {/* Connection dot */}
          {currentUser?.is_admin && (
            <div 
              className={`sidebar-connection ${connectionStatus}`}
              style={{ cursor: "pointer" }}
              onClick={() => {
                const currentUrl = getApiUrl();
                const newUrl = prompt("Configure Backend API Server URL (e.g. ngrok URL or localhost):", currentUrl);
                if (newUrl !== null) {
                  try {
                    setApiUrl(newUrl.trim());
                    window.location.reload();
                  } catch (err) {
                    alert(err.message);
                  }
                }
              }}
              title="Click to configure backend API URL"
            >
              <div className="connection-dot" />
              <span>{connectionStatus === "active" ? "API Connected" : connectionStatus === "checking" ? "Connecting..." : "API Offline"}</span>
            </div>
          )}

          {/* User menu */}
          <div className="sidebar-user" onClick={() => setUserMenuOpen(!userMenuOpen)}>
            <div className="sidebar-avatar">
              {currentUser?.username?.[0]?.toUpperCase() || "U"}
            </div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <p className="sidebar-username">{currentUser?.username}</p>
              <p className="sidebar-role">
                {currentUser?.is_admin ? "Administrator" : "User"}
              </p>
            </div>
            <ChevronDown size={14} style={{ color: "var(--sidebar-text)", transition: "transform 0.2s", transform: userMenuOpen ? "rotate(180deg)" : "rotate(0deg)" }} />
          </div>

          {userMenuOpen && (
            <div className="user-menu-popup">
              <button id="logout-btn" className="user-menu-item danger" onClick={handleLogout}>
                <LogOut size={14} />
                Sign Out
              </button>
            </div>
          )}
        </div>
      </aside>

      {/* ── Main Content ──────────────────────────────────────────────────────── */}
      <main className="main-content">
        {/* Page header — no tunnel input visible to users */}
        <header className="page-header">
          <div className="page-heading">
            <div className="page-eyebrow"><span>Workspace</span><ChevronRight size={11} /><strong>{pageTitle()}</strong></div>
            <h1 className="page-title">{pageTitle()}</h1>
            <p className="page-subtitle">{pageSubtitle()}</p>
          </div>

          {/* Compact user info chip (desktop) */}
          <div className="header-actions">
            <div className={`header-api-status ${connectionStatus}`} title="Backend API status">
              {connectionStatus === "active" ? <Wifi size={14} /> : <WifiOff size={14} />}
              <span>{connectionStatus === "active" ? "Live" : connectionStatus === "checking" ? "Checking" : "Offline"}</span>
            </div>
            <button className="header-icon-btn" onClick={() => handleNavClick("notifications")} aria-label="Open notifications">
              <Bell size={17} />
            </button>
            <div className="header-user-chip">
            <div className="chip-avatar">{currentUser?.username?.[0]?.toUpperCase()}</div>
            <span>{currentUser?.username}</span>
            {currentUser?.is_admin && (
              <span className="chip-admin-badge">
                <Shield size={10} /> Admin
              </span>
            )}
            <button id="header-logout-btn" className="chip-logout-btn" onClick={handleLogout} title="Sign out">
              <LogOut size={13} />
            </button>
            </div>
          </div>
        </header>

        {/* Active view */}
        <div className="page-content">
          <ErrorBoundary resetKey={activeTab}>
            <Suspense fallback={
              <div className="page-loader" role="status" aria-live="polite">
                <LoaderCircle className="animate-spin" size={22} />
                <span>Loading workspace…</span>
              </div>
            }>
              {renderActiveComponent()}
            </Suspense>
          </ErrorBoundary>
        </div>
      </main>
    </div>
  );
}
