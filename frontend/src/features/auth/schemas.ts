import { z } from "zod";

/** Client-side rules mirror the API's (app/core/schemas.py); the API re-validates all. */
export const PASSWORD_MIN = 12;
export const PASSWORD_MAX = 128;

export const email = z
  .string()
  .trim()
  .min(1, "Informe seu e-mail.")
  .max(320, "E-mail longo demais.")
  .pipe(z.email("Informe um e-mail válido."));

export const newPassword = z
  .string()
  .min(PASSWORD_MIN, `Use pelo menos ${PASSWORD_MIN} caracteres.`)
  .max(PASSWORD_MAX, `Use no máximo ${PASSWORD_MAX} caracteres.`)
  .refine(
    (value) => value.length < PASSWORD_MIN || value.trim().length > 0,
    "A senha não pode ter apenas espaços.",
  );

export const personName = z
  .string()
  .trim()
  .min(2, "Informe seu nome.")
  .max(120, "Use no máximo 120 caracteres.");

export const organizationName = z
  .string()
  .trim()
  .min(2, "Informe o nome da empresa.")
  .max(120, "Use no máximo 120 caracteres.");

export const loginSchema = z.object({
  email,
  password: z.string().min(1, "Informe sua senha.").max(PASSWORD_MAX),
});

export const registerSchema = z.object({
  organization_name: organizationName,
  full_name: personName,
  email,
  password: newPassword,
});
