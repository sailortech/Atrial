# Atrial

Sistema de fila de atendimento para a recepção de uma clínica, feito em **Flask** como projeto de estudo.

A recepção cadastra quem chega, o sistema organiza a fila por prioridade, quem atende chama o próximo para um consultório, e uma TV na sala de espera mostra quem foi chamado e para onde.

O projeto tem duas partes:

| Pasta | O que é |
|---|---|
| [`backend/`](backend/) | O sistema completo em **Flask**: banco de dados, regras, login e as páginas da recepção (HTML montado no servidor) |
| [`frontend/`](frontend/) | Telas em **React**, que conversam com o Flask por uma API JSON. Tem todas as telas do sistema (veja [Frontend em React](#frontend-em-react)) |

## O que ele faz

**Fila e atendimento**
- Cadastro de pacientes com validação de CPF (dígitos verificadores) e de data de nascimento.
- Fila ordenada por prioridade (**Urgente → Preferencial → Normal**) e, no empate, por ordem de chegada.
- **Chamar próximo** para um local (triagem, consultório...). O último local escolhido fica lembrado.
- **Chamar de novo**, para quem não apareceu, e **Não compareceu**, para encerrar sem atendimento.
- Tempo de espera e duração de cada atendimento.
- Busca por nome ou CPF que ignora acentos e maiúsculas ("joao" acha "João").
- A página de pacientes se atualiza sozinha a cada 20 segundos.

**Painel da TV** (`/painel`)
- Mostra quem está sendo chamado e para onde, com as últimas chamadas e quantas pessoas estão na fila.
- Atualiza a cada 3 segundos, pisca e toca um aviso sonoro a cada chamada. O som precisa de um clique em "Ativar som" quando a TV é ligada, porque os navegadores bloqueiam áudio automático.
- Mostra só o primeiro nome e a inicial do sobrenome ("Maria S."), porque a tela é pública.
- Abre sem login.

**Relatório do dia** (`/relatorio`)
- Chegadas, atendimentos, ausências, espera média e maior espera, e duração média.
- Gráfico de chegadas por hora, com uma tabela que mostra os mesmos números.
- Números por prioridade e por local.

**Usuários e segurança**
- Login obrigatório em todas as páginas, menos no painel da TV.
- Dois papéis: **Recepção** (fila e relatório) e **Administração** (também cadastra locais e usuários).
- A administração cadastra pessoas, desativa quem saiu da clínica e redefine senhas esquecidas. Uma senha dada pela administração é provisória e precisa ser trocada no primeiro acesso.
- Proteção contra CSRF em todos os formulários, senhas guardadas só como *hash*, sessões derrubadas quando a senha muda e bloqueio de 15 minutos depois de 5 senhas erradas.

## Como instalar

Requisitos: **Python 3.14** (a versão usada e testada no desenvolvimento; versões um pouco mais antigas provavelmente funcionam, mas não foram testadas) e **Git**.

Os comandos abaixo são para o **PowerShell (Windows)**. No Linux e no macOS, troque `venv\Scripts\python` por `venv/bin/python`.

```powershell
# 1. Baixe o projeto e entre na pasta do backend
git clone <endereço-do-repositório> Atrial
cd Atrial\backend

# 2. Crie o ambiente virtual e instale as dependências
python -m venv venv
venv\Scripts\python -m pip install -r requirements-dev.txt

# 3. Crie o banco de dados (aplica todas as migrations)
venv\Scripts\python -m flask --app app db upgrade

# 4. Crie o primeiro usuário da administração
#    (o comando pergunta o nome e a senha)
venv\Scripts\python -m flask --app app criar-usuario seu.login --admin
```

O banco já nasce com quatro locais: Triagem e Consultório 1, 2 e 3. Eles podem ser mudados depois, na página **Locais**.

> **Por que `python -m flask` em vez de só `flask`?** Assim o comando usa com certeza o Flask instalado no `venv`. Em algumas máquinas, o `flask.exe` do `venv` falha sem mostrar erro.

## Como rodar

**Todos os comandos do backend são rodados de dentro da pasta `backend/`.**

```powershell
cd backend
venv\Scripts\python -m flask --app app run --debug
```

Abra **http://127.0.0.1:5000** e entre com o usuário criado no passo 4. Os outros usuários podem ser cadastrados pela página **Usuários**.

**A versão em React** fica em **http://127.0.0.1:5000/app/**, servida pelo próprio Flask, mas só depois de gerada uma vez (veja [Frontend em React](#frontend-em-react)):

```powershell
cd frontend
npm install        # só na primeira vez
npm run build      # de novo sempre que o código do React mudar
```

O `--debug` reinicia o servidor sozinho quando um arquivo muda, e mostra os erros detalhados no navegador. **Use só no seu computador.** Se o servidor ficar mostrando um erro estranho depois de você editar vários arquivos de uma vez, pare (Ctrl+C) e rode de novo.

### Painel na TV

Abra **http://127.0.0.1:5000/painel** no navegador da TV, em tela cheia (F11), e clique uma vez em **Ativar som**. Para a TV acessar o computador que roda o Atrial, os dois precisam estar na mesma rede, e o servidor precisa ser iniciado com `--host 0.0.0.0`. Nesse caso, a TV usa o endereço IP do computador no lugar de `127.0.0.1`.

## Testes

```powershell
cd backend
venv\Scripts\python -m pytest
```

São mais de 200 testes, e todos rodam em cerca de 10 segundos. Eles usam um banco **em memória**, então nunca tocam no `backend/instance/atrial.db`. Rode os testes depois de qualquer mudança.

Alguns testes funcionam como **redes de segurança**: eles falham se alguém criar uma rota que abre sem login, um formulário sem o código CSRF ou uma rota de administração sem teste de permissão.

## Mudanças no banco (migrations)

A estrutura do banco é controlada pelo **Flask-Migrate** (Alembic). Ao mudar um modelo em `app.py` (por exemplo, criar uma coluna):

```powershell
venv\Scripts\python -m flask --app app db migrate -m "o que mudou"
venv\Scripts\python -m flask --app app db upgrade
```

Sempre **leia o arquivo gerado** em `backend/migrations/versions/` antes do `upgrade`. Duas situações pedem ajuste à mão:

- **Coluna obrigatória (`nullable=False`) numa tabela que já tem dados:** precisa de um `server_default`. Sem ele, o banco não sabe o que colocar nas linhas que já existem.
- **Dados antigos que precisam ser preenchidos:** a coluna nova nasce vazia nas linhas que já existem. Exemplos no projeto: `0ee83d5ff5b7` (nome para a busca sem acentos) e `a77785478cf8` (última chamada).

Antes de mexer no banco de verdade, faça uma cópia do `backend/instance/atrial.db`. Para desfazer a última migration, use `db downgrade`.

## Configuração

| Variável de ambiente | Para que serve | Se não for definida |
|---|---|---|
| `SECRET_KEY` | Assina o cookie de login e os códigos CSRF. Quem souber essa chave consegue se passar por qualquer usuário. | É gerada uma chave aleatória e guardada em `backend/instance/secret_key` |
| `DATABASE_URL` | Endereço do banco de dados | `sqlite:///atrial.db` (o arquivo fica em `backend/instance/`) |

A pasta `backend/instance/` guarda o banco e a chave secreta, e **não vai para o Git** (está no `.gitignore`).

## Organização do código

```
backend/
  app.py                  todo o sistema: modelos, regras, rotas e comandos
  templates/
    base.html             esqueleto das páginas (menu e mensagens)
    pacientes.html        fila e atendimento
    _listas_pacientes.html  as três tabelas da fila (atualizadas sozinhas)
    _campos_paciente.html   campos do formulário de paciente (cadastro e edição)
    painel.html           tela da TV, versão Flask (não usa base.html)
    relatorio.html        relatório do dia e gráfico
    locais.html, usuarios.html, minha_senha.html, ...
  static/css/style.css    todo o visual das páginas Flask
  tests/
    conftest.py           preparação dos testes (fixtures)
    test_*.py             um arquivo por assunto
  migrations/versions/    histórico de mudanças do banco
  instance/               banco e chave secreta (fora do Git)
  venv/                   ambiente virtual do Python (fora do Git)

frontend/
  index.html              página onde o React é carregado
  vite.config.js          configuração do Vite (inclui o proxy para o Flask)
  package.json            dependências do JavaScript e comandos (npm run ...)
  src/
    main.jsx              ponto de partida do React
    App.jsx               rotas (qual tela aparece em cada endereço)
    api.js                conversa com a API do Flask (CSRF, erros)
    sessao.jsx            quem está logado (Context), para qualquer componente
    formularios.js        ajudantes dos formulários (marcar campo com erro)
    paginas/              telas inteiras (Pacientes, Relatorio, Locais, Usuarios...)
    componentes/          pedaços da tela (Login, Cabecalho, Painel, Mensagem...)
      AreaLogada.jsx, SoAdmin.jsx   "portarias": exigem login / administração
      pacientes/, relatorio/, usuarios/   pedaços de cada tela
    hooks/                lógica reaproveitável (usePacientes, useRelatorio, usePainel, useSom)
    app.css               visual das telas da recepção
    painel.css            visual do painel da TV
```

Templates que começam com `_` são **pedaços** incluídos em outras páginas, e não páginas inteiras.

Dentro do `app.py`, as partes estão separadas por comentários (`# ---------- Login ----------`, `# ---------- Relatório do dia ----------`, ...). Os comentários explicam o **porquê** de cada decisão, especialmente nas partes de segurança.

### Algumas decisões de projeto

- **Tudo protegido por padrão:** o login é exigido num `before_request`, e não rota por rota. Uma rota nova já nasce protegida.
- **O paciente guarda o *nome* do local, não o id:** é o registro do que aconteceu. Se um consultório for desativado depois, o histórico não muda.
- **Desativar em vez de apagar** (locais e usuários): o histórico continua fazendo sentido.
- **`chamado_em` × `ultima_chamada`:** a espera é medida até a **primeira** chamada. Chamar de novo quem não apareceu não aumenta a espera no relatório.
- **Relatório:** as contas são feitas em Python, e não em SQL, porque fica mais fácil de ler. Com o movimento de um dia, são poucas linhas.

## Frontend em React

A pasta `frontend/` tem a versão em **React** de todas as telas do sistema. As páginas do Flask continuam funcionando normalmente: as duas versões usam o mesmo banco, as mesmas regras e até o mesmo login.

O React mora em **`/app/`**: os endereços abaixo ficam `/app/pacientes`, `/app/relatorio` e assim por diante.

| Endereço (no React) | Tela |
|---|---|
| `/pacientes` | Login + lista de pacientes: chamar, concluir, chamar de novo, não compareceu, busca |
| `/pacientes/novo` | Cadastro de paciente |
| `/pacientes/:id/editar` | Edição de paciente (e, numa área separada, excluir) |
| `/relatorio?dia=AAAA-MM-DD` | Relatório do dia, com o gráfico de chegadas por hora |
| `/minha-senha` | Trocar a própria senha (com senha provisória, é a única tela liberada) |
| `/locais` | Locais de atendimento (só administração) |
| `/usuarios` | Usuários: criar, mudar papel, desativar, redefinir senha (só administração) |
| `/painel` | Painel da TV (sem login) |

Requisito: **Node.js** (testado com o 24), que já traz o `npm`.

```powershell
# Uma vez só: baixa as bibliotecas (React, Vite...) para frontend\node_modules
cd frontend
npm install
```

Há dois jeitos de rodar o React:

| | Para quê | Como | Endereço |
|---|---|---|---|
| **Pronto (build)** | Usar o sistema | `npm run build` e depois só o Flask | http://127.0.0.1:5000/app/ |
| **Desenvolvimento** | Mexer no código | Flask num terminal e `npm run dev` em outro | http://localhost:5173/app/ |

- **Pronto:** `npm run build` gera os arquivos finais em `frontend/dist/` (fora do Git), e o Flask os entrega em `/app/...` (rota `frontend_react` no `app.py`). Um servidor só. Qualquer endereço que não seja um arquivo (`/app/relatorio?dia=...`) recebe o `index.html`, e o React decide a tela: por isso o F5 e os links diretos funcionam. **Mudou o código do React? Rode `npm run build` de novo.**
- **Desenvolvimento:** o Vite mostra cada mudança na hora, sem precisar de build. O código fica em `frontend/src/`, e o navegador se atualiza sozinho a cada arquivo salvo.

**Como o React fala com o Flask (no desenvolvimento):** o React roda no Vite, na porta 5173, e o Flask roda na 5000. Quando o React pede `/api/...` ou `/painel/dados`, o Vite repassa o pedido para o Flask (o *proxy*, configurado em `vite.config.js`). Para o navegador, tudo parece um site só, e por isso o **cookie de login do Flask** funciona no React também.

A API fica no fim do `backend/app.py` (seção "API JSON"), e as rotas dela usam **as mesmas funções** das páginas HTML (`autenticar`, `acao_chamar_proximo`, ...): as regras ficam num lugar só. Ela segue estas convenções:

- **Login:** `GET /api/sessao` diz quem está logado e entrega o código CSRF; `POST /api/login` e `POST /api/logout` entram e saem.
- **Métodos:** `GET` lê, `POST` cria ou executa uma ação, `PUT` salva a edição e `DELETE` apaga (ex.: `GET`, `PUT` e `DELETE` em `/api/pacientes/7`).
- **CSRF:** todo pedido que muda algo (`POST`, `PUT`, `DELETE`) manda o código no cabeçalho `X-CSRFToken`. O [`src/api.js`](frontend/src/api.js) faz isso sozinho.
- **Erros:** um código HTTP e `{"erro": "mensagem"}`. `401` = não está logado, `403` = sem permissão (ou senha provisória), `404` = não encontrado, `409` = não deu por causa da situação atual (fila vazia, último local ativo, o próprio acesso), `422` = dados inválidos, com `{"erros": {"campo": "mensagem"}}` para o React mostrar cada erro embaixo do seu campo.

Se o Flask estiver em outro endereço, defina `ATRIAL_BACKEND` antes do `npm run dev`, por exemplo `$env:ATRIAL_BACKEND="http://127.0.0.1:5051"`.

Outros comandos, sempre rodados de dentro de `frontend/`:

| Comando | O que faz |
|---|---|
| `npm run lint` | Procura erros comuns no código (ESLint) |
| `npm run build` | Gera a versão final, otimizada, em `frontend/dist/` |

## Dependências

**Backend:** `backend/requirements.txt` tem o que o sistema precisa para rodar: Flask, Flask-SQLAlchemy, Flask-Migrate, Flask-Login e Flask-WTF. `backend/requirements-dev.txt` acrescenta o **pytest**, que só é usado no desenvolvimento.

**Frontend:** `frontend/package.json` lista o React e as ferramentas de desenvolvimento (Vite e ESLint). O `package-lock.json` guarda as versões exatas instaladas, para todo mundo instalar igual.
