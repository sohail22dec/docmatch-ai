import { supabase } from "./supabase";
import type { User, Session } from "@supabase/supabase-js";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// ─────────────────────────────────────────────
// Anonymous Session
// ─────────────────────────────────────────────

/**
 * On first app load: if no Supabase session exists, create an anonymous one.
 * This gives every visitor a valid JWT immediately, without requiring sign-up.
 */
export async function getOrCreateAnonSession(): Promise<Session | null> {
  const { data: existing } = await supabase.auth.getSession();
  if (existing.session) return existing.session;

  const { data, error } = await supabase.auth.signInAnonymously();
  if (error) {
    console.error("[auth] Failed to create anonymous session:", error.message);
    return null;
  }
  return data.session;
}

// ─────────────────────────────────────────────
// Token Helper
// ─────────────────────────────────────────────

/**
 * Returns the current user's JWT access token.
 * Used to set the Authorization header on every API request.
 */
export async function getAuthToken(): Promise<string | null> {
  const { data } = await supabase.auth.getSession();
  if (data.session?.access_token) {
    return data.session.access_token;
  }
  const session = await getOrCreateAnonSession();
  return session?.access_token ?? null;
}

/**
 * Returns the current Supabase user object, or null if not signed in.
 */
export async function getCurrentUser(): Promise<User | null> {
  const { data } = await supabase.auth.getUser();
  return data.user ?? null;
}

// ─────────────────────────────────────────────
// Google OAuth
// ─────────────────────────────────────────────

export async function signInWithGoogle(): Promise<void> {
  const { error } = await supabase.auth.signInWithOAuth({
    provider: "google",
    options: {
      redirectTo: `${window.location.origin}/`,
    },
  });
  if (error) throw new Error(error.message);
}

// ─────────────────────────────────────────────
// Email + Password
// ─────────────────────────────────────────────

export async function signUpWithEmail(
  email: string,
  password: string
): Promise<User> {
  const { data, error } = await supabase.auth.signUp({ email, password });
  if (error) throw new Error(error.message);
  if (!data.user) throw new Error("Sign up failed — no user returned.");
  return data.user;
}

export async function signInWithEmail(
  email: string,
  password: string
): Promise<User> {
  const { data, error } = await supabase.auth.signInWithPassword({
    email,
    password,
  });
  if (error) throw new Error(error.message);
  if (!data.user) throw new Error("Sign in failed — no user returned.");
  return data.user;
}

// ─────────────────────────────────────────────
// Sign Out
// ─────────────────────────────────────────────

export async function signOut(): Promise<void> {
  const { error } = await supabase.auth.signOut();
  if (error) throw new Error(error.message);
}

// ─────────────────────────────────────────────
// Link Anonymous → Real Account
// ─────────────────────────────────────────────

/**
 * After a successful sign-up or login, tell the backend to reassign
 * all anonymous chat sessions to the newly authenticated user_id,
 * preserving the full chat history.
 */
export async function linkAnonSessions(
  anonUserId: string,
  realUserId: string,
  authToken: string
): Promise<void> {
  try {
    await fetch(`${API_BASE_URL}/api/auth/link-sessions`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${authToken}`,
      },
      body: JSON.stringify({
        anon_user_id: anonUserId,
        real_user_id: realUserId,
      }),
    });
  } catch (e) {
    console.error("[auth] Failed to link anonymous sessions:", e);
  }
}
