"use client";

import React, { useState } from "react";
import { X, Mail, Lock, Eye, EyeOff, Loader2 } from "lucide-react";

function GoogleIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" aria-hidden="true">
      <path
        d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
        fill="#4285F4"
      />
      <path
        d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
        fill="#34A853"
      />
      <path
        d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l3.66-2.84z"
        fill="#FBBC05"
      />
      <path
        d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
        fill="#EA4335"
      />
    </svg>
  );
}
import {
  signInWithGoogle,
  signInWithEmail,
  signUpWithEmail,
} from "../../../lib/auth";

interface AuthModalProps {
  onClose: () => void;
  onSuccess: () => void;
  messageCount: number;
  limit: number;
}

type Tab = "login" | "signup";

export default function AuthModal({
  onClose,
  onSuccess,
  messageCount,
  limit,
}: AuthModalProps) {
  const [tab, setTab] = useState<Tab>("signup");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [googleLoading, setGoogleLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  const handleGoogleSignIn = async () => {
    setGoogleLoading(true);
    setError(null);
    try {
      await signInWithGoogle();
      // Google OAuth redirects the page — onSuccess will be called via onAuthStateChange
    } catch (e: any) {
      setError(e.message || "Google sign-in failed.");
      setGoogleLoading(false);
    }
  };

  const handleEmailSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email || !password) {
      setError("Please fill in both fields.");
      return;
    }
    setIsLoading(true);
    setError(null);
    setSuccessMsg(null);

    try {
      if (tab === "signup") {
        await signUpWithEmail(email, password);
        setSuccessMsg(
          "Account created! Check your email to confirm, then you're all set."
        );
      } else {
        await signInWithEmail(email, password);
        onSuccess();
      }
    } catch (e: any) {
      setError(e.message || "Authentication failed. Please try again.");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    /* Backdrop */
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ background: "rgba(0,0,0,0.6)", backdropFilter: "blur(6px)" }}
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      {/* Modal card */}
      <div
        className="relative w-full max-w-md rounded-2xl overflow-hidden shadow-2xl"
        style={{
          background: "var(--bg-secondary)",
          border: "1px solid var(--border-color)",
        }}
      >
        {/* Gradient accent bar */}
        <div
          className="h-1 w-full"
          style={{
            background:
              "linear-gradient(90deg, var(--accent), #6366f1, #a855f7)",
          }}
        />

        {/* Close button */}
        <button
          onClick={onClose}
          className="absolute top-4 right-4 p-1.5 rounded-lg transition-colors cursor-pointer"
          style={{ color: "var(--text-tertiary)" }}
          onMouseEnter={(e) =>
            (e.currentTarget.style.background = "var(--bg-hover)")
          }
          onMouseLeave={(e) =>
            (e.currentTarget.style.background = "transparent")
          }
          title="Dismiss — continue as guest"
        >
          <X size={18} />
        </button>

        <div className="p-8 pt-6">
          {/* Header */}
          <div className="mb-6 text-center">
            <div
              className="inline-flex items-center justify-center w-12 h-12 rounded-2xl mb-3"
              style={{ background: "var(--accent-subtle, rgba(99,102,241,0.12))" }}
            >
              <span className="text-2xl">🩺</span>
            </div>
            <h2
              className="text-xl font-semibold mb-1"
              style={{ color: "var(--text-primary)" }}
            >
              {tab === "signup" ? "Create your free account" : "Welcome back"}
            </h2>
            <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
              {tab === "signup"
                ? "Sign up to save your chat history and get unlimited access."
                : "Log in to continue your research and access your saved chats."}
            </p>
          </div>

          {/* Google button */}
          <button
            id="google-signin-btn"
            onClick={handleGoogleSignIn}
            disabled={googleLoading || isLoading}
            className="w-full flex items-center justify-center gap-3 py-3 px-4 rounded-xl font-medium text-sm transition-all mb-4 cursor-pointer disabled:opacity-60 disabled:cursor-not-allowed"
            style={{
              background: "var(--bg-primary)",
              border: "1px solid var(--border-color)",
              color: "var(--text-primary)",
            }}
            onMouseEnter={(e) => {
              if (!googleLoading && !isLoading)
                e.currentTarget.style.background = "var(--bg-hover)";
            }}
            onMouseLeave={(e) =>
              (e.currentTarget.style.background = "var(--bg-primary)")
            }
          >
            {googleLoading ? (
              <Loader2 size={18} className="animate-spin" />
            ) : (
              <GoogleIcon />
            )}
            Continue with Google
          </button>

          {/* Divider */}
          <div className="flex items-center gap-3 mb-4">
            <div
              className="flex-1 h-px"
              style={{ background: "var(--border-color)" }}
            />
            <span className="text-xs" style={{ color: "var(--text-tertiary)" }}>
              or continue with email
            </span>
            <div
              className="flex-1 h-px"
              style={{ background: "var(--border-color)" }}
            />
          </div>

          {/* Tab switcher */}
          <div
            className="flex rounded-xl p-1 mb-5"
            style={{ background: "var(--bg-primary)" }}
          >
            {(["signup", "login"] as Tab[]).map((t) => (
              <button
                key={t}
                onClick={() => {
                  setTab(t);
                  setError(null);
                  setSuccessMsg(null);
                }}
                className="flex-1 py-2 rounded-lg text-sm font-medium transition-all cursor-pointer"
                style={{
                  background:
                    tab === t ? "var(--bg-secondary)" : "transparent",
                  color:
                    tab === t ? "var(--text-primary)" : "var(--text-tertiary)",
                  boxShadow:
                    tab === t
                      ? "0 1px 4px rgba(0,0,0,0.15)"
                      : "none",
                }}
              >
                {t === "signup" ? "Sign Up" : "Log In"}
              </button>
            ))}
          </div>

          {/* Email/password form */}
          <form onSubmit={handleEmailSubmit} className="space-y-3">
            <div className="relative">
              <Mail
                size={16}
                className="absolute left-3 top-1/2 -translate-y-1/2"
                style={{ color: "var(--text-tertiary)" }}
              />
              <input
                id="auth-email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="Email address"
                className="w-full pl-10 pr-4 py-3 rounded-xl text-sm outline-none transition-all"
                style={{
                  background: "var(--bg-primary)",
                  border: "1px solid var(--border-color)",
                  color: "var(--text-primary)",
                }}
                onFocus={(e) =>
                  (e.currentTarget.style.borderColor = "var(--accent)")
                }
                onBlur={(e) =>
                  (e.currentTarget.style.borderColor = "var(--border-color)")
                }
              />
            </div>

            <div className="relative">
              <Lock
                size={16}
                className="absolute left-3 top-1/2 -translate-y-1/2"
                style={{ color: "var(--text-tertiary)" }}
              />
              <input
                id="auth-password"
                type={showPassword ? "text" : "password"}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Password"
                className="w-full pl-10 pr-10 py-3 rounded-xl text-sm outline-none transition-all"
                style={{
                  background: "var(--bg-primary)",
                  border: "1px solid var(--border-color)",
                  color: "var(--text-primary)",
                }}
                onFocus={(e) =>
                  (e.currentTarget.style.borderColor = "var(--accent)")
                }
                onBlur={(e) =>
                  (e.currentTarget.style.borderColor = "var(--border-color)")
                }
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="absolute right-3 top-1/2 -translate-y-1/2 cursor-pointer"
                style={{ color: "var(--text-tertiary)" }}
              >
                {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            </div>

            {/* Error / success messages */}
            {error && (
              <p
                className="text-xs px-3 py-2 rounded-lg"
                style={{
                  background: "rgba(239,68,68,0.1)",
                  color: "#ef4444",
                  border: "1px solid rgba(239,68,68,0.2)",
                }}
              >
                {error}
              </p>
            )}
            {successMsg && (
              <p
                className="text-xs px-3 py-2 rounded-lg"
                style={{
                  background: "rgba(34,197,94,0.1)",
                  color: "#22c55e",
                  border: "1px solid rgba(34,197,94,0.2)",
                }}
              >
                {successMsg}
              </p>
            )}

            <button
              id="auth-submit-btn"
              type="submit"
              disabled={isLoading || googleLoading}
              className="w-full py-3 rounded-xl font-semibold text-sm transition-all cursor-pointer disabled:opacity-60 disabled:cursor-not-allowed"
              style={{
                background: "var(--accent)",
                color: "var(--text-on-accent)",
              }}
            >
              {isLoading ? (
                <span className="flex items-center justify-center gap-2">
                  <Loader2 size={16} className="animate-spin" />
                  {tab === "signup" ? "Creating account..." : "Signing in..."}
                </span>
              ) : tab === "signup" ? (
                "Create Free Account"
              ) : (
                "Log In"
              )}
            </button>
          </form>

          {/* Dismiss link */}
          <p className="text-center text-xs mt-4" style={{ color: "var(--text-tertiary)" }}>
            <button
              onClick={onClose}
              className="underline underline-offset-2 cursor-pointer hover:opacity-80 transition-opacity"
            >
              Continue as guest
            </button>
          </p>
        </div>
      </div>
    </div>
  );
}
