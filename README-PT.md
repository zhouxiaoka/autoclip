<div align="center">

<img src="src-tauri/icons/128x128.png" alt="AutoClip" width="72" height="72">

# AutoClip

### Um link. Um clique.

Código aberto, com corte e render no seu computador. Cole um link, escolha a plataforma e gere <b>vídeo, capa e texto</b>,<br>
para Douyin, Xiaohongshu, TikTok, Reels, YouTube Shorts, Bilibili ou YouTube.<br>
O app é grátis; modelos cloud cobram por uso. Ajuste no editor quando precisar.

<p>
  <a href="https://github.com/zhouxiaoka/autoclip/releases/latest"><img src="https://img.shields.io/github/v/release/zhouxiaoka/autoclip?style=flat-square" alt="GitHub release"></a>
  <a href="https://github.com/zhouxiaoka/autoclip/stargazers"><img src="https://img.shields.io/github/stars/zhouxiaoka/autoclip?style=flat-square" alt="GitHub stars"></a>
  <a href="https://github.com/zhouxiaoka/autoclip/releases"><img src="https://img.shields.io/github/downloads/zhouxiaoka/autoclip/total?style=flat-square" alt="Downloads"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-blue?style=flat-square" alt="License: MIT"></a>
</p>

<a href="https://trendshift.io/repositories/25801"><img src="https://trendshift.io/api/badge/repositories/25801" alt="AutoClip — GitHub Trending" width="250" height="55"></a>

**[Baixar desktop](https://github.com/zhouxiaoka/autoclip/releases/latest)** · [Casos](https://zhouxiaoka.github.io/autoclip_intro/cases/) · [Início rápido](#início-rápido) · [Documentação](#documentação) · [Problema](https://github.com/zhouxiaoka/autoclip/issues/new/choose)

[简体中文](README.md) · [English](README-EN.md) · [日本語](README-JA.md) · [한국어](README-KO.md) · [Español](README-ES.md) · **Português** · [Русский](README-RU.md) · [Français](README-FR.md)

</div>

**[1.5.0 foi lançado oficialmente](https://github.com/zhouxiaoka/autoclip/releases/tag/v1.5.0)**, com desktop, CLI e MCP atualizados. Veja o [changelog](CHANGELOG.md) para produção automática, paginação de legendas, enquadramento e fila de vídeos longos. Atualize instalações antigas.

## Cortes reais

![Cortes verticais do AutoClip: entrevista Xiaohongshu, podcast TikTok, entrevista Douyin, podcast Shorts](docs/images/v2/demo-wall.webp)

Exemplos dos formatos entrevista e podcast do AutoClip. Vídeos completos e fontes estão na **[biblioteca de casos →](https://zhouxiaoka.github.io/autoclip_intro/cases/)**.

Cada clipe tem vídeo, capa, título, descrição, hashtags e kit ZIP para a plataforma. A biblioteca recebe novidades; [envie seus clipes](https://github.com/zhouxiaoka/autoclip/discussions/new?category=show-and-tell).

Os direitos do original ficam com os autores. Exemplos: [Dwarkesh Patel — Dario Amodei](https://www.youtube.com/watch?v=n1E9IZfvGMA) · [Y Combinator — Sam Altman](https://www.youtube.com/watch?v=ZIaOBAjvc38) · [WIRED — Hideo Kojima](https://www.youtube.com/watch?v=02Ah5VQrzvA)

## O que faz

### Cole o link e pronto

Gere no formato e duração da plataforma. Cada plataforma renderiza até 10 clipes elegíveis mais bem pontuados; os demais ficam sob demanda. Capa, título, descrição, hashtags e kit ZIP estão incluídos.

### O empacotamento já vem

Douyin / Xiaohongshu usam entrevista por padrão; TikTok / Reels / Shorts, podcast em tela cheia. O layout vertical pode mudar sem alterar o idioma da plataforma. Bilibili / YouTube são horizontais. O quadro segue o falante e preserva cenas sem pessoas. O encerramento de marca vem ligado e pode ser desligado nas configurações; o texto copiado não leva assinatura AutoClip.

### Fica no seu computador

Corte, enquadramento e render são locais. Escolha o modelo de análise e use legendas do autor, Whisper / SenseVoice local ou transcrição cloud configurada. CLI / MCP compartilham o fluxo do desktop.

## Tempo e custo com fontes reais

São três fontes diferentes medidas durante o desenvolvimento, não um comparativo controlado com a mesma entrada. Os valores estimam o uso de texto do qwen-plus na época, sem ASR cloud, imagens AI ou publicação. A cobrança real é do fornecedor.

| Versão | Original | Saída | Custo estimado do modelo de texto (CNY) |
| --- | --- | ---: | ---: |
| **Nova · com legendas** | Jensen · 1h43m (EN → Xiaohongshu) | **7,5 min / 10 cortes** | **¥0,09** |
| Nova · sem legendas | TIM × Luo Yonghao · 2h52m (ZH → Douyin) | 29,5 min / 10 cortes | ¥0,20 |
| Anterior | MrBeast · 2h06m (EN → TikTok) | 65 min | ¥0,64 |

<details>
<summary>Condições e registros</summary>

1º de outubro de 2026, mesmo Mac Apple Silicon. Os dois casos novos geraram 10 clipes; o anterior, 33, com fonte e quantidade diferentes. Jensen usou legendas do autor; TIM, Whisper base local.

Legendas do autor dispensam transcrição. Sem elas, escolha ASR local ou cloud. Plataformas e clipes extras aumentam tempo e uso. [Medições e cálculo](docs/COST_PER_VIDEO.md) (chinês).

</details>

## Escolha modelos e fluxo de dados

Corte e render ficam no computador. Análise cloud envia legendas e texto relevante; entendimento visual ou geração com referência envia quadros necessários; transcrição cloud envia áudio. Análise e transcrição locais dispensam a API cloud correspondente. Clipes são enviados às plataformas conectadas quando você escolhe publicar. Estatísticas e relatórios de erro podem ser desligados. [Privacidade](docs/PRIVACY.en.md).

## Início rápido

| Você quer | Use | Precisa de |
| --- | --- | --- |
| Fazer cortes neste computador | **Desktop** | macOS Apple Silicon ou Windows x64 |
| Hospedar / Linux | **Docker** | Docker e Compose v2 |
| Lote / agentes | **CLI / MCP** | Python 3.10+ (3.11 recomendado) e FFmpeg |

### Desktop

1. **Instale.** Em [Releases](https://github.com/zhouxiaoka/autoclip/releases/latest). macOS Apple Silicon: `.dmg`. Windows 10 / 11 x64: `-setup.exe`. Python e FFmpeg vêm junto.
2. **Configure um modelo.** Escolha o provedor e a API Key, selecione um modelo de análise disponível, teste a conexão e salve. Para modelos locais, carregue um modelo e inicie Ollama / LM Studio primeiro.
3. **Link e plataforma.** Comece com entrevista ou podcast legendado e escolha layout vertical. Sem legendas, prepare Whisper / SenseVoice ou configure transcrição cloud nas configurações.
4. **Revise e salve.** Confira legendas, quadro e conteúdo, depois baixe o kit ou conecte uma conta para postar. Gere alternativas quando precisar de mais clipes.

Intel Mac / Linux podem usar Docker ou CLI. Veja o [guia de instalação](docs/USER_INSTALLATION_GUIDE.en.md) e a [1.5.0 Release](https://github.com/zhouxiaoka/autoclip/releases/tag/v1.5.0) para requisitos, primeira abertura e escopo de validação.

[Guia de instalação](docs/USER_INSTALLATION_GUIDE.en.md) · [Problemas](docs/FAQ.en.md)

**Docker / Web**

```bash
git clone https://github.com/zhouxiaoka/autoclip.git
cd autoclip
cp env.example .env
mkdir -p data logs uploads
docker compose up -d --build
```

Abra a [UI web](http://localhost:3000). A [API](http://localhost:8000/docs) fica disponível depois do backend. [Guia Docker](docs/DOCKER.en.md).

No Linux, se o bind falhar por permissão, ajuste o dono primeiro:

```bash
docker compose run --rm --no-deps --user root --entrypoint sh autoclip -c 'chown -R autoclip:autoclip /app/data /app/logs /app/uploads'
docker compose up -d
```

Para IP de rede ou domínio próprio, adicione o frontend a `AUTOCLIP_ALLOWED_ORIGINS` no `.env` (separado por vírgulas).

**CLI / MCP**

Python 3.10+ (3.11 recomendado), FFmpeg e FFprobe no PATH; Redis não é necessário. Baixe o [ZIP oficial CLI / MCP](https://github.com/zhouxiaoka/autoclip/releases/download/v1.5.0/autoclip-1.5.0-cli-mcp.zip), extraia e execute naquele diretório:

```bash
python3 -m venv venv
source venv/bin/activate
python -m pip install -r requirements.txt
python -m pip install --force-reinstall --no-deps autoclip-1.5.0-py3-none-any.whl
```

Os comandos acima são para macOS / Linux. No Windows, crie com `py -m venv venv` e ative com `.\venv\Scripts\Activate.ps1`; depois use os mesmos comandos `python -m pip`.

Salve os modelos antes: use configurações do desktop ou configure seu diretório pelo exemplo sem chaves do ZIP. [CLI / MCP](docs/CLI_AND_MCP.md) (chinês). `produce` não usa a substituição temporária de `run --provider`. `--srt` evita transcrever.

```bash
autoclip --version
autoclip produce talk.mp4 --srt talk.srt --platform douyin --portrait-style podcast --json
autoclip outputs PROJECT_ID --export-kits
```

O cliente MCP inicia o servidor. Para depuração separada, execute `autoclip mcp` em outro terminal; o OpenCode pode ser configurado com `autoclip mcp install opencode`.

Troque `PROJECT_ID` pelo ID retornado. MCP usa `start_quick_output` / `get_quick_output_status`; `command` aponta ao caminho absoluto de `autoclip` no venv e `args` é `["mcp"]`. `run` / `export` e ferramentas antigas continuam. [CLI / MCP](docs/CLI_AND_MCP.md) (chinês), [OpenCode](docs/OPENCODE.en.md), [Agent skill](skills/autoclip/SKILL.md) (chinês).

## Modelos

| Opção | Configuração |
| --- | --- |
| API na nuvem | Escolha o provedor e a API Key. Compatível com OpenAI aceita Base URL. |
| Ollama | Endereço padrão `http://localhost:11434/v1`. Baixe e inicie um modelo local, depois escolha um modelo oferecido pelo servidor. Sem API Key. |
| LM Studio | Carregue um modelo e inicie o Local Server, `http://localhost:1234/v1` por padrão. |

Dentro do Docker, `localhost` é o contêiner. Use um endereço do host que o contêiner alcance.

[Modelos](docs/MULTI_LLM_PROVIDER_GUIDE.md) (chinês) · [Local e contêineres](docs/CLI_AND_MCP.md) (chinês)

## Agradecimentos ❤️

<table>
  <tr>
    <td align="center" width="140">
      <a href="https://88api.ai/sign-up?aff=2PIc"><img src="docs/sponsors/88api-logo.jpg" alt="88API" width="88"></a><br>
      <a href="https://88api.ai/sign-up?aff=2PIc"><strong>88API</strong></a>
    </td>
    <td>
      Agradecemos à <strong>88API</strong> por patrocinar o AutoClip! Reúne GPT, Claude, Gemini, Grok, DeepSeek, Kimi e GLM para analisar legendas, selecionar destaques e gerar títulos.<br>
      🎨 <strong>Multimídia</strong>: Modelos de imagem, vídeo e áudio, incluindo GPT-Image, Seedance, Veo, MiniMax Hailuo H3, Kling, Whisper e TTS. O AutoClip utiliza APIs compatíveis de análise, capas e transcrição.<br>
      🏷️ <strong>Serviço e faturamento</strong>: Segundo o parceiro, a operação é de uma empresa no exterior, com atendimento humano, faturas e proporção de recarga de 1:1; aplicam-se as condições da plataforma.<br>
      🎁 <strong>Novos usuários</strong>: Receba créditos de teste para avaliar modelos pelo <a href="https://88api.ai/sign-up?aff=2PIc">link de indicação</a>, conforme as condições da promoção. <a href="docs/88API_SETUP.en.md">Guia de configuração (inglês)</a>
    </td>
  </tr>
  <tr>
    <td align="center" width="140">
      <a href="https://www.infistar.cc/register?aff=XLK3BCM6&amp;ref_source=link"><img src="docs/sponsors/infistar-logo.svg" alt="Infistar" width="88"></a><br>
      <a href="https://www.infistar.cc/register?aff=XLK3BCM6&amp;ref_source=link"><strong>Infistar.cc</strong></a>
    </td>
    <td>
      Agradecemos à <strong>Infistar.cc</strong> por patrocinar o AutoClip! Sua API com vários modelos pode ser usada para analisar transcrições de vídeos longos, selecionar destaques e gerar títulos.<br>
      ⚙️ <strong>Configuração compatível</strong>: No AutoClip, escolha o provedor compatível com OpenAI e informe a Base URL, sua chave de API e um modelo disponível.<br>
      🧩 <strong>Vários modelos</strong>: O parceiro oferece Claude, GPT, Gemini, DeepSeek e outras famílias. Escolha modelos que aceitem o endpoint compatível para comparar a análise de transcrições e a seleção de destaques.<br>
      🏷️ <strong>Preços e serviços</strong>: Segundo o parceiro, alguns modelos custam a partir de <strong>1% do preço oficial</strong>, com cobrança em RMB, emissão de faturas e verificação de autenticidade dos modelos. Confira os modelos, preços e condições atuais na plataforma.<br>
      🎁 <strong>Oferta para AutoClip</strong>: Novos usuários podem receber <strong>$5 em créditos de teste</strong> pelo <a href="https://www.infistar.cc/register?aff=XLK3BCM6&amp;ref_source=link">link de indicação</a>, conforme as condições da promoção. <a href="docs/INFISTAR_SETUP.en.md">Guia de configuração (inglês)</a>
    </td>
  </tr>
</table>

## Perguntas frequentes

<details>
<summary>É grátis? Preciso de API Key?</summary>

App grátis sob MIT. Análise, transcrição e imagens cloud usam suas credenciais e tarifas do fornecedor. A capa automática não usa geração paga por padrão. Ollama / LM Studio dispensam chave cloud, mas exigem hardware. Publicar exige sua conta Bilibili ou [Upload-Post](https://www.upload-post.com).

</details>

<details>
<summary>Meus vídeos são enviados?</summary>

Corte e render ficam no computador. Análise cloud envia legendas e texto relevante; entendimento visual ou geração com referência envia quadros necessários; transcrição cloud envia áudio. Análise e transcrição locais dispensam a API cloud correspondente. Clipes são enviados às plataformas conectadas quando você escolhe publicar. Estatísticas e relatórios de erro podem ser desligados. [Privacidade](docs/PRIVACY.en.md).

</details>

<details>
<summary>Quais vídeos funcionam melhor?</summary>

Entrevistas, podcasts, cursos e vídeos falados são os principais casos validados. Legendas do autor são mais rápidas; sem elas, transcrição local/cloud. Para jogos ou pouco diálogo, ative entendimento visual com modelo de imagens e revise os momentos escolhidos.

</details>

<details>
<summary>Por que não saiu nenhum clipe?</summary>

Confira transcrição, modelo, FFmpeg, disco e regras da plataforma. YouTube longo exige clipes completos de no mínimo 180 segundos; use Shorts/Bilibili para fontes curtas. Inclua versão 1.5.0, OS, duração, modelo e logs sem segredos em [problemas conhecidos](https://github.com/zhouxiaoka/autoclip/issues/96).

</details>

[Solução de problemas](docs/FAQ.en.md) · [Problemas conhecidos](https://github.com/zhouxiaoka/autoclip/issues/96)

## Documentação

| Você quer | Docs |
| --- | --- |
| Instalar e primeiros cortes | [Instalação](docs/USER_INSTALLATION_GUIDE.en.md) |
| Hospedar e automatizar | [Docker](docs/DOCKER.en.md) · [CLI / MCP](docs/CLI_AND_MCP.md) (chinês) · [Agent skill](skills/autoclip/SKILL.md) (chinês) · [OpenCode](docs/OPENCODE.en.md) |
| Modelos e falhas | [Modelos](docs/MULTI_LLM_PROVIDER_GUIDE.md) (chinês) · [FAQ](docs/FAQ.en.md) |
| Versões, roteiro, privacidade | [Changelog](CHANGELOG.md) · [Roteiro](ROADMAP.md) (chinês) · [Quadro](docs/COMMUNITY_BOARD.md) (chinês) · [Privacidade](docs/PRIVACY.en.md) |
| Contribuir e traduzir | [Contribuir](CONTRIBUTING.md) (chinês) · [Traduções](docs/i18n.md) (chinês) |

## Contribuir

Correções, exemplos, feedback e traduções são bem-vindos. Se o AutoClip ajudar, um star ajuda de volta.

- **Conversar:** [Discussions](https://github.com/zhouxiaoka/autoclip/discussions) · [Primeiro corte](https://github.com/zhouxiaoka/autoclip/discussions/128) · [Ideias](https://github.com/zhouxiaoka/autoclip/discussions/129)
- **Falhas:** [formulário](https://github.com/zhouxiaoka/autoclip/issues/new/choose) com SO, versão, modelo, passos e logs sem segredo
- **Parcerias:** [christine_zhouye@163.com](mailto:christine_zhouye@163.com)

Mantido por uma pessoa. Sem suporte ao vivo nem deploy um a um.

![Star History](https://api.star-history.com/svg?repos=zhouxiaoka/autoclip&type=Date)

Obrigado ao FastAPI, React, Tauri, FFmpeg, yt-dlp, Whisper, FunASR e a quem contribui. [MIT License](LICENSE).
