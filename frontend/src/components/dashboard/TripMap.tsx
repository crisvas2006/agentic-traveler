"use client";

import { useEffect, useRef, useState } from "react";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { getMapStyle } from "@/lib/map-style";
import type { Trip, TripDay } from "@/lib/dashboard-data";
import type { UserProfile } from "@/hooks/useUserProfile";

interface TripMapProps {
  trip?: Trip | null;
  days?: TripDay[];
  activeDayN?: number;
  theme: "light" | "dark";
  userProfile?: UserProfile;
}

export default function TripMap({ trip, days, activeDayN, theme, userProfile }: TripMapProps) {
  const mapContainer = useRef<HTMLDivElement>(null);
  const map = useRef<maplibregl.Map | null>(null);
  const [mapLoaded, setMapLoaded] = useState(false);
  const markersRef = useRef<maplibregl.Marker[]>([]);

  const [visible, setVisible] = useState(false);

  // Initialize Map
  useEffect(() => {
    const timer = setTimeout(() => {
      setVisible(true);
    }, 2000);

    if (!mapContainer.current || map.current) return () => clearTimeout(timer);

    const initialCenter: [number, number] = [0, 20];
    const initialZoom = 1.5;

    const m = new maplibregl.Map({
      container: mapContainer.current,
      style: "https://tiles.openfreemap.org/styles/liberty", // temporary until loaded
      center: initialCenter,
      zoom: initialZoom,
    });

    m.on("load", () => {
      setMapLoaded(true);
    });

    map.current = m;

    return () => {
      clearTimeout(timer);
      m.remove();
      map.current = null;
    };
  }, [trip]);

  // Update style based on theme
  useEffect(() => {
    if (!map.current) return;
    getMapStyle(theme).then((style) => {
      map.current?.setStyle(style);
    });
  }, [theme]);

  // Handle Trip/Day Selection and Markers
  useEffect(() => {
    if (!map.current || !mapLoaded) return;

    // Check prefers-reduced-motion
    const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    // Clear old markers
    markersRef.current.forEach((m) => m.remove());
    markersRef.current = [];

    if (!trip || !trip.destinations || trip.destinations.length === 0) {
      // No trip selected, zoom out to world view
      map.current.flyTo({ center: [0, 20], zoom: 1.5, duration: 2000, animate: !prefersReducedMotion });
      return;
    }

    const destinations = trip.destinations.filter((d) => d.status === "confirmed" && d.coords);
    if (destinations.length === 0) return;

    // Add markers for confirmed destinations
    const bounds = new maplibregl.LngLatBounds();
    let targetDest = destinations[0];

    // Try to match active day to a destination
    if (activeDayN && days && days.length > 0) {
      const activeDay = days.find((d) => d.n === activeDayN);
      if (activeDay) {
        const textToSearch = (activeDay.title + " " + activeDay.blocks.map(b => b.title).join(" ")).toLowerCase();
        const matchedDest = destinations.find(d => textToSearch.includes(d.name.toLowerCase()));
        if (matchedDest) {
          targetDest = matchedDest;
        }
      }
    }

    destinations.forEach((dest, i) => {
      if (!dest.coords) return;
      
      const el = document.createElement("div");
      el.className = "w-6 h-6 rounded-full bg-primary border-2 border-white shadow-lg flex items-center justify-center text-white text-xs font-bold cursor-pointer";
      el.innerText = `${i + 1}`;

      const popupHtml = `
        <div class="p-2 text-sm">
          <div class="font-bold text-base mb-1">${dest.name}</div>
          <a href="https://www.google.com/maps/search/?api=1&query=${dest.coords.lat},${dest.coords.lng}" 
             target="_blank" rel="noopener noreferrer" 
             class="text-primary hover:underline font-medium">
            Open in Google Maps
          </a>
        </div>
      `;

      const popup = new maplibregl.Popup({ offset: 15, closeButton: false }).setHTML(popupHtml);

      const marker = new maplibregl.Marker({ element: el })
        .setLngLat([dest.coords.lng, dest.coords.lat])
        .setPopup(popup)
        .addTo(map.current!);
      
      markersRef.current.push(marker);

      // We use the first dest or a specific one for bounding/focus
      if (dest.id === targetDest.id) {
        if (dest.coords.bbox) {
          bounds.extend([dest.coords.bbox[2], dest.coords.bbox[0]]);
          bounds.extend([dest.coords.bbox[3], dest.coords.bbox[1]]);
        } else {
          bounds.extend([dest.coords.lng, dest.coords.lat]);
        }
      }
    });

    // Fly to target destination bounding box or point
    if (!bounds.isEmpty()) {
      // If it's a single point, set zoom directly
      if (bounds.getNorthEast().toArray().join() === bounds.getSouthWest().toArray().join()) {
        map.current.flyTo({
          center: bounds.getCenter(),
          zoom: 11,
          duration: 2500,
          animate: !prefersReducedMotion,
        });
      } else {
        map.current.fitBounds(bounds, {
          padding: 50,
          duration: 2500,
          maxZoom: 13,
          animate: !prefersReducedMotion,
        });
      }
    }
  }, [trip, activeDayN, mapLoaded, days]);

  return <div ref={mapContainer} className={`absolute inset-0 w-full h-full transition-opacity duration-1000 ${visible ? 'opacity-100' : 'opacity-0'}`} />;
}
