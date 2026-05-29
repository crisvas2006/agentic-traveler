"use client";

import { useMemo } from "react";
import type { TripDay } from "@/lib/dashboard-data";

interface KyotoMapProps {
  days: TripDay[];
  todayN: number;
  activeDayN: number;
  theme: "light" | "dark";
  novelty?: "tame" | "wild";
  weather?: string;
  onSelectPin?: (block: TripDay["blocks"][number]) => void;
}

const PIN = {
  past:   { fill: "color-mix(in oklab, var(--foreground) 35%, transparent)", ring: "transparent", num: "color-mix(in oklab, var(--background) 80%, transparent)" },
  today:  { fill: "var(--primary)", ring: "color-mix(in oklab, var(--primary) 40%, transparent)", num: "#fff" },
  future: { fill: "transparent", ring: "color-mix(in oklab, var(--foreground) 30%, transparent)", num: "color-mix(in oklab, var(--foreground) 55%, transparent)" },
};

function HillRange({ d, opacity = 0.5, theme }: { d: string; opacity?: number; theme: "light" | "dark" }) {
  return (
    <path
      d={d}
      fill={
        theme === "dark"
          ? `rgba(99,102,241,${0.06 + opacity * 0.04})`
          : `rgba(120,113,108,${0.06 + opacity * 0.06})`
      }
    />
  );
}

function ContourLines({ paths, theme }: { paths: string[]; theme: "light" | "dark" }) {
  return (
    <>
      {paths.map((d, i) => (
        <path
          key={i}
          d={d}
          fill="none"
          stroke={theme === "dark" ? "rgba(148,163,184,.18)" : "rgba(100,116,139,.22)"}
          strokeWidth="0.6"
          strokeDasharray="2 3"
        />
      ))}
    </>
  );
}

export function KyotoMap({ days, todayN, activeDayN, onSelectPin, theme, novelty = "tame", weather = "" }: KyotoMapProps) {
  const activeDay = days.find((d) => d.n === activeDayN) || days.find((d) => d.n === todayN);
  const todayBlocks = activeDay?.blocks || [];
  const currentBlock = todayBlocks.find((b) => b.current);

  const routePath = useMemo(() => {
    if (todayBlocks.length < 2) return "";
    const pts = todayBlocks.map((b) => b.pin);
    let p = `M ${pts[0].x} ${pts[0].y}`;
    for (let i = 1; i < pts.length; i++) {
      const a = pts[i - 1], b = pts[i];
      const mx = (a.x + b.x) / 2 + (b.y - a.y) * 0.18;
      const my = (a.y + b.y) / 2 - (b.x - a.x) * 0.18;
      p += ` Q ${mx} ${my} ${b.x} ${b.y}`;
    }
    return p;
  }, [todayBlocks]);

  const bgFill    = theme === "dark" ? "#0a0f1f"              : "#f7f5f0";
  const waterFill = theme === "dark" ? "rgba(56,189,248,.16)" : "rgba(56,189,248,.32)";

  return (
    <svg viewBox="0 0 1000 1000" preserveAspectRatio="xMidYMid slice" className="w-full h-full">
      <defs>
        <radialGradient id="map-vignette" cx="50%" cy="50%" r="80%">
          <stop offset="50%" stopColor={bgFill} stopOpacity="0" />
          <stop offset="100%" stopColor={theme === "dark" ? "#020617" : "#e7e4dc"} stopOpacity="1" />
        </radialGradient>
        <linearGradient id="route-grad" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="var(--primary)" />
          <stop offset="100%" stopColor="#9333ea" />
        </linearGradient>
        {/* Was: <filter id="route-glow"><feGaussianBlur stdDeviation="3"/></filter>
            Removed — SVG filters re-run every frame the path under them
            redraws (and the dashed route below animates continuously). We get
            the same soft glow much cheaper by stacking a wider semi-transparent
            stroke underneath the main path. See the route block below. */}
        <pattern id="paper" x="0" y="0" width="6" height="6" patternUnits="userSpaceOnUse">
          <circle
            cx="1" cy="1" r="0.4"
            fill={theme === "dark" ? "rgba(148,163,184,.06)" : "rgba(120,113,108,.08)"}
          />
        </pattern>
      </defs>

      {/* Base */}
      <rect width="1000" height="1000" fill={bgFill} />
      <rect width="1000" height="1000" fill="url(#paper)" />

      {/* Higashiyama */}
      <HillRange theme={theme} opacity={1}
        d="M 760,0 L 820,80 880,40 940,140 1000,90 1000,520 940,560 980,620 920,680 1000,720 1000,1000 800,1000 760,940 820,880 740,820 800,760 720,720 780,640 720,580 800,520 740,440 800,360 720,300 780,220 720,140 Z" />
      <HillRange theme={theme} opacity={0.6}
        d="M 720,120 L 760,200 700,280 760,360 700,440 760,520 700,600 760,680 700,760 760,840 700,920 720,1000 820,1000 820,80 Z" />

      {/* Arashiyama */}
      <HillRange theme={theme} opacity={1}
        d="M 0,260 L 60,340 120,280 180,360 100,420 160,500 100,580 0,540 Z" />
      <HillRange theme={theme} opacity={0.6}
        d="M 0,500 L 80,580 140,520 200,600 120,680 60,640 0,700 Z" />
      <HillRange theme={theme} opacity={0.5}
        d="M 0,720 L 80,800 40,860 120,900 60,1000 0,1000 Z" />

      <ContourLines theme={theme} paths={[
        "M 780,140 Q 860,160 940,200",
        "M 760,320 Q 880,340 980,380",
        "M 780,560 Q 860,580 980,600",
        "M 20,360 Q 100,360 180,400",
        "M 40,560 Q 120,560 200,600",
      ]} />

      {/* City grid */}
      <g stroke={theme === "dark" ? "rgba(148,163,184,.08)" : "rgba(100,116,139,.14)"} strokeWidth="0.7">
        {Array.from({ length: 14 }).map((_, i) => (
          <line key={`v${i}`} x1={260 + i * 28} y1={180} x2={260 + i * 28} y2={780} />
        ))}
        {Array.from({ length: 18 }).map((_, i) => (
          <line key={`h${i}`} x1={250} y1={200 + i * 33} x2={680} y2={200 + i * 33} />
        ))}
      </g>

      {/* Kamogawa river */}
      <path
        d="M 600,0 C 580,120 600,200 590,300 C 580,400 610,460 595,560 C 580,660 605,740 590,840 C 580,920 600,980 595,1000"
        fill="none" stroke={waterFill} strokeWidth="14" strokeLinecap="round"
      />
      <path
        d="M 600,0 C 580,120 600,200 590,300 C 580,400 610,460 595,560 C 580,660 605,740 590,840 C 580,920 600,980 595,1000"
        fill="none"
        stroke={theme === "dark" ? "rgba(56,189,248,.45)" : "rgba(14,165,233,.5)"}
        strokeWidth="2" strokeLinecap="round"
      />
      <path d="M 590,640 C 640,650 690,670 740,660" fill="none" stroke={waterFill} strokeWidth="6" strokeLinecap="round" />

      {/* District labels */}
      <g
        fontFamily="'Geist Mono', ui-monospace, monospace"
        fontSize="13"
        letterSpacing="1.5"
        fill={theme === "dark" ? "rgba(226,232,240,.5)" : "rgba(51,65,85,.55)"}
        textAnchor="middle"
      >
        <text x="160" y="430" transform="rotate(-15 160 430)">ARASHIYAMA</text>
        <text x="780" y="460" transform="rotate(82 780 460)">HIGASHIYAMA</text>
        <text x="445" y="430">DOWNTOWN</text>
        <text x="650" y="430" fontSize="11" opacity="0.7">GION</text>
        <text x="700" y="740" fontSize="11" opacity="0.7">TOFUKU-JI</text>
        <text x="760" y="800" fontSize="11" opacity="0.7">FUSHIMI</text>
        <text x="450" y="490" fontSize="11" opacity="0.7">NISHIKI</text>
        <text x="595" y="65" fontSize="9" opacity="0.45" letterSpacing="3">⇡ KITAYAMA</text>
        <text x="920" y="780" fontSize="9" opacity="0.55" letterSpacing="2">KIX →</text>
      </g>

      {/* Vignette */}
      <rect width="1000" height="1000" fill="url(#map-vignette)" pointerEvents="none" />

      {/* Rain texture */}
      {weather === "rain" && (
        <g opacity={theme === "dark" ? 0.18 : 0.22}>
          {Array.from({ length: 60 }).map((_, i) => {
            const x = (i * 173) % 1000;
            const y = (i * 97) % 1000;
            return (
              <line
                key={i} x1={x} y1={y} x2={x - 8} y2={y + 16}
                stroke={theme === "dark" ? "#bae6fd" : "#0284c7"} strokeWidth="0.8"
              />
            );
          })}
        </g>
      )}

      {/* Past-day pins */}
      {days.filter((d) => d.status === "past").flatMap((d) =>
        d.blocks.map((b) => (
          <circle key={`${d.n}-${b.id}`} cx={b.pin.x} cy={b.pin.y} r="6" fill={PIN.past.fill} />
        ))
      )}

      {/* Future-day pins */}
      {days.filter((d) => d.status === "future").flatMap((d) =>
        d.blocks.map((b) => (
          <circle
            key={`${d.n}-${b.id}`} cx={b.pin.x} cy={b.pin.y} r="6"
            fill="none" stroke={PIN.future.ring} strokeWidth="1.5" strokeDasharray="2 2"
          />
        ))
      )}

      {/* Route for active day */}
      {routePath && (
        <>
          {/* Soft glow: three stacked semi-transparent strokes replacing the
              old feGaussianBlur filter. Static — no per-frame GPU filter pass. */}
          <path d={routePath} stroke="url(#route-grad)" strokeWidth="16" fill="none"
                opacity="0.10" strokeLinecap="round" />
          <path d={routePath} stroke="url(#route-grad)" strokeWidth="10" fill="none"
                opacity="0.25" strokeLinecap="round" />
          {/* Static dashed route. The previous marching-ants animation
              repainted the SVG (and therefore re-blurred the glass panels)
              every frame for a purely cosmetic effect. */}
          <path d={routePath} stroke="url(#route-grad)" strokeWidth="3" fill="none"
                strokeDasharray="6 6" strokeLinecap="round" strokeLinejoin="round" />
        </>
      )}

      {/* Active-day numbered pins */}
      {todayBlocks.map((b, i) => (
        <g key={b.id} onClick={() => onSelectPin?.(b)} style={{ cursor: "pointer" }}>
          {b.current && (
            <circle cx={b.pin.x} cy={b.pin.y} r="22" fill={PIN.today.ring}
                    className="map-pin-pulse"
                    style={{ transformOrigin: `${b.pin.x}px ${b.pin.y}px` }} />
          )}
          <circle
            cx={b.pin.x} cy={b.pin.y} r="16"
            fill={PIN.today.fill} stroke="#fff" strokeWidth="3"
            style={{ filter: "drop-shadow(0 4px 8px rgba(37,99,235,.4))" }}
          />
          <text
            x={b.pin.x} y={b.pin.y + 5} textAnchor="middle"
            fontFamily="Geist, sans-serif" fontWeight="800" fontSize="14"
            fill={PIN.today.num}
          >
            {i + 1}
          </text>
        </g>
      ))}

      {/* Wild novelty halos — static rings. The SMIL r animation here added
          three continuously-redrawing circles on top of an already-busy SVG
          for very subtle visual benefit. */}
      {novelty === "wild" && currentBlock && (
        <g opacity="0.5">
          {[80, 130, 180].map((r) => (
            <circle
              key={r} cx={currentBlock.pin.x} cy={currentBlock.pin.y} r={r}
              fill="none" stroke="url(#route-grad)" strokeWidth="0.6" strokeDasharray="1 6"
            />
          ))}
        </g>
      )}

      {/* You-are-here marker — CSS-driven blink. */}
      {currentBlock && (
        <g>
          <circle cx={currentBlock.pin.x - 30} cy={currentBlock.pin.y - 30} r="5"
                  fill="#34d399" className="map-here-blink" />
          <text
            x={currentBlock.pin.x - 22} y={currentBlock.pin.y - 26}
            fontFamily="'Geist Mono', monospace" fontSize="10"
            fill={theme === "dark" ? "#34d399" : "#059669"}
            fontWeight="600"
          >
            YOU
          </text>
        </g>
      )}
    </svg>
  );
}
