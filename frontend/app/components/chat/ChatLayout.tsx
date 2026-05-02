"use client";

import React, { useState, useEffect, useRef } from "react";
import dynamic from "next/dynamic";
import Sidebar from "./Sidebar";
import ChatHeader from "./ChatHeader";
import ChatArea from "./ChatArea";

// Dynamically import ChatInput with SSR disabled to prevent hydration mismatches 
// on interactive elements like the button and textarea auto-resize.
const ChatInput = dynamic(() => import("./ChatInput"), { 
  ssr: false,
  loading: () => <div className="h-[76px] w-full" style={{ background: "var(--bg-primary)" }} /> 
});

type Message = {
  role: "user" | "assistant";
  content: string;
};

type Session = {
  id: string;
  title: string;
  created_at: string;
};

// Use environment variable for production, fallback to local for dev
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function ChatLayout() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [sessions, setSessions] = useState<Session[]>([]);
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null);
  const [userId, setUserId] = useState<string | null>(null);
  // Ref so fetchSessions always has the current userId without stale closures
  const userIdRef = useRef<string | null>(null);
  const [specialtyNeeded, setSpecialtyNeeded] = useState<string | null>(null);
  const [isWaitingForLocation, setIsWaitingForLocation] = useState(false);
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);
  const [isMobile, setIsMobile] = useState(false);
  const [isDarkMode, setIsDarkMode] = useState(false);
  const [location, setLocation] = useState<{ lat: number; lng: number } | null>(null);

  // --- Booking State ---
  const [selectedClinic, setSelectedClinic] = useState<any>(null);
  const [currentBooking, setCurrentBooking] = useState<any>(null);
  const [bookingConfirmed, setBookingConfirmed] = useState(false);
  const [bookingId, setBookingId] = useState<string | null>(null);

  // On mount: detect theme and screen size
  useEffect(() => {
    const checkMobile = () => {
      const mobile = window.innerWidth < 768;
      setIsMobile(mobile);
      if (mobile) setIsSidebarOpen(false);
      else setIsSidebarOpen(true);
    };
    
    checkMobile();
    window.addEventListener("resize", checkMobile);

    const saved = localStorage.getItem("theme");
    if (saved === "dark") {
      setIsDarkMode(true);
    } else if (saved === "light") {
      setIsDarkMode(false);
    } else {
      setIsDarkMode(window.matchMedia("(prefers-color-scheme: dark)").matches);
    }

    return () => window.removeEventListener("resize", checkMobile);
  }, []);

  // Fetch sessions on mount — always using the ref to avoid stale state
  useEffect(() => {
    let storedId = localStorage.getItem("docmatch_user_id");
    if (!storedId) {
        storedId = typeof crypto !== "undefined" && crypto.randomUUID 
            ? crypto.randomUUID() 
            : "user_" + Math.random().toString(36).substring(2, 11);
        localStorage.setItem("docmatch_user_id", storedId);
    }
    userIdRef.current = storedId; // Sync ref BEFORE state so all callbacks see it
    setUserId(storedId);
    fetchSessions(storedId);
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

  const fetchSessions = async (currentUserId?: string | null) => {
    // Always prefer the explicit argument, then the ref (always current), then state (may be stale)
    const idToUse = currentUserId ?? userIdRef.current ?? userId;
    if (!idToUse) {
      console.warn("[fetchSessions] No userId available — skipping fetch");
      return;
    }

    try {
      const response = await fetch(`${API_BASE_URL}/api/sessions?user_id=${idToUse}`);
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
      const response = await fetch(`${API_BASE_URL}/api/sessions/${sessionId}/messages`);
      if (response.ok) {
        const data = await response.json();
        const formatted = data.messages.map((msg: any) => ({
          role: msg.role,
          content: msg.content,
        }));
        setMessages(formatted);
        // On mobile, close sidebar after selecting a chat
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
    clinicToSelect?: any, // New parameter for direct booking trigger
    currentMessages?: Message[], // Add this parameter to prevent stale state
    specialtyOverride?: string | null, // Prevent stale specialty state
    sessionIdOverride?: string | null // NEW: Prevent stale session ID state
  ) => {
    if (!messageContent.trim() || isLoading) return;

    const baseMessages = currentMessages || messages;
    const userMessage: Message = { role: "user", content: messageContent };
    const newMessages = [...baseMessages, userMessage];

    setMessages(newMessages);
    setInput("");
    setIsLoading(true);

    // If we're selecting a clinic, update state locally before sending
    const updatedSelectedClinic = clinicToSelect || selectedClinic;
    if (clinicToSelect) setSelectedClinic(clinicToSelect);

    // Use overrides if provided (for auto-submit on location button click), otherwise use state
    const latToSend = coordsOverride !== undefined ? coordsOverride?.lat ?? null : location?.lat ?? null;
    const lngToSend = coordsOverride !== undefined ? coordsOverride?.lng ?? null : location?.lng ?? null;

    try {
      const activeSessionId = sessionIdOverride || currentSessionId;
      const response = await fetch(`${API_BASE_URL}/api/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: activeSessionId,
          user_id: userId,
          messages: newMessages,
          latitude: latToSend,
          longitude: lngToSend,
          specialty_needed: specialtyOverride !== undefined ? specialtyOverride : specialtyNeeded,
          selected_clinic: updatedSelectedClinic,
          current_booking: currentBooking,
          booking_confirmed: bookingConfirmed,
          booking_id: bookingId
        }),
      });

      if (!response.ok) throw new Error("Failed to fetch response");

      const data = await response.json();

      const responseMessages: Message[] = [
        ...newMessages,
        { role: "assistant", content: data.response },
      ];
      setMessages(responseMessages);

      // Update booking state from backend response
      setSelectedClinic(data.selected_clinic);
      setCurrentBooking(data.current_booking);
      setBookingConfirmed(data.booking_confirmed);
      setBookingId(data.booking_id);
      setSpecialtyNeeded(data.specialty_needed);

      const isLocationPending = data.action === "request_location" && !latToSend;

      if (!currentSessionId && data.session_id) {
        setCurrentSessionId(data.session_id);
        // Only refresh sidebar now if we're NOT about to auto-submit a location.
        // If a location request is coming, we'll refresh after that completes.
        if (!isLocationPending) {
          fetchSessions(userIdRef.current); // Pass ref — avoids stale state closure
        }
      }

      // AUTO-TRIGGER LOCATION: If backend asks for location, trigger browser prompt
      if (isLocationPending) {
        if (navigator.geolocation) {
          setIsLoading(true);
          setIsWaitingForLocation(true);
          const resolvedSessionId = data.session_id || currentSessionId;
          navigator.geolocation.getCurrentPosition(
            (pos) => {
              const coords = { lat: pos.coords.latitude, lng: pos.coords.longitude };
              setLocation(coords);
              setIsWaitingForLocation(false);
              sendMessage(
                "📍 Here is my current location.",
                coords,
                undefined,
                responseMessages,
                data.specialty_needed,
                resolvedSessionId
              );
              // Refresh sidebar AFTER the full flow (location reply) is triggered
              fetchSessions(userIdRef.current);
            },
            (err) => {
              console.warn("Location permission denied or error:", err);
              setIsWaitingForLocation(false);
              setIsLoading(false);
              // Still refresh sidebar so the session appears even if location was denied
              fetchSessions(userIdRef.current);
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
          content:
            "Sorry, I encountered an error. Please ensure the backend is running.",
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
    const triggerMsg = `I want to book an appointment at ${clinic.name}`;
    sendMessage(triggerMsg, undefined, clinic);
  };

  const handleNewChat = () => {
    setCurrentSessionId(null);
    setMessages([]);
    setLocation(null);
    setSelectedClinic(null);
    setCurrentBooking(null);
    setBookingConfirmed(false);
    setBookingId(null);
    setSpecialtyNeeded(null);
    if (isMobile) setIsSidebarOpen(false);
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
      const response = await fetch(`${API_BASE_URL}/api/sessions/${sessionId}`, {
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
    <div className="h-full flex overflow-hidden" style={{ background: "var(--bg-primary)" }}>
      {/* Overlay for mobile when sidebar is open */}
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
          onBookAppointment={handleBookAppointment}
        />

        <ChatInput
          input={input}
          onInputChange={setInput}
          onSubmit={handleSubmit}
          isLoading={isLoading}
          placeholder={isWaitingForLocation ? "Waiting for location permission..." : "Message Medical Assistant..."}
        />
      </div>
    </div>
  );
}
