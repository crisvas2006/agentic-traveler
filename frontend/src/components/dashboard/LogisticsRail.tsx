"use client";

import { TripBooking } from "@/lib/dashboard-data";
import { BookingCard } from "./BookingCard";
import { Plus } from "lucide-react";
import { Button } from "@/components/ui/button";

interface LogisticsRailProps {
  bookings: TripBooking[];
  onEdit: (booking: TripBooking) => void;
  onAdd: (kind: string) => void;
}

export function LogisticsRail({ bookings, onEdit, onAdd }: LogisticsRailProps) {
  const groups = {
    "Flights": bookings.filter(b => b.kind === "flight"),
    "Stays": bookings.filter(b => b.kind === "accommodation"),
    "Transit": bookings.filter(b => b.kind === "ground"),
    "Restaurants": bookings.filter(b => b.kind === "restaurant"),
    "Activities": bookings.filter(b => b.kind === "activity"),
  };

  return (
    <div className="flex flex-col gap-6 p-4">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold text-slate-900">Logistics</h3>
      </div>
      
      {Object.entries(groups).map(([title, items]) => (
        <div key={title} className="flex flex-col gap-3">
          <h4 className="text-sm font-medium text-slate-700 uppercase tracking-wider">{title}</h4>
          {items.length > 0 ? (
            items.map(booking => (
              <BookingCard key={booking.id} booking={booking} onEdit={onEdit} />
            ))
          ) : (
            <Button variant="ghost" size="sm" className="w-full justify-start text-slate-400 border border-dashed border-slate-200" onClick={() => onAdd(title.toLowerCase())}>
              <Plus className="mr-2 h-4 w-4" /> Add {title.toLowerCase().slice(0, -1)}
            </Button>
          )}
        </div>
      ))}
    </div>
  );
}
