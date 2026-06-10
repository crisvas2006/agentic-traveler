"use client";

import { TripBooking } from "@/lib/dashboard-data";
import { Plane, Bed, Train, Utensils, CalendarDays, MoreVertical } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

interface BookingCardProps {
  booking: TripBooking;
  onEdit: (booking: TripBooking) => void;
}

const KIND_ICONS = {
  flight: Plane,
  accommodation: Bed,
  ground: Train,
  restaurant: Utensils,
  activity: CalendarDays,
  other: CalendarDays,
};

export function BookingCard({ booking, onEdit }: BookingCardProps) {
  const Icon = KIND_ICONS[booking.kind] || CalendarDays;
  const { payload } = booking;
  
  let line1 = "";
  let line2 = "";
  
  if (booking.kind === "flight") {
    line1 = `${payload.airline || "Flight"} ${payload.number || ""} · ${payload.from_ || "Origin"} → ${payload.to || "Dest"}`;
    line2 = payload.depart_local || booking.datetime_local || "";
  } else if (booking.kind === "accommodation") {
    line1 = payload.name || "Hotel";
    line2 = `Check-in: ${payload.check_in || "TBD"}`;
  } else if (booking.kind === "ground") {
    line1 = `Transit · ${payload.from_ || "Origin"} → ${payload.to || "Dest"}`;
    line2 = payload.datetime_local || "";
  } else {
    line1 = payload.name || "Reservation";
    line2 = payload.datetime_local || "";
  }

  return (
    <Card className="flex items-center p-3 gap-3 hover:bg-slate-50 transition-colors">
      <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-slate-100 text-slate-600">
        <Icon className="h-5 w-5" />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-slate-900 truncate">{line1}</p>
        <p className="text-xs text-slate-500 truncate">{line2}</p>
      </div>
      <Button variant="ghost" size="icon" onClick={() => onEdit(booking)}>
        <MoreVertical className="h-4 w-4" />
      </Button>
    </Card>
  );
}
