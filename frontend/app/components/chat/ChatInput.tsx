"use client";

import React, { useRef, useEffect } from "react";
import { ArrowUp, Loader2 } from "lucide-react";

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
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Auto-resize textarea — use useLayoutEffect to prevent layout shifts/flashes
  React.useLayoutEffect(() => {
    const textarea = textareaRef.current;
    if (!textarea) return;

    // Reset height to 'auto' to measure scrollHeight accurately
    textarea.style.height = "auto";
    
    // For empty input, force the standard min-height to avoid measurement glitches on some mobile browsers
    if (!input) {
      textarea.style.height = "44px";
      textarea.style.overflowY = "hidden";
      return;
    }

    const newHeight = Math.min(textarea.scrollHeight, 200);
    textarea.style.height = `${newHeight}px`;
    textarea.style.overflowY = textarea.scrollHeight > 200 ? "auto" : "hidden";
  }, [input]);

  // Refocus textarea after loading finished
  useEffect(() => {
    if (!isLoading) {
      textareaRef.current?.focus();
    }
  }, [isLoading]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (input.trim() && !isLoading) {
        const form = e.currentTarget.closest("form");
        if (form) form.requestSubmit();
      }
    }
  };

  const isSubmitDisabled = !input.trim() || isLoading;

  return (
    <div
      className="shrink-0 px-3 md:px-4 pb-3 md:pb-4 pt-2"
      style={{ background: "var(--bg-primary)" }}
    >
      <form
        onSubmit={onSubmit}
        className="max-w-3xl mx-auto relative flex items-end gap-2"
      >
        <div className="relative flex-1">
          <textarea
            ref={textareaRef}
            rows={1}
            value={input}
            onChange={(e) => onInputChange(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={placeholder || "Message Medical Assistant..."}
            disabled={isLoading}
            className="w-full py-3 md:py-4 pl-4 md:pl-5 pr-12 md:pr-14 rounded-2xl md:rounded-3xl text-sm md:text-base outline-none transition-[color,background-color,border-color,box-shadow] resize-none block leading-relaxed"
            style={{
              background: "var(--bg-input)",
              color: "var(--text-primary)",
              border: "1px solid var(--border-input)",
              minHeight: "44px",
              maxHeight: "200px",
              overflowY: "hidden", 
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
            className="absolute right-1.5 md:right-2 bottom-1.5 md:bottom-2 w-8 h-8 md:w-10 md:h-10 flex items-center justify-center rounded-full transition-all disabled:opacity-30 cursor-pointer disabled:cursor-not-allowed"
            style={{
              background: input.trim() ? "var(--accent)" : "transparent",
              color: input.trim()
                ? "var(--text-on-accent)"
                : "var(--text-tertiary)",
            }}
          >
            {isLoading ? (
              <Loader2 size={18} className="animate-spin" />
            ) : (
              <ArrowUp size={20} strokeWidth={2.5} />
            )}
          </button>
        </div>
      </form>

      <p className="text-center text-xs mt-1.5 max-w-3xl mx-auto" style={{ color: "var(--text-tertiary)" }}>
        AI assistant for informational purposes only. Not a substitute for professional medical advice.
      </p>
    </div>
  );
}
