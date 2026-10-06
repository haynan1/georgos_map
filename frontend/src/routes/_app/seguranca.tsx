import { useForm } from "@tanstack/react-form";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import { Monitor, Smartphone } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { z } from "zod";
import { FormAlert } from "@/components/form-alert";
import { applyServerErrors, FormField, focusFirstInvalid } from "@/components/form-field";
import { PageHeader, Section } from "@/components/page-header";
import { PasswordInput } from "@/components/password-input";
import { SubmitButton } from "@/components/submit-button";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { FieldGroup } from "@/components/ui/field";
import { Skeleton } from "@/components/ui/skeleton";
import { PasswordHint } from "@/features/auth/password-hint";
import { newPassword } from "@/features/auth/schemas";
import { useSession } from "@/features/auth/session";
import { activeSessionsQuery } from "@/features/organization/queries";
import { api, type Schemas, unwrap } from "@/lib/api/client";
import { errorMessage } from "@/lib/errors";
import { describeDevice, formatRelative, isMobileDevice } from "@/lib/format";

export const Route = createFileRoute("/_app/seguranca")({
  head: () => ({ meta: [{ title: "Segurança · Georgos Map" }] }),
  component: SecurityPage,
});

function SecurityPage() {
  const session = useSession();
  return (
    <>
      <PageHeader
        eyebrow={session.user.email}
        title="Segurança"
        description="Sua senha e os dispositivos conectados à sua conta."
      />
      <SessionsSection />
      <PasswordSection />
    </>
  );
}

function SessionsSection() {
  const queryClient = useQueryClient();
  const sessions = useQuery(activeSessionsQuery);
  const others = sessions.data?.filter((item) => !item.current).length ?? 0;
  const refresh = () => queryClient.invalidateQueries({ queryKey: activeSessionsQuery.queryKey });

  const revokeOthers = useMutation({
    mutationFn: () => unwrap(api.POST("/api/v1/auth/sessions/revoke-others")),
    onSuccess: async () => {
      await refresh();
      toast.success("Os outros dispositivos foram desconectados.");
    },
    onError: (error) => toast.error(errorMessage(error)),
  });

  return (
    <Section
      title="Sessões ativas"
      description="Encerre qualquer sessão que você não reconheça."
      actions={
        others > 0 && (
          <Button
            variant="outline"
            size="sm"
            disabled={revokeOthers.isPending}
            onClick={() => revokeOthers.mutate()}
          >
            Encerrar as outras {others}
          </Button>
        )
      }
    >
      <ul className="divide-y overflow-hidden rounded-xl border bg-card">
        {sessions.data
          ? sessions.data.map((item) => (
              <SessionRow key={item.id} item={item} onRevoked={refresh} />
            ))
          : [0, 1].map((row) => (
              <li key={row}>
                <Skeleton className="h-[4.25rem] rounded-none" />
              </li>
            ))}
      </ul>
    </Section>
  );
}

function SessionRow({
  item,
  onRevoked,
}: {
  item: Schemas["ActiveSessionView"];
  onRevoked: () => Promise<void>;
}) {
  const DeviceIcon = isMobileDevice(item.user_agent) ? Smartphone : Monitor;
  const revoke = useMutation({
    mutationFn: () =>
      unwrap(
        api.DELETE("/api/v1/auth/sessions/{session_id}", {
          params: { path: { session_id: item.id } },
        }),
      ),
    onSuccess: async () => {
      await onRevoked();
      toast.success("Sessão encerrada.");
    },
    onError: (error) => toast.error(errorMessage(error)),
  });

  return (
    <li className="flex flex-wrap items-center gap-x-4 gap-y-2 px-5 py-4">
      <span className="flex size-9 items-center justify-center rounded-lg border bg-background">
        <DeviceIcon className="size-4 text-muted-foreground" aria-hidden="true" />
      </span>
      <div className="min-w-0 flex-1">
        <p className="flex items-center gap-2 text-sm font-medium">
          {describeDevice(item.user_agent)}
          {item.current && (
            <Badge className="border-primary/30 bg-primary/10 font-normal text-primary">
              Este dispositivo
            </Badge>
          )}
        </p>
        <p className="mt-0.5 font-mono text-xs text-subtle-foreground">
          {item.ip_address ?? "IP desconhecido"} · ativo {formatRelative(item.last_seen_at)}
        </p>
      </div>
      {!item.current && (
        <Button
          variant="ghost"
          size="sm"
          disabled={revoke.isPending}
          onClick={() => revoke.mutate()}
          className="text-muted-foreground hover:text-destructive"
        >
          Encerrar
        </Button>
      )}
    </li>
  );
}

const passwordSchema = z
  .object({
    current_password: z.string().min(1, "Informe sua senha atual."),
    new_password: newPassword,
  })
  .refine((value) => value.current_password !== value.new_password, {
    message: "A nova senha precisa ser diferente da atual.",
    path: ["new_password"],
  });

function PasswordSection() {
  const session = useSession();
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);

  const form = useForm({
    defaultValues: { current_password: "", new_password: "" },
    validators: { onChange: passwordSchema },
    onSubmitInvalid: focusFirstInvalid,
    onSubmit: async ({ value, formApi }) => {
      setError(null);
      try {
        await unwrap(api.POST("/api/v1/auth/password", { body: value }));
        formApi.reset();
        await queryClient.invalidateQueries({ queryKey: activeSessionsQuery.queryKey });
        toast.success("Senha alterada. Os outros dispositivos foram desconectados.");
      } catch (caught) {
        if (!applyServerErrors(formApi, caught)) setError(errorMessage(caught));
      }
    },
  });

  return (
    <Section
      title="Senha"
      description="Ao alterar a senha, todos os outros dispositivos são desconectados."
    >
      <form
        noValidate
        className="max-w-md rounded-xl border bg-card p-6"
        onSubmit={(event) => {
          event.preventDefault();
          void form.handleSubmit();
        }}
      >
        <input type="email" hidden readOnly autoComplete="username" value={session.user.email} />
        <FieldGroup className="gap-5">
          <FormAlert message={error} />
          <form.Field name="current_password">
            {(field) => (
              <FormField field={field} label="Senha atual">
                {(control) => <PasswordInput {...control} autoComplete="current-password" />}
              </FormField>
            )}
          </form.Field>
          <form.Field name="new_password">
            {(field) => (
              <FormField
                field={field}
                label="Nova senha"
                description={<PasswordHint value={field.state.value} />}
              >
                {(control) => <PasswordInput {...control} autoComplete="new-password" />}
              </FormField>
            )}
          </form.Field>
          <form.Subscribe selector={(state) => state.isSubmitting}>
            {(submitting) => (
              <SubmitButton submitting={submitting} className="w-auto self-start">
                Alterar senha
              </SubmitButton>
            )}
          </form.Subscribe>
        </FieldGroup>
      </form>
    </Section>
  );
}
