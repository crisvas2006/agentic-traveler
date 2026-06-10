"use client";

import { TripBooking } from "@/lib/dashboard-data";
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription } from "@/components/ui/sheet";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import { useState, useEffect } from "react";

interface BookingFormSheetProps {
  booking: Partial<TripBooking> | null;
  onClose: () => void;
  onSave: (updated: Partial<TripBooking>) => void;
}

export function BookingFormSheet({ booking, onClose, onSave }: BookingFormSheetProps) {
  const [formData, setFormData] = useState<Record<string, string | undefined>>({});
  
  useEffect(() => {
    if (booking) {
      // eslint-disable-next-line
      setFormData({
        ...(booking.payload || {}),
        datetime_local: booking.datetime_local,
        confirmation_code: booking.confirmation_code
      });
    }
  }, [booking]);

  if (!booking) return null;

  const handleChange = (key: string, value: string) => {
    setFormData(prev => ({ ...prev, [key]: value }));
  };

  const handleSave = () => {
    const updated: Partial<TripBooking> = {
      ...booking,
      datetime_local: formData.datetime_local,
      confirmation_code: formData.confirmation_code,
      payload: { ...formData }
    };
    // Clean up top-level duplicated keys from payload if needed
    if (updated.payload) {
      delete updated.payload.datetime_local;
      delete updated.payload.confirmation_code;
    }
    onSave(updated);
  };

  const kind = booking.kind || "booking";

  return (
    <Sheet open={!!booking} onOpenChange={(open) => !open && onClose()}>
      <SheetContent className="overflow-y-auto sm:max-w-md">
        <SheetHeader>
          <SheetTitle>Edit {kind.charAt(0).toUpperCase() + kind.slice(1)}</SheetTitle>
          <SheetDescription>Update your booking details.</SheetDescription>
        </SheetHeader>
        
        <div className="grid gap-4 py-4 px-4">
          {kind !== "ground" && (
            <div className="grid grid-cols-4 items-center gap-4">
              <Label htmlFor="confirmation_code" className="text-right text-xs">Confirm Code</Label>
              <Input id="confirmation_code" value={formData.confirmation_code || ""} onChange={(e) => handleChange("confirmation_code", e.target.value)} className="col-span-3" />
            </div>
          )}
          
          {kind === "flight" && (
            <>
              <div className="grid grid-cols-4 items-center gap-4">
                <Label htmlFor="airline" className="text-right text-xs">Airline</Label>
                <Input id="airline" value={formData.airline || ""} onChange={(e) => handleChange("airline", e.target.value)} className="col-span-3" />
              </div>
              <div className="grid grid-cols-4 items-center gap-4">
                <Label htmlFor="number" className="text-right text-xs">Flight No.</Label>
                <Input id="number" value={formData.number || ""} onChange={(e) => handleChange("number", e.target.value)} className="col-span-3" />
              </div>
              <div className="grid grid-cols-4 items-center gap-4">
                <Label htmlFor="from_" className="text-right text-xs">From</Label>
                <Input id="from_" value={formData.from_ || ""} onChange={(e) => handleChange("from_", e.target.value)} className="col-span-3" />
              </div>
              <div className="grid grid-cols-4 items-center gap-4">
                <Label htmlFor="to" className="text-right text-xs">To</Label>
                <Input id="to" value={formData.to || ""} onChange={(e) => handleChange("to", e.target.value)} className="col-span-3" />
              </div>
            </>
          )}

          {kind === "accommodation" && (
            <>
              <div className="grid grid-cols-4 items-center gap-4">
                <Label htmlFor="name" className="text-right text-xs">Name</Label>
                <Input id="name" value={formData.name || ""} onChange={(e) => handleChange("name", e.target.value)} className="col-span-3" />
              </div>
              <div className="grid grid-cols-4 items-center gap-4">
                <Label htmlFor="address" className="text-right text-xs">Address</Label>
                <Input id="address" value={formData.address || ""} onChange={(e) => handleChange("address", e.target.value)} className="col-span-3" />
              </div>
              <div className="grid grid-cols-4 items-center gap-4">
                <Label htmlFor="check_in" className="text-right text-xs">Check In</Label>
                <Input id="check_in" value={formData.check_in || ""} onChange={(e) => handleChange("check_in", e.target.value)} className="col-span-3" />
              </div>
              <div className="grid grid-cols-4 items-center gap-4">
                <Label htmlFor="check_out" className="text-right text-xs">Check Out</Label>
                <Input id="check_out" value={formData.check_out || ""} onChange={(e) => handleChange("check_out", e.target.value)} className="col-span-3" />
              </div>
            </>
          )}

          {kind === "ground" && (
            <>
              <div className="grid grid-cols-4 items-center gap-4">
                <Label htmlFor="from_" className="text-right text-xs">From</Label>
                <Input id="from_" value={formData.from_ || ""} onChange={(e) => handleChange("from_", e.target.value)} className="col-span-3" />
              </div>
              <div className="grid grid-cols-4 items-center gap-4">
                <Label htmlFor="to" className="text-right text-xs">To</Label>
                <Input id="to" value={formData.to || ""} onChange={(e) => handleChange("to", e.target.value)} className="col-span-3" />
              </div>
              <div className="grid grid-cols-4 items-center gap-4">
                <Label htmlFor="datetime_local" className="text-right text-xs">Date/Time</Label>
                <Input id="datetime_local" value={formData.datetime_local || ""} onChange={(e) => handleChange("datetime_local", e.target.value)} className="col-span-3" />
              </div>
            </>
          )}

          {(kind === "restaurant" || kind === "activity") && (
            <>
              <div className="grid grid-cols-4 items-center gap-4">
                <Label htmlFor="name" className="text-right text-xs">Name</Label>
                <Input id="name" value={formData.name || ""} onChange={(e) => handleChange("name", e.target.value)} className="col-span-3" />
              </div>
              <div className="grid grid-cols-4 items-center gap-4">
                <Label htmlFor="datetime_local" className="text-right text-xs">Date/Time</Label>
                <Input id="datetime_local" value={formData.datetime_local || ""} onChange={(e) => handleChange("datetime_local", e.target.value)} className="col-span-3" />
              </div>
              <div className="grid grid-cols-4 items-center gap-4">
                <Label htmlFor="reservation_status" className="text-right text-xs">Status</Label>
                <Input id="reservation_status" value={formData.reservation_status || ""} onChange={(e) => handleChange("reservation_status", e.target.value)} className="col-span-3" />
              </div>
            </>
          )}

          <div className="grid grid-cols-4 items-start gap-4">
            <Label htmlFor="notes" className="text-right text-xs pt-2">Notes</Label>
            <Textarea id="notes" value={formData.notes || ""} onChange={(e) => handleChange("notes", e.target.value)} className="col-span-3 h-32" />
          </div>
        </div>
        
        <div className="flex justify-end mt-4 px-4 pb-4">
          <Button onClick={handleSave}>Save changes</Button>
        </div>
      </SheetContent>
    </Sheet>
  );
}
