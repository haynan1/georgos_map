import { describe, expect, it } from "vitest";
import { describeDevice, firstName, formatRelative, initials, isMobileDevice } from "./format";

const CHROME_WINDOWS =
  "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0 Safari/537.36";
const SAFARI_IPHONE =
  "Mozilla/5.0 (iPhone; CPU iPhone OS 19_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/19.0 Mobile/15E148 Safari/604.1";
const EDGE =
  "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0 Safari/537.36 Edg/141.0";

describe("describeDevice", () => {
  it.each([
    [CHROME_WINDOWS, "Chrome · Windows"],
    [SAFARI_IPHONE, "Safari · iOS"],
    [EDGE, "Edge · Windows"],
    [null, "Dispositivo desconhecido"],
  ])("labels %s", (userAgent, label) => {
    expect(describeDevice(userAgent)).toBe(label);
  });

  it("detects phones", () => {
    expect(isMobileDevice(SAFARI_IPHONE)).toBe(true);
    expect(isMobileDevice(CHROME_WINDOWS)).toBe(false);
  });
});

describe("names", () => {
  it("builds initials from first and last name", () => {
    expect(initials("Ana Maria Souza")).toBe("AS");
    expect(initials("  carlos ")).toBe("C");
  });

  it("extracts the first name", () => {
    expect(firstName("Ana Maria Souza")).toBe("Ana");
  });
});

describe("formatRelative", () => {
  const now = new Date("2026-10-06T12:00:00Z");

  it("speaks in pt-BR", () => {
    expect(formatRelative("2026-10-06T11:59:50Z", now)).toBe("agora mesmo");
    expect(formatRelative("2026-10-06T11:00:00Z", now)).toBe("há 1 hora");
    expect(formatRelative("2026-10-05T12:00:00Z", now)).toBe("ontem");
  });
});
