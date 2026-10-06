# Contribuindo

## Fluxo

1. Branch a partir de `main`: `feat/...`, `fix/...`, `chore/...`.
2. Commits pequenos, mensagem no imperativo (`Add machine registry`).
3. Pull request com o CI verde. Nada entra em `main` sem revisão de outra dupla.

## Backend — adicionando um módulo de negócio (Dupla 03)

Exemplo: máquinas.

**1. Modelo** em `backend/app/modules/machines/models.py`. Toda tabela de negócio tem
`organization_id`:

```python
class Machine(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "machines"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(120))
```

Registre o model em `app/db/registry.py`.

**2. Migração** — gere e **revise** o arquivo:

```bash
docker compose run --rm migrate alembic revision --autogenerate --rev-id 0002 -m "machines"
```

Logo depois do `create_table`, ligue o isolamento por empresa:

```python
from app.db.rls import disable_tenant_isolation, enable_tenant_isolation

def upgrade() -> None:
    op.create_table("machines", ...)
    enable_tenant_isolation("machines")

def downgrade() -> None:
    disable_tenant_isolation("machines")
    op.drop_table("machines")
```

Não é preciso dar `GRANT`: a role da API já recebe permissão em toda tabela nova.

**3. Rotas** — proteja cada endpoint com a permissão adequada. A sessão do banco já chega
vinculada à empresa do usuário:

```python
CanWrite = Annotated[AuthContext, require(Permission.MACHINES_WRITE)]

@router.post("/machines", status_code=201)
async def create_machine(payload: MachineCreate, auth: CanWrite, db: DbSession) -> MachineView:
    machine = Machine(organization_id=auth.organization.id, **payload.model_dump())
    ...
```

Mesmo com RLS, **filtre sempre por `auth.organization.id`** — são duas camadas de proteção,
não uma.

**4. Testes** em `backend/tests/`, contra Postgres real. Inclua sempre um teste provando que a
empresa A não vê dados da empresa B.

**5. Contrato** — depois de mudar a API, regenere os tipos do frontend (com a API rodando):

```bash
cd frontend && pnpm gen:api
```

### Permissões disponíveis

Definidas em `backend/app/security/permissions.py` (espelhadas em
`frontend/src/features/auth/roles.ts`). Precisa de uma nova? Adicione ao enum, à matriz de
papéis e ao teste `test_permission_matrix` — e avise a Dupla 02.

## Frontend — adicionando uma tela (Dupla 01)

- Páginas autenticadas ficam em `src/routes/_app/` (o guard de sessão já está no layout).
- Dados: `useQuery`/`useMutation` com o client tipado `api` de `@/lib/api/client`. Chaves de
  cache de dados da empresa começam com `["org", organizationId, ...]`.
- Esconda ações sem permissão com `hasPermission(session, "...")` — mas lembre que quem
  garante a regra é a API.
- Componentes shadcn: `npx shadcn@4 add <componente>`. **Atenção:** o CLI às vezes reescreve o
  import `@/lib/utils` como o pacote npm `cn` (que não tem nada a ver com o projeto). O Biome
  bloqueia esse import; se aparecer, corrija o import e rode `pnpm remove cn`.
- Formulários: `FormField` + TanStack Form + Zod (veja `src/routes/_auth/entrar.tsx`).
- Tokens de design em `src/styles/globals.css` — nada de cor hex solta em componente.

## Regras inegociáveis

- Nenhum segredo no código ou no compose. Tudo via `.env` (que nunca é commitado).
- Nenhuma tabela de negócio sem `organization_id` + RLS.
- Nenhum endpoint de negócio sem `require(Permission...)`.
- Nenhuma dependência nova sem justificativa no PR.
- Testes acompanham a feature, não vêm "depois".
