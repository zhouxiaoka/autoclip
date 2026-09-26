<div align="center">

<img src="src-tauri/icons/128x128.png" alt="AutoClip" width="80" height="80">

# AutoClip

**Transforme vídeos longos em momentos que merecem ser compartilhados.**

[简体中文](README.md) · [English](README-EN.md) · [日本語](README-JA.md) · [한국어](README-KO.md) · [Español](README-ES.md) · **Português** · [Русский](README-RU.md) · [Français](README-FR.md)

[![GitHub release](https://img.shields.io/github/v/release/zhouxiaoka/autoclip?style=flat-square)](https://github.com/zhouxiaoka/autoclip/releases/latest)
[![GitHub stars](https://img.shields.io/github/stars/zhouxiaoka/autoclip?style=flat-square)](https://github.com/zhouxiaoka/autoclip/stargazers)
[![GitHub forks](https://img.shields.io/github/forks/zhouxiaoka/autoclip?style=flat-square)](https://github.com/zhouxiaoka/autoclip/forks)
[![GitHub issues](https://img.shields.io/github/issues/zhouxiaoka/autoclip?style=flat-square)](https://github.com/zhouxiaoka/autoclip/issues)
[![License: MIT](https://img.shields.io/github/license/zhouxiaoka/autoclip?style=flat-square)](LICENSE)

<p align="center">
  <a href="https://trendshift.io/repositories/25801"><img src="https://trendshift.io/api/badge/repositories/25801" alt="AutoClip — GitHub Trending #3" width="250" height="55"></a>
</p>

Edição local · traga sua própria chave de modelo

Conquista registrada pelo Trendshift; não é um ranking ao vivo. GitHub Trending e Trendshift são listas diferentes.

[Site](https://zhouxiaoka.github.io/autoclip_intro/) · [Discussions](https://github.com/zhouxiaoka/autoclip/discussions) · [Relatar um problema](https://github.com/zhouxiaoka/autoclip/issues)

**Instaladores desktop: [macOS · Apple Silicon](https://github.com/zhouxiaoka/autoclip/releases/latest) · [Windows · x64](https://github.com/zhouxiaoka/autoclip/releases/latest)**

[Instalação e primeiros clipes (English)](docs/USER_INSTALLATION_GUIDE.en.md) · [Guia completo de solução de problemas (inglês)](docs/FAQ.en.md)

</div>

A partir da v1.3.1, o aplicativo, o site e o README oferecem chinês, inglês, japonês, coreano, espanhol, português, russo e francês. Escolha o idioma no cabeçalho ou siga o sistema. Seus arquivos e o conteúdo gerado mantêm o idioma original.

O AutoClip usa IA para analisar legendas, encontrar destaques, criar títulos e gerar clipes e coletâneas automaticamente. Ideal para entrevistas, podcasts, cursos e gravações de transmissões ao vivo, oferece um aplicativo desktop, uma interface web via Docker e acesso por CLI / MCP.

## Veja a interface

![AutoClip v1.3.0 — local video import](docs/images/import-local.jpg)

Interface web real da v1.3.0: adicione um vídeo local na área de importação, com legendas SRT opcionais.

## O que você pode fazer

| Recurso | Descrição |
| --- | --- |
| Importar vídeos | Use arquivos locais ou links do YouTube e Bilibili, com legendas SRT opcionais. |
| Encontrar destaques | Extraia resumos, intervalos por assunto, pontuações e títulos a partir das legendas. |
| Criar clipes e coletâneas | Gere clipes e coletâneas sugeridas e ajuste a ordem manualmente. |
| Publicar (v1.3.2) | A partir da **v1.3.2**, com os clipes prontos, publique ou agende na mesma página. Plataformas no exterior usam o Upload-Post; no Bilibili, cole os cookies de login uma vez em Configurações. O padrão fica o mais privado que a plataforma permitir; também dá para exportar sem publicar. Detalhes: [guia de publicação (chinês)](docs/PUBLISH_UPLOAD_POST.md). |
| Capa automática (v1.3.2) | Ao publicar, uma capa é gerada automaticamente para o Bilibili não recusar uma capa vazia; os padrões seguem as notas do instalador. Disponível na **v1.3.2**. |
| Exportar para publicar | Use predefinições para Douyin, Xiaohongshu, YouTube Shorts e Bilibili, com legendas embutidas e cartões de título. |
| Escolher modelos | Suporta Qwen, OpenAI, Gemini, DeepSeek, Doubao Seed, Kimi, GLM e modelos locais via Ollama / LM Studio (traga sua própria chave de API). |
| Automatizar tarefas | Organize execuções pela CLI ou acesse o mesmo fluxo de processamento por um cliente MCP. |

> Importar vídeo → Legendas / transcrição → Análise e pontuação por IA → Clipes e coletâneas → Exportação

## Início rápido

### 1. Aplicativo desktop

Baixe o instalador adequado em [GitHub Releases](https://github.com/zhouxiaoka/autoclip/releases/latest):

| Plataforma | Instalação |
| --- | --- |
| macOS · Apple Silicon | `.dmg` |
| Windows 10 / 11 · x64 | `-setup.exe` |
| Intel Mac / Linux | Use Docker ou a CLI abaixo |

Os instaladores incluem Python e FFmpeg. Consulte cada versão para verificar as plataformas disponíveis e as instruções da primeira execução. Após instalar, escolha o provedor de modelos nas configurações, teste a conexão, salve e importe um vídeo.

### 2. Docker / Web

Requer Docker e Docker Compose v2. Execute os comandos na raiz do repositório:

```bash
git clone https://github.com/zhouxiaoka/autoclip.git
cd autoclip
```

```bash
cp env.example .env
```

Antes de iniciar, edite `.env`: selecione `LLM_PROVIDER` e informe a chave de API e o modelo correspondentes. Você também pode configurar o provedor pela interface após iniciar.

```bash
mkdir -p data logs uploads
docker compose up -d --build
```

Abra a [interface web](http://localhost:3000). A [documentação da API](http://localhost:8000/docs) estará disponível após a inicialização do backend. Veja o [guia do Docker](DOCKER.md) (em chinês) para mais detalhes.

No Linux, se os diretórios montados causarem erros de permissão, corrija a propriedade dos diretórios de dados do projeto com este comando e inicie os serviços novamente:

```bash
docker compose run --rm --no-deps --user root --entrypoint sh autoclip -c 'chown -R autoclip:autoclip /app/data /app/logs /app/uploads'
docker compose up -d
```

### 3. CLI / MCP

Requer Python 3.10 ou superior (3.11 recomendado) e FFmpeg no PATH. O exemplo usa um shell de macOS / Linux; no PowerShell do Windows, ative o ambiente com `venv\Scripts\Activate.ps1`. O processamento local pela CLI não precisa de Redis.

```bash
git clone https://github.com/zhouxiaoka/autoclip.git
cd autoclip
python3 -m venv venv
source venv/bin/activate
python -m pip install -r requirements.txt
python -m pip install -e .
```

Exemplo com modelo local: instale e inicie o Ollama, depois baixe um modelo. Vídeos sem legendas exigem `faster-whisper`; o modelo de voz é baixado no primeiro uso. Para usar legendas existentes, adicione `--srt talk.srt`.

```bash
ollama pull qwen2.5:7b
python -m pip install faster-whisper
autoclip doctor --provider ollama
autoclip run talk.mp4 --provider ollama --json
```

Substitua `PROJECT_ID` pelo ID do projeto retornado após o processamento para exportar no formato Shorts. Inicie o servidor MCP via stdio com `autoclip mcp`:

```bash
autoclip export PROJECT_ID --preset shorts
autoclip mcp
```

No cliente MCP, defina `command` como o caminho absoluto de `autoclip` no ambiente virtual e `args` como `["mcp"]`. Veja o [guia de CLI / MCP](docs/CLI_AND_MCP.md) e a [skill para agentes](skills/autoclip/SKILL.md) (ambos em chinês).

## Configuração de modelos

| Opção | Configuração |
| --- | --- |
| Modelos na nuvem | Em Configurações, selecione Qwen, OpenAI, Gemini, DeepSeek, Doubao Seed, Kimi ou GLM e informe a chave de API. Endpoints compatíveis aceitam uma Base URL personalizada. |
| Ollama | Endereço padrão: `http://localhost:11434/v1`; modelo: `qwen2.5:7b`. Não exige chave de API. |
| LM Studio | Carregue um modelo e inicie o Local Server, por padrão em `http://localhost:1234/v1`. Selecione um modelo disponível no seu servidor. |

Dentro do Docker, `localhost` aponta para o próprio contêiner. Para usar um modelo no host, configure um endereço acessível pelo contêiner; consulte o guia de CLI / MCP. O corte dos vídeos é local; a análise com modelos na nuvem envia o texto das legendas ao provedor escolhido. Downloads de vídeos e modelos ainda precisam de internet.

## Perguntas frequentes

<details>
<summary>É gratuito? Preciso de uma chave de API?</summary>

O AutoClip em si continua gratuito e de código aberto sob MIT. Provedores de modelos na nuvem cobram pelo uso e exigem sua própria chave de API. Ollama / LM Studio não precisam de chave de nuvem, mas exigem modelos e hardware adequado. A partir da **v1.3.2**, publicar no exterior exige a sua própria conta [Upload-Post](https://www.upload-post.com). Planos gratuitos e pagos, e os limites diários de TikTok, YouTube, Instagram e outras plataformas, seguem as páginas do próprio Upload-Post. Não são promessas do AutoClip.

</details>

<details>
<summary>Meus vídeos são enviados para a nuvem?</summary>

A edição fica no seu dispositivo. A análise com modelos na nuvem envia o texto das legendas ao provedor escolhido. O clipe pronto só sai da máquina depois que você clica em Publicar, e só para as plataformas que você conectou. Também dá para baixar sem publicar. Essa página Publicar está disponível na **v1.3.2**. Estatísticas e relatórios de erros dependem da versão e das configurações; consulte as notas de privacidade.

</details>

<details>
<summary>Posso usar vídeos sem legendas?</summary>

Sim, após preparar os componentes locais do Whisper e um modelo de voz. Também é possível importar SRT existente. Legendas precisas podem reduzir o tempo e os erros de transcrição.

</details>

<details>
<summary>Por que nenhum clipe foi gerado?</summary>

Verifique a etapa que falhou: legendas vazias, conexão com o modelo, pontuação mínima muito alta ou problemas no FFmpeg e no disco. Você pode reduzir o limite de 0.7 para 0.5, mas isso não garante clipes.

</details>

<details>
<summary>Quais vídeos funcionam melhor e quanto tempo leva?</summary>

A análise usa principalmente as legendas, sendo adequada para entrevistas, podcasts, aulas e comentários falados. Ação visual ou música podem ter resultados limitados. O tempo depende da duração, do hardware, do modelo e da exportação; comece com uma amostra curta.

</details>

[Guia completo de solução de problemas (inglês)](docs/FAQ.en.md) · [Problemas conhecidos](https://github.com/zhouxiaoka/autoclip/issues/96)

## Documentação

O README está disponível em oito idiomas; a maioria dos guias detalhados está em chinês. Os idiomas do README não indicam os idiomas compatíveis com a interface ou com os modelos de transcrição.

- [Instalação e primeiros clipes (English)](docs/USER_INSTALLATION_GUIDE.en.md)
- [Implantação com Docker (chinês)](DOCKER.md)
- [CLI, MCP e modelos locais (chinês)](docs/CLI_AND_MCP.md)
- [Provedores de modelos (chinês)](docs/MULTI_LLM_PROVIDER_GUIDE.md)
- [Perguntas frequentes (chinês)](docs/FAQ.md)
- [Guia de contribuição (chinês)](CONTRIBUTING.md)
- [Histórico de alterações](CHANGELOG.md)
- [Privacidade (chinês / inglês)](docs/PRIVACY.en.md)
- [Tradução do README e manutenção dos selos (chinês)](docs/i18n.md)

## Contribua e entre em contato

Correções, comentários e melhorias nas traduções são bem-vindos. Ao relatar um erro, inclua sistema operacional, versão, modelo, passos para reprodução e logs sem informações confidenciais.

Projeto mantido por uma pessoa no tempo livre. O prazo de resposta varia; não há suporte imediato nem assistência individual de implantação. Consulte as perguntas frequentes e os problemas conhecidos antes de entrar em contato.

Ideias, usos e pedidos de modelo vão para as [GitHub Discussions](https://github.com/zhouxiaoka/autoclip/discussions). Erros reproduzíveis usam o [formulário de issue](https://github.com/zhouxiaoka/autoclip/issues/new/choose). Regras do quadro: [community board](docs/COMMUNITY_BOARD.md) (chinês).

- [Boas-vindas e categorias](https://github.com/zhouxiaoka/autoclip/discussions/127)
- [Perguntas do primeiro clipe](https://github.com/zhouxiaoka/autoclip/discussions/128)
- [Ideias](https://github.com/zhouxiaoka/autoclip/discussions/129)

- E-mail: [christine_zhouye@163.com](mailto:christine_zhouye@163.com)

Agradecemos ao FastAPI, React, Tauri, FFmpeg, yt-dlp, Whisper e a todas as pessoas que contribuem. Distribuído sob a [licença MIT](LICENSE). Se o AutoClip for útil, considere dar uma estrela ao projeto.

[![Star History](https://api.star-history.com/svg?repos=zhouxiaoka/autoclip&type=Date)](https://star-history.com/#zhouxiaoka/autoclip&Date)
