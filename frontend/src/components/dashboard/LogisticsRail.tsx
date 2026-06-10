"use client";

import { TripBooking } from "@/lib/dashboard-data";
import { BookingCard } from "./BookingCard";
import { Plus } from "lucide-react";
import { Button } from "@/components/ui/button";

interface LogisticsProps {
  bookings: TripBooking[];
  onEdit: (booking: TripBooking) => void;
  onAdd: (kind: string) => void;
  isOpen: boolean;
  onClose: () => void;
  onOpen?: () => void;
}

export function LogisticsSummary({ bookings, onOpen }: { bookings: TripBooking[], onOpen: () => void }) {
  const groups = {
    "Flights": bookings.filter(b => b.kind === "flight"),
    "Stays": bookings.filter(b => b.kind === "accommodation"),
    "Transit": bookings.filter(b => b.kind === "ground"),
    "Restaurants": bookings.filter(b => b.kind === "restaurant"),
    "Activities": bookings.filter(b => b.kind === "activity"),
  };

  const total = bookings.length;

  return (
    <div className="rounded-xl border border-border p-3.5" style={{ background: "color-mix(in oklab, var(--background) 50%, transparent)" }}>
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-xs font-bold uppercase tracking-[0.14em] text-muted-foreground">Logistics</h3>
        <button onClick={onOpen} className="text-xs font-semibold text-primary hover:underline">
          {total > 0 ? `Manage ${total} bookings` : "Plan logistics"}
        </button>
      </div>
      
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
        {Object.entries(groups).map(([title, items]) => {
          return (
            <button
              key={title}
              onClick={onOpen}
              className="flex items-center gap-2 p-2 rounded-lg border border-dashed border-border/80 hover:bg-foreground/[0.03] hover:border-primary/40 transition-colors text-left"
            >
              {items.length > 0 ? (
                <div className="w-2 h-2 rounded-full bg-primary flex-shrink-0" />
              ) : (
                <Plus className="w-3 h-3 text-muted-foreground flex-shrink-0" />
              )}
              <div className="flex flex-col min-w-0">
                <span className="text-[10px] font-bold text-foreground truncate">{title}</span>
                <span className="text-[9px] text-muted-foreground">
                  {items.length > 0 ? `${items.length} saved` : "Add"}
                </span>
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}

export function LogisticsPanel({ bookings, onEdit, onAdd, isOpen, onClose }: LogisticsProps) {
  if (!isOpen) return null;

  const groups = {
    "Flights": bookings.filter(b => b.kind === "flight"),
    "Stays": bookings.filter(b => b.kind === "accommodation"),
    "Transit": bookings.filter(b => b.kind === "ground"),
    "Restaurants": bookings.filter(b => b.kind === "restaurant"),
    "Activities": bookings.filter(b => b.kind === "activity"),
  };

  return (
    <>
      {/* Mobile backdrop */}
      <div 
        className="fixed inset-0 bg-black/20 z-40 md:hidden backdrop-blur-sm" 
        onClick={onClose} 
      />
      
      {/* Panel */}
      <div className="fixed inset-y-0 right-0 z-50 w-full max-w-sm bg-background border-l border-border shadow-2xl flex flex-col md:absolute md:left-[-380px] md:right-auto md:w-[380px] md:border-r animate-slide-left md:animate-fade-in rounded-none md:rounded-l-2xl">
        <div className="flex items-center justify-between p-4 border-b border-border bg-muted/30">
          <h3 className="text-base font-extrabold tracking-tight">Logistics</h3>
          <button onClick={onClose} className="p-2 -mr-2 rounded-full hover:bg-foreground/5 text-muted-foreground transition">
            <Plus className="w-5 h-5 rotate-45" />
          </button>
        </div>
        
        <div className="flex-1 overflow-y-auto p-4 space-y-6 scrollbar-primary">
          {Object.entries(groups).map(([title, items]) => (
            <div key={title} className="flex flex-col gap-3">
              <h4 className="text-[10px] font-bold text-muted-foreground uppercase tracking-wider flex items-center gap-2">
                <span className="h-px bg-border flex-1"></span>
                {title}
                <span className="h-px bg-border flex-1"></span>
              </h4>
              {items.length > 0 ? (
                items.map(booking => (
                  <BookingCard key={booking.id} booking={booking} onEdit={onEdit} />
                ))
              ) : (
                <Button variant="ghost" size="sm" className="w-full justify-start text-muted-foreground border border-dashed border-border/80 hover:border-primary/40 hover:bg-primary/[0.03]" onClick={() => onAdd(title === "Flights" ? "flight" : title === "Stays" ? "accommodation" : title === "Transit" ? "ground" : title === "Restaurants" ? "restaurant" : "activity")}>
                  <Plus className="mr-2 h-4 w-4" /> Add {title.toLowerCase()}
                </Button>
              )}
            </div>
          ))}
        </div>
      </div>
    </>
  );
}
