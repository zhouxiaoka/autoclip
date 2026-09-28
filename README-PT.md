<div align="center">

<img src="src-tauri/icons/128x128.png" alt="AutoClip" width="80" height="80">

# AutoClip

**Encontre os melhores momentos dos seus vídeos com IA e gere clipes curtos em HD com um clique.**

[简体中文](README.md) · [English](README-EN.md) · [日本語](README-JA.md) · [한국어](README-KO.md) · [Español](README-ES.md) · **Português** · [Русский](README-RU.md) · [Français](README-FR.md)

[![GitHub release](https://img.shields.io/github/v/release/zhouxiaoka/autoclip?style=flat-square)](https://github.com/zhouxiaoka/autoclip/releases/latest)
[![GitHub stars](https://img.shields.io/github/stars/zhouxiaoka/autoclip?style=flat-square)](https://github.com/zhouxiaoka/autoclip/stargazers)
[![GitHub forks](https://img.shields.io/github/forks/zhouxiaoka/autoclip?style=flat-square)](https://github.com/zhouxiaoka/autoclip/forks)
[![GitHub issues](https://img.shields.io/github/issues/zhouxiaoka/autoclip?style=flat-square)](https://github.com/zhouxiaoka/autoclip/issues)
[![License: MIT](https://img.shields.io/github/license/zhouxiaoka/autoclip?style=flat-square)](LICENSE)

<p align="center">
  <a href="https://trendshift.io/repositories/25801"><img src="https://trendshift.io/api/badge/repositories/25801" alt="AutoClip — Trendshift" width="250" height="55"></a>
</p>

Grátis e de código aberto · Edição local · Modelos locais e na nuvem

[Site](https://zhouxiaoka.github.io/autoclip_intro/) · [Discussions](https://github.com/zhouxiaoka/autoclip/discussions) · [Relatar um problema](https://github.com/zhouxiaoka/autoclip/issues)

**Instaladores desktop: [macOS · Apple Silicon](https://github.com/zhouxiaoka/autoclip/releases/latest) · [Windows · x64](https://github.com/zhouxiaoka/autoclip/releases/latest)**

[Instalação e primeiros clipes (English)](docs/USER_INSTALLATION_GUIDE.en.md) · [Guia completo de solução de problemas (inglês)](docs/FAQ.en.md)

</div>

Transforme entrevistas, podcasts, cursos e gravações de lives em vídeos curtos. O AutoClip encontra destaques, gera títulos e cria clipes e compilações que você pode ajustar e exportar.

## Prévia

![Tela de importação do AutoClip](docs/images/import-local.jpg)

Importe um vídeo local com legendas SRT opcionais. A imagem mostra a interface em chinês.

## Funcionalidades

| Função | Descrição |
| --- | --- |
| Importar vídeos | Arquivos locais e links do YouTube ou Bilibili. |
| Encontrar destaques | Analisa legendas para selecionar trechos, gerar títulos e organizar assuntos na linha do tempo. |
| Editar clipes | Cria clipes e compilações; ajuste início e fim, texto e proporção da imagem. |
| Destaques de jogos | Detecta eventos em partidas gravadas. É preciso configurar um modelo visual e ativar a análise de jogos; o provedor cobra as chamadas na nuvem. [Configuração (chinês)](docs/MULTI_LLM_PROVIDER_GUIDE.md). |
| Exportar e publicar | Vídeos verticais ou horizontais com legendas e cartões de título, capas automáticas e publicação imediata ou agendada. [Guia de publicação (chinês)](docs/PUBLISH_UPLOAD_POST.md). |
| Modelos e automação | Qwen, OpenAI, Gemini, DeepSeek e outros modelos na nuvem, ou modelos locais com Ollama / LM Studio. Acesso por CLI e MCP. |

> Importar → Confirmar o tipo de vídeo → Análise e edição com IA → Ajustar e exportar

## Como começar

1. **Instale.** Baixe o `.dmg` para macOS Apple Silicon ou o `-setup.exe` para Windows x64 em [GitHub Releases](https://github.com/zhouxiaoka/autoclip/releases/latest). Python e FFmpeg estão incluídos.
2. **Configure um modelo.** Nas configurações, informe sua API Key ou conecte um modelo local, teste a conexão e salve.
3. **Crie clipes.** Importe o vídeo e confirme seu tipo para iniciar a análise e a edição. Revise, ajuste e exporte o resultado.

A instalação, importação e gravação de arquivos em uma máquina Windows física ainda aguardam validação. No Intel Mac e Linux, use Docker ou a CLI.

[Instalação (inglês)](docs/USER_INSTALLATION_GUIDE.en.md) · [Solução de problemas (inglês)](docs/FAQ.en.md)

<details>
<summary>Docker / Web, CLI e MCP</summary>

- **Docker / Web:** Hospede a interface web com o [guia do Docker (inglês)](docs/DOCKER.en.md).
- **CLI:** Processamento em lote e scripts; veja o [guia da CLI (chinês)](docs/CLI_AND_MCP.md).
- **MCP:** Conecte um cliente seguindo o mesmo guia ou use a [Agent skill (chinês)](skills/autoclip/SKILL.md).

</details>

## Perguntas frequentes

<details>
<summary>Quanto custa?</summary>

O AutoClip é gratuito e de código aberto, sob licença MIT. Modelos na nuvem exigem sua própria API Key e são cobrados pelo provedor. Modelos locais do Ollama / LM Studio dispensam chave de nuvem. A publicação em plataformas internacionais exige sua conta no [Upload-Post](https://www.upload-post.com); consulte preços e limites no site.

</details>

<details>
<summary>Meu vídeo é enviado para a nuvem?</summary>

A edição e a renderização ocorrem no seu computador. A análise de legendas na nuvem envia o texto relevante; a análise visual envia quadros selecionados e o texto necessário. Ao publicar, o vídeo final é enviado às plataformas conectadas. Você também pode exportar apenas localmente. [Privacidade (inglês)](docs/PRIVACY.en.md).

</details>

<details>
<summary>Posso usar vídeos sem legenda?</summary>

Sim. Configure o Whisper local e um modelo de voz para transcrever, ou importe um SRT existente. Comece com um vídeo curto com legendas seguindo o [guia inicial (inglês)](docs/USER_INSTALLATION_GUIDE.en.md).

</details>

<details>
<summary>Quais vídeos funcionam melhor? É possível exportar em HD?</summary>

A análise de legendas é adequada para entrevistas, podcasts, cursos e vídeos com fala. Gravações de jogos podem usar análise visual. Há exportação horizontal e vertical em 1080p; a qualidade depende do original e das configurações. O tempo de processamento varia conforme a duração, o modelo e o hardware.

</details>

## Documentação e comunidade

- [Instalação (inglês)](docs/USER_INSTALLATION_GUIDE.en.md) · [Modelos (chinês)](docs/MULTI_LLM_PROVIDER_GUIDE.md) · [Ajuda (inglês)](docs/FAQ.en.md)
- [Histórico de alterações (chinês)](CHANGELOG.md) · [Documentação (chinês)](docs/README.md)
- Compartilhe perguntas e ideias em [Discussions](https://github.com/zhouxiaoka/autoclip/discussions) e relate bugs em [Issues](https://github.com/zhouxiaoka/autoclip/issues/new/choose).
- Contribuições de código, documentação e tradução são bem-vindas. [Guia de contribuição (chinês)](CONTRIBUTING.md).
- Contato e patrocínios: [christine_zhouye@163.com](mailto:christine_zhouye@163.com)

Obrigado a todos os colaboradores e a projetos como FastAPI, React, Tauri, FFmpeg, yt-dlp e Whisper. Se o AutoClip ajudar você, considere dar uma Star.

[![Star History](https://api.star-history.com/svg?repos=zhouxiaoka/autoclip&type=Date)](https://star-history.com/#zhouxiaoka/autoclip&Date)
