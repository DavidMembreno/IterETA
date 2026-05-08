import { useEffect, useState } from "react";

export default function Splash({ onDone }: { onDone: () => void }) {
  const [phase, setPhase] = useState<"idle" | "driving" | "stopped" | "title" | "fadeout">("idle");

  useEffect(() => {
    const t0 = setTimeout(() => setPhase("driving"), 120);
    const t1 = setTimeout(() => setPhase("stopped"), 2800);
    const t2 = setTimeout(() => setPhase("title"), 3400);
    const t3 = setTimeout(() => setPhase("fadeout"), 5000);
    const t4 = setTimeout(() => onDone(), 5700);
    return () => [t0, t1, t2, t3, t4].forEach(clearTimeout);
  }, [onDone]);

  const fadingOut = phase === "fadeout";
  const showPuff  = phase === "stopped" || phase === "title" || phase === "fadeout";
  const showTitle = phase === "title" || phase === "fadeout";

  const translateX =
    phase === "idle"    ? "120vw"
    : phase === "driving" ? "0px"
    : "0px";

  return (
    <div style={{
      position: "fixed",
      inset: 0,
      background: "#f9fafb",
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      zIndex: 9999,
      overflow: "hidden",
      opacity: fadingOut ? 0 : 1,
      transition: fadingOut ? "opacity 0.7s ease" : "none",
    }}>

      {/* Single unified column — car + title together */}
      <div style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        marginTop: "-120px",
      }}>

        {/* Car + puff wrapper */}
        <div style={{ position: "relative" }}>
          <img
            src="/car.png"
            alt="car"
            style={{
              width: 280,
              display: "block",
              transform: `scaleX(-1) translateX(${translateX})`,
              transition: phase === "driving"
                ? "transform 2.6s cubic-bezier(0.16, 1, 0.3, 1)"
                : "none",
            }}
          />

          {/* Exhaust puffs */}
          {showPuff && (
            <div style={{
              position: "absolute",
              right: -10,
              bottom: 30,
              display: "flex",
              gap: 5,
            }}>
              {[0, 1, 2].map((i) => (
                <div key={i} style={{
                  width: 16 + i * 8,
                  height: 16 + i * 8,
                  borderRadius: "50%",
                  background: "rgba(150,150,150,0.35)",
                  filter: "blur(5px)",
                  animation: `puff 1.1s ease ${i * 0.13}s both`,
                }} />
              ))}
            </div>
          )}
        </div>

        {/* Title sits directly under car, no divider */}
        <div style={{
          marginTop: -400,
          textAlign: "center",
          opacity: showTitle ? 1 : 0,
          filter: showTitle ? "blur(0px)" : "blur(14px)",
          transform: showTitle ? "translateY(0)" : "translateY(8px)",
          transition: "opacity 0.6s ease, filter 0.6s ease, transform 0.6s ease",
        }}>
          <h1 style={{
            margin: 0,
            fontSize: 44,
            fontWeight: 800,
            color: "#b91c1c",
            letterSpacing: "-1.5px",
            fontFamily: "system-ui, sans-serif",
          }}>
            IterETA
          </h1>
          <p style={{
            margin: "6px 0 0",
            fontSize: 13,
            color: "#6b7280",
            fontFamily: "system-ui, sans-serif",
          }}>
            Personal Transportation Reliability Platform
          </p>
        </div>

      </div>

      <style>{`
        @keyframes puff {
          0%   { opacity: 0; transform: scale(0.4) translateY(4px); }
          40%  { opacity: 0.7; }
          100% { opacity: 0; transform: scale(1.5) translateY(-20px); }
        }
      `}</style>
    </div>
  );
}