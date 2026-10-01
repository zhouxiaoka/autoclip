<div align="center">

<img src="src-tauri/icons/128x128.png" alt="AutoClip" width="72" height="72">

# AutoClip

### Um link. Um clique.

Código aberto, grátis e no seu computador. Cole um link, gaste alguns centavos e receba <b>mais de 10 cortes prontos para postar</b>,<br>
cada um com capa, título, descrição e hashtags para Douyin, Xiaohongshu, TikTok, Reels ou YouTube Shorts.<br>
Sem editor. Sem conversa longa com um chat de IA.

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

## Cortes reais

![Cortes verticais do AutoClip: entrevista Xiaohongshu, podcast TikTok, entrevista Douyin, podcast Shorts](docs/images/v2/demo-wall.webp)

Cada original foi um único link. Cada corte acima é a saída crua do AutoClip — escolha, enquadramento, tradução, empacotamento — sem edição manual. **[Assistir com áudio na biblioteca →](https://zhouxiaoka.github.io/autoclip_intro/cases/)**

Cada corte entrega o kit de publicação: vídeo vertical, capa, título, descrição e hashtags. A biblioteca é atualizada; [envie os seus](https://github.com/zhouxiaoka/autoclip/discussions/new?category=show-and-tell).

Os direitos do original ficam com os autores. Exemplos: [Dwarkesh Patel — Dario Amodei](https://www.youtube.com/watch?v=n1E9IZfvGMA) · [Y Combinator — Sam Altman](https://www.youtube.com/watch?v=ZIaOBAjvc38) · [WIRED — Hideo Kojima](https://www.youtube.com/watch?v=02Ah5VQrzvA)

## O que faz

### Cole o link e pronto
Sem editor e sem chat de IA. Escolha a plataforma e gere no formato certo. Capa, título, descrição e hashtags vêm juntos.

### O empacotamento já vem
Estilo entrevista no Douyin / Xiaohongshu; estilo podcast no TikTok / Reels / Shorts. O quadro segue quem fala; material estrangeiro ganha título local e legendas bilíngues.

### Fica no seu computador
Corte e render são locais. Você escolhe o modelo, abre o editor só se quiser ajustar e usa CLI / MCP para lote.

## Rápido e barato

Um link entra, **mais de 10** cortes prontos saem, cada um com capa, título, descrição e hashtags.

| Versão | Original | Saída | Custo |
| --- | --- | ---: | ---: |
| **Nova · com legendas** | Jensen · 1h43m (EN → Xiaohongshu) | **7,5 min / 10 cortes** | **¥0,09** |
| Nova · sem legendas | TIM × Luo Yonghao · 2h52m (ZH → Douyin) | 29,5 min / 10 cortes | ¥0,20 |
| Anterior | MrBeast · 2h06m (EN → TikTok) | 65 min | ¥0,64 |

Uma entrevista de 2–3 h costuma ficar em ¥0,1–0,2. Sem legendas do autor, o reconhecimento de voz é local e demora mais; o vídeo não sai da máquina.

<details>
<summary>Como esses números foram medidos</summary>

1º de outubro de 2026, o mesmo Mac Apple Silicon, modelo de análise qwen-plus (¥0,8 / ¥2 por milhão de tokens de entrada / saída, preço de terceiros Aliyun Bailian). O custo é só chamada de modelo.

Os 7,5 min de Jensen: ~1 min de download, sem ASR graças às legendas do autor, 25 s de seleção, ~2,5 min de corte / quadro / empacote, ~3 min para renderizar 10. A versão anterior gastava 35 min só na seleção.

Esta versão muda quatro coisas: uma passagem na transcrição inteira; chamadas em paralelo; pula ASR local se houver legendas do autor; renderiza só os 10 melhores por padrão.

</details>

## Frente a ferramentas cloud mensais

| | AutoClip | Ferramentas cloud mensais |
| --- | --- | --- |
| Custo | O app é grátis; o modelo é por uso, ~¥0,1–0,2 por 2–3 h | Assinatura mensal, por tempo de processo |
| Onde o vídeo é processado | Seu computador; a nuvem só vê o texto | Upload para a nuvem do fornecedor |
| Modelos | Você escolhe, inclusive local | Os do fornecedor |
| Plataformas chinesas | Modelos Douyin, Xiaohongshu, Bilibili | Principalmente internacionais |
| Código | MIT, pode alterar e hospedar | Fechado |

A coluna da direita segue páginas públicas de produtos semelhantes em outubro de 2026; confira cada produto.

## Início rápido

| Você quer | Use | Precisa de |
| --- | --- | --- |
| Fazer cortes neste computador | **Desktop** | macOS Apple Silicon ou Windows x64 |
| Hospedar / Linux | **Docker** | Docker e Compose v2 |
| Lote / agentes | **CLI / MCP** | Python 3.10+ (3.11 recomendado) e FFmpeg |

### Desktop

1. **Instale.** Em [Releases](https://github.com/zhouxiaoka/autoclip/releases/latest). macOS Apple Silicon: `.dmg`. Windows 10 / 11 x64: `-setup.exe`. Python e FFmpeg vêm junto.
2. **Configure um modelo.** Escolha o provedor em Ajustes e cole a API Key; o modelo de análise é escolhido sozinho. No local, inicie o Ollama ou o LM Studio antes.
3. **Cole um link e escolha a plataforma.** Comece com uma entrevista ou podcast de 10–30 min com legendas. Sem elas, prepare Whisper ou SenseVoice em Ajustes.
4. **Pegue os cortes.** Veja os 10 melhores, edite se quiser, baixe ou publique.

Os instaladores ainda não têm notarização da Apple nem assinatura do Windows. No macOS, a primeira abertura é com clique direito → Abrir. No Windows, Mais informações → Executar mesmo assim.

[Guia de instalação](docs/USER_INSTALLATION_GUIDE.en.md) · [Problemas](docs/FAQ.en.md)

**Docker / Web**

```bash
git clone https://github.com/zhouxiaoka/autoclip.git
cd autoclip
cp env.example .env          # 选择 LLM_PROVIDER，填 API Key 和模型名；也可以启动后在设置页配置
mkdir -p data logs uploads
docker compose up -d --build
```

Abra a [UI web](http://localhost:3000). A [API](http://localhost:8000/docs) fica disponível depois do backend. [Guia Docker](docs/DOCKER.en.md).

No Linux, se o bind falhar por permissão, ajuste o dono primeiro:

```bash
docker compose run --rm --no-deps --user root --entrypoint sh autoclip -c 'chown -R autoclip:autoclip /app/data /app/logs /app/uploads'
docker compose up -d
```

**CLI / MCP**

Precisa de Python 3.10+ (3.11 recomendado) e FFmpeg no PATH. CLI local não precisa de Redis.

```bash
git clone https://github.com/zhouxiaoka/autoclip.git
cd autoclip
python3 -m venv venv && source venv/bin/activate   # Windows PowerShell：venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m pip install -e .
```

```bash
ollama pull qwen2.5:7b
python -m pip install faster-whisper                # 无字幕视频需要；已有字幕可用 --srt talk.srt
autoclip doctor --provider ollama
autoclip run talk.mp4 --provider ollama --json
autoclip export PROJECT_ID --preset shorts
autoclip mcp                                        # stdio MCP 服务
autoclip mcp install opencode                       # opencode 一条命令接入
```

No cliente MCP, `command` é o caminho absoluto do `autoclip` no venv e `args` é `["mcp"]`. [CLI / MCP](docs/CLI_AND_MCP.md) (chinês), [OpenCode](docs/OPENCODE.en.md), [Agent skill](skills/autoclip/SKILL.md) (chinês).

## Modelos

| Opção | Configuração |
| --- | --- |
| API na nuvem | Escolha o provedor e a API Key. Compatível com OpenAI aceita Base URL. |
| Ollama | `http://localhost:11434/v1` por padrão, modelo `qwen2.5:7b`, sem chave. |
| LM Studio | Carregue um modelo e inicie o Local Server, `http://localhost:1234/v1` por padrão. |

Dentro do Docker, `localhost` é o contêiner. Use um endereço do host que o contêiner alcance.

[Modelos](docs/MULTI_LLM_PROVIDER_GUIDE.md) (chinês) · [Local e contêineres](docs/CLI_AND_MCP.md) (chinês)

## Patrocinadores

Obrigado a estes parceiros. Os dois expõem API compatível com OpenAI: escolha em Ajustes, cole a chave e os modelos aparecem.

<table>
  <tr>
    <td align="center" width="140" valign="middle">
      <a href="https://88api.ai/sign-up?aff=2PIc"><img src="docs/sponsors/88api-logo.jpg" alt="88API" width="72"></a><br>
      <a href="https://88api.ai/sign-up?aff=2PIc"><strong>88API</strong></a>
    </td>
    <td valign="middle">
      Agregador de tokens: GPT, Claude, Gemini, Grok, DeepSeek, Kimi, GLM, mais imagem, vídeo e voz. Suporte, nota fiscal, recarga 1:1. Crédito de teste no <a href="https://88api.ai/sign-up?aff=2PIc">link de indicação</a>. <a href="docs/88API_SETUP.en.md">Guia</a>
    </td>
  </tr>
  <tr>
    <td align="center" width="140" valign="middle">
      <a href="https://www.infistar.cc/register?aff=XLK3BCM6&amp;ref_source=link"><img src="docs/sponsors/infistar-logo.svg" alt="Infistar" width="72"></a><br>
      <a href="https://www.infistar.cc/register?aff=XLK3BCM6&amp;ref_source=link"><strong>Infistar</strong></a>
    </td>
    <td valign="middle">
      API multimodelo: Claude, GPT, Gemini, DeepSeek e outros; alguns a 1% do preço oficial, RMB, nota e verificação. US$ 5 de teste no <a href="https://www.infistar.cc/register?aff=XLK3BCM6&amp;ref_source=link">link de indicação</a>. <a href="docs/INFISTAR_SETUP.en.md">Guia</a>
    </td>
  </tr>
</table>

Serviços, preços e ofertas vêm dos parceiros; vale o que estiver no site deles.

## Perguntas frequentes

<details>
<summary>É grátis? Preciso de API Key?</summary>

O AutoClip é grátis e MIT. Modelos na nuvem são cobrados pelo provedor e pedem a sua chave; uma entrevista de 1 h 43 min mediu cerca de ¥0,09. Ollama / LM Studio não pedem chave na nuvem, mas pedem hardware. Publicar no exterior exige a sua conta [Upload-Post](https://www.upload-post.com).

</details>

<details>
<summary>Meus vídeos são enviados?</summary>

Corte e render ficam no aparelho. Modelos na nuvem recebem o texto. O corte só sai depois de Publicar, para as plataformas que você conectou. Análise e relatórios de erro podem ser desligados. [Privacidade](docs/PRIVACY.en.md).

</details>

<details>
<summary>Que vídeos funcionam melhor?</summary>

A análise usa sobretudo a transcrição: entrevistas, podcasts, cursos e talking-head. Legendas do autor são as mais rápidas; sem elas, primeiro transcreve no local. Ação ou música pura rende pouco.

</details>

<details>
<summary>Por que não saíram cortes?</summary>

Veja a etapa que falhou: legendas vazias, conexão do modelo, FFmpeg ou disco. Tente um modelo mais forte. Se continuar, descreva tipo, duração e modelo em [problemas conhecidos](https://github.com/zhouxiaoka/autoclip/issues/96).

</details>

[Guia de problemas](docs/FAQ.en.md) · [Problemas conhecidos](https://github.com/zhouxiaoka/autoclip/issues/96)

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
