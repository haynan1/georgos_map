const relative = new Intl.RelativeTimeFormat("pt-BR", { numeric: "auto" });
const dateTime = new Intl.DateTimeFormat("pt-BR", { dateStyle: "medium", timeStyle: "short" });
const date = new Intl.DateTimeFormat("pt-BR", { dateStyle: "long" });

const UNITS: [Intl.RelativeTimeFormatUnit, number][] = [
  ["year", 31_536_000],
  ["month", 2_592_000],
  ["week", 604_800],
  ["day", 86_400],
  ["hour", 3_600],
  ["minute", 60],
];

export function formatRelative(iso: string, now: Date = new Date()): string {
  const seconds = Math.round((new Date(iso).getTime() - now.getTime()) / 1000);
  for (const [unit, size] of UNITS) {
    if (Math.abs(seconds) >= size) {
      return relative.format(Math.round(seconds / size), unit);
    }
  }
  return "agora mesmo";
}

export function formatDateTime(iso: string): string {
  return dateTime.format(new Date(iso));
}

export function formatDate(iso: string): string {
  return date.format(new Date(iso));
}

export function initials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  const first = parts[0]?.[0] ?? "";
  const last = parts.length > 1 ? (parts.at(-1)?.[0] ?? "") : "";
  return (first + last).toUpperCase();
}

export function firstName(name: string): string {
  return name.trim().split(/\s+/)[0] ?? name;
}

type Signature = readonly [pattern: RegExp, label: string];

const BROWSERS: readonly Signature[] = [
  [/Edg\//, "Edge"],
  [/OPR\//, "Opera"],
  [/Firefox\//, "Firefox"],
  [/Chrome\//, "Chrome"],
  [/Safari\//, "Safari"],
];

const SYSTEMS: readonly Signature[] = [
  [/Android/, "Android"],
  [/iPhone|iPad|iPod/, "iOS"],
  [/Windows/, "Windows"],
  [/Mac OS X|Macintosh/, "macOS"],
  [/Linux/, "Linux"],
];

function detect(signatures: readonly Signature[], userAgent: string): string | null {
  return signatures.find(([pattern]) => pattern.test(userAgent))?.[1] ?? null;
}

/** Human-friendly device label from a User-Agent string (no third-party parser needed). */
export function describeDevice(userAgent: string | null): string {
  if (!userAgent) return "Dispositivo desconhecido";
  const browser = detect(BROWSERS, userAgent) ?? "Navegador";
  const system = detect(SYSTEMS, userAgent);
  return system ? `${browser} · ${system}` : browser;
}

export function isMobileDevice(userAgent: string | null): boolean {
  return userAgent ? /Android|iPhone|iPad|iPod|Mobile/.test(userAgent) : false;
}
