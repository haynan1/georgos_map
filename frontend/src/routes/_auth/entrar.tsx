import { useForm } from "@tanstack/react-form";
import { useQueryClient } from "@tanstack/react-query";
import { createFileRoute, Link, useRouter } from "@tanstack/react-router";
import { useState } from "react";
import { z } from "zod";
import { FormAlert } from "@/components/form-alert";
import { applyServerErrors, FormField, focusFirstInvalid } from "@/components/form-field";
import { PasswordInput } from "@/components/password-input";
import { SubmitButton } from "@/components/submit-button";
import { FieldGroup } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { AuthHeading } from "@/features/auth/auth-layout";
import { loginSchema } from "@/features/auth/schemas";
import { applySession, safeRedirect } from "@/features/auth/session";
import { api, unwrap } from "@/lib/api/client";
import { errorMessage } from "@/lib/errors";

export const Route = createFileRoute("/_auth/entrar")({
  validateSearch: z.object({ redirect: z.string().optional() }),
  head: () => ({ meta: [{ title: "Entrar · Georgos Map" }] }),
  component: LoginPage,
});

function LoginPage() {
  const { redirect } = Route.useSearch();
  const router = useRouter();
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);

  const form = useForm({
    defaultValues: { email: "", password: "" },
    validators: { onChange: loginSchema },
    onSubmitInvalid: focusFirstInvalid,
    onSubmit: async ({ value, formApi }) => {
      setError(null);
      try {
        const session = await unwrap(
          api.POST("/api/v1/auth/login", {
            body: { email: value.email.trim(), password: value.password },
          }),
        );
        applySession(queryClient, session);
        await router.navigate({ href: safeRedirect(redirect) });
      } catch (caught) {
        if (!applyServerErrors(formApi, caught)) setError(errorMessage(caught));
      }
    },
  });

  return (
    <>
      <AuthHeading
        title="Entrar"
        description="Bem-vindo de volta. Acesse a operação da sua empresa."
      />
      <form
        noValidate
        onSubmit={(event) => {
          event.preventDefault();
          void form.handleSubmit();
        }}
      >
        <FieldGroup className="gap-5">
          <FormAlert message={error} />
          <form.Field name="email">
            {(field) => (
              <FormField field={field} label="E-mail">
                {(control) => (
                  <Input
                    {...control}
                    type="email"
                    autoComplete="username"
                    inputMode="email"
                    autoFocus
                    className="h-11"
                  />
                )}
              </FormField>
            )}
          </form.Field>
          <form.Field name="password">
            {(field) => (
              <FormField field={field} label="Senha">
                {(control) => (
                  <PasswordInput {...control} autoComplete="current-password" className="h-11" />
                )}
              </FormField>
            )}
          </form.Field>
          <form.Subscribe selector={(state) => state.isSubmitting}>
            {(submitting) => <SubmitButton submitting={submitting}>Entrar</SubmitButton>}
          </form.Subscribe>
        </FieldGroup>
      </form>
      <p className="mt-8 text-sm text-muted-foreground">
        Ainda não tem conta?{" "}
        <Link
          to="/cadastro"
          className="font-medium text-foreground underline-offset-4 hover:underline"
        >
          Cadastre sua empresa
        </Link>
      </p>
    </>
  );
}
