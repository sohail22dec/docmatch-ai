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

// Use environment variable for production, fallback to local for dev
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function ChatLayout() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [sessions, setSessions] = useState<Session[]>([]);
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null);
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
      const response = await fetch(`${API_BASE_URL}/api/sessions`);
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
    clinicToSelect?: any // New parameter for direct booking trigger
  ) => {
    if (!messageContent.trim() || isLoading) return;

    const userMessage: Message = { role: "user", content: messageContent };
    const newMessages = [...messages, userMessage];

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
      const response = await fetch(`${API_BASE_URL}/api/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: currentSessionId,
          messages: newMessages,
          latitude: latToSend,
          longitude: lngToSend,
          selected_clinic: updatedSelectedClinic,
          current_booking: currentBooking,
          booking_confirmed: bookingConfirmed,
          booking_id: bookingId
        }),
      });

      if (!response.ok) throw new Error("Failed to fetch response");

      const data = await response.json();

      setMessages([
        ...newMessages,
        { role: "assistant", content: data.response },
      ]);

      // Update booking state from backend response
      setSelectedClinic(data.selected_clinic);
      setCurrentBooking(data.current_booking);
      setBookingConfirmed(data.booking_confirmed);
      setBookingId(data.booking_id);

      if (!currentSessionId && data.session_id) {
        setCurrentSessionId(data.session_id);
        fetchSessions();
      }

      // AUTO-TRIGGER LOCATION: If backend asks for location, trigger browser prompt
      if (data.action === "request_location" && !latToSend) {
        if (navigator.geolocation) {
          setIsLoading(true); // Start loading BEFORE the prompt shows
          navigator.geolocation.getCurrentPosition(
            (pos) => {
              const coords = { lat: pos.coords.latitude, lng: pos.coords.longitude };
              setLocation(coords);
              // sendMessage will handle resetting isLoading finally
              sendMessage("📍 Location shared automatically", coords);
            },
            (err) => {
              console.warn("Location permission denied or error:", err);
              setIsLoading(false); // Stop loading if denied or error
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
        />
      </div>
    </div>
  );
}
