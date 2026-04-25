"use client";

import React, { useState, useEffect } from "react";
import Sidebar from "./Sidebar";
import ChatHeader from "./ChatHeader";
import ChatArea from "./ChatArea";
import ChatInput from "./ChatInput";

type Message = {
  role: "user" | "assistant";
  content: string;
};

type Session = {
  id: string;
  title: string;
  created_at: string;
};

export default function ChatLayout() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [sessions, setSessions] = useState<Session[]>([]);
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null);
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);
  const [isDarkMode, setIsDarkMode] = useState(false);

  // On mount: detect theme from localStorage or system preference
  useEffect(() => {
    const saved = localStorage.getItem("theme");
    if (saved === "dark") {
      setIsDarkMode(true);
    } else if (saved === "light") {
      setIsDarkMode(false);
    } else {
      // No saved preference — use system setting
      setIsDarkMode(window.matchMedia("(prefers-color-scheme: dark)").matches);
    }
  }, []);

  // Fetch sessions on mount
  useEffect(() => {
    fetchSessions();
  }, []);

  // Dark mode: toggle .dark class on <html> and save to localStorage
  useEffect(() => {
    if (isDarkMode) {
      document.documentElement.classList.add("dark");
    } else {
      document.documentElement.classList.remove("dark");
    }
  }, [isDarkMode]);

  // ---- API Functions ----

  const fetchSessions = async () => {
    try {
      const response = await fetch("/api/sessions");
      if (response.ok) {
        const data = await response.json();
        setSessions(data.sessions || []);
      }
    } catch (error) {
      console.error("Failed to fetch sessions:", error);
    }
  };

  const loadSession = async (sessionId: string) => {
    setCurrentSessionId(sessionId);
    setIsLoading(true);
    setMessages([]);
    try {
      const response = await fetch(`/api/sessions/${sessionId}/messages`);
      if (response.ok) {
        const data = await response.json();
        const formatted = data.messages.map((msg: any) => ({
          role: msg.role,
          content: msg.content,
        }));
        setMessages(formatted);
      }
    } catch (error) {
      console.error("Failed to load session:", error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isLoading) return;

    const userMessage: Message = { role: "user", content: input };
    const newMessages = [...messages, userMessage];

    setMessages(newMessages);
    setInput("");
    setIsLoading(true);

    try {
      const response = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: currentSessionId,
          messages: newMessages,
        }),
      });

      if (!response.ok) throw new Error("Failed to fetch response");

      const data = await response.json();

      setMessages([
        ...newMessages,
        { role: "assistant", content: data.response },
      ]);

      if (!currentSessionId && data.session_id) {
        setCurrentSessionId(data.session_id);
        fetchSessions();
      }
    } catch (error) {
      console.error("Chat error:", error);
      setMessages([
        ...newMessages,
        {
          role: "assistant",
          content:
            "Sorry, I encountered an error. Please ensure the backend is running.",
        },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleNewChat = () => {
    setCurrentSessionId(null);
    setMessages([]);
  };

  const handleDeleteSession = async (
    sessionId: string,
    e: React.MouseEvent
  ) => {
    e.stopPropagation();

    const confirmed = window.confirm(
      "Are you sure you want to delete this conversation? This cannot be undone."
    );
    if (!confirmed) return;

    setSessions(sessions.filter((s) => s.id !== sessionId));
    if (currentSessionId === sessionId) {
      handleNewChat();
    }

    try {
      const response = await fetch(`/api/sessions/${sessionId}`, {
        method: "DELETE",
      });
      if (!response.ok) {
        fetchSessions();
      }
    } catch (error) {
      console.error("Error deleting session:", error);
      fetchSessions();
    }
  };

  const handleSuggestionClick = (text: string) => {
    setInput(text);
  };

  // ---- Render ----

  return (
    <div className="h-full flex" style={{ background: "var(--bg-primary)" }}>
      <Sidebar
        sessions={sessions}
        currentSessionId={currentSessionId}
        isSidebarOpen={isSidebarOpen}
        onNewChat={handleNewChat}
        onSelectSession={loadSession}
        onDeleteSession={handleDeleteSession}
      />

      <div className="flex-1 flex flex-col min-w-0">
        <ChatHeader
          isDarkMode={isDarkMode}
          onToggleDarkMode={() => {
            const newValue = !isDarkMode;
            setIsDarkMode(newValue);
            localStorage.setItem("theme", newValue ? "dark" : "light");
          }}
          isSidebarOpen={isSidebarOpen}
          onToggleSidebar={() => setIsSidebarOpen(!isSidebarOpen)}
        />

        <ChatArea
          messages={messages}
          isLoading={isLoading}
          onSuggestionClick={handleSuggestionClick}
        />

        <ChatInput
          input={input}
          onInputChange={setInput}
          onSubmit={handleSubmit}
          isLoading={isLoading}
        />
      </div>
    </div>
  );
}
