# Georgos Map

**Onde as máquinas conquistam organização.**

Gestão de frota de máquinas agrícolas — máquinas, manutenção, peças, operação e telemetria,
com o acesso de cada pessoa da equipe sob controle da empresa.

> *γεωργός* — aquele que trabalha a terra.

## Rodando localmente

Pré-requisitos: **Docker Desktop**. (Para rodar ferramentas fora do Docker: Python 3.14 + `uv`,
Node 24 + `pnpm` 12.)

```bash
cp .env.example .env
```

Troque todos os valores `change-me` do `.env` (gere com
`python -c "import secrets; print(secrets.token_hex(32))"`). Depois:

```bash
docker compose up --build
```

| | |
|---|---|
| App (hot reload) | http://localhost:5173 |
| API + docs | http://localhost:8000/api/docs |
| Postgres | `localhost:55432` |

As migrações rodam sozinhas no boot (serviço `migrate`). Os dados ficam no volume `pgdata`.

### Formato de produção

```bash
docker compose -f docker-compose.yml up --build
```

App em http://localhost:8080 — imagens finais, sem reload, containers somente-leitura.

### Dados: backup e restauração

Os dados vivem no volume `pgdata`. **Nunca rode `docker compose down -v`** sem um backup:
o `-v` apaga o volume.

Backup (formato custom, comprimido):

```bash
docker compose exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > backup-$(date +%Y%m%d-%H%M).dump
```

Restauração (sobrescreve o banco atual):

```bash
docker compose exec -T db sh -c 'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists' < backup.dump
```

A role da API é criada só na primeira inicialização do volume (`infra/postgres/initdb`). Se
trocar `APP_DB_PASSWORD` depois, atualize também no banco com `ALTER ROLE`.

## Testes e qualidade

```bash
docker compose run --rm api-test
```

```bash
cd frontend && pnpm test && pnpm typecheck && pnpm lint
```

```bash
cd backend && uv run ruff check . && uv run mypy app tests
```

O CI (`.github/workflows/ci.yml`) roda tudo isso, valida as migrações (upgrade → check → downgrade
→ upgrade), audita dependências e constrói as imagens Docker.

## Documentação

- [ARCHITECTURE.md](ARCHITECTURE.md) — stack, decisões e segurança, com o porquê de cada uma.
- [CONTRIBUTING.md](CONTRIBUTING.md) — como cada dupla adiciona módulos, telas e permissões.
- [AGENTS.md](AGENTS.md) — regras do projeto para Claude Code e Codex.

## Licença

**Software proprietário — todos os direitos reservados.** Ver [LICENSE](LICENSE).

Este repositório é público apenas para visualização. Copiar, executar, modificar,
distribuir, usar como base para outro produto ou para treinar modelos de IA é proibido a
quem não é colaborador autorizado do projeto ([AUTHORS.md](AUTHORS.md)). Contribuições
externas não são aceitas.

## Times

| Dupla | Responsabilidade |
|---|---|
| 01 — Fellipe e Junior | Frontend, UI e UX |
| 02 — Haynan e Matheus | Estrutura, autenticação, sessões, permissões e segurança |
| 03 — Arthur e Luiz | Banco de dados, APIs operacionais e regras de negócio |
