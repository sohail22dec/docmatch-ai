"use client";

import { useState } from "react";
import type { FormEvent, ReactNode } from "react";
import { CalendarDays, Clock, Mail, Phone, User, X } from "lucide-react";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const TIME_SLOTS = [
  "09:00 AM",
  "10:00 AM",
  "11:00 AM",
  "12:00 PM",
  "02:00 PM",
  "03:00 PM",
  "04:00 PM",
  "05:00 PM",
];

type BookingModalProps = {
  clinic: any;
  sessionId: string | null;
  specialty: string | null;
  onClose: () => void;
  onBooked: (booking: any) => void;
  onBookingFailed?: (error: string) => void;
};

export default function BookingModal({
  clinic,
  sessionId,
  specialty,
  onClose,
  onBooked,
  onBookingFailed,
}: BookingModalProps) {
  const [patientName, setPatientName] = useState("");
  const [patientEmail, setPatientEmail] = useState("");
  const [patientPhone, setPatientPhone] = useState("");
  const [appointmentDate, setAppointmentDate] = useState("");
  const [timeSlot, setTimeSlot] = useState(TIME_SLOTS[0]);
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const clinicId = clinic?.id || clinic?.place_id || clinic?.name || "";
  const clinicName = clinic?.name || "Selected clinic";
  const clinicAddress = clinic?.address || null;

  const submitBooking = async (event: FormEvent) => {
    event.preventDefault();
    setError(null);
    setIsSubmitting(true);

    try {
      const response = await fetch(`${API_BASE_URL}/api/bookings`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: sessionId,
          clinic_id: clinicId,
          clinic_name: clinicName,
          clinic_address: clinicAddress,
          specialty,
          patient_name: patientName,
          patient_email: patientEmail,
          patient_phone: patientPhone,
          appointment_date: appointmentDate,
          time_slot: timeSlot,
        }),
      });

      const data = await response.json().catch(() => null);
      if (!response.ok) {
        const detail = data?.detail;
        const message =
          detail?.message ||
          detail?.details?.[0]?.message ||
          "Unable to complete the booking.";
        throw new Error(message);
      }

      onBooked(data.booking);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Unable to complete the booking.";
      setError(msg);
      onBookingFailed?.(msg);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center px-4">
      <div
        className="absolute inset-0 bg-black/50 backdrop-blur-sm"
        onClick={onClose}
      />
      <form
        onSubmit={submitBooking}
        className="relative w-full max-w-md rounded-lg border shadow-xl"
        style={{
          background: "var(--bg-primary)",
          borderColor: "var(--border-color)",
          color: "var(--text-primary)",
        }}
      >
        <div
          className="flex items-start justify-between gap-4 border-b px-5 py-4"
          style={{ borderColor: "var(--border-color)" }}
        >
          <div className="min-w-0">
            <h2 className="text-base font-semibold">Book Appointment</h2>
            <p
              className="mt-1 truncate text-sm"
              style={{ color: "var(--text-secondary)" }}
              title={clinicName}
            >
              {clinicName}
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-md p-1.5 transition-colors"
            style={{ color: "var(--text-secondary)" }}
            aria-label="Close booking form"
          >
            <X size={18} />
          </button>
        </div>

        <div className="space-y-4 px-5 py-4">
          <Field icon={<User size={16} />} label="Patient Name">
            <input
              value={patientName}
              onChange={(e) => setPatientName(e.target.value)}
              required
              className="w-full bg-transparent text-sm outline-none"
              placeholder="Full name"
            />
          </Field>

          <Field icon={<Mail size={16} />} label="Email">
            <input
              type="email"
              value={patientEmail}
              onChange={(e) => setPatientEmail(e.target.value)}
              required
              className="w-full bg-transparent text-sm outline-none"
              placeholder="name@example.com"
            />
          </Field>

          <Field icon={<Phone size={16} />} label="Phone Number">
            <input
              value={patientPhone}
              onChange={(e) => setPatientPhone(e.target.value)}
              required
              className="w-full bg-transparent text-sm outline-none"
              placeholder="Contact number"
            />
          </Field>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <Field icon={<CalendarDays size={16} />} label="Appointment Date">
              <input
                type="date"
                value={appointmentDate}
                onChange={(e) => setAppointmentDate(e.target.value)}
                required
                className="w-full bg-transparent text-sm outline-none"
              />
            </Field>

            <Field icon={<Clock size={16} />} label="Time Slot">
              <select
                value={timeSlot}
                onChange={(e) => setTimeSlot(e.target.value)}
                required
                className="w-full bg-transparent text-sm outline-none"
              >
                {TIME_SLOTS.map((slot) => (
                  <option key={slot} value={slot}>
                    {slot}
                  </option>
                ))}
              </select>
            </Field>
          </div>

          {error && (
            <p className="text-sm font-medium text-red-500">{error}</p>
          )}
        </div>

        <div
          className="flex justify-end gap-3 border-t px-5 py-4"
          style={{ borderColor: "var(--border-color)" }}
        >
          <button
            type="button"
            onClick={onClose}
            className="rounded-md border px-4 py-2 text-sm font-semibold"
            style={{
              borderColor: "var(--border-color)",
              color: "var(--text-secondary)",
            }}
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={isSubmitting}
            className="rounded-md px-4 py-2 text-sm font-semibold disabled:opacity-60"
            style={{
              background: "var(--accent)",
              color: "var(--text-on-accent)",
            }}
          >
            {isSubmitting ? "Booking..." : "Book"}
          </button>
        </div>
      </form>
    </div>
  );
}

function Field({
  icon,
  label,
  children,
}: {
  icon: ReactNode;
  label: string;
  children: ReactNode;
}) {
  return (
    <label>
      <span
        className="mb-1.5 block text-xs font-semibold"
        style={{ color: "var(--text-secondary)" }}
      >
        {label}
      </span>
      <span
        className="flex items-center gap-2 rounded-md border px-3 py-2"
        style={{ borderColor: "var(--border-color)" }}
      >
        <span style={{ color: "var(--accent)" }}>{icon}</span>
        {children}
      </span>
    </label>
  );
}
