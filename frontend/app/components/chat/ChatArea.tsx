"use client";

import React, { useState, useRef, useEffect } from "react";
import { Bot, Sparkles } from "lucide-react";

type Message = {
  role: "user" | "assistant";
  content: string;
};

interface ChatAreaProps {
  messages: Message[];
  isLoading: boolean;
  onSuggestionClick: (text: string) => void;
}

export default function ChatArea({
  messages,
  isLoading,
  onSuggestionClick,
}: ChatAreaProps) {
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

  // Welcome screen
  if (messages.length === 0 && !isLoading) {
    return (
      <div
        className="flex-1 flex flex-col items-center justify-center px-4"
        style={{ color: "var(--text-secondary)" }}
      >
        <div
          className="w-14 h-14 rounded-full flex items-center justify-center mb-5"
          style={{ background: "var(--bg-secondary)" }}
        >
          <Sparkles size={28} style={{ color: "var(--accent)" }} />
        </div>
        <h2
          className="text-xl font-semibold mb-2"
          style={{ color: "var(--text-primary)" }}
        >
          How can I help you today?
        </h2>
        <p className="text-sm mb-8 text-center max-w-md">
          I can help analyze symptoms, search for medical information, and
          provide general health guidance.
        </p>
        <div className="flex flex-wrap gap-2 justify-center max-w-lg">
          {[
            "I have a bad headache and nausea",
            "What are common flu symptoms?",
            "My throat is sore and I have a fever",
          ].map((suggestion) => (
            <button
              key={suggestion}
              onClick={() => onSuggestionClick(suggestion)}
              className="px-4 py-2 text-sm rounded-full transition-colors cursor-pointer"
              style={{
                background: "var(--bg-secondary)",
                color: "var(--text-secondary)",
                border: "1px solid var(--border-color)",
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = "var(--bg-hover)";
                e.currentTarget.style.color = "var(--text-primary)";
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = "var(--bg-secondary)";
                e.currentTarget.style.color = "var(--text-secondary)";
              }}
            >
              {suggestion}
            </button>
          ))}
        </div>
      </div>
    );
  }

  // Message list
  return (
    <div className="flex-1 overflow-y-auto">
      <div className="max-w-3xl mx-auto px-3 md:px-4 py-4 md:py-6 space-y-5 md:space-y-6">
        {messages.map((msg, idx) => (
          <MessageRow key={idx} role={msg.role} content={msg.content} />
        ))}

        {isLoading && (
          <div className="flex gap-3 md:gap-4 py-2">
            <div
              className="w-8 h-8 rounded-full flex items-center justify-center shrink-0"
              style={{ background: "var(--bg-secondary)" }}
            >
              <Bot size={18} style={{ color: "var(--accent)" }} />
            </div>
            <div className="flex items-center gap-2 pt-1">
              <div className="flex gap-1">
                <span
                  className="w-2 h-2 rounded-full animate-bounce"
                  style={{
                    background: "var(--text-tertiary)",
                    animationDelay: "0ms",
                  }}
                />
                <span
                  className="w-2 h-2 rounded-full animate-bounce"
                  style={{
                    background: "var(--text-tertiary)",
                    animationDelay: "150ms",
                  }}
                />
                <span
                  className="w-2 h-2 rounded-full animate-bounce"
                  style={{
                    background: "var(--text-tertiary)",
                    animationDelay: "300ms",
                  }}
                />
              </div>
              <span
                className="text-sm"
                style={{ color: "var(--text-tertiary)" }}
              >
                Thinking...
              </span>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>
    </div>
  );
}

// ---- Inline MessageRow component ----

function MessageRow({ role, content }: { role: string; content: string }) {
  const isUser = role === "user";

  return (
    <div className="flex gap-3 md:gap-4">
      {/* Avatar */}
      <div
        className="w-8 h-8 rounded-full flex items-center justify-center shrink-0 text-sm font-semibold"
        style={
          isUser
            ? {
                background: "var(--accent)",
                color: "var(--text-on-accent)",
              }
            : {
                background: "var(--bg-secondary)",
                color: "var(--accent)",
              }
        }
      >
        {isUser ? "U" : <Bot size={18} />}
      </div>

      {/* Content */}
      <div className="flex-1 min-w-0 pt-0.5">
        <p
          className="text-xs font-medium mb-1"
          style={{ color: "var(--text-tertiary)" }}
        >
          {isUser ? "You" : "Medical Assistant"}
        </p>
        <div
          className="text-sm leading-relaxed whitespace-pre-wrap"
          style={{ color: "var(--text-primary)" }}
        >
          {content}
        </div>
      </div>
    </div>
  );
}
