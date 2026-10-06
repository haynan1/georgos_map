import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, api, setCsrfToken, unwrap } from "./client";

function respond(status: number, body: unknown) {
  return vi.fn<typeof fetch>(async () =>
    status === 204
      ? new Response(null, { status })
      : Response.json(body, { status, headers: { "Content-Type": "application/json" } }),
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
  setCsrfToken(null);
});

describe("api client", () => {
  it("sends the CSRF token on state-changing requests only", async () => {
    const fetchMock = respond(204, null);
    vi.stubGlobal("fetch", fetchMock);
    setCsrfToken("token-123");

    await api.POST("/api/v1/auth/logout");
    await api.GET("/api/v1/auth/sessions");

    const [post, get] = fetchMock.mock.calls.map(([request]) => request as Request);
    expect(post?.headers.get("X-CSRF-Token")).toBe("token-123");
    expect(get?.headers.get("X-CSRF-Token")).toBeNull();
  });

  it("never attaches a token after sign-out", async () => {
    const fetchMock = respond(204, null);
    vi.stubGlobal("fetch", fetchMock);
    setCsrfToken(null);

    await api.POST("/api/v1/auth/logout");

    const request = fetchMock.mock.calls[0]?.[0] as Request;
    expect(request.headers.has("X-CSRF-Token")).toBe(false);
  });

  it("turns the error envelope into a typed ApiError", async () => {
    vi.stubGlobal(
      "fetch",
      respond(401, {
        error: {
          code: "invalid_credentials",
          message: "E-mail ou senha incorretos.",
          request_id: "r1",
        },
      }),
    );

    const error = await unwrap(
      api.POST("/api/v1/auth/login", { body: { email: "a@b.com", password: "x" } }),
    ).catch((caught: unknown) => caught);

    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({
      status: 401,
      code: "invalid_credentials",
      message: "E-mail ou senha incorretos.",
      requestId: "r1",
    });
  });

  it("keeps field-level validation issues", async () => {
    vi.stubGlobal(
      "fetch",
      respond(422, {
        error: {
          code: "validation_error",
          message: "Verifique os campos informados.",
          fields: [{ loc: ["body", "email"], message: "Informe um e-mail válido." }],
        },
      }),
    );

    const error = await unwrap(api.GET("/api/v1/auth/session")).catch((caught: unknown) => caught);

    expect((error as ApiError).fields).toEqual([
      { loc: ["body", "email"], message: "Informe um e-mail válido." },
    ]);
  });

  it("reports network failures in plain language", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => {
        throw new TypeError("Failed to fetch");
      }),
    );

    await expect(unwrap(api.GET("/api/v1/auth/session"))).rejects.toMatchObject({
      status: 0,
      code: "network_error",
    });
  });
});
