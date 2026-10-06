import { cn } from "@/lib/utils";

/*
 * Procedural topographic field map for the authentication panel.
 *
 * Everything is generated deterministically at module load (no images, no network, no
 * runtime cost per render): contour isolines, cultivated crop rows, a survey grid, and a
 * machine route with live markers. Motion is limited to the route and marker pulses and
 * is disabled under prefers-reduced-motion by the global stylesheet.
 */

const WIDTH = 800;
const HEIGHT = 1000;

function contour(
  cx: number,
  cy: number,
  radius: number,
  seed: number,
  squash = 0.82,
  points = 96,
): string {
  let d = "";
  for (let i = 0; i <= points; i++) {
    const t = (i / points) * Math.PI * 2;
    const wobble =
      1 +
      0.11 * Math.sin(3 * t + seed * 0.45) +
      0.05 * Math.sin(5 * t - seed * 0.8) +
      0.025 * Math.sin(9 * t + seed);
    const x = cx + Math.cos(t) * radius * wobble;
    const y = cy + Math.sin(t) * radius * wobble * squash;
    d += `${i === 0 ? "M" : "L"}${x.toFixed(1)} ${y.toFixed(1)}`;
  }
  return `${d}Z`;
}

const RIDGE = Array.from({ length: 15 }, (_, i) => ({
  d: contour(540, 360, 34 + i * 30, i),
  opacity: 0.2 - i * 0.011,
  major: i % 5 === 4,
}));

const HOLLOW = Array.from({ length: 8 }, (_, i) => ({
  d: contour(150, 780, 26 + i * 26, i + 20, 0.7),
  opacity: 0.14 - i * 0.012,
  major: i % 5 === 4,
}));

// Crop rows inside a tilted field polygon, clipped so they read as a cultivated plot.
const FIELD = "M430 640 L790 560 L800 900 L470 990 Z";
const ROWS = Array.from({ length: 34 }, (_, i) => {
  const offset = i * 13;
  return `M${380 + offset} 1000 C ${420 + offset} 860, ${470 + offset} 720, ${520 + offset} 560`;
});

const ROUTE =
  "M118 268 C 210 300, 260 380, 330 420 S 470 470, 560 520 S 650 640, 610 720 S 560 840, 640 900";

const MACHINES = [
  { x: 330, y: 420, id: "TR-04", status: "12,4 km/h", delay: "0s" },
  { x: 610, y: 720, id: "CH-01", status: "Colheita", delay: "1.1s" },
  { x: 118, y: 268, id: "PL-07", status: "Em pátio", delay: "2.2s" },
];

const GRID_X = Array.from({ length: 7 }, (_, i) => (i + 1) * 100);
const GRID_Y = Array.from({ length: 9 }, (_, i) => (i + 1) * 100);

export function FieldMap({ className }: { className?: string }) {
  return (
    <svg
      viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
      preserveAspectRatio="xMidYMid slice"
      aria-hidden="true"
      className={cn("pointer-events-none select-none", className)}
    >
      <defs>
        <radialGradient id="fm-glow" cx="68%" cy="36%" r="55%">
          <stop offset="0%" stopColor="var(--primary)" stopOpacity="0.07" />
          <stop offset="100%" stopColor="var(--primary)" stopOpacity="0" />
        </radialGradient>
        <linearGradient id="fm-fade" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="var(--background)" stopOpacity="0.15" />
          <stop offset="45%" stopColor="var(--background)" stopOpacity="0" />
          <stop offset="72%" stopColor="var(--background)" stopOpacity="0.55" />
          <stop offset="100%" stopColor="var(--background)" stopOpacity="0.96" />
        </linearGradient>
        <clipPath id="fm-field">
          <path d={FIELD} />
        </clipPath>
      </defs>

      <rect width={WIDTH} height={HEIGHT} fill="url(#fm-glow)" />

      <g stroke="var(--foreground)" strokeOpacity="0.035" strokeWidth="1">
        {GRID_X.map((x) => (
          <line key={`x${x}`} x1={x} y1="0" x2={x} y2={HEIGHT} />
        ))}
        {GRID_Y.map((y) => (
          <line key={`y${y}`} x1="0" y1={y} x2={WIDTH} y2={y} />
        ))}
      </g>

      <g clipPath="url(#fm-field)" stroke="var(--foreground)" strokeOpacity="0.075" fill="none">
        {ROWS.map((d) => (
          <path key={d} d={d} strokeWidth="1.2" />
        ))}
      </g>
      <path d={FIELD} fill="none" stroke="var(--foreground)" strokeOpacity="0.1" />

      <g fill="none" stroke="var(--foreground)">
        {[...RIDGE, ...HOLLOW].map((line) => (
          <path
            key={line.d}
            d={line.d}
            strokeOpacity={Math.max(line.opacity, 0.03)}
            strokeWidth={line.major ? 1.4 : 0.9}
          />
        ))}
      </g>

      <path
        d={ROUTE}
        fill="none"
        stroke="var(--primary)"
        strokeOpacity="0.55"
        strokeWidth="1.5"
        strokeDasharray="2 7"
        strokeLinecap="round"
        className="[animation:route-flow_6s_linear_infinite]"
      />

      {MACHINES.map((machine) => (
        <g key={machine.id} transform={`translate(${machine.x} ${machine.y})`}>
          <circle
            r="14"
            fill="var(--primary)"
            fillOpacity="0.18"
            className="origin-center [animation:marker-pulse_3.3s_ease-out_infinite] [transform-box:fill-box]"
            style={{ animationDelay: machine.delay }}
          />
          <circle r="4" fill="var(--primary)" />
          <circle r="7.5" fill="none" stroke="var(--primary)" strokeOpacity="0.5" />
          <text
            x="16"
            y="-4"
            className="fill-foreground font-mono"
            fontSize="12"
            letterSpacing="1.2"
          >
            {machine.id}
          </text>
          <text x="16" y="12" className="fill-muted-foreground font-mono" fontSize="11">
            {machine.status}
          </text>
        </g>
      ))}

      {/* Survey-grid coordinates, kept on the right edge, clear of the wordmark. */}
      <g
        className="fill-subtle-foreground font-mono"
        fontSize="10"
        letterSpacing="1.5"
        textAnchor="end"
      >
        <text x="784" y="196">
          15°47′S
        </text>
        <text x="784" y="496">
          15°49′S
        </text>
        <text x="784" y="22">
          47°52′W
        </text>
      </g>

      <rect width={WIDTH} height={HEIGHT} fill="url(#fm-fade)" />
    </svg>
  );
}
