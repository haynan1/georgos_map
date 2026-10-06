import { useForm } from "@tanstack/react-form";
import { useQueryClient } from "@tanstack/react-query";
import { createFileRoute, Link, useRouter } from "@tanstack/react-router";
import { useState } from "react";
import { FormAlert } from "@/components/form-alert";
import { applyServerErrors, FormField, focusFirstInvalid } from "@/components/form-field";
import { PasswordInput } from "@/components/password-input";
import { SubmitButton } from "@/components/submit-button";
import { FieldGroup } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { AuthHeading } from "@/features/auth/auth-layout";
import { PasswordHint } from "@/features/auth/password-hint";
import { registerSchema } from "@/features/auth/schemas";
import { applySession } from "@/features/auth/session";
import { api, unwrap } from "@/lib/api/client";
import { errorMessage } from "@/lib/errors";

export const Route = createFileRoute("/_auth/cadastro")({
  head: () => ({ meta: [{ title: "Criar conta · Georgos Map" }] }),
  component: RegisterPage,
});

function RegisterPage() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);

  const form = useForm({
    defaultValues: { organization_name: "", full_name: "", email: "", password: "" },
    validators: { onChange: registerSchema },
    onSubmitInvalid: focusFirstInvalid,
    onSubmit: async ({ value, formApi }) => {
      setError(null);
      try {
        const session = await unwrap(
          api.POST("/api/v1/auth/register", { body: registerSchema.parse(value) }),
        );
        applySession(queryClient, session);
        await router.navigate({ to: "/" });
      } catch (caught) {
        if (!applyServerErrors(formApi, caught)) setError(errorMessage(caught));
      }
    },
  });

  return (
    <>
      <AuthHeading
        title="Criar conta"
        description="Cadastre sua empresa. Você será o proprietário e poderá convidar a equipe."
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
          <form.Field name="organization_name">
            {(field) => (
              <FormField field={field} label="Nome da empresa">
                {(control) => (
                  <Input {...control} autoComplete="organization" autoFocus className="h-11" />
                )}
              </FormField>
            )}
          </form.Field>
          <form.Field name="full_name">
            {(field) => (
              <FormField field={field} label="Seu nome">
                {(control) => <Input {...control} autoComplete="name" className="h-11" />}
              </FormField>
            )}
          </form.Field>
          <form.Field name="email">
            {(field) => (
              <FormField field={field} label="E-mail">
                {(control) => (
                  <Input
                    {...control}
                    type="email"
                    autoComplete="email"
                    inputMode="email"
                    className="h-11"
                  />
                )}
              </FormField>
            )}
          </form.Field>
          <form.Field name="password">
            {(field) => (
              <FormField
                field={field}
                label="Senha"
                description={<PasswordHint value={field.state.value} />}
              >
                {(control) => (
                  <PasswordInput {...control} autoComplete="new-password" className="h-11" />
                )}
              </FormField>
            )}
          </form.Field>
          <form.Subscribe selector={(state) => state.isSubmitting}>
            {(submitting) => <SubmitButton submitting={submitting}>Criar conta</SubmitButton>}
          </form.Subscribe>
        </FieldGroup>
      </form>
      <p className="mt-8 text-sm text-muted-foreground">
        Já tem conta?{" "}
        <Link
          to="/entrar"
          className="font-medium text-foreground underline-offset-4 hover:underline"
        >
          Entrar
        </Link>
      </p>
    </>
  );
}
