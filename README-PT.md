<div align="center">

<img src="src-tauri/icons/128x128.png" alt="AutoClip" width="72" height="72">

# AutoClip

### Ferramenta de código aberto para extrair destaques de vídeos com IA

Transforme vídeos longos em momentos que merecem ser compartilhados.

[![GitHub release](https://img.shields.io/github/v/release/zhouxiaoka/autoclip?style=flat-square)](https://github.com/zhouxiaoka/autoclip/releases/latest)
[![GitHub stars](https://img.shields.io/github/stars/zhouxiaoka/autoclip?style=flat-square)](https://github.com/zhouxiaoka/autoclip/stargazers)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue?style=flat-square)](LICENSE)

<p align="center">
  <a href="https://trendshift.io/repositories/25801"><img src="https://trendshift.io/api/badge/repositories/25801" alt="AutoClip — GitHub Trending" width="250" height="55"></a>
  <a href="https://trendshift.io/repositories/25801"><img src="https://trendshift.io/api/badge/trendshift/repositories/25801/daily?language=Python" alt="AutoClip — Trendshift Python daily ranking" width="250" height="55"></a>
  <a href="https://trendshift.io/repositories/25801"><img src="https://trendshift.io/api/badge/trendshift/repositories/25801/daily" alt="AutoClip — Trendshift daily ranking, all languages" width="250" height="55"></a>
</p>

**[Baixar aplicativo](https://github.com/zhouxiaoka/autoclip/releases/latest)** · [Início rápido](#quick-start) · [Site](https://zhouxiaoka.github.io/autoclip_intro/) · [Documentação](#documentation) · [Relatar problema](https://github.com/zhouxiaoka/autoclip/issues/new/choose)

[简体中文](README.md) · [English](README-EN.md) · [日本語](README-JA.md) · [한국어](README-KO.md) · [Español](README-ES.md) · **Português** · [Русский](README-RU.md) · [Français](README-FR.md)

</div>

O AutoClip usa IA para analisar legendas, encontrar destaques, criar títulos e gerar clipes e coletâneas automaticamente. Ideal para entrevistas, podcasts, cursos e gravações de transmissões ao vivo, oferece um aplicativo desktop, uma interface web via Docker e acesso por CLI / MCP.

## Veja a interface

![Importação e gerenciamento de projetos](docs/images/home-v1.4.0.png)

<table>
  <tr>
    <td width="50%" align="center"><strong>Clipes gerados por IA</strong></td>
    <td width="50%" align="center"><strong>Prévia e edição no Studio</strong></td>
  </tr>
  <tr>
    <td><a href="docs/images/clips-v1.4.0.png"><img src="docs/images/clips-v1.4.0.png" alt="Clipes gerados por IA" width="100%"></a></td>
    <td><a href="docs/images/studio-v1.4.0.png"><img src="docs/images/studio-v1.4.0.png" alt="Prévia e edição no Studio" width="100%"></a></td>
  </tr>
</table>

<sub>Interface real da v1.4.0 com correções posteriores do Studio: importe vídeos, confira clipes realmente gerados e edite no Studio. A interface está em chinês; a transcrição e os títulos do exemplo estão em inglês.</sub>

[Versão das capturas e origem do exemplo (chinês)](docs/images/README.md)

## Agradecimentos ❤️

<table>
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

## O que você pode fazer

### Encontre destaques em vídeos longos

- **Importar vídeos**: Use arquivos locais ou links do YouTube e Bilibili, com legendas SRT opcionais.

<details>
<summary>Ver captura · Importar vídeos</summary>

![Importar vídeos](docs/images/feature-import.png)

</details>

- **Encontrar destaques**: Extraia resumos, intervalos por assunto, pontuações e títulos a partir das legendas.

<details>
<summary>Ver captura · Encontrar destaques</summary>

![Encontrar destaques](docs/images/clips-v1.4.0.png)

</details>

- **Criar clipes e coletâneas**: Gere clipes e coletâneas sugeridas e ajuste a ordem manualmente.

<details>
<summary>Ver captura · Criar clipes e coletâneas</summary>

![Criar clipes e coletâneas](docs/images/feature-collections.png)

</details>


### Exporte e publique

- **Exportar para publicar**: Use predefinições para Douyin, Xiaohongshu, YouTube Shorts e Bilibili, com legendas embutidas e cartões de título.

<details>
<summary>Ver captura · Exportar para publicar</summary>

![Exportar para publicar](docs/images/feature-export.png)

</details>

- **Capas e publicação**: Desde a v1.3.2, gere capas e publique imediatamente ou com agendamento. Conecte plataformas internacionais pela sua conta Upload-Post; o Bilibili é configurado separadamente.

<details>
<summary>Ver captura · Capas e publicação</summary>

![Capas e publicação](docs/images/feature-publish.png)

![Capas e publicação](docs/images/feature-cover.png)

A demonstração não tem uma conta de publicação conectada. As imagens mostram a entrada de publicação e as configurações de capa, não publicações concluídas.

</details>

- **Gerenciamento de publicações**: Consulte o histórico e o calendário, gerencie publicações pendentes ou apenas baixe os clipes.

<details>
<summary>Ver captura · Gerenciamento de publicações</summary>

![Gerenciamento de publicações](docs/images/feature-calendar.png)

</details>


<details>
<summary>Plataformas, requisitos de conta e detalhes de exportação</summary>

Quando os clipes estiverem prontos, abra Publicar em um clipe. Disponível na **v1.3.2**. No exterior, usam-se as plataformas ligadas na sua própria conta Upload-Post: TikTok, Instagram, YouTube, Facebook, LinkedIn, X, Threads, Pinterest, Bluesky, Discord, Telegram e Google Business, conforme o que essa conta tiver ligado. O Bilibili é uma conta: cole um Cookie uma vez em Configurações.

Ele precisa incluir SESSDATA, bili_jct e DedeUserID. Publique agora ou agende. Título e descrição são opcionais e, se ficarem vazios, usam o título do clipe. Legendas embutidas vêm ligadas, assim como o cartão de título de cerca de 4 segundos.

A visibilidade padrão é só eu / private onde a plataforma aceita. O AutoClip promete isso apenas para TikTok, YouTube e Bilibili. Também dá para baixar sem publicar. A página do projeto mostra o histórico e o calendário, e cancela um agendamento que ainda não saiu. «Planejar a semana» vale só para o exterior: preenche segunda, quarta e sexta às 09:00, sem Bilibili.

Contas verticais saem em 9:16, sem corte de 60 segundos. Só Bilibili usa paisagem. Só LinkedIn ou X mantém o enquadramento original. Vertical e Bilibili no mesmo envio são renderizados separados.

Na publicação, uma capa pode ser gerada automaticamente, para o Bilibili não recusar uma capa vazia.

Os detalhes da capa e do cartão de título padrão seguem as notas desse instalador. Disponível na **v1.3.2**.

</details>

### Trabalhe do seu jeito

- **Escolha os modelos**: Qwen, APIs compatíveis com OpenAI, Gemini e outros serviços em nuvem, ou modelos locais pelo Ollama / LM Studio.

<details>
<summary>Ver captura · Escolha os modelos</summary>

![Escolha os modelos](docs/images/feature-models.png)

</details>

- **Automatizar tarefas**: Organize execuções pela CLI ou acesse o mesmo fluxo de processamento por um cliente MCP.

<details>
<summary>Ver captura · Automatizar tarefas</summary>

![Automatizar tarefas](docs/images/feature-cli.png)

CLI / MCP não tem GUI: a captura mostra uma página com a saída real da ajuda dos comandos.

</details>

- **Interface multilíngue**: A partir da v1.3.1, o aplicativo, o site e o README oferecem chinês, inglês, japonês, coreano, espanhol, português, russo e francês. Escolha o idioma no cabeçalho ou siga o sistema. Seus arquivos e o conteúdo gerado mantêm o idioma original.

<details>
<summary>Ver captura · Interface multilíngue</summary>

![Interface multilíngue](docs/images/feature-languages.png)

Interface em inglês e menu de idiomas; a mídia e o conteúdo gerado mantêm o idioma original.

</details>


> Importar vídeo → Legendas / transcrição → Análise e pontuação por IA → Clipes e coletâneas → Exportação

<a id="quick-start"></a>

## Início rápido

| Uso | Opção recomendada | Requisitos |
| --- | --- | --- |
| Editar no computador | **Aplicativo desktop** | macOS Apple Silicon / Windows x64 |
| Servidor próprio / Linux | **Docker** | Docker + Compose v2 |
| Processamento em lote / agentes | **CLI / MCP** | Python 3.10+ (recomendado 3.11) + FFmpeg |

### Desktop: seus primeiros clipes

1. **Instale.** Baixe em [Releases](https://github.com/zhouxiaoka/autoclip/releases/latest) o `.dmg` para macOS Apple Silicon ou `-setup.exe` para Windows 10 / 11 x64. Python e FFmpeg estão incluídos. Para Intel Mac / Linux, use Docker ou CLI. Confira os requisitos de cada versão.
2. **Configure o modelo.** Escolha o provedor nas configurações, informe a chave de API e o modelo, teste a conexão e salve. Para modelos locais, inicie primeiro o Ollama ou LM Studio.
3. **Importe um vídeo.** Comece com uma amostra de 3–5 minutos, com legendas SRT se disponíveis. Sem legendas, prepare primeiro os componentes locais do Whisper e o modelo de voz nas configurações.
4. **Revise e exporte.** Confira os limites, títulos e conteúdo dos clipes. Escolha uma predefinição de exportação ou conecte uma conta para publicar.

[Guia completo de instalação (inglês)](docs/USER_INSTALLATION_GUIDE.en.md) · [Solução de problemas (inglês)](docs/FAQ.en.md)

<details>
<summary><strong>Docker / Web</strong></summary>

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

</details>

<details>
<summary><strong>CLI / MCP</strong></summary>

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

</details>

## Configuração de modelos

| Opção | Configuração |
| --- | --- |
| Modelos na nuvem | Escolha o provedor nas configurações e informe sua chave de API e o modelo. Serviços compatíveis com OpenAI também permitem configurar a Base URL. |
| Ollama | Endereço padrão: `http://localhost:11434/v1`; modelo: `qwen2.5:7b`. Não exige chave de API. |
| LM Studio | Carregue um modelo e inicie o Local Server, por padrão em `http://localhost:1234/v1`. Selecione um modelo disponível no seu servidor. |

Dentro do Docker, `localhost` aponta para o próprio contêiner. Para usar um modelo no host, configure um endereço acessível pelo contêiner; consulte o guia de CLI / MCP. O corte dos vídeos é local; a análise com modelos na nuvem envia o texto das legendas ao provedor escolhido. Downloads de vídeos e modelos ainda precisam de internet.

[Infistar · Guia de configuração (inglês)](docs/INFISTAR_SETUP.en.md)

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

Veja o [guia dos primeiros clipes (inglês)](docs/USER_INSTALLATION_GUIDE.en.md) para preparar amostras e consultar exemplos públicos.

</details>

[Guia completo de solução de problemas (inglês)](docs/FAQ.en.md) · [Problemas conhecidos](https://github.com/zhouxiaoka/autoclip/issues/96)

<a id="documentation"></a>

## Documentação

| Assunto | Documentação |
| --- | --- |
| Primeiros passos | [Instalação (inglês)](docs/USER_INSTALLATION_GUIDE.en.md) |
| Hospedagem e automação | [Docker (inglês)](docs/DOCKER.en.md) · [CLI / MCP (chinês)](docs/CLI_AND_MCP.md) · [Agent skill (chinês)](skills/autoclip/SKILL.md) |
| Modelos e solução de problemas | [Modelos (chinês)](docs/MULTI_LLM_PROVIDER_GUIDE.md) · [Solução de problemas (inglês)](docs/FAQ.en.md) |
| Versões e privacidade | [Histórico de alterações](CHANGELOG.md) · [Privacidade (inglês)](docs/PRIVACY.en.md) |
| Desenvolvimento e tradução | [Contribuição (chinês)](CONTRIBUTING.md) · [Manutenção de traduções (chinês)](docs/i18n.md) |
| Configuração do patrocinador | [Infistar](docs/INFISTAR_SETUP.en.md) |

O README está disponível em oito idiomas. Os guias de instalação, Docker e solução de problemas também estão em inglês; as demais referências detalhadas estão principalmente em chinês.

## Contribua e entre em contato

Correções, comentários e melhorias nas traduções são bem-vindos. Ao relatar um erro, inclua sistema operacional, versão, modelo, passos para reprodução e logs sem informações confidenciais.

Projeto mantido por uma pessoa no tempo livre. O prazo de resposta varia; não há suporte imediato nem assistência individual de implantação. Consulte as perguntas frequentes e os problemas conhecidos antes de entrar em contato.

Ideias, usos e pedidos de modelo vão para as [GitHub Discussions](https://github.com/zhouxiaoka/autoclip/discussions). Erros reproduzíveis usam o [formulário de issue](https://github.com/zhouxiaoka/autoclip/issues/new/choose). Regras do quadro: [community board](docs/COMMUNITY_BOARD.md) (chinês).

- [Boas-vindas e categorias](https://github.com/zhouxiaoka/autoclip/discussions/127)
- [Perguntas do primeiro clipe](https://github.com/zhouxiaoka/autoclip/discussions/128)
- [Ideias](https://github.com/zhouxiaoka/autoclip/discussions/129)

- E-mail: [christine_zhouye@163.com](mailto:christine_zhouye@163.com)

Agradecemos ao FastAPI, React, Tauri, FFmpeg, yt-dlp, Whisper e a todas as pessoas que contribuem. Distribuído sob a [licença MIT](LICENSE). Se o AutoClip for útil, considere dar uma estrela ao projeto.

<details>
<summary>Reconhecimento da comunidade · Star History</summary>

Estes selos são fornecidos pelo Trendshift. Clique para consultar as conquistas registradas do AutoClip. GitHub Trending e Trendshift são rankings diferentes; os selos mostram conquistas registradas, não uma posição em tempo real.

[![Star History](https://api.star-history.com/svg?repos=zhouxiaoka/autoclip&type=Date)](https://star-history.com/#zhouxiaoka/autoclip&Date)

</details>
