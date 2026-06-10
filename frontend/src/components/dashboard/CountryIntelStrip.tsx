"use client";

import { useState } from "react";
import { formatIntelCard } from "@/lib/intel-render";
import { RefreshCwIcon } from "lucide-react";
import { createClient } from "@/utils/supabase/client";

import { ChevronDownIcon } from "./DashIcons";

interface CountryIntelStripProps {
  tripId: string;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  countryIntel: any[];
  destination?: string;
}

export function CountryIntelStrip({ tripId, countryIntel, destination }: CountryIntelStripProps) {
  const [refreshing, setRefreshing] = useState<Record<string, boolean>>({});
  const [openIsos, setOpenIsos] = useState<Record<string, boolean>>({});

  // If no intel is available, create a dummy entry to show placeholders
  const intelList = countryIntel && countryIntel.length > 0 
    ? countryIntel 
    : [{ iso_country: destination || "Unknown", isPlaceholder: true }];

  const handleRefresh = async (iso: string) => {
    setRefreshing(prev => ({ ...prev, [iso]: true }));
    try {
      const supabase = createClient();
      const { data: { session } } = await supabase.auth.getSession();
      if (!session) return;
      
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8080"}/trips/${tripId}/intel/refresh?iso=${iso}`, {
        method: "POST",
        headers: {
          "Authorization": `Bearer ${session.access_token}`,
        },
      });
      if (res.ok) {
        // Just rely on realtime update to hide the spinner when data changes,
        // or clear it after 10 seconds as a fallback.
        setTimeout(() => {
          setRefreshing(prev => ({ ...prev, [iso]: false }));
        }, 10000);
      } else {
        setRefreshing(prev => ({ ...prev, [iso]: false }));
      }
    } catch (e) {
      setRefreshing(prev => ({ ...prev, [iso]: false }));
    }
  };

  return (
    <div className="mb-4 space-y-4">
      {intelList.map((intel, idx) => {
        const iso = intel.iso_country as string;
        const fetchedAt = intel.fetched_at ? new Date(intel.fetched_at as string).toLocaleDateString() : "Unknown";
        const isOpen = openIsos[iso] || false;
        
        const cards = [
          formatIntelCard("entry", intel.entry),
          formatIntelCard("safety", intel.safety),
          formatIntelCard("health", intel.health),
          formatIntelCard("money", intel.money),
          formatIntelCard("climate", intel.climate_by_month),
          formatIntelCard("connectivity", intel.connectivity)
        ];

        return (
          <div key={`${iso}-${idx}`} className="rounded-xl border border-border overflow-hidden">
            <div
              onClick={() => setOpenIsos(prev => ({ ...prev, [iso]: !prev[iso] }))}
              className="w-full flex items-center justify-between px-3 py-2.5 hover:bg-foreground/[0.03] transition cursor-pointer"
            >
              <span className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground flex-1 text-left">
                Country Intel • {iso}
              </span>
              <div className="flex items-center gap-2">
                {!intel.isPlaceholder && (
                  <>
                    <span className="text-[10px] text-muted-foreground">Last checked: {fetchedAt}</span>
                    <button 
                      onClick={(e) => { e.stopPropagation(); handleRefresh(iso); }}
                      disabled={refreshing[iso]}
                      title="Refresh Intel"
                      className="p-1 rounded-full hover:bg-foreground/5 text-muted-foreground transition-colors disabled:opacity-50"
                    >
                      <RefreshCwIcon className={`w-3 h-3 ${refreshing[iso] ? "animate-spin" : ""}`} />
                    </button>
                  </>
                )}
                <ChevronDownIcon width={14} height={14} className={`text-muted-foreground transition-transform ${isOpen ? "rotate-180" : ""}`} />
              </div>
            </div>
            
            {isOpen && (
              <div className="px-3 pb-3 animate-fade-up">
                <div className="flex gap-2 overflow-x-auto pb-2 scrollbar-primary -mx-2 px-2">
                  {cards.map((card, i) => (
                    <div 
                      key={i} 
                      className="flex-shrink-0 w-[180px] rounded-xl border border-border p-3"
                      style={{ background: "color-mix(in oklab, var(--background) 50%, transparent)" }}
                    >
                      <div className="flex items-center gap-1.5 mb-1.5">
                        <span className="text-sm">{card.icon}</span>
                        <span className="text-xs font-bold">{card.title}</span>
                      </div>
                      <div className="text-xs text-muted-foreground leading-snug line-clamp-3">
                        {card.content}
                      </div>
                      {!intel.isPlaceholder && (
                        <div className="mt-3 space-y-1">
                          <p className="text-[9px] text-muted-foreground/70 italic leading-tight">
                            Verify with official sources before booking.
                          </p>
                          {intel.sources && intel.sources.length > 0 && (
                            <p className="text-[9px] text-muted-foreground/70 truncate">
                              Source: <a href={intel.sources[0]} target="_blank" rel="noreferrer" className="underline hover:text-primary">{intel.sources[0]}</a>
                            </p>
                          )}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
