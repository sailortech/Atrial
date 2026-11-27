# Atrial

Sistema de fila de atendimento para a recepção de uma clínica, feito com **Flask** e **React** como projeto de estudo.

A recepção cadastra quem chega, o sistema organiza a fila por prioridade, quem atende chama o próximo para um consultório, e uma TV na sala de espera mostra quem foi chamado e para onde.

O projeto tem duas partes:

| Pasta | O que é |
|---|---|
| [`backend/`](backend/) | **Flask**: banco de dados, regras, login e uma **API JSON**. Também entrega as telas do React prontas, em `/app/` |
| [`frontend/`](frontend/) | **React**: todas as telas do sistema, que conversam com o Flask pela API |

> **Histórico:** o sistema começou com páginas montadas pelo próprio Flask (templates HTML). Elas foram levadas para o React uma a uma e depois aposentadas. Os endereços antigos (`/pacientes`, `/painel`...) continuam funcionando e levam para a tela equivalente do React.

## O que ele faz

**Fila e atendimento**
- Cadastro e edição de pacientes, com validação de CPF (dígitos verificadores) e de data de nascimento.
- Fila ordenada por prioridade (**Urgente → Preferencial → Normal**) e, no empate, por ordem de chegada.
- **Chamar próximo** para um local (triagem, consultório...). O último local escolhido fica lembrado.
- **Chamar de novo**, para quem não apareceu, e **Não compareceu**, para encerrar sem atendimento.
- Tempo de espera e duração de cada atendimento.
- Busca por nome ou CPF que ignora acentos e maiúsculas ("joao" acha "João").
- A lista de pacientes se atualiza sozinha a cada 20 segundos.
- **Tema claro, escuro ou automático** (segue o Windows ou o celular), escolhido no cabeçalho. A escolha fica guardada em cada computador.

**Painel da TV** (`/app/painel`)
- Mostra quem está sendo chamado e para onde, com as últimas chamadas e quantas pessoas estão na fila.
- Atualiza a cada 3 segundos, pisca e toca um aviso sonoro a cada chamada. O som precisa de um clique em "Ativar som" quando a TV é ligada, porque os navegadores bloqueiam áudio automático.
- Mostra só o primeiro nome e a inicial do sobrenome ("Maria S."), porque a tela é pública.
- Abre sem login.

**Relatório do dia** (`/app/relatorio`)
- Chegadas, atendimentos, ausências, espera média e maior espera, e duração média.
- Gráfico de chegadas por hora, com uma tabela que mostra os mesmos números.
- Números por prioridade e por local.

**Usuários e segurança**
- Login obrigatório em todas as telas, menos no painel da TV.
- Dois papéis: **Recepção** (fila e relatório) e **Administração** (também cadastra locais e usuários).
- A administração cadastra pessoas, desativa quem saiu da clínica e redefine senhas esquecidas. Uma senha dada pela administração é provisória e precisa ser trocada no primeiro acesso.
- Locais podem ser adicionados, renomeados e desativados.
- Proteção contra CSRF em todo pedido que muda algo, senhas guardadas só como *hash*, sessões derrubadas quando a senha muda e bloqueio de 15 minutos depois de 5 senhas erradas.

## Como instalar

Requisitos:
- **Python 3.14** (a versão usada e testada no desenvolvimento; versões um pouco mais antigas provavelmente funcionam, mas não foram testadas);
- **Node.js** (testado com o 24), que já traz o `npm`;
- **Git**.

Os comandos abaixo são para o **PowerShell (Windows)**. No Linux e no macOS, troque `venv\Scripts\python` por `venv/bin/python`.

```powershell
# 1. Baixe o projeto
git clone <endereço-do-repositório> Atrial
cd Atrial

# 2. Backend: ambiente virtual, dependências e banco de dados
cd backend
python -m venv venv
venv\Scripts\python -m pip install -r requirements-dev.txt
venv\Scripts\python -m flask --app app db upgrade

# 3. Crie o primeiro usuário da administração
#    (o comando pergunta o nome e a senha)
venv\Scripts\python -m flask --app app criar-usuario seu.login --admin

# 4. Frontend: baixa as bibliotecas e gera as telas prontas
cd ..\frontend
npm install
npm run build
```

O banco já nasce com quatro locais: Triagem e Consultório 1, 2 e 3. Eles podem ser mudados depois, na tela **Locais**.

> **Por que `python -m flask` em vez de só `flask`?** Assim o comando usa com certeza o Flask instalado no `venv`. Em algumas máquinas, o `flask.exe` do `venv` falha sem mostrar erro.

## Como rodar

### Para usar no dia a dia

Dê **dois cliques em `iniciar.cmd`**, na pasta do projeto. (Ou, no terminal: `cd backend` e `venv\Scripts\python servidor.py`.)

Abre uma janela que mostra os endereços:

```
  Atrial ligado. Para desligar: Ctrl+C (ou feche esta janela).

  Neste computador:   http://127.0.0.1:5000
  Na TV (painel):     http://192.168.0.12:5000/app/painel
  Outros computadores: http://192.168.0.12:5000
```

Abra o primeiro endereço e entre com o usuário criado no passo 3. Os outros usuários podem ser cadastrados na tela **Usuários**. **Deixe a janela aberta** enquanto o sistema estiver em uso: fechar a janela desliga o Atrial.

O `servidor.py` usa o **Waitress**, um servidor feito para uso de verdade, e aceita conexões da rede, para a TV e outros computadores. Na primeira vez, o **Firewall do Windows** pergunta se o Python pode usar a rede: permita em **redes privadas**. Antes de ligar, ele confere o React: sem `npm run build`, não liga e explica o que fazer; com o build desatualizado em relação ao código, liga e avisa.

### Para programar no backend

```powershell
cd backend
venv\Scripts\python -m flask --app app run --debug
```

O `--debug` reinicia o servidor sozinho quando um arquivo do backend muda, e mostra os erros detalhados. **Use só no seu computador, nunca no dia a dia da clínica:** a página de erro do modo debug mostra o código do sistema. Se o servidor ficar mostrando um erro estranho depois de você editar vários arquivos de uma vez, pare (Ctrl+C) e rode de novo.

O Flask entrega as telas que o `npm run build` gerou. **Mudou o código do React? Rode `npm run build` de novo** (ou use o modo abaixo).

### Para programar no React

```powershell
# Terminal 1
cd backend
venv\Scripts\python -m flask --app app run --debug

# Terminal 2
cd frontend
npm run dev
```

Abra **http://localhost:5173/app/**. O Vite mostra cada mudança na hora, sem precisar de build, e o navegador se atualiza sozinho a cada arquivo salvo.

### Painel na TV

Ligue o Atrial pelo `iniciar.cmd` e, no navegador da TV, abra o endereço que aparece na janela em **"Na TV (painel)"**. Ponha em tela cheia (F11) e clique uma vez em **Ativar som**. A TV e o computador precisam estar na mesma rede. (O endereço antigo, `/painel`, também funciona.)

## Testes

São duas suítes, uma para cada parte:

```powershell
cd backend
venv\Scripts\python -m pytest      # Flask: regras e API

cd ..\frontend
npm test                           # React: componentes e telas (Vitest)
```

**Backend:** quase 300 testes, que rodam em cerca de 15 segundos. Eles usam um banco **em memória**, então nunca tocam no `backend/instance/atrial.db`. Rode os testes depois de qualquer mudança.

Alguns testes do backend funcionam como **redes de segurança**: eles falham se alguém criar uma rota que abre sem login, uma rota de administração sem teste de permissão, ou um pedido que muda algo sem exigir o código CSRF.

**Frontend:** os testes ficam ao lado do arquivo testado (`Mensagem.jsx` → `Mensagem.test.jsx`) e rodam num navegador simulado (jsdom), sem servidor nenhum: [`src/testes/simularApi.js`](frontend/src/testes/simularApi.js) troca o `fetch` por um falso, que responde como o Flask responderia. Os testes de tela usam a Testing Library, que procura os elementos como a pessoa (ou o leitor de tela) os encontraria: pelo texto, pelo rótulo do campo, pelo nome do botão. Para os testes rodarem de novo a cada arquivo salvo, use `npm run test:watch`.

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
| `ATRIAL_FRONTEND_DIST` | Pasta com o React pronto, que o Flask entrega em `/app/` | `frontend/dist/` |
| `ATRIAL_PORTA` | Porta do `servidor.py` | `5000` |
| `ATRIAL_HOST` | Quem pode abrir o `servidor.py`: `0.0.0.0` (a rede toda) ou `127.0.0.1` (só este computador) | `0.0.0.0` |
| `ATRIAL_BACKEND` | Só no `npm run dev`: endereço do Flask para onde o Vite repassa a API | `http://127.0.0.1:5000` |

A pasta `backend/instance/` guarda o banco e a chave secreta, e **não vai para o Git** (está no `.gitignore`). A `frontend/dist/` também não: ela é gerada pelo `npm run build`.

## Organização do código

```
iniciar.cmd               dois cliques: liga o Atrial para usar (chama o servidor.py)

backend/
  app.py                  todo o backend: modelos, regras, API e comandos
  servidor.py             liga o Atrial com o Waitress, na rede (uso do dia a dia)
  tests/
    conftest.py           preparação dos testes (fixtures)
    test_*.py             um arquivo por assunto
  migrations/versions/    histórico de mudanças do banco
  instance/               banco e chave secreta (fora do Git)
  venv/                   ambiente virtual do Python (fora do Git)

frontend/
  index.html              página onde o React é carregado
  vite.config.js          configuração do Vite (endereço /app/, proxy para o Flask, testes)
  package.json            dependências do JavaScript e comandos (npm run ...)
  src/
    main.jsx              ponto de partida do React
    App.jsx               rotas (qual tela aparece em cada endereço)
    api.js                conversa com a API do Flask (CSRF, erros)
    sessao.jsx            quem está logado (Context), para qualquer componente
    formularios.js        ajudantes dos formulários (máscara do CPF, campo com erro)
    paginas/              telas inteiras (Pacientes, Relatorio, Locais, Usuarios...)
    componentes/          pedaços da tela (Login, Cabecalho, Painel, Mensagem...)
      AreaLogada.jsx, SoAdmin.jsx   "portarias": exigem login / administração
      pacientes/, relatorio/, locais/, usuarios/   pedaços de cada tela
    hooks/                lógica reaproveitável (usePacientes, useRelatorio, usePainel, useSom)
    testes/               preparação dos testes e o simulador da API
    app.css               visual das telas da recepção
    painel.css            visual do painel da TV
```

Dentro do `app.py`, as partes estão separadas por comentários (`# ---------- Login ----------`, `# ---------- Relatório do dia ----------`, ...). Os comentários explicam o **porquê** de cada decisão, especialmente nas partes de segurança.

### Algumas decisões de projeto

- **Regras separadas das rotas:** cada ação (`acao_chamar_proximo`, `acao_renomear_local`...) é uma função comum, e a rota da API só a chama e transforma o resultado em JSON. A regra fica fácil de ler e de testar.
- **Tudo protegido por padrão:** o login é exigido num `before_request`, e não rota por rota. Uma rota nova já nasce protegida.
- **Quem protege é o Flask:** o React esconde o que a pessoa não pode usar (por exemplo, Locais para a recepção), mas isso é só conforto. Quem recusa de verdade é a API.
- **O paciente guarda o *nome* do local, não o id:** é o registro do que aconteceu. Se um consultório for desativado ou renomeado depois, o histórico não muda.
- **Desativar em vez de apagar** (locais e usuários): o histórico continua fazendo sentido.
- **`chamado_em` × `ultima_chamada`:** a espera é medida até a **primeira** chamada. Chamar de novo quem não apareceu não aumenta a espera no relatório.
- **Cores só em variáveis CSS:** todas as cores das telas ficam no topo do `app.css`, com um conjunto para o tema claro e outro para o escuro, e o contraste de cada texto foi conferido nos dois. Trocar de tema é só trocar o valor das variáveis.
- **Relatório:** as contas são feitas em Python, e não em SQL, porque fica mais fácil de ler. Com o movimento de um dia, são poucas linhas. O desenho do gráfico é feito pelo React.

## Telas e API

O React mora em **`/app/`**:

| Endereço | Tela |
|---|---|
| `/app/pacientes` | Login + lista de pacientes: chamar, concluir, chamar de novo, não compareceu, busca |
| `/app/pacientes/novo` | Cadastro de paciente |
| `/app/pacientes/:id/editar` | Edição de paciente (e, numa área separada, excluir) |
| `/app/relatorio?dia=AAAA-MM-DD` | Relatório do dia, com o gráfico de chegadas por hora |
| `/app/minha-senha` | Trocar a própria senha (com senha provisória, é a única tela liberada) |
| `/app/locais` | Locais de atendimento (só administração) |
| `/app/usuarios` | Usuários: criar, mudar papel, desativar, redefinir senha (só administração) |
| `/app/painel` | Painel da TV (sem login) |

Para o Flask, todo o React é **uma** página: qualquer endereço em `/app/` que não seja um arquivo (JS, CSS) recebe o mesmo `index.html`, e o React decide qual tela desenhar. Por isso o F5 e os links diretos funcionam.

**Como o React fala com o Flask no desenvolvimento:** o React roda no Vite, na porta 5173, e o Flask na 5000. Quando o React pede `/api/...` ou `/painel/dados`, o Vite repassa o pedido para o Flask (o *proxy*, configurado em `vite.config.js`). Para o navegador, tudo parece um site só, e por isso o **cookie de login do Flask** funciona também.

A API fica no fim do `backend/app.py` (seção "API JSON") e segue estas convenções:

- **Login:** `GET /api/sessao` diz quem está logado e entrega o código CSRF; `POST /api/login` e `POST /api/logout` entram e saem.
- **Métodos:** `GET` lê, `POST` cria ou executa uma ação, `PUT` salva a edição e `DELETE` apaga (ex.: `GET`, `PUT` e `DELETE` em `/api/pacientes/7`).
- **CSRF:** todo pedido que muda algo (`POST`, `PUT`, `DELETE`) manda o código no cabeçalho `X-CSRFToken`. O [`src/api.js`](frontend/src/api.js) faz isso sozinho.
- **Erros:** um código HTTP e `{"erro": "mensagem"}`. `401` = não está logado, `403` = sem permissão (ou senha provisória), `404` = não encontrado, `409` = não deu por causa da situação atual (fila vazia, último local ativo, o próprio acesso), `422` = dados inválidos, com `{"erros": {"campo": "mensagem"}}` para o React mostrar cada erro embaixo do seu campo.

Comandos do frontend, sempre rodados de dentro de `frontend/`:

| Comando | O que faz |
|---|---|
| `npm run dev` | Modo de desenvolvimento (Vite), em http://localhost:5173/app/ |
| `npm run build` | Gera a versão final, otimizada, em `frontend/dist/` (a que o Flask entrega) |
| `npm test` | Roda os testes automáticos (Vitest) |
| `npm run test:watch` | Os testes, de novo a cada arquivo salvo |
| `npm run lint` | Procura erros comuns no código (ESLint) |

## Dependências

**Backend:** `backend/requirements.txt` tem o que o sistema precisa para rodar: Flask, Flask-SQLAlchemy, Flask-Migrate, Flask-Login, Flask-WTF e o Waitress (o servidor do `servidor.py`). `backend/requirements-dev.txt` acrescenta o **pytest**, que só é usado no desenvolvimento.

**Frontend:** `frontend/package.json` lista o React e o React Router, e as ferramentas de desenvolvimento (Vite, ESLint, e para os testes Vitest, jsdom e Testing Library). O `package-lock.json` guarda as versões exatas instaladas, para todo mundo instalar igual.
