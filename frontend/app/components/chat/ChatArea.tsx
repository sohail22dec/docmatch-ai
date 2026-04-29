"use client";

import React, { useState, useRef, useEffect } from "react";
import { Bot, Sparkles, MapPin, Star, ExternalLink } from "lucide-react";

type Message = {
  role: "user" | "assistant";
  content: string;
};

interface ChatAreaProps {
  messages: Message[];
  isLoading: boolean;
  onSuggestionClick: (text: string) => void;
  onBookAppointment: (clinic: any) => void;
}

export default function ChatArea({
  messages,
  isLoading,
  onSuggestionClick,
  onBookAppointment,
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
          <MessageRow 
            key={idx} 
            role={msg.role} 
            content={msg.content} 
            onBookAppointment={onBookAppointment}
          />
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

// ---- Components ----

function BookingConfirmationCard({ data }: { data: any }) {
  return (
    <div 
      className="my-4 rounded-2xl overflow-hidden border-2 shadow-lg max-w-sm"
      style={{ 
        background: "var(--bg-secondary)",
        borderColor: "#22c55e" 
      }}
    >
      <div className="bg-green-500 p-3 text-white flex items-center gap-2">
        <Sparkles size={18} />
        <span className="font-bold text-sm text-white">Booking Confirmed</span>
      </div>
      <div className="p-4 space-y-3">
        <div>
           <p className="text-[10px] uppercase font-bold opacity-50" style={{ color: "var(--text-tertiary)" }}>Booking ID</p>
           <p className="text-sm font-mono font-bold" style={{ color: "var(--accent)" }}>{data.id}</p>
        </div>
        <div>
           <p className="text-[10px] uppercase font-bold opacity-50" style={{ color: "var(--text-tertiary)" }}>Clinic</p>
           <p className="text-sm font-bold" style={{ color: "var(--text-primary)" }}>{data.clinic}</p>
           <p className="text-xs opacity-70" style={{ color: "var(--text-secondary)" }}>{data.address}</p>
        </div>
        <div className="grid grid-cols-2 gap-4 pt-1 border-t border-dashed" style={{ borderColor: "var(--border-color)" }}>
           <div>
              <p className="text-[10px] uppercase font-bold opacity-50" style={{ color: "var(--text-tertiary)" }}>Patient</p>
              <p className="text-xs font-semibold" style={{ color: "var(--text-primary)" }}>{data.patient}</p>
           </div>
           <div>
              <p className="text-[10px] uppercase font-bold opacity-50" style={{ color: "var(--text-tertiary)" }}>Appointment</p>
              <p className="text-xs font-semibold" style={{ color: "var(--text-primary)" }}>{data.date} @ {data.time}</p>
           </div>
        </div>
      </div>
    </div>
  );
}

function ClinicCard({ 
  name, 
  rating, 
  address, 
  onBook 
}: { 
  name: string; 
  rating: string; 
  address: string;
  onBook: () => void;
}) {
  const mapsUrl = `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(name + " " + address)}`;

  return (
    <div 
      className="py-4 border-b last:border-b-0 group transition-all"
      style={{ borderColor: "var(--border-color)" }}
    >
      <div className="flex justify-between items-start gap-4">
        <div className="flex-1 min-w-0">
          <h3 className="font-bold text-sm mb-1" style={{ color: "var(--text-primary)" }}>
            {name}
          </h3>
          
          <div className="flex flex-col gap-1 mb-2">
            <div className="flex items-center gap-1 text-yellow-500 text-xs font-bold">
              <Star size={12} fill="currentColor" />
              {rating || "N/A"}
              <span className="ml-2 text-[10px] opacity-40 font-normal" style={{ color: "var(--text-tertiary)" }}>• Verified Clinic</span>
            </div>
            <div className="flex items-start gap-1.5 mt-1" style={{ color: "var(--text-secondary)" }}>
              <MapPin size={13} className="shrink-0 mt-0.5" style={{ color: "var(--accent)" }} />
              <span className="text-xs leading-snug">{address}</span>
            </div>
          </div>
        </div>

        <div className="shrink-0 flex flex-col gap-2">
          <a 
            href={mapsUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center justify-center gap-1 px-3 py-1.5 rounded-lg text-[11px] font-bold transition-all"
            style={{ 
              background: "var(--bg-secondary)",
              color: "var(--accent)",
              border: "1px solid var(--border-color)"
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = "var(--bg-hover)";
              e.currentTarget.style.borderColor = "var(--accent)";
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = "var(--bg-secondary)";
              e.currentTarget.style.borderColor = "var(--border-color)";
            }}
          >
            <ExternalLink size={12} />
            Maps
          </a>
          <button 
            onClick={onBook}
            className="flex items-center justify-center gap-1 px-3 py-1.5 rounded-lg text-[11px] font-bold transition-all cursor-pointer"
            style={{ 
              background: "var(--accent)",
              color: "var(--text-on-accent)",
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.opacity = "0.9";
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.opacity = "1";
            }}
          >
            Book
          </button>
        </div>
      </div>
    </div>
  );
}

function MessageRow({ 
  role, 
  content,
  onBookAppointment 
}: { 
  role: string; 
  content: string;
  onBookAppointment: (clinic: any) => void;
}) {
  const isUser = role === "user";

  // 1. Parse Clinic blocks
  const clinicParts = content.split(/---CLINIC---/);
  const clinicIntro = clinicParts[0].trim();
  
  const clinics = clinicParts.slice(1).map((p) => {
    const [data, rest] = p.split(/---END---/);
    const nameMatch = data.match(/NAME:\s*(.*)/);
    const ratingMatch = data.match(/RATING:\s*(.*)/);
    const addressMatch = data.match(/ADDRESS:\s*(.*)/);
    
    return {
      name: nameMatch?.[1] || "",
      rating: ratingMatch?.[1] || "",
      address: addressMatch?.[1] || "",
      afterText: rest || ""
    };
  });

  // 2. Parse Booking Confirmation blocks
  const bookingParts = content.split(/---BOOKING_CONFIRMED---/);
  const bookingIntro = bookingParts[0].trim();
  
  const bookings = bookingParts.slice(1).map((p) => {
    const [data, rest] = p.split(/---END---/);
    const idMatch = data.match(/ID:\s*(.*)/);
    const clinicMatch = data.match(/CLINIC:\s*(.*)/);
    const addressMatch = data.match(/ADDRESS:\s*(.*)/);
    const patientMatch = data.match(/PATIENT:\s*(.*)/);
    const dateMatch = data.match(/DATE:\s*(.*)/);
    const timeMatch = data.match(/TIME:\s*(.*)/);
    
    return {
      id: idMatch?.[1] || "",
      clinic: clinicMatch?.[1] || "",
      address: addressMatch?.[1] || "",
      patient: patientMatch?.[1] || "",
      date: dateMatch?.[1] || "",
      time: timeMatch?.[1] || "",
      afterText: rest || ""
    };
  });

  // Determine if this is a clinic message or a booking message
  const hasClinics = clinics.length > 0;
  const hasBookings = bookings.length > 0;
  const introText = hasBookings ? bookingIntro : clinicIntro;
  const finalText = hasBookings ? bookings[bookings.length-1].afterText : (hasClinics ? clinics[clinics.length-1].afterText : "");

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
          className="text-sm leading-relaxed"
          style={{ color: "var(--text-primary)" }}
        >
          {introText && <div className="whitespace-pre-wrap mb-3">{introText}</div>}
          
          {hasClinics && (
            <div 
              className="my-3 rounded-xl border p-1 px-4 shadow-sm"
              style={{ 
                background: "var(--bg-secondary)",
                borderColor: "var(--border-color)"
              }}
            >
              {clinics.map((clinic, i) => (
                <ClinicCard 
                  key={i}
                  name={clinic.name} 
                  rating={clinic.rating} 
                  address={clinic.address}
                  onBook={() => onBookAppointment(clinic)} 
                />
              ))}
            </div>
          )}

          {hasBookings && (
            <div className="my-2">
              {bookings.map((booking, i) => (
                <BookingConfirmationCard key={i} data={booking} />
              ))}
            </div>
          )}
          
          {finalText && <div className="whitespace-pre-wrap mt-3">{finalText.trim()}</div>}
        </div>
      </div>
    </div>
  );
}
