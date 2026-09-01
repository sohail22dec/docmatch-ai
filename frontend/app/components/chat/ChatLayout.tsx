"use client";

import React, { useState, useEffect, useRef } from "react";
import dynamic from "next/dynamic";
import type { User } from "@supabase/supabase-js";
import Sidebar from "./Sidebar";
import ChatHeader from "./ChatHeader";
import ChatArea from "./ChatArea";
import AuthModal from "../auth/AuthModal";
import BookingModal from "./BookingModal";
import {
  getOrCreateAnonSession,
  getAuthToken,
  getCurrentUser,
  linkAnonSessions,
} from "../../../lib/auth";
import { supabase } from "../../../lib/supabase";

const ChatInput = dynamic(() => import("./ChatInput"), {
  ssr: false,
  loading: () => (
    <div className="h-[76px] w-full" style={{ background: "var(--bg-primary)" }} />
  ),
});

import type { Message } from "./types";

type Session = {
  id: string;
  title: string;
  created_at: string;
};

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const ANON_MESSAGE_LIMIT = 5;

export default function ChatLayout() {
  // ── Chat state ───────────────────────────────────────────────────────────
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [sessions, setSessions] = useState<Session[]>([]);
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null);
  const userIdRef = useRef<string | null>(null);
  const [specialtyNeeded, setSpecialtyNeeded] = useState<string | null>(null);
  const [isWaitingForLocation, setIsWaitingForLocation] = useState(false);
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);
  const [isMobile, setIsMobile] = useState(false);
  const [isDarkMode, setIsDarkMode] = useState(false);
  const [location, setLocation] = useState<{ lat: number; lng: number } | null>(null);

  // ── Booking state ────────────────────────────────────────────────────────
  const [selectedClinic, setSelectedClinic] = useState<any>(null);
  const [currentBooking, setCurrentBooking] = useState<any>(null);
  const [bookingConfirmed, setBookingConfirmed] = useState(false);
  const [bookingId, setBookingId] = useState<string | null>(null);
  const [showBookingModal, setShowBookingModal] = useState(false);

  // ── Auth state ───────────────────────────────────────────────────────────
  const [user, setUser] = useState<User | null>(null);
  const [isAnonymous, setIsAnonymous] = useState(true);
  const [messageCount, setMessageCount] = useState(0);
  const [showAuthModal, setShowAuthModal] = useState(false);
  // Track the anon user_id BEFORE upgrade so we can link their sessions
  const anonUserIdRef = useRef<string | null>(null);

  // ── On mount: theme, screen size, auth init ──────────────────────────────
  useEffect(() => {
    const checkMobile = () => {
      const mobile = window.innerWidth < 768;
      setIsMobile(mobile);
      setIsSidebarOpen(!mobile);
    };
    checkMobile();
    window.addEventListener("resize", checkMobile);

    const saved = localStorage.getItem("theme");
    if (saved === "dark") setIsDarkMode(true);
    else if (saved === "light") setIsDarkMode(false);
    else setIsDarkMode(window.matchMedia("(prefers-color-scheme: dark)").matches);

    return () => window.removeEventListener("resize", checkMobile);
  }, []);

  // ── Initialize Supabase Auth ─────────────────────────────────────────────
  useEffect(() => {
    const initAuth = async () => {
      const session = await getOrCreateAnonSession();
      if (session) {
        const currentUser = session.user;
        const anon = currentUser.role === "anon" || currentUser.is_anonymous === true;

        setUser(currentUser);
        setIsAnonymous(anon);
        userIdRef.current = currentUser.id;

        if (anon) {
          anonUserIdRef.current = currentUser.id;
        }

        fetchSessions(currentUser.id);
      }
    };
    initAuth();

    // Listen for sign-in / sign-out events (including Google OAuth redirect)
    const { data: listener } = supabase.auth.onAuthStateChange(
      async (event, session) => {
        if (event === "SIGNED_IN" && session) {
          const newUser = session.user;
          const anon = newUser.role === "anon" || newUser.is_anonymous === true;
          const prevAnonId = anonUserIdRef.current;

          setUser(newUser);
          setIsAnonymous(anon);
          userIdRef.current = newUser.id;

          // If upgrading from anon → real, link sessions on the backend
          if (!anon && prevAnonId && prevAnonId !== newUser.id) {
            const token = session.access_token;
            await linkAnonSessions(prevAnonId, newUser.id, token);
            anonUserIdRef.current = null;
          }

          setShowAuthModal(false);
          fetchSessions(newUser.id);
        } else if (event === "SIGNED_OUT") {
          setUser(null);
          setIsAnonymous(true);
          userIdRef.current = null;
          setSessions([]);
          handleNewChat();
        }
      }
    );

    return () => listener.subscription.unsubscribe();
  }, []);

  // ── Dark mode sync ───────────────────────────────────────────────────────
  useEffect(() => {
    document.documentElement.classList.toggle("dark", isDarkMode);
  }, [isDarkMode]);

  // ── API helpers ──────────────────────────────────────────────────────────

  const fetchSessions = async (currentUserId?: string | null) => {
    const idToUse = currentUserId ?? userIdRef.current;
    if (!idToUse) return;
    try {
      const response = await fetch(
        `${API_BASE_URL}/api/sessions?user_id=${idToUse}`
      );
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
      const response = await fetch(
        `${API_BASE_URL}/api/sessions/${sessionId}/messages`
      );
      if (response.ok) {
        const data = await response.json();
        setMessages(
          data.messages.map((msg: any) => ({
            role: msg.role,
            content: msg.content,
            metadata: msg.metadata || (msg.clinics ? { clinics: msg.clinics } : undefined),
          }))
        );
        if (isMobile) setIsSidebarOpen(false);
      }
    } catch (error) {
      console.error("Failed to load session:", error);
    } finally {
      setIsLoading(false);
    }
  };

  const sendMessage = async (
    messageContent: string,
    coordsOverride?: { lat: number; lng: number } | null,
    clinicToSelect?: any,
    currentMessages?: Message[],
    specialtyOverride?: string | null,
    sessionIdOverride?: string | null
  ) => {
    if (!messageContent.trim() || isLoading) return;

    const baseMessages = currentMessages || messages;
    const userMessage: Message = { role: "user", content: messageContent };
    const newMessages = [...baseMessages, userMessage];

    setMessages(newMessages);
    setInput("");
    setIsLoading(true);

    const updatedSelectedClinic = clinicToSelect || selectedClinic;
    if (clinicToSelect) setSelectedClinic(clinicToSelect);

    const latToSend =
      coordsOverride !== undefined ? coordsOverride?.lat ?? null : location?.lat ?? null;
    const lngToSend =
      coordsOverride !== undefined ? coordsOverride?.lng ?? null : location?.lng ?? null;

    try {
      const token = await getAuthToken();
      const activeSessionId = sessionIdOverride || currentSessionId;

      let currentUserId = userIdRef.current;
      if (!currentUserId) {
        const u = await getCurrentUser();
        if (u) {
          currentUserId = u.id;
          userIdRef.current = u.id;
        }
      }

      const response = await fetch(`${API_BASE_URL}/api/chat`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({
          session_id: activeSessionId,
          user_id: currentUserId,
          messages: newMessages,
          latitude: latToSend,
          longitude: lngToSend,
          specialty_needed:
            specialtyOverride !== undefined ? specialtyOverride : specialtyNeeded,
          selected_clinic: updatedSelectedClinic,
          current_booking: currentBooking,
          booking_confirmed: bookingConfirmed,
          booking_id: bookingId,
        }),
      });

      if (!response.ok) {
        const errText = await response.text().catch(() => "No text");
        console.error("HTTP Error:", response.status, errText);
        throw new Error(`Failed to fetch response: ${response.status} - ${errText}`);
      }

      const data = await response.json();

      const metadata = data.metadata || (data.clinics ? { clinics: data.clinics } : undefined);
      let responseMessages = newMessages;

      if (data.action === "open_booking_form" && data.selected_clinic) {
        setSelectedClinic(data.selected_clinic);
        setShowBookingModal(true);
      } else {
        responseMessages = [
          ...newMessages,
          {
            role: "assistant",
            content: data.response,
            metadata: metadata,
          },
        ];
      }
      setMessages(responseMessages);

      // Update booking state
      setSelectedClinic(data.selected_clinic);
      setCurrentBooking(data.current_booking);
      setBookingConfirmed(data.booking_confirmed);
      setBookingId(data.booking_id);
      setSpecialtyNeeded(data.specialty_needed);

      // Track message count & show modal if limit reached
      if (data.message_count !== undefined) {
        setMessageCount(data.message_count);
      }
      if (data.limit_reached && isAnonymous) {
        setShowAuthModal(true);
      }

      const isLocationPending =
        (data.action === "request_current_location" || data.action === "request_location") && !latToSend;

      if (!currentSessionId && data.session_id) {
        setCurrentSessionId(data.session_id);
        if (!isLocationPending) fetchSessions(userIdRef.current);
      }

      if (isLocationPending) {
        const activeSessionId = data.session_id || currentSessionId;
        if (navigator.geolocation && activeSessionId) {
          setIsLoading(true);
          setIsWaitingForLocation(true);

          const sendLocationPayload = async (lat: number | null, lng: number | null) => {
            try {
              const token = getAuthToken();
              const locRes = await fetch(`${API_BASE_URL}/api/chat/location`, {
                method: "POST",
                headers: {
                  "Content-Type": "application/json",
                  ...(token ? { Authorization: `Bearer ${token}` } : {}),
                },
                body: JSON.stringify({
                  session_id: activeSessionId,
                  latitude: lat,
                  longitude: lng,
                }),
              });

              if (locRes.ok) {
                const locData = await locRes.json();
                if (locData.response) {
                  setMessages((current) => [
                    ...current,
                    {
                      role: "assistant",
                      content: locData.response,
                      metadata: locData.metadata,
                    },
                  ]);
                }
              }
            } catch (err) {
              console.error("Location submission error:", err);
            } finally {
              setIsWaitingForLocation(false);
              setIsLoading(false);
              fetchSessions(userIdRef.current);
            }
          };

          navigator.geolocation.getCurrentPosition(
            (pos) => {
              const coords = { lat: pos.coords.latitude, lng: pos.coords.longitude };
              setLocation(coords);
              sendLocationPayload(coords.lat, coords.lng);
            },
            (err) => {
              console.warn("Location permission denied or unavailable:", err);
              sendLocationPayload(null, null);
            }
          );
        }
      }
    } catch (error) {
      console.error("Chat error:", error);
      setMessages([
        ...newMessages,
        {
          role: "assistant",
          content: "Sorry, I encountered an error. Please ensure the backend is running.",
        },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    sendMessage(input);
  };

  const handleBookAppointment = (clinic: any) => {
    setSelectedClinic(clinic);
    setShowBookingModal(true);
  };

  const handleNewChat = () => {
    setCurrentSessionId(null);
    setMessages([]);
    setLocation(null);
    setSelectedClinic(null);
    setCurrentBooking(null);
    setBookingConfirmed(false);
    setBookingId(null);
    setShowBookingModal(false);
    setSpecialtyNeeded(null);
    if (isMobile) setIsSidebarOpen(false);
  };

  const handleDeleteSession = async (sessionId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!window.confirm("Delete this conversation? This cannot be undone.")) return;

    setSessions(sessions.filter((s) => s.id !== sessionId));
    if (currentSessionId === sessionId) handleNewChat();

    try {
      const response = await fetch(`${API_BASE_URL}/api/sessions/${sessionId}`, {
        method: "DELETE",
      });
      if (!response.ok) fetchSessions();
    } catch {
      fetchSessions();
    }
  };

  const handleSuggestionClick = (text: string) => setInput(text);

  const handleSignOut = () => {
    // Re-initialize anonymous session after sign-out
    getOrCreateAnonSession().then((session) => {
      if (session) {
        setUser(session.user);
        setIsAnonymous(true);
        setMessageCount(0);
        anonUserIdRef.current = session.user.id;
        userIdRef.current = session.user.id;
        fetchSessions(session.user.id);
      }
    });
  };

  const handleBookingComplete = async (booking: any) => {
    setCurrentBooking(booking);
    setBookingConfirmed(true);
    setBookingId(booking?.id || null);
    setShowBookingModal(false);

    try {
      const token = getAuthToken();
      const response = await fetch(`${API_BASE_URL}/api/chat/events`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({
          session_id: currentSessionId,
          type: "booking_completed",
          booking: {
            clinic_name: booking.clinic_name,
            appointment_date: booking.appointment_date,
            time_slot: booking.time_slot,
          },
        }),
      });

      if (response.ok) {
        const data = await response.json();
        setMessages((current) => [
          ...current,
          {
            role: "assistant",
            content: data.message,
            metadata: data.metadata || (data.clinics ? { clinics: data.clinics } : undefined),
          },
        ]);
        fetchSessions(userIdRef.current);
        return;
      }
    } catch (err) {
      console.error("Failed to post booking_completed event:", err);
    }

    // Fallback confirmation message if event API fails
    setMessages((current) => [
      ...current,
      {
        role: "assistant",
        content: `✅ Your appointment with ${booking.clinic_name} has been booked successfully for ${booking.appointment_date} at ${booking.time_slot}. A confirmation email has been sent.`,
      },
    ]);
  };

  const handleBookingFailed = async (errorMessage: string) => {
    setShowBookingModal(false);

    try {
      const token = getAuthToken();
      const response = await fetch(`${API_BASE_URL}/api/chat/events`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({
          session_id: currentSessionId,
          type: "booking_failed",
          error: errorMessage,
        }),
      });

      if (response.ok) {
        const data = await response.json();
        setMessages((current) => [
          ...current,
          {
            role: "assistant",
            content: data.message,
            metadata: data.metadata,
          },
        ]);
        return;
      }
    } catch (err) {
      console.error("Failed to post booking_failed event:", err);
    }

    // Fallback failure message if event API fails
    setMessages((current) => [
      ...current,
      {
        role: "assistant",
        content: `❌ Booking failed: ${errorMessage}`,
      },
    ]);
  };

  // ── Render ───────────────────────────────────────────────────────────────
  return (
    <div className="h-full flex overflow-hidden" style={{ background: "var(--bg-primary)" }}>
      {/* Auth modal */}
      {showAuthModal && (
        <AuthModal
          onClose={() => setShowAuthModal(false)}
          onSuccess={() => setShowAuthModal(false)}
          messageCount={messageCount}
          limit={ANON_MESSAGE_LIMIT}
        />
      )}

      {showBookingModal && selectedClinic && (
        <BookingModal
          clinic={selectedClinic}
          sessionId={currentSessionId}
          specialty={specialtyNeeded}
          onClose={() => setShowBookingModal(false)}
          onBooked={handleBookingComplete}
          onBookingFailed={handleBookingFailed}
        />
      )}

      {/* Mobile sidebar overlay */}
      {isMobile && isSidebarOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/50 backdrop-blur-sm transition-opacity"
          onClick={() => setIsSidebarOpen(false)}
        />
      )}

      <Sidebar
        sessions={sessions}
        currentSessionId={currentSessionId}
        isSidebarOpen={isSidebarOpen}
        onNewChat={handleNewChat}
        onSelectSession={loadSession}
        onDeleteSession={handleDeleteSession}
        isMobile={isMobile}
      />

      <div className="flex-1 flex flex-col min-w-0 h-full relative">
        <ChatHeader
          isDarkMode={isDarkMode}
          onToggleDarkMode={() => {
            const v = !isDarkMode;
            setIsDarkMode(v);
            localStorage.setItem("theme", v ? "dark" : "light");
          }}
          isSidebarOpen={isSidebarOpen}
          onToggleSidebar={() => setIsSidebarOpen(!isSidebarOpen)}
          user={user}
          isAnonymous={isAnonymous}
          messageCount={messageCount}
          anonLimit={ANON_MESSAGE_LIMIT}
          onSignInClick={() => setShowAuthModal(true)}
          onSignOut={handleSignOut}
        />

        <ChatArea
          messages={messages}
          isLoading={isLoading}
          onSuggestionClick={handleSuggestionClick}
          onBookAppointment={handleBookAppointment}
        />

        <ChatInput
          input={input}
          onInputChange={setInput}
          onSubmit={handleSubmit}
          isLoading={isLoading}
          placeholder={
            isWaitingForLocation
              ? "Waiting for location permission..."
              : "Message Medical Assistant..."
          }
        />
      </div>
    </div>
  );
}
