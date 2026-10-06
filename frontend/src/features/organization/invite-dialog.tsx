import { useForm } from "@tanstack/react-form";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Check, Copy, MessageCircle } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { z } from "zod";
import { FormAlert } from "@/components/form-alert";
import { applyServerErrors, FormField, focusFirstInvalid } from "@/components/form-field";
import { SubmitButton } from "@/components/submit-button";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Field, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { assignableRoles, ROLE_DESCRIPTION, ROLE_LABEL, type Role } from "@/features/auth/roles";
import { email } from "@/features/auth/schemas";
import { useSession } from "@/features/auth/session";
import { api, type Schemas, unwrap } from "@/lib/api/client";
import { errorMessage } from "@/lib/errors";
import { formatDate } from "@/lib/format";

const inviteSchema = z.object({ email, role: z.string() });

export function InviteDialog({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const [created, setCreated] = useState<Schemas["CreatedInvitationView"] | null>(null);

  const close = (next: boolean) => {
    onOpenChange(next);
    if (!next) setCreated(null);
  };

  return (
    <Dialog open={open} onOpenChange={close}>
      <DialogContent className="sm:max-w-md">
        {created ? (
          <InvitationLink invitation={created} onDone={() => close(false)} />
        ) : (
          <InviteForm onCreated={setCreated} />
        )}
      </DialogContent>
    </Dialog>
  );
}

function InviteForm({
  onCreated,
}: {
  onCreated: (invitation: Schemas["CreatedInvitationView"]) => void;
}) {
  const session = useSession();
  const queryClient = useQueryClient();
  const roles = assignableRoles(session.role);
  const [error, setError] = useState<string | null>(null);

  const invite = useMutation({
    mutationFn: (body: { email: string; role: Role }) =>
      unwrap(api.POST("/api/v1/organization/invitations", { body })),
    onSuccess: async (invitation) => {
      await queryClient.invalidateQueries({ queryKey: ["org", session.organization.id] });
      onCreated(invitation);
    },
  });

  const form = useForm({
    defaultValues: { email: "", role: "operator" as string },
    validators: { onChange: inviteSchema },
    onSubmitInvalid: focusFirstInvalid,
    onSubmit: async ({ value, formApi }) => {
      setError(null);
      try {
        await invite.mutateAsync({ email: value.email.trim(), role: value.role as Role });
      } catch (caught) {
        if (!applyServerErrors(formApi, caught)) setError(errorMessage(caught));
      }
    },
  });

  return (
    <form
      noValidate
      onSubmit={(event) => {
        event.preventDefault();
        void form.handleSubmit();
      }}
    >
      <DialogHeader className="mb-6">
        <DialogTitle className="font-display text-3xl font-normal">Convidar pessoa</DialogTitle>
        <DialogDescription>
          Geramos um link de acesso único, válido por 7 dias, para você enviar como preferir.
        </DialogDescription>
      </DialogHeader>
      <FieldGroup className="gap-5">
        <FormAlert message={error} />
        <form.Field name="email">
          {(field) => (
            <FormField field={field} label="E-mail da pessoa">
              {(control) => (
                <Input
                  {...control}
                  type="email"
                  inputMode="email"
                  autoComplete="off"
                  autoFocus
                  className="h-10"
                />
              )}
            </FormField>
          )}
        </form.Field>
        <form.Field name="role">
          {(field) => (
            <Field>
              <FieldLabel htmlFor="invite-role">Papel</FieldLabel>
              <Select value={field.state.value} onValueChange={field.handleChange}>
                <SelectTrigger id="invite-role" className="h-10 w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {roles.map((role) => (
                    <SelectItem key={role} value={role}>
                      {ROLE_LABEL[role]}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <p className="text-sm text-muted-foreground">
                {ROLE_DESCRIPTION[field.state.value as Role]}
              </p>
            </Field>
          )}
        </form.Field>
      </FieldGroup>
      <DialogFooter className="mt-8">
        <form.Subscribe selector={(state) => state.isSubmitting}>
          {(submitting) => (
            <SubmitButton submitting={submitting} className="mt-0">
              Gerar convite
            </SubmitButton>
          )}
        </form.Subscribe>
      </DialogFooter>
    </form>
  );
}

function InvitationLink({
  invitation,
  onDone,
}: {
  invitation: Schemas["CreatedInvitationView"];
  onDone: () => void;
}) {
  const session = useSession();
  const [copied, setCopied] = useState(false);
  const url = `${window.location.origin}/convite#${invitation.token}`;
  const message = `Você foi convidado para a equipe ${session.organization.name} no Georgos Map: ${url}`;

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(url);
      setCopied(true);
      toast.success("Link copiado.");
    } catch {
      toast.error("Não foi possível copiar. Selecione o link e copie manualmente.");
    }
  };

  return (
    <>
      <DialogHeader className="mb-6">
        <DialogTitle className="font-display text-3xl font-normal">Convite pronto</DialogTitle>
        <DialogDescription>
          Envie este link para <strong className="text-foreground">{invitation.email}</strong>. Por
          segurança, ele só é exibido agora e expira em {formatDate(invitation.expires_at)}.
        </DialogDescription>
      </DialogHeader>
      <div className="flex gap-2">
        <Input
          readOnly
          value={url}
          aria-label="Link do convite"
          onFocus={(event) => event.currentTarget.select()}
          className="h-10 font-mono text-xs"
        />
        <Button
          type="button"
          variant="outline"
          size="icon-lg"
          onClick={copy}
          aria-label="Copiar link"
        >
          {copied ? <Check className="text-success" /> : <Copy />}
        </Button>
      </div>
      <DialogFooter className="mt-8 gap-2 sm:justify-between">
        <Button asChild variant="outline" size="lg">
          <a
            href={`https://wa.me/?text=${encodeURIComponent(message)}`}
            target="_blank"
            rel="noopener noreferrer"
          >
            <MessageCircle aria-hidden="true" />
            Enviar pelo WhatsApp
          </a>
        </Button>
        <Button size="lg" onClick={onDone}>
          Concluir
        </Button>
      </DialogFooter>
    </>
  );
}
