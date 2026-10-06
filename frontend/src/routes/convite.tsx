import { useForm } from "@tanstack/react-form";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { createFileRoute, Link, useRouter } from "@tanstack/react-router";
import { LinkIcon } from "lucide-react";
import { useState } from "react";
import { z } from "zod";
import { FormAlert } from "@/components/form-alert";
import { applyServerErrors, FormField, focusFirstInvalid } from "@/components/form-field";
import { PasswordInput } from "@/components/password-input";
import { SubmitButton } from "@/components/submit-button";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { FieldGroup } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { AuthHeading, AuthLayout } from "@/features/auth/auth-layout";
import { PasswordHint } from "@/features/auth/password-hint";
import { ROLE_DESCRIPTION, ROLE_LABEL } from "@/features/auth/roles";
import { newPassword, personName } from "@/features/auth/schemas";
import { applySession } from "@/features/auth/session";
import { ApiError, api, type Schemas, unwrap } from "@/lib/api/client";
import { errorMessage } from "@/lib/errors";
import { formatDate } from "@/lib/format";

/*
 * The invitation token travels in the URL fragment (/convite#<token>): browsers never
 * send fragments to servers, so it cannot leak into access logs or Referer headers.
 * It stays outside the /_auth group on purpose: someone already signed in must still be
 * able to accept an invitation into another company.
 */
export const Route = createFileRoute("/convite")({
  head: () => ({ meta: [{ title: "Convite · Georgos Map" }] }),
  component: InvitationPage,
});

function readToken(): string {
  return window.location.hash.replace(/^#/, "").trim();
}

function InvitationPage() {
  const [token] = useState(readToken);
  const preview = useQuery({
    queryKey: ["invitation-preview", token],
    queryFn: () => unwrap(api.POST("/api/v1/invitations/preview", { body: { token } })),
    enabled: token.length >= 16,
    retry: false,
    staleTime: Number.POSITIVE_INFINITY,
  });

  return (
    <AuthLayout>
      {token.length < 16 || preview.isError ? (
        <UnavailableInvitation
          reason={
            preview.error instanceof ApiError && preview.error.status !== 410
              ? errorMessage(preview.error)
              : null
          }
        />
      ) : preview.data ? (
        <AcceptInvitation token={token} invitation={preview.data} />
      ) : (
        <div className="space-y-4" role="status" aria-busy="true" aria-label="Carregando convite">
          <Skeleton className="h-11 w-3/4" />
          <Skeleton className="h-5 w-full" />
          <Skeleton className="mt-8 h-11 w-full" />
          <Skeleton className="h-11 w-full" />
        </div>
      )}
    </AuthLayout>
  );
}

function UnavailableInvitation({ reason }: { reason: string | null }) {
  return (
    <>
      <div className="mb-6 flex size-11 items-center justify-center rounded-xl border bg-card">
        <LinkIcon className="size-5 text-muted-foreground" aria-hidden="true" />
      </div>
      <AuthHeading
        title="Convite indisponível"
        description={
          reason ??
          "Este link expirou, foi cancelado ou já foi utilizado. Peça um novo convite ao administrador da sua empresa."
        }
      />
      <Button asChild variant="outline" size="xl" className="w-full">
        <Link to="/entrar">Ir para o login</Link>
      </Button>
    </>
  );
}

function AcceptInvitation({
  token,
  invitation,
}: {
  token: string;
  invitation: Schemas["InvitationPreview"];
}) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  const existing = invitation.account_exists;

  const schema = existing
    ? z.object({ full_name: z.string(), password: z.string().min(1, "Informe sua senha.") })
    : z.object({ full_name: personName, password: newPassword });

  const form = useForm({
    defaultValues: { full_name: "", password: "" },
    validators: { onChange: schema },
    onSubmitInvalid: focusFirstInvalid,
    onSubmit: async ({ value, formApi }) => {
      setError(null);
      try {
        const session = await unwrap(
          api.POST("/api/v1/invitations/accept", {
            body: existing
              ? { token, password: value.password }
              : { token, password: value.password, full_name: value.full_name.trim() },
          }),
        );
        applySession(queryClient, session);
        window.history.replaceState(null, "", window.location.pathname);
        await router.navigate({ to: "/" });
      } catch (caught) {
        if (!applyServerErrors(formApi, caught)) setError(errorMessage(caught));
      }
    },
  });

  return (
    <>
      <p className="font-mono text-[0.6875rem] uppercase tracking-[0.24em] text-muted-foreground">
        Convite para a equipe
      </p>
      <h1 className="mt-4 font-display text-[2.75rem] leading-none tracking-[-0.01em] text-balance">
        {invitation.organization_name}
      </h1>
      <div className="mt-5 flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
        <Badge variant="secondary">{ROLE_LABEL[invitation.role]}</Badge>
        <span>{ROLE_DESCRIPTION[invitation.role]}</span>
      </div>
      <dl className="mt-6 grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5 border-y py-4 text-sm">
        <dt className="text-muted-foreground">E-mail</dt>
        <dd className="truncate font-medium">{invitation.email}</dd>
        <dt className="text-muted-foreground">Válido até</dt>
        <dd>{formatDate(invitation.expires_at)}</dd>
      </dl>
      <p className="mt-6 mb-5 text-[0.9375rem] text-muted-foreground">
        {existing
          ? "Você já tem uma conta. Confirme sua senha para entrar nesta empresa."
          : "Crie seu acesso para entrar na empresa."}
      </p>

      <form
        noValidate
        onSubmit={(event) => {
          event.preventDefault();
          void form.handleSubmit();
        }}
      >
        <input type="email" hidden readOnly autoComplete="username" value={invitation.email} />
        <FieldGroup className="gap-5">
          <FormAlert message={error} />
          {!existing && (
            <form.Field name="full_name">
              {(field) => (
                <FormField field={field} label="Seu nome">
                  {(control) => (
                    <Input {...control} autoComplete="name" autoFocus className="h-11" />
                  )}
                </FormField>
              )}
            </form.Field>
          )}
          <form.Field name="password">
            {(field) => (
              <FormField
                field={field}
                label={existing ? "Sua senha" : "Crie uma senha"}
                description={existing ? undefined : <PasswordHint value={field.state.value} />}
              >
                {(control) => (
                  <PasswordInput
                    {...control}
                    autoComplete={existing ? "current-password" : "new-password"}
                    autoFocus={existing}
                    className="h-11"
                  />
                )}
              </FormField>
            )}
          </form.Field>
          <form.Subscribe selector={(state) => state.isSubmitting}>
            {(submitting) => (
              <SubmitButton submitting={submitting}>
                {existing ? "Entrar na empresa" : "Criar acesso"}
              </SubmitButton>
            )}
          </form.Subscribe>
        </FieldGroup>
      </form>
    </>
  );
}
