"use client";

import React, { useState, useRef, useEffect } from "react";
import { LogOut, User, ChevronDown } from "lucide-react";
import type { User as SupabaseUser } from "@supabase/supabase-js";
import { signOut } from "../../../lib/auth";

interface UserMenuProps {
  user: SupabaseUser | null;
  isAnonymous: boolean;
  messageCount: number;
  limit: number;
  onSignInClick: () => void;
  onSignOut: () => void;
}

export default function UserMenu({
  user,
  isAnonymous,
  messageCount,
  limit,
  onSignInClick,
  onSignOut,
}: UserMenuProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [imgError, setImgError] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  // Close dropdown when clicking outside
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  const handleSignOut = async () => {
    setIsOpen(false);
    try {
      await signOut();
      onSignOut();
    } catch (e) {
      console.error("Sign out error:", e);
    }
  };

  // ── Anonymous user pill ──────────────────────────────────────────────────
  if (isAnonymous) {
    return (
      <button
        id="user-menu-guest-btn"
        onClick={onSignInClick}
        className="flex items-center gap-2 px-4 py-1.5 rounded-full text-xs font-medium transition-all cursor-pointer"
        style={{
          background: "var(--text-primary)",
          color: "var(--bg-primary)",
          border: "none",
        }}
        onMouseEnter={(e) => {
          e.currentTarget.style.opacity = "0.8";
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.opacity = "1";
        }}
        title="Sign in or create an account"
      >
        <User size={13} />
        <span>Login / Sign up</span>
      </button>
    );
  }

  // ── Authenticated user dropdown ──────────────────────────────────────────
  const displayName =
    user?.user_metadata?.full_name ||
    user?.user_metadata?.name ||
    user?.email?.split("@")[0] ||
    "User";

  const avatarUrl =
    user?.user_metadata?.avatar_url || user?.user_metadata?.picture || null;

  const initials = displayName
    .split(" ")
    .map((n: string) => n[0])
    .join("")
    .toUpperCase()
    .slice(0, 2);

  return (
    <div className="relative" ref={menuRef}>
      <button
        id="user-menu-btn"
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center gap-2 px-2 py-1.5 rounded-full transition-all cursor-pointer"
        style={{
          border: "1px solid var(--border-color)",
          background: isOpen ? "var(--bg-hover)" : "var(--bg-secondary)",
        }}
        onMouseEnter={(e) =>
          (e.currentTarget.style.background = "var(--bg-hover)")
        }
        onMouseLeave={(e) =>
          (e.currentTarget.style.background = isOpen
            ? "var(--bg-hover)"
            : "var(--bg-secondary)")
        }
      >
        {/* Avatar */}
        {avatarUrl && !imgError ? (
          <img
            src={avatarUrl}
            alt={displayName}
            className="w-6 h-6 rounded-full object-cover shrink-0"
            referrerPolicy="no-referrer"
            onError={() => setImgError(true)}
          />
        ) : (
          <div
            className="w-6 h-6 rounded-full flex items-center justify-center text-xs font-semibold shrink-0"
            style={{
              background: "var(--accent)",
              color: "var(--text-on-accent)",
            }}
          >
            {initials}
          </div>
        )}
        <span
          className="text-xs font-medium max-w-[100px] truncate hidden sm:block"
          style={{ color: "var(--text-primary)" }}
        >
          {displayName}
        </span>
        <ChevronDown
          size={13}
          style={{
            color: "var(--text-tertiary)",
            transform: isOpen ? "rotate(180deg)" : "none",
            transition: "transform 0.15s",
          }}
        />
      </button>

      {/* Dropdown */}
      {isOpen && (
        <div
          className="absolute right-0 top-full mt-1.5 w-52 rounded-xl overflow-hidden shadow-xl z-50"
          style={{
            background: "var(--bg-secondary)",
            border: "1px solid var(--border-color)",
          }}
        >
          {/* User info */}
          <div
            className="px-4 py-3"
            style={{ borderBottom: "1px solid var(--border-color)" }}
          >
            <p
              className="text-sm font-medium truncate"
              style={{ color: "var(--text-primary)" }}
            >
              {displayName}
            </p>
            {user?.email && (
              <p
                className="text-xs truncate mt-0.5"
                style={{ color: "var(--text-tertiary)" }}
              >
                {user.email}
              </p>
            )}
          </div>

          {/* Sign out */}
          <button
            id="sign-out-btn"
            onClick={handleSignOut}
            className="w-full flex items-center gap-3 px-4 py-2.5 text-sm transition-colors cursor-pointer"
            style={{ color: "var(--text-secondary)" }}
            onMouseEnter={(e) =>
              (e.currentTarget.style.background = "var(--bg-hover)")
            }
            onMouseLeave={(e) =>
              (e.currentTarget.style.background = "transparent")
            }
          >
            <LogOut size={15} />
            Sign out
          </button>
        </div>
      )}
    </div>
  );
}
