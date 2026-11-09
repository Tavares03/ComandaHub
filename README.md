<div align="center">

# 🍔 ComandaHub

**Central de pedidos multi-loja para restaurantes: iFood, 99Food, delivery próprio, retirada e balcão em uma única operação.**

Kanban de pedidos, tela da cozinha, caixa, estoque com ficha técnica, clientes e fidelidade, relatório de lucro por canal e cardápio online, tudo com isolamento por loja e controle de acesso por perfil.

[![CI](https://github.com/Tavares03/ComandaHub/actions/workflows/ci.yml/badge.svg)](https://github.com/Tavares03/ComandaHub/actions/workflows/ci.yml)
![Angular](https://img.shields.io/badge/Angular-18-DD0031?logo=angular&logoColor=white)
![TypeScript](https://img.shields.io/badge/TypeScript-5.5-3178C6?logo=typescript&logoColor=white)
![Tailwind CSS](https://img.shields.io/badge/Tailwind_CSS-3-06B6D4?logo=tailwindcss&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-Python_3.12+-009688?logo=fastapi&logoColor=white)
![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2-D71F00?logo=sqlalchemy&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-17-4169E1?logo=postgresql&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white)
![License](https://img.shields.io/badge/licen%C3%A7a-MIT-green)

<img src="docs/screenshots/central-de-pedidos.png" alt="Central de pedidos em Kanban" width="900" />

</div>

---

## Sumário

- [Visão geral](#visão-geral)
- [Telas](#telas)
- [Funcionalidades](#funcionalidades)
- [Arquitetura](#arquitetura)
- [Como rodar](#como-rodar)
- [Credenciais e roteiro de demonstração](#credenciais-e-roteiro-de-demonstração)
- [Perfis e permissões](#perfis-e-permissões)
- [Configuração](#configuração)
- [API](#api)
- [Testes e qualidade](#testes-e-qualidade)
- [Deploy em produção](#deploy-em-produção)
- [Estrutura do projeto](#estrutura-do-projeto)
- [Decisões técnicas](#decisões-técnicas)
- [Roadmap](#roadmap)
- [Licença](#licença)

## Visão geral

Um restaurante que vende pelo iFood, pelo 99Food, pelo WhatsApp e no balcão costuma operar com vários tablets, papel e planilha. O ComandaHub junta tudo em um só fluxo:

1. **Todo pedido cai na mesma Central**, venha de onde vier, com o mesmo número sequencial do dia.
2. **A cozinha enxerga só o que precisa preparar**, com observações e "sem cebola" destacados.
3. **O estoque baixa sozinho** pela ficha técnica de cada item (inclusive combo e adicionais) e o item **sai do cardápio quando um ingrediente principal acaba**.
4. **O dono vê o lucro real por canal**: vendas − comissão do app − custo dos ingredientes.

É um sistema **multi-tenant**: um usuário pode trabalhar em várias lojas, com um perfil diferente em cada uma, e os dados de uma loja nunca aparecem em outra.

> As integrações com iFood e 99Food funcionam em **modo simulado** pelo *Laboratório de pedidos*: os conectores normalizam pedidos no mesmo formato que a integração oficial usaria (veja `backend/app/connectors`). A conexão real depende das credenciais de cada loja junto aos marketplaces.

## Telas

| Dashboard | Cozinha |
|---|---|
| ![Dashboard](docs/screenshots/dashboard.png) | ![Cozinha](docs/screenshots/cozinha.png) |
| **Pedido local** (pizza meio a meio) | **Cardápio, estoque e ficha técnica** |
| ![Pedido local](docs/screenshots/pedido-local.png) | ![Cardápio](docs/screenshots/cardapio.png) |
| **Relatórios e lucro por canal** | **Cardápio online (celular)** |
| ![Relatórios](docs/screenshots/relatorios.png) | <img src="docs/screenshots/cardapio-online-mobile.png" alt="Cardápio online" width="260" /> |

## Funcionalidades

### Operação
- **Central de pedidos em Kanban**: novos → aceitos → em preparo → prontos → saiu para entrega → finalizados, com transições validadas no backend, aviso sonoro de pedido novo, detalhes, histórico de eventos e impressão de comanda (80 mm).
- **Sino no topo** com a contagem de pedidos aguardando aceite, visível de qualquer tela.
- **Tela da Cozinha** com cards grandes, tempo na fila e ações de preparo.
- **Pedido local** (balcão, retirada e delivery próprio) com busca, filtro por categoria e cálculo de valores **sempre no servidor**.
- **Caixa**: abertura com troco, sangria e reforço, vendas do turno por forma de pagamento e fechamento com diferença apurada.
- **Entregas**: bairros com taxa e tempo estimado, motoboys escolhidos na saída para entrega e relatório de quanto pagar a cada um.

### Cardápio e estoque
- **Personalização de itens** por grupos de escolha: ponto da carne, adicionais, retirar ingredientes, pizza meio a meio, borda (detalhes [abaixo](#personalização-de-itens)).
- **Combo dentro do item**: escolher "Combo" libera acompanhamento e bebida, ligados aos produtos reais do cardápio.
- **Pausa por canal** (iFood, 99Food, Local): pausar só o item ou também dentro dos combos, em uma ou em todas as lojas, com prévia do que vai mudar.
- **Estoque por ingrediente**: ficha técnica, baixa automática nos pedidos, devolução no cancelamento, entrada e contagem com histórico, alerta de estoque baixo e **pausa automática quando zera** (o item volta sozinho quando chega mercadoria).
- **Custo e margem** de cada item a partir da ficha técnica; o custo fica gravado no pedido.
- **Preço por canal** (ex.: mais caro no iFood), com ajuste em lote por percentual e arredondamento para ,90.

### Clientes e vendas
- **Clientes pelo telefone**, com histórico e total gasto.
- **Cupons** (% ou R$, pedido mínimo, validade no fuso da loja e limite de usos).
- **Programa de fidelidade**: cada pedido **finalizado** vale 1 ponto e, ao atingir a meta, o próximo pedido ganha desconto. O resgate é feito pelo atendente.
- **Cardápio online público** em `/cardapio/<loja>`: o cliente monta o pedido (entrega ou retirada), acompanha o status em `/pedido/<código>` e pode mandar o resumo no WhatsApp da loja. A loja pode **fechar para pedidos** sem tirar o cardápio do ar.

### Gestão
- **Dashboard** do dia: pedidos, faturamento, ticket médio, volume por hora e vendas dos últimos 7 dias, tudo no fuso da loja.
- **Relatórios** por período: vendas por canal, produtos mais vendidos e **lucro por canal** (vendas − comissão − custo).
- **Usuários da loja**: adicionar, mudar perfil, redefinir senha e remover acesso. Cada usuário pode trocar a própria senha.
- **Multi-loja**: seletor de loja no topo; um usuário pode ser administrador em uma loja e cozinha em outra.

### Segurança
- Senhas com **bcrypt** e autenticação **JWT**; ao expirar a sessão, o painel volta para o login com aviso, sem deixar telas paradas.
- **Isolamento por loja** em todos os endpoints e **permissões por perfil** aplicadas no backend.
- **Limite de tentativas** no login (força bruta), nos pedidos do cardápio público (spam) e na validação de cupons.
- Cardápio público não deixa ninguém resgatar a fidelidade nem sobrescrever o cadastro de outro cliente pelo telefone.
- Em produção, a API **não sobe com `SECRET_KEY` fraca**, o seed demo é bloqueado e o simulador é desligado.

### Personalização de itens

Cada produto pode ter grupos de escolha (há modelos prontos e dá para copiar de outro produto):

| Campo | Para que serve |
|---|---|
| Mínimo | 1 ou mais deixa o grupo obrigatório (ex.: ponto da carne, bebida do combo) |
| Máximo | Limite de escolhas: 1 vira escolha única; 0 = sem limite (ex.: retirar ingredientes) |
| Como cobrar | `Somar` (adicionais), `Mais cara` (pizza meio a meio pelo sabor mais caro) ou `Média` |
| Pode repetir | Permite a mesma opção mais de uma vez (ex.: 2x carne extra) |

Cada escolha pode ter uma observação própria (ex.: metade Calabresa "sem cebola"). O backend valida tudo (obrigatórios, limites, repetição, opção de outro produto) e calcula o preço. Cada item do pedido guarda um **retrato das escolhas**, então a comanda continua igual mesmo se o cardápio mudar depois.

## Arquitetura

```mermaid
flowchart LR
    subgraph Clientes
        P[Painel da loja<br/>Angular]
        C[Cardápio online<br/>/cardapio/loja]
        M[iFood / 99Food<br/>conectores]
    end
    subgraph API[FastAPI]
        R[Rotas /api/v1<br/>auth, perfis e loja]
        S[Serviços<br/>pedidos, estoque, caixa,<br/>clientes, relatórios]
    end
    DB[(PostgreSQL)]
    P -- JWT --> R
    C -- público + limite de tentativas --> R
    M -- pedido normalizado --> S
    R --> S --> DB
```

- **Frontend**: Angular 18 com componentes standalone, signals, lazy loading por tela, guards de autenticação e perfil, e Tailwind CSS. Atualização por polling (5 s na Central e 4 s na Cozinha).
- **Backend**: FastAPI + SQLAlchemy 2 + Alembic, em camadas de rotas (`api/`), regras de negócio (`services/`), modelos (`models/`), contratos (`schemas/`) e conectores de marketplaces (`connectors/`).
- **Banco**: PostgreSQL (produção e desenvolvimento) ou SQLite (desenvolvimento e testes).

Ciclo de vida de um pedido:

```mermaid
stateDiagram-v2
    [*] --> NEW: pedido criado
    NEW --> ACCEPTED: aceitar
    ACCEPTED --> PREPARING: iniciar preparo
    PREPARING --> READY: pronto
    READY --> OUT_FOR_DELIVERY: delivery
    READY --> FINISHED: balcão / retirada
    OUT_FOR_DELIVERY --> FINISHED
    NEW --> CANCELED
    ACCEPTED --> CANCELED
    PREPARING --> CANCELED
    READY --> CANCELED
    OUT_FOR_DELIVERY --> CANCELED
    FINISHED --> [*]: ponto de fidelidade
    CANCELED --> [*]: devolve estoque, cupom e pontos
```

## Como rodar

### Pré-requisitos

- **Docker** com Docker Compose, **ou** Python 3.12+ e Node.js 20+
- PostgreSQL na porta `5432`. Sem um Postgres, use o que vem no compose (`--profile db`) ou rode com SQLite.

### Opção 1: Docker (recomendado)

```bash
git clone https://github.com/Tavares03/ComandaHub.git
cd ComandaHub
cp .env.example .env
```

**Já tem PostgreSQL na máquina** (usuário/senha `postgres`/`postgres` na porta 5432)? O banco `comandahub` é criado sozinho:

```bash
docker compose up --build
```

**Não tem PostgreSQL?** Suba o incluso junto:

```bash
docker compose --profile db up --build
```

Na subida, a API espera o banco, aplica as migrations e carrega os **dados demo** (3 lojas, cardápios, usuários e pedidos dos últimos 7 dias). O seed é idempotente: pode reiniciar à vontade.

| Serviço | Endereço |
|---|---|
| Painel | http://localhost:4200 |
| API | http://localhost:8000 |
| Swagger (documentação interativa) | http://localhost:8000/docs |
| Cardápio online demo | http://localhost:4200/cardapio/burger-station |

### Opção 2: sem Docker

**Backend** (terminal 1):

```bash
cd backend
cp .env.example .env                # ajuste DATABASE_URL se precisar

# Windows (PowerShell)
py -m venv .venv
.venv\Scripts\pip install -r requirements-dev.txt
.venv\Scripts\python -m scripts.wait_for_db   # cria o banco "comandahub" se não existir
.venv\Scripts\alembic upgrade head
.venv\Scripts\python -m scripts.seed
.venv\Scripts\uvicorn app.main:app --reload --port 8000

# Linux / macOS
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m scripts.wait_for_db
.venv/bin/alembic upgrade head
.venv/bin/python -m scripts.seed
.venv/bin/uvicorn app.main:app --reload --port 8000
```

> **Sem PostgreSQL nenhum:** use SQLite trocando no `backend/.env` para `DATABASE_URL=sqlite+pysqlite:///./comandahub.db`.

**Frontend** (terminal 2):

```bash
cd frontend
npm install
npm start          # http://localhost:4200
```

## Credenciais e roteiro de demonstração

Todas as contas demo usam a senha **`demo123`** (a tela de login permite escolher a conta com um clique):

| E-mail | Perfil |
|---|---|
| `admin@comandahub.local` | Administrador das 3 lojas |
| `burger@comandahub.local` | Atendente do Burger Station |
| `smash@comandahub.local` | Atendente do Smash House |
| `pizza@comandahub.local` | Atendente da Pizzaria Bella Massa |
| `cozinha@comandahub.local` | Cozinha nas 3 lojas |

Roteiro sugerido (cerca de 5 minutos):

1. Entre como **admin** e abra o **Laboratório** → *Simular pedido iFood*.
2. Na **Central de pedidos**, aceite, inicie o preparo, marque como pronto e despache. O sino do topo mostra os pedidos aguardando.
3. Abra a **Cozinha** para ver a fila de preparo.
4. Em **Pedido local**, troque para a *Pizzaria Bella Massa* e lance uma **Pizza Grande meio a meio** com observação por sabor e borda.
5. No **Cardápio → Ingredientes**, faça uma contagem zerando o *Pao brioche* (ingrediente principal dos burgers): os itens saem do cardápio sozinhos. Registre uma entrada e eles voltam.
6. Abra o **cardápio online** em `/cardapio/burger-station`, faça um pedido e acompanhe pelo link gerado.
7. Em **Relatórios**, veja o lucro por canal, já descontadas a comissão e o custo dos ingredientes.
8. Saia e entre como **cozinha**: o menu mostra só *Cozinha* e *Cardápio*.

## Perfis e permissões

As mesmas regras valem no menu, nas rotas do painel e nos endpoints da API:

| Área | Administrador | Atendente | Cozinha |
|---|:---:|:---:|:---:|
| Cozinha (fila de preparo) | ✅ | ✅ | ✅ |
| Cardápio e entrada de estoque | ✅ | ✅ | ✅ |
| Editar cardápio, pausas e preços | ✅ | ✅ | — |
| Dashboard, Central de pedidos, Pedido local | ✅ | ✅ | — |
| Caixa, Clientes e cupons | ✅ | ✅¹ | — |
| Cancelar pedido | ✅ | ✅ | — |
| Relatórios financeiros e pagamento de motoboys | ✅ | — | — |
| Configurações da loja e usuários | ✅ | — | — |

¹ Criar, editar e excluir cupons é exclusivo do administrador.

## Configuração

Variáveis de ambiente da API (em `backend/.env` ou no ambiente do container):

| Variável | Padrão | Descrição |
|---|---|---|
| `ENVIRONMENT` | `development` | `production` exige `SECRET_KEY` forte, bloqueia o seed demo e desliga o simulador |
| `DATABASE_URL` | `postgresql+psycopg://postgres:postgres@localhost:5432/comandahub` | Conexão do SQLAlchemy (PostgreSQL ou SQLite) |
| `SECRET_KEY` | — | Assina os tokens JWT. Em produção: 32+ caracteres aleatórios |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `720` | Duração da sessão (12 h) |
| `BACKEND_CORS_ORIGINS` | `http://localhost:4200,...` | Origens liberadas (lista separada por vírgula) |
| `LOG_LEVEL` | `INFO` | Logs estruturados em JSON (structlog) |
| `SEED_DEMO_DATA` | `false` (imagem) / `true` (compose dev) | Carrega os dados demo na subida do container |

## API

A documentação interativa fica em **`/docs`** (Swagger) e **`/redoc`**. Todas as rotas ficam sob `/api/v1`:

| Grupo | Rotas principais |
|---|---|
| Autenticação | `POST /auth/login`, `GET /auth/me`, `POST /auth/me/password` |
| Lojas e usuários | `GET/PATCH /establishments/{id}`, `GET/POST/PATCH/DELETE /establishments/{id}/users` |
| Pedidos | `GET/POST /orders`, `GET /orders/board`, `GET /orders/pending-count`, `PATCH /orders/{id}/status`, `/courier`, `/payment` |
| Cardápio | `products`, `categories`, `ingredients` (+ `/stock`, `/movements`), `availability`, `channel-prices` |
| Clientes | `customers`, `customers/lookup`, `coupons`, `coupons/validate` |
| Entregas | `delivery-zones`, `couriers`, `couriers/report` |
| Caixa | `cash/current`, `cash/open`, `cash/movements`, `cash/close`, `cash/sessions` |
| Relatórios | `dashboard`, `reports/overview`, `sales-by-channel`, `top-products`, `profit-by-channel` |
| Público (sem login) | `GET /public/stores/{slug}`, `POST /public/stores/{slug}/orders`, `GET /public/orders/{token}` |
| Simulador (só dev) | `POST /dev/establishments/{id}/simulate-order` |

Exemplo de pedido com personalização (o preço é sempre recalculado no servidor):

```json
POST /api/v1/establishments/{id}/orders
{
  "fulfillment_type": "COUNTER",
  "payment_method": "PIX",
  "items": [
    {
      "product_id": "…",
      "quantity": 1,
      "options": [
        { "option_id": "…", "quantity": 1, "notes": "sem cebola" },
        { "option_id": "…", "quantity": 1 }
      ],
      "notes": "cortar ao meio"
    }
  ]
}
```

## Testes e qualidade

```bash
cd backend
pytest -q            # 140+ testes de API: pedidos, estoque, caixa, perfis, cardápio online...
```

O CI (GitHub Actions, em `.github/workflows/ci.yml`) roda a cada push e pull request:

- **Backend**: aplica as migrations num **PostgreSQL real**, verifica com `alembic check` se os models e as migrations estão sincronizados, roda o seed duas vezes (idempotência) e executa a suíte de testes.
- **Frontend**: build de produção do Angular (compilação estrita de templates).
- **Docker**: build das imagens do backend e do frontend de produção.

## Deploy em produção

O arquivo `docker-compose.prod.yml` sobe PostgreSQL, API e **nginx** servindo o painel e repassando `/api` na mesma porta:

```bash
cp .env.example .env
# edite .env: SECRET_KEY (python -c "import secrets; print(secrets.token_urlsafe(48))") e POSTGRES_PASSWORD
docker compose -f docker-compose.prod.yml up -d --build

# primeiro acesso: cria a loja e o administrador (a senha é pedida no terminal)
docker compose -f docker-compose.prod.yml exec backend \
  python -m scripts.create_admin --email voce@sualoja.com.br --name "Seu Nome" --store "Sua Loja"
```

Em produção não há dados demo, credenciais na tela de login nem simulador. O administrador cadastra os demais usuários em **Configurações**.

Checklist:
- Coloque **HTTPS** na frente (proxy reverso, load balancer ou CDN).
- Faça backup do volume `postgres_data`.
- O limite de tentativas é guardado em memória **por processo**: para rodar várias instâncias da API, troque por um contador compartilhado (ex.: Redis).

## Estrutura do projeto

```text
comandahub/
├── backend/
│   ├── app/
│   │   ├── api/v1/endpoints/   # rotas REST (auth, pedidos, cardápio, caixa, público...)
│   │   ├── connectors/         # normalização de pedidos de marketplaces (simulados)
│   │   ├── core/               # config, segurança, dependências, limite de tentativas, fuso
│   │   ├── models/             # SQLAlchemy
│   │   ├── schemas/            # Pydantic (contratos da API)
│   │   ├── services/           # regras de negócio
│   │   └── main.py
│   ├── alembic/                # migrations
│   ├── scripts/                # seed demo, create_admin, wait_for_db
│   ├── tests/
│   ├── docker-entrypoint.sh
│   └── Dockerfile
├── frontend/
│   ├── src/app/
│   │   ├── core/               # API, auth, perfis, guards, interceptor
│   │   ├── features/           # telas (lazy loading)
│   │   ├── layouts/            # shell com menu, sino e troca de loja
│   │   └── shared/             # helpers de status, opções e preço
│   ├── nginx.conf
│   └── Dockerfile              # estágios dev (ng serve) e prod (nginx)
├── docs/screenshots/
├── .github/workflows/ci.yml
├── docker-compose.yml          # desenvolvimento
└── docker-compose.prod.yml     # exemplo de produção
```

## Decisões técnicas

- **Preço calculado só no servidor.** O frontend mostra uma prévia, mas o total do pedido sempre sai do backend, que valida produto, loja, canal, disponibilidade e regras de cada grupo de opções.
- **Retrato do pedido.** Itens guardam nome, preço, escolhas e custo do momento da venda, então relatórios e comandas não mudam quando o cardápio muda.
- **Numeração diária por loja** (`CH-AAMMDD-0001`) protegida por restrição única no banco, com nova tentativa em caso de corrida.
- **Datas em UTC, dia no fuso da loja.** Tudo é gravado em UTC (inclusive no SQLite) e "hoje" (dashboard, cupons, numeração) é calculado no fuso configurado da loja.
- **Pontos de fidelidade na finalização**, não na criação: pedidos falsos ou cancelados não contam.
- **Polling em vez de WebSocket** nesta versão: é simples, resistente a quedas de conexão e suficiente para o volume de uma loja. A troca por push está no roadmap.

## Roadmap

- [ ] Integração oficial com iFood e 99Food (OAuth e webhooks dos marketplaces)
- [ ] Atualização em tempo real via WebSocket / Server-Sent Events
- [ ] Emissão de NFC-e
- [ ] Impressão direta em impressora térmica (ESC/POS), sem diálogo do navegador
- [ ] Upload de imagens de produtos e logo (hoje os campos aceitam URL)
- [ ] Horário de funcionamento estruturado, abrindo e fechando a loja online automaticamente
- [ ] Cadastro self-service de novas lojas (onboarding)
- [ ] Testes end-to-end do frontend

## Licença

Distribuído sob a licença MIT. Veja [LICENSE](LICENSE).

As imagens de produtos dos dados demo vêm do [Unsplash](https://unsplash.com). Marcas citadas (iFood, 99Food) pertencem aos seus donos e aparecem apenas para identificar os canais de venda.
