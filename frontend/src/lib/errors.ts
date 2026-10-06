import { ApiError } from "@/lib/api/client";

export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  return "Algo deu errado. Tente novamente em instantes.";
}
