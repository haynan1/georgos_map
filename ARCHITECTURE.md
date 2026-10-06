# Arquitetura — Georgos Map

Sistema web de gestão de frota de máquinas agrícolas, multiempresa. Este documento registra
**o que foi escolhido e por quê**. Toda decisão aqui tem uma razão; "todo mundo usa" não é uma.

```
 Navegador (desktop / celular)
        │  HTTPS, um único domínio
        ▼
 ┌──────────────┐  /api/*   ┌──────────────┐  SQL (role sem privilégio de schema) ┌──────────────┐
 │ web (nginx)  │ ────────▶ │ api (FastAPI)│ ───────────────────────────────────▶ │ PostgreSQL 18│
 │ SPA estática │           │ uvicorn      │                                      │ RLS por empresa│
 └──────────────┘           └──────────────┘                                      └──────────────┘
   rede "edge"                 edge + data                                          rede "data" (interna)
```

## Stack

A stack-base foi definida pelo grupo. As escolhas complementares (marcadas com ✦) são da Dupla 02.

| Camada | Escolha | Por quê |
|---|---|---|
| Frontend | React 19 + TypeScript 7 + Vite 8 | Definido pelo grupo. TS 7 (compilador nativo) torna o typecheck ~10× mais rápido. |
| UI | Tailwind 4 + shadcn/ui | Definido pelo grupo. Componentes copiados para o repo (`src/components/ui`), sem lock-in. |
| Roteamento ✦ | TanStack Router | Rotas, parâmetros e search params 100% tipados; guards (`beforeLoad`) integrados ao cache de dados. |
| Dados no cliente ✦ | TanStack Query | Cache, invalidação e estados de loading/erro sem reinventar. |
| Formulários ✦ | TanStack Form + Zod 4 | Tipagem ponta a ponta, Standard Schema nativo, mesmo ecossistema do Router/Query. |
| Client HTTP ✦ | openapi-fetch + tipos gerados do OpenAPI | O frontend quebra **em tempo de compilação** se o contrato da API mudar. `pnpm gen:api`. |
| Lint/format JS ✦ | Biome | Uma ferramenta em vez de ESLint + Prettier; ~20× mais rápida. |
| Gerenciador JS ✦ | pnpm 12 | Bloqueia scripts de instalação por padrão e exige 3 dias de "idade" de versões novas (`minimumReleaseAge`) — mitiga ataques de supply-chain. |
| Backend | Python 3.14 + FastAPI | Definido pelo grupo. |
| ORM / migrações | SQLAlchemy 2.1 (async) + Alembic | Definido pelo grupo. Driver `asyncpg` (o mais rápido para Postgres em Python). |
| Banco | PostgreSQL 18 | Definido pelo grupo. A v18 traz `uuidv7()` nativo. |
| Python tooling ✦ | uv + ruff + mypy (strict) | `uv` resolve e instala em segundos com lockfile; ruff substitui flake8/isort/black. |
| Hash de senha ✦ | Argon2id (argon2-cffi) | Primeira recomendação da OWASP; resistente a GPU/ASIC. Parâmetros RFC 9106. |
| Mapas | MapLibre GL JS | Definido pelo grupo — entra quando o módulo de telemetria/mapa for construído (não instalado ainda). |

## Decisões de arquitetura

### Sessões no servidor, não JWT
O navegador guarda apenas um token opaco (256 bits) em cookie `HttpOnly` + `Secure` +
`SameSite=Lax` com prefixo `__Host-`. O banco guarda só o **SHA-256** do token.

- **Revogação imediata**: logout, "encerrar outras sessões", troca de senha e remoção de
  membro derrubam o acesso na hora. Com JWT isso exige blacklist — ou seja, sessão no servidor
  de qualquer forma.
- **Listagem de dispositivos**: a tela de Segurança mostra cada sessão ativa.
- **Expiração dupla**: inatividade (24h) e absoluta (14 dias), configuráveis.
- **Custo**: uma consulta indexada por requisição, que também carrega usuário, empresa e papel.
  `last_seen_at` só é gravado no máximo uma vez por minuto.

### CSRF
Defesa em três camadas: (1) cookie `SameSite=Lax`; (2) token sincronizador por sessão
(HMAC do id da sessão) enviado no header `X-CSRF-Token` em toda requisição que altera estado,
mantido só em memória no frontend; (3) middleware que rejeita requisições cross-site por
`Origin`/`Sec-Fetch-Site` — isso também protege login e cadastro contra *login CSRF*.

### Multiempresa (multi-tenant) com isolamento em duas camadas
- **Usuário é global; acesso é por vínculo** (`memberships`). Uma pessoa pode ser admin em uma
  empresa e leitora em outra, e trocar de empresa sem sair.
- **Camada de aplicação**: toda consulta de dados de negócio filtra pela empresa da sessão.
- **Camada de banco (Row-Level Security)**: tabelas de negócio recebem uma policy que compara
  `organization_id` com `app.organization_id`, setado **por transação** (`set_config(..., true)`).
  A API conecta com uma role **sem privilégio de schema e sem BYPASSRLS** — se alguém esquecer
  um filtro, o resultado é zero linhas, nunca dados de outra empresa. Sem empresa vinculada,
  o padrão é falhar fechado.
  Ver `backend/app/db/rls.py` e o teste `test_row_level_security_isolates_tenants`.

### Privilégio mínimo no banco
| Role | Usada por | Pode |
|---|---|---|
| `POSTGRES_USER` (owner) | container `migrate` (one-shot) | DDL — criar/alterar tabelas |
| `APP_DB_USER` | API em runtime | Apenas `SELECT/INSERT/UPDATE/DELETE`. Em `audit_events`, só `INSERT/SELECT` |

O container da API **nunca recebe** a credencial de owner. A trilha de auditoria é
append-only no nível do banco: nem uma API comprometida consegue reescrevê-la.

### Permissões (RBAC)
Papéis por empresa: `owner > admin > manager > operator > viewer`. As permissões derivam do
papel **em código** (`backend/app/security/permissions.py`) — versionadas, revisadas e testadas.
Regras: ninguém concede papel acima do próprio; só se gerencia quem está abaixo (owners
gerenciam owners); ninguém altera o próprio papel.

### Convites sem infraestrutura de e-mail
O admin gera um link de uso único (7 dias) e envia por onde quiser (WhatsApp incluso). O token
viaja no **fragmento** da URL (`/convite#token`) — o navegador nunca envia fragmentos ao servidor,
então o token não vaza em logs nem em `Referer`. Para contas existentes, aceitar exige a senha.

### Rate limiting no Postgres
Janelas fixas em uma tabela (`rate_limit_buckets`), com chaves pseudonimizadas por HMAC
(nenhum IP ou e-mail em claro). Funciona entre réplicas sem adicionar Redis.
Login: 30 tentativas/15 min por IP e bloqueio da conta após 8 falhas/15 min.

### Contrato de erros único
Toda resposta de erro: `{"error": {"code", "message", "request_id", "fields?"}}`. `code` é estável
para máquinas; `message` é pt-BR para pessoas; validação retorna erros por campo, sem nunca
ecoar o valor enviado (senhas não vazam em logs nem na UI).

### UUIDv7 como chave primária
IDs globais e não sequenciais (não enumeráveis por URL), mas ordenados no tempo: inserts
continuam no fim do índice B-tree, ao contrário do UUIDv4. Também servem como cursor de paginação.

## Segurança — resumo do que já está em vigor

- Argon2id; comparação em tempo constante; hash "fantasma" para e-mails inexistentes (sem
  enumeração por tempo de resposta); mensagens de login idênticas para e-mail ou senha errados.
- Sessão nova a cada login (sem *session fixation*); revogação em troca de senha.
- Headers: CSP restritiva (API: `default-src 'none'`; SPA: só `'self'`), `X-Frame-Options: DENY`,
  `nosniff`, `Referrer-Policy`, COOP, `Permissions-Policy`, HSTS quando em HTTPS.
- `Cache-Control: no-store` em toda resposta da API.
- CORS desligado por padrão (mesma origem); wildcard rejeitado na inicialização.
- Produção recusa subir com `SECRET_KEY` placeholder ou cookie sem `Secure`.
- Proxy sobrescreve `X-Forwarded-For` (cliente não forja IP para burlar rate limit).
- Containers: multi-stage, usuário não-root, `read_only`, `cap_drop: ALL`, `no-new-privileges`;
  banco em rede interna sem rota externa; portas publicadas apenas em `127.0.0.1`.
- Supply-chain: lockfiles commitados, actions fixadas por SHA, Dependabot, `pip-audit` e
  `pnpm audit` no CI, pnpm com scripts bloqueados e idade mínima de releases.

## Estrutura de pastas

```
backend/
  app/
    core/        config, erros, logging, middlewares, schemas base
    db/          base declarativa, sessão + tenant, helper de RLS, registry de models
    security/    senhas, tokens, permissões, rate limit
    modules/     um diretório por domínio: models, schemas, service, router
      auth/          sessões, login, cadastro, senha
      organizations/ empresa, membros, convites, auditoria (leitura)
      audit/         gravação de eventos
      health/        liveness/readiness
    maintenance.py   limpeza periódica de sessões/convites/buckets expirados
  migrations/    Alembic (roda como owner)
  tests/         integração contra Postgres real, como a role de runtime
frontend/
  src/
    routes/      páginas (roteamento por arquivo; _auth = público, _app = autenticado)
    features/    lógica por domínio (auth, organization, shell)
    components/  componentes compartilhados; ui/ = shadcn
    lib/         client da API (tipos gerados), formatação, utilitários
  nginx/         configuração de produção (proxy /api, headers, cache)
infra/postgres/  criação da role de runtime no primeiro boot do banco
```

## Portas (todas em 127.0.0.1)

| Serviço | Dev (`docker compose up`) | Formato produção |
|---|---|---|
| Web | 5173 (Vite, hot reload) | 8080 (nginx) |
| API | 8000 (docs em `/api/docs`) | só pela rede interna, via `/api` do web |
| Postgres | 55432 | não exposto |

## Custo de operação

Sem APIs pagas nem serviços gerenciados obrigatórios. Roda em uma VM de 2 vCPU / 4 GB
(≈ US$ 20–40/mês) para dezenas de empresas. Pontos de atenção de capacidade:

- Login custa ~64 MiB de RAM e ~50–100 ms de CPU por tentativa (Argon2id, proposital).
  O rate limit impede que isso vire vetor de negação de serviço.
- Cada requisição autenticada faz 1 consulta indexada para a sessão.
- Telemetria (Dupla 03) será o primeiro componente de volume real; avaliar particionamento
  por tempo (ou TimescaleDB) quando sair da simulação.

## Atualização de dependências

O Dependabot propõe semanalmente atualizações de bibliotecas (minor/patch agrupadas; majors
uma por PR). **Runtimes não sobem de versão maior automaticamente** — Node, Python, PostgreSQL
e imagens base exigem mudança coordenada:

| Runtime | Regra |
|---|---|
| Node | Só versões **LTS**. Sobe junto: `Dockerfile`, `setup-node` no CI, `engines`, `@types/node` e as máquinas do time. |
| Python | Nova versão (3.x) só após as dependências publicarem wheels; sobe `Dockerfile`, `.python-version`, `requires-python` e ruff/mypy. |
| PostgreSQL | Versão maior exige `pg_upgrade` (ou dump/restore) do volume — nunca só trocar a tag. Backup antes, sempre. |

## Próximos passos de segurança (não implementados ainda)

- Verificação de e-mail e recuperação de senha (requer provedor de e-mail transacional).
- MFA (TOTP/passkeys) — recomendado para owners e admins.
- Verificação de senhas vazadas (HIBP, k-anonymity).
