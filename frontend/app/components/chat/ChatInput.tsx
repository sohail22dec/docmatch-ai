"use client";

import React from "react";
import { Send, Loader2 } from "lucide-react";

interface ChatInputProps {
  input: string;
  onInputChange: (value: string) => void;
  onSubmit: (e: React.FormEvent) => void;
  isLoading: boolean;
  placeholder?: string;
}

export default function ChatInput({
  input,
  onInputChange,
  onSubmit,
  isLoading,
  placeholder,
}: ChatInputProps) {
  const [mounted, setMounted] = React.useState(false);

  React.useEffect(() => {
    setMounted(true);
  }, []);

  // Prevent hydration mismatch: force 'true' during initial render on both server and client
  const isSubmitDisabled = mounted ? (!input.trim() || isLoading) : true;

  return (
    <div
      className="shrink-0 px-3 md:px-4 pb-3 md:pb-4 pt-2"
      style={{ background: "var(--bg-primary)" }}
    >
      <form onSubmit={onSubmit} className="max-w-3xl mx-auto relative flex items-center gap-2">
        {/* Text input */}
        <div className="relative flex-1">
          <input
            type="text"
            value={input}
            onChange={(e) => onInputChange(e.target.value)}
            placeholder={placeholder || "Message Medical Assistant..."}
            disabled={isLoading}
            className="w-full py-3 pl-4 pr-12 rounded-xl text-sm outline-none transition-all"
            style={{
              background: "var(--bg-input)",
              color: "var(--text-primary)",
              border: "1px solid var(--border-input)",
            }}
            onFocus={(e) => {
              e.currentTarget.style.borderColor = "var(--accent)";
              e.currentTarget.style.boxShadow =
                "0 0 0 2px color-mix(in srgb, var(--accent) 20%, transparent)";
            }}
            onBlur={(e) => {
              e.currentTarget.style.borderColor = "var(--border-input)";
              e.currentTarget.style.boxShadow = "none";
            }}
          />
          <button
            type="submit"
            disabled={isSubmitDisabled}
            className="absolute right-2 top-1/2 -translate-y-1/2 p-2 rounded-lg transition-all disabled:opacity-30 cursor-pointer disabled:cursor-not-allowed"
            style={{
              background: input.trim() ? "var(--accent)" : "transparent",
              color: input.trim() ? "var(--text-on-accent)" : "var(--text-tertiary)",
            }}
          >
            {isLoading ? (
              <Loader2 size={18} className="animate-spin" />
            ) : (
              <Send size={18} />
            )}
          </button>
        </div>
      </form>

      <p
        className="text-center text-xs mt-1.5 max-w-3xl mx-auto"
        style={{ color: "var(--text-tertiary)" }}
      >
        AI assistant for informational purposes only. Not a substitute for professional medical advice.
      </p>
    </div>
  );
}
