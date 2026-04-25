"use client";

import React from "react";
import { Sun, Moon, PanelLeftClose, PanelLeftOpen } from "lucide-react";

interface ChatHeaderProps {
  isDarkMode: boolean;
  onToggleDarkMode: () => void;
  isSidebarOpen: boolean;
  onToggleSidebar: () => void;
}

export default function ChatHeader({
  isDarkMode,
  onToggleDarkMode,
  isSidebarOpen,
  onToggleSidebar,
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
          Medical Assistant
        </span>
      </div>

      {/* Right: dark mode toggle */}
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
    </div>
  );
}
