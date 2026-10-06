import { useForm } from "@tanstack/react-form";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { z } from "zod";
import { Input } from "@/components/ui/input";
import { ApiError } from "@/lib/api/client";
import { applyServerErrors, FormField, focusFirstInvalid } from "./form-field";

const schema = z.object({
  email: z.email("Informe um e-mail válido."),
  name: z.string().min(2, "Informe seu nome."),
});

function Harness({ onSubmit }: { onSubmit: (value: z.infer<typeof schema>) => unknown }) {
  const form = useForm({
    defaultValues: { email: "", name: "" },
    validators: { onChange: schema },
    onSubmitInvalid: focusFirstInvalid,
    onSubmit: async ({ value, formApi }) => {
      try {
        await onSubmit(value);
      } catch (error) {
        applyServerErrors(formApi, error);
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
      <form.Field name="name">
        {(field) => (
          <FormField field={field} label="Nome">
            {(control) => <Input {...control} />}
          </FormField>
        )}
      </form.Field>
      <form.Field name="email">
        {(field) => (
          <FormField field={field} label="E-mail" description="Usado para entrar.">
            {(control) => <Input {...control} type="email" />}
          </FormField>
        )}
      </form.Field>
      <button type="submit">Enviar</button>
    </form>
  );
}

describe("FormField", () => {
  it("does not show errors while the user is still typing", async () => {
    const user = userEvent.setup();
    render(<Harness onSubmit={vi.fn()} />);

    await user.type(screen.getByLabelText("E-mail"), "ana@");
    expect(screen.queryByText("Informe um e-mail válido.")).not.toBeInTheDocument();
    expect(screen.getByText("Usado para entrar.")).toBeInTheDocument();

    await user.tab();
    const input = screen.getByLabelText("E-mail");
    expect(await screen.findByText("Informe um e-mail válido.")).toBeInTheDocument();
    expect(input).toHaveAttribute("aria-invalid", "true");
    expect(input).toHaveAttribute("aria-describedby", "field-email-error");
  });

  it("focuses the first invalid field after a failed submit", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();
    render(<Harness onSubmit={onSubmit} />);

    await user.click(screen.getByRole("button", { name: "Enviar" }));

    await waitFor(() => expect(screen.getByLabelText("Nome")).toHaveFocus());
    expect(screen.getByText("Informe seu nome.")).toBeInTheDocument();
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("attaches API validation errors to the matching field and clears them on edit", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn(async () => {
      throw new ApiError(422, "validation_error", "Verifique os campos informados.", [
        { loc: ["body", "email"], message: "Este domínio não é aceito." },
      ]);
    });
    render(<Harness onSubmit={onSubmit} />);

    await user.type(screen.getByLabelText("Nome"), "Ana Souza");
    await user.type(screen.getByLabelText("E-mail"), "ana@fazenda.test");
    await user.click(screen.getByRole("button", { name: "Enviar" }));

    expect(await screen.findByText("Este domínio não é aceito.")).toBeInTheDocument();
    await waitFor(() => expect(screen.getByLabelText("E-mail")).toHaveFocus());

    await user.type(screen.getByLabelText("E-mail"), "x");
    expect(screen.queryByText("Este domínio não é aceito.")).not.toBeInTheDocument();
  });

  it("leaves non-field errors to the caller", () => {
    const form = { state: { values: { email: "" } }, setFieldMeta: vi.fn() };
    const generic = new ApiError(401, "invalid_credentials", "E-mail ou senha incorretos.");
    expect(applyServerErrors(form as never, generic)).toBe(false);
    expect(applyServerErrors(form as never, new Error("boom"))).toBe(false);
    expect(form.setFieldMeta).not.toHaveBeenCalled();
  });
});
