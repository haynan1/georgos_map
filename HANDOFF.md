# HANDOFF — checkpoint entre sessões

> **Para agentes (Claude Code, Codex):** leia este arquivo inteiro antes de começar. Ao
> terminar a sessão, atualize-o no mesmo PR do trabalho (ver "Protocolo" no fim).
> Para humanos: é o resumo mais rápido de onde o projeto está e do que vem a seguir.

**Último checkpoint:** 2026-10-06 — Dupla 02 (Haynan), sessão com Claude Code.
**`main` em:** `ab4db56` — licença proprietária.

---

## 1. Estado atual (verificado)

| Área | Situação |
|---|---|
| Backend | FastAPI + Postgres 18. Cadastro de empresa, login/logout, sessões no servidor, troca de senha e de empresa, convites, membros/papéis, auditoria. **76 testes**, cobertura 94%. |
| Segurança | RLS por empresa (helper pronto, ainda sem tabela de negócio usando), role de banco com privilégio mínimo, CSRF, rate limit atômico, Argon2id com concorrência limitada, headers/CSP. |
| Frontend | Login, cadastro, convite, visão geral, equipe, segurança, atividade. Client tipado gerado do OpenAPI. **29 testes.** |
| Infra | `docker compose up --build` sobe tudo (dev). Formato produção: `docker compose -f docker-compose.yml up --build`. |
| CI | 3 jobs obrigatórios: Backend, Frontend, Docker images. Actions fixadas por SHA. |
| GitHub | Repo **público**, licença **proprietária** (`LICENSE`, `AUTHORS.md`). `main` protegida: só via PR, CI verde, branch atualizada, histórico linear, sem force push, vale também para admin. Secret scanning + push protection, alertas de vulnerabilidade e reporte privado de falhas ativados. |
| Colaboradores | `haynan1`, `luizhenriquemb071013-beep`, `valthazaar`, `fellipeaugusto-bit`. |
| Aberto | Issue #3 (Node 26 LTS). Nenhuma PR aberta. |

Ainda **não existe** nenhum módulo de negócio (máquinas, manutenção, peças, comercial,
telemetria): isso é da Dupla 03. MapLibre ainda não está instalado.

## 2. Como retomar

```bash
git switch main && git pull
docker compose up --build
docker compose run --rm api-test
cd frontend && pnpm install && pnpm lint && pnpm typecheck && pnpm test
```

App em http://localhost:5173, docs da API em http://localhost:8000/api/docs. Se o `.env` não
existir: `cp .env.example .env` e gere os segredos (ver README). Para entrar localmente,
cadastre uma empresa nova em `/cadastro`.

## 3. Próximos passos (em ordem)

**Decisões/ações humanas pendentes**
1. Subir as aprovações obrigatórias de 0 para 1 agora que há colaboradores. Hoje está em 0,
   ajuste decidido pelo humano:
   `gh api -X PATCH repos/haynan1/georgos_map/branches/main/protection/required_pull_request_reviews -F required_approving_review_count=1`
2. Completar os sobrenomes em `AUTHORS.md` e confirmar quem é cada login de colaborador.
3. Escolher o provedor de e-mail transacional (sugestões: Resend, Postmark, Amazon SES).
   Isso destrava os itens 5 e 6.

**Engenharia — Dupla 02**
4. Issue #3: migrar para Node 26 a partir de **28/10/2026** (checklist na issue).
5. Verificação de e-mail no cadastro. Isso também fecha a enumeração de contas, já que hoje o
   cadastro responde 409 para e-mail existente.
6. Recuperação de senha (token de uso único por e-mail, mesmo padrão dos convites).
7. MFA (TOTP e/ou passkeys), obrigatório para `owner`/`admin`.
8. Checagem de senha vazada (HIBP, k-anonymity) no cadastro e na troca de senha.
9. `CODEOWNERS`: `backend/app/security/`, `backend/app/modules/auth/`, `backend/migrations/`
   e `infra/` exigem revisão da Dupla 02. Depois, ativar "require review from code owners".
10. Política de retenção da trilha de auditoria (LGPD) e paginação real em membros (hoje há
    teto de 500).

**Coordenação**
- Dupla 03: o primeiro módulo de negócio deve seguir o `CONTRIBUTING.md` (tabela com
  `organization_id` + `enable_tenant_isolation` + `require(Permission...)` + teste de
  isolamento entre empresas). A Dupla 02 revisa.
- Dupla 01: tokens de design em `frontend/src/styles/globals.css`, shell em
  `frontend/src/features/shell/`. A evolução de UI é deles.

## 4. Decisões já tomadas (não reabrir sem motivo novo)

Detalhes e motivos em `ARCHITECTURE.md`.
- Sessão no servidor (cookie `__Host-`, HttpOnly), **não** JWT.
- Isolamento em 2 camadas (filtro na aplicação + RLS no Postgres).
- Papéis por empresa e permissões definidas em código (`app/security/permissions.py`).
- Convites por link, com o token no fragmento da URL, sem infraestrutura de e-mail.
- Runtimes (Node/Python/Postgres) **nunca** sobem de versão maior pelo Dependabot.
- Visual: dark-first, Instrument Serif + Geist, um único acento (lima). Sugestões genéricas
  de ferramentas de design (glassmorphism, azul + laranja, "evitar dark") foram descartadas.

## 5. Armadilhas conhecidas

- O CLI do shadcn reescreve `@/lib/utils` como o pacote npm `cn` e o instala. Corrija o
  import e rode `pnpm remove cn` (o Biome bloqueia o import).
- TypeScript 7 não tem API JS: `pnpm gen:api` usa TS 6 via `pnpm dlx`. A API precisa estar
  rodando em `:8000`.
- No FastAPI 0.142, `app.routes` não lista os endpoints (routers são anexados de forma lazy).
  Para enumerar, use `app.openapi()["paths"]`.
- O nginx deve repassar `Host $http_host`, com a porta, senão a guarda de Origin bloqueia o SPA.
- O `email-validator` rejeita domínios `.test`: use domínios realistas em testes manuais.
- Nova migração: `docker compose run --rm migrate alembic revision ...`. Só o container
  `migrate` tem credencial de owner.
- Mudou a API? Rode `pnpm gen:api` e commite `frontend/src/lib/api/schema.gen.ts`.

## 6. Regras de processo

- Nada vai direto para `main`: branch → PR → CI verde → merge com rebase.
- **Agentes não fazem merge sem autorização explícita do humano naquela sessão**
  (o modo automático do Claude Code bloqueia merge sem revisão, e isso é intencional).
- Nunca force push em `main`. Nunca `docker compose down -v` sem backup (README).
- Segredos só no `.env` local, nunca no repositório, que é público.

---

## Protocolo de checkpoint (obrigatório ao fim de toda sessão)

1. Atualize **Último checkpoint**, o commit da `main` e as seções 1, 3 e 5 com o que mudou.
   Apague o que ficou obsoleto: este arquivo descreve o estado atual, não guarda histórico.
2. Acrescente **uma linha** no histórico abaixo.
3. Commite no mesmo PR do trabalho da sessão.

## Histórico de sessões

| Data | Quem | Resumo |
|---|---|---|
| 2026-10-06 | Haynan (D02) + Claude Code | Fundação: auth, sessões, RBAC, RLS, convites, auditoria, frontend, Docker, CI. Repo público com licença proprietária, `main` protegida, política do Dependabot. |
