"use client";

import React from "react";
import { Sun, Moon, PanelLeftClose, PanelLeftOpen } from "lucide-react";
import type { User } from "@supabase/supabase-js";
import UserMenu from "../auth/UserMenu";

interface ChatHeaderProps {
  isDarkMode: boolean;
  onToggleDarkMode: () => void;
  isSidebarOpen: boolean;
  onToggleSidebar: () => void;
  // Auth props
  user: User | null;
  isAnonymous: boolean;
  messageCount: number;
  anonLimit: number;
  onSignInClick: () => void;
  onSignOut: () => void;
}

export default function ChatHeader({
  isDarkMode,
  onToggleDarkMode,
  isSidebarOpen,
  onToggleSidebar,
  user,
  isAnonymous,
  messageCount,
  anonLimit,
  onSignInClick,
  onSignOut,
}: ChatHeaderProps) {
  return (
    <div
      className="shrink-0 flex items-center justify-between px-4 h-12"
      style={{
        borderBottom: "1px solid var(--border-color)",
        background: "var(--bg-primary)",
      }}
    >
      {/* Left: sidebar toggle + title */}
      <div className="flex items-center gap-3">
        <button
          onClick={onToggleSidebar}
          className="p-1.5 rounded-md transition-colors cursor-pointer"
          style={{ color: "var(--text-secondary)" }}
          onMouseEnter={(e) => {
            e.currentTarget.style.background = "var(--bg-hover)";
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.background = "transparent";
          }}
          title={isSidebarOpen ? "Close sidebar" : "Open sidebar"}
        >
          {isSidebarOpen ? (
            <PanelLeftClose size={18} />
          ) : (
            <PanelLeftOpen size={18} />
          )}
        </button>
        <span
          className="text-sm font-medium"
          style={{ color: "var(--text-primary)" }}
        >
          DocMatch AI
        </span>
      </div>

      {/* Right: dark mode toggle + user menu */}
      <div className="flex items-center gap-2">
        <button
          onClick={onToggleDarkMode}
          className="p-2 rounded-md transition-colors cursor-pointer"
          style={{ color: "var(--text-secondary)" }}
          onMouseEnter={(e) => {
            e.currentTarget.style.background = "var(--bg-hover)";
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.background = "transparent";
          }}
          title={isDarkMode ? "Switch to light mode" : "Switch to dark mode"}
        >
          {isDarkMode ? <Sun size={18} /> : <Moon size={18} />}
        </button>

        <UserMenu
          user={user}
          isAnonymous={isAnonymous}
          messageCount={messageCount}
          limit={anonLimit}
          onSignInClick={onSignInClick}
          onSignOut={onSignOut}
        />
      </div>
    </div>
  );
}
