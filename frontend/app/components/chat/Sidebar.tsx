"use client";

import React from "react";
import {
  PlusCircle,
  MessageSquare,
  Trash2,
} from "lucide-react";

type Session = {
  id: string;
  title: string;
  created_at: string;
};

interface SidebarProps {
  sessions: Session[];
  currentSessionId: string | null;
  isSidebarOpen: boolean;
  onNewChat: () => void;
  onSelectSession: (id: string) => void;
  onDeleteSession: (id: string, e: React.MouseEvent) => void;
  isMobile?: boolean;
}

export default function Sidebar({
  sessions,
  currentSessionId,
  isSidebarOpen,
  onNewChat,
  onSelectSession,
  onDeleteSession,
  isMobile = false,
}: SidebarProps) {
  return (
    <div
      className={`shrink-0 flex flex-col overflow-hidden transition-all duration-300 ease-in-out ${
        isMobile ? "fixed inset-y-0 left-0 z-50 shadow-2xl" : "relative"
      }`}
      style={{
        width: isSidebarOpen ? "260px" : "0px",
        background: "var(--bg-sidebar)",
        borderRight: isSidebarOpen ? "1px solid var(--border-color)" : "none",
        transform: isMobile && !isSidebarOpen ? "translateX(-100%)" : "translateX(0)",
        opacity: !isMobile && !isSidebarOpen ? 0 : 1,
      }}
    >
      {/* Header + New Chat */}
      <div className="p-3 shrink-0">
        <button
          onClick={onNewChat}
          className="w-full flex items-center gap-2 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors cursor-pointer"
          style={{
            border: "1px solid var(--border-color)",
            color: "var(--text-primary)",
            background: "var(--bg-primary)",
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.background = "var(--bg-hover)";
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.background = "var(--bg-primary)";
          }}
        >
          <PlusCircle size={16} />
          New chat
        </button>
      </div>

      {/* Session list */}
      <div className="flex-1 overflow-y-auto px-2 pb-3">
        <p
          className="text-xs font-medium uppercase tracking-wider px-2 mb-2"
          style={{ color: "var(--text-tertiary)" }}
        >
          Recent
        </p>

        {sessions.length === 0 ? (
          <p
            className="text-sm px-2 italic"
            style={{ color: "var(--text-tertiary)" }}
          >
            No conversations yet
          </p>
        ) : (
          <div className="space-y-0.5">
            {sessions.map((session) => {
              const isActive = currentSessionId === session.id;
              return (
                <div
                  key={session.id}
                  className="group flex items-center rounded-lg transition-colors"
                  style={{
                    background: isActive
                      ? "var(--bg-active)"
                      : "transparent",
                  }}
                  onMouseEnter={(e) => {
                    if (!isActive)
                      e.currentTarget.style.background = "var(--bg-hover)";
                  }}
                  onMouseLeave={(e) => {
                    if (!isActive)
                      e.currentTarget.style.background = "transparent";
                  }}
                >
                  <button
                    onClick={() => onSelectSession(session.id)}
                    className="flex items-center gap-2 flex-1 overflow-hidden px-3 py-2 text-left cursor-pointer"
                  >
                    <MessageSquare
                      size={14}
                      className="shrink-0"
                      style={{
                        color: isActive
                          ? "var(--accent)"
                          : "var(--text-tertiary)",
                      }}
                    />
                    <span
                      className="text-sm truncate"
                      style={{
                        color: isActive
                          ? "var(--accent)"
                          : "var(--text-primary)",
                        fontWeight: isActive ? 500 : 400,
                      }}
                    >
                      {session.title}
                    </span>
                  </button>
                  <button
                    onClick={(e) => onDeleteSession(session.id, e)}
                    className={`p-1.5 mr-1 rounded transition-opacity cursor-pointer ${
                      isMobile ? "opacity-100" : "opacity-0 group-hover:opacity-100"
                    }`}
                    style={{ color: "var(--text-tertiary)" }}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.color = "#ef4444";
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.color = "var(--text-tertiary)";
                    }}
                    title="Delete chat"
                  >
                    <Trash2 size={14} />
                  </button>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
