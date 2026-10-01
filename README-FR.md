<div align="center">

<img src="src-tauri/icons/128x128.png" alt="AutoClip" width="72" height="72">

# AutoClip

### Un lien. Un clic.

Open source, avec coupe et rendu sur votre ordinateur. Collez un lien, choisissez la plateforme et obtenez <b>vidéo, couverture et texte</b>,<br>
pour Douyin, Xiaohongshu, TikTok, Reels, YouTube Shorts, Bilibili ou YouTube.<br>
L’app est gratuite ; les modèles cloud sont facturés à l’usage. Ajustez dans l’éditeur si besoin.

<p>
  <a href="https://github.com/zhouxiaoka/autoclip/releases/latest"><img src="https://img.shields.io/github/v/release/zhouxiaoka/autoclip?style=flat-square" alt="GitHub release"></a>
  <a href="https://github.com/zhouxiaoka/autoclip/stargazers"><img src="https://img.shields.io/github/stars/zhouxiaoka/autoclip?style=flat-square" alt="GitHub stars"></a>
  <a href="https://github.com/zhouxiaoka/autoclip/releases"><img src="https://img.shields.io/github/downloads/zhouxiaoka/autoclip/total?style=flat-square" alt="Downloads"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-blue?style=flat-square" alt="License: MIT"></a>
</p>

<a href="https://trendshift.io/repositories/25801"><img src="https://trendshift.io/api/badge/repositories/25801" alt="AutoClip — GitHub Trending" width="250" height="55"></a>

**[Télécharger le bureau](https://github.com/zhouxiaoka/autoclip/releases/latest)** · [Cas](https://zhouxiaoka.github.io/autoclip_intro/cases/) · [Démarrage](#démarrage) · [Docs](#documentation) · [Signaler](https://github.com/zhouxiaoka/autoclip/issues/new/choose)

[简体中文](README.md) · [English](README-EN.md) · [日本語](README-JA.md) · [한국어](README-KO.md) · [Español](README-ES.md) · [Português](README-PT.md) · [Русский](README-RU.md) · **Français**

</div>

**[1.5.0 est officiellement disponible](https://github.com/zhouxiaoka/autoclip/releases/tag/v1.5.0)**, pour bureau, CLI et MCP. Le [journal des changements](CHANGELOG.md) couvre production automatique, pagination des sous-titres, cadrage et file des vidéos longues. Mettez les anciennes versions à jour.

## Vrais clips

![Clips verticaux AutoClip : interview Xiaohongshu, podcast TikTok, interview Douyin, podcast Shorts](docs/images/v2/demo-wall.webp)

Chaque source n’était qu’un lien. Chaque clip ci-dessus est la sortie brute d’AutoClip — choix, cadrage, traduction, habillage — sans retouche. **[Voir avec le son dans la bibliothèque →](https://zhouxiaoka.github.io/autoclip_intro/cases/)**

Chaque clip comprend vidéo, couverture, titre, description, hashtags et kit ZIP pour la plateforme. La bibliothèque évolue ; [proposez vos clips](https://github.com/zhouxiaoka/autoclip/discussions/new?category=show-and-tell).

Les droits de l’original restent aux auteurs. Exemples : [Dwarkesh Patel — Dario Amodei](https://www.youtube.com/watch?v=n1E9IZfvGMA) · [Y Combinator — Sam Altman](https://www.youtube.com/watch?v=ZIaOBAjvc38) · [WIRED — Hideo Kojima](https://www.youtube.com/watch?v=02Ah5VQrzvA)

## Ce que ça fait

### Collez un lien, c’est tout

Produisez au format et à la durée de la plateforme. Chaque plateforme rend automatiquement jusqu’à 10 clips admissibles les mieux classés ; les autres sont à la demande. Couverture, titre, description, hashtags et kit ZIP sont inclus.

### L’habillage est inclus

Douyin / Xiaohongshu : interview par défaut ; TikTok / Reels / Shorts : podcast plein écran. Choisissez le format vertical sans changer la langue de la plateforme. Bilibili / YouTube restent horizontaux. Le cadrage suit l’intervenant et préserve les scènes sans personne. La fin de marque est active par défaut et désactivable dans Réglages ; le texte copié ne porte pas de signature AutoClip.

### Ça reste sur votre machine

Coupe, cadrage et rendu sont locaux. Choisissez votre modèle et utilisez les sous-titres auteur, Whisper / SenseVoice local ou une transcription cloud configurée. CLI / MCP partagent le flux de production du bureau.

## Temps et coûts sur de vraies sources

Trois sources différentes mesurées pendant le développement, pas un test contrôlé sur la même entrée. Les coûts estiment l’usage texte de qwen-plus à l’époque, hors ASR cloud, images AI et publication. La facture dépend du fournisseur.

| Version | Source | Sortie | Coût estimé du modèle texte (CNY) |
| --- | --- | ---: | ---: |
| **Nouvelle · avec sous-titres** | Jensen · 1h43 (EN → Xiaohongshu) | **7,5 min / 10 clips** | **¥0,09** |
| Nouvelle · sans sous-titres | TIM × Luo Yonghao · 2h52 (ZH → Douyin) | 29,5 min / 10 clips | ¥0,20 |
| Ancienne | MrBeast · 2h06 (EN → TikTok) | 65 min | ¥0,64 |

<details>
<summary>Conditions et mesures</summary>

1er octobre 2026, même Mac Apple Silicon. Les deux nouveaux traitements rendent 10 clips ; l’ancien, 33. Sources et quantités diffèrent. Jensen utilise les sous-titres auteur ; TIM, Whisper base local.

Les sous-titres auteur évitent la transcription. Sinon, choisissez ASR local ou cloud. Plateformes et clips supplémentaires ajoutent temps et consommation. [Mesures et méthode](docs/COST_PER_VIDEO.md) (chinois).

</details>

## Choisissez modèles et flux de données

Coupe et rendu restent sur votre ordinateur. L’analyse cloud envoie les sous-titres et textes utiles ; la compréhension visuelle ou les images avec référence envoie les images échantillonnées nécessaires ; la transcription cloud envoie l’audio. Analyse et transcription locales n’exigent pas l’API cloud correspondante. Les clips sont envoyés aux plateformes liées quand vous choisissez Publier. Statistiques et rapports d’erreur sont désactivables. [Confidentialité](docs/PRIVACY.en.md).

## Démarrage

| Vous voulez | Utilisez | Il faut |
| --- | --- | --- |
| Faire des clips sur cet ordi | **Bureau** | macOS Apple Silicon ou Windows x64 |
| Auto-héberger / Linux | **Docker** | Docker et Compose v2 |
| Lots / agents | **CLI / MCP** | Python 3.10+ (3.11 conseillé) et FFmpeg |

### Bureau

1. **Installer.** Depuis [Releases](https://github.com/zhouxiaoka/autoclip/releases/latest). macOS Apple Silicon : `.dmg`. Windows 10 / 11 x64 : `-setup.exe`. Python et FFmpeg sont inclus.
2. **Configurer un modèle.** Choisissez un fournisseur dans Réglages et entrez la clé ; le modèle d’analyse se choisit tout seul. En local, lancez d’abord Ollama ou LM Studio.
3. **Lien et plateforme.** Essayez une interview ou un podcast sous-titré et choisissez le format vertical. Sinon, préparez Whisper / SenseVoice ou configurez la transcription cloud dans Réglages.
4. **Vérifiez et enregistrez.** Contrôlez sous-titres, cadrage et contenu, puis téléchargez le kit ou liez un compte pour publier. Générez les alternatives au besoin.

Les installeurs n’ont pas encore la notarisation Apple ni la signature Windows. Sur macOS, premier lancement via clic droit → Ouvrir. Sur Windows, Plus d’infos → Exécuter quand même.

Intel Mac / Linux peuvent utiliser Docker ou CLI. Le paquet Windows a passé installation, mise à niveau et vidéo en CI ; la validation humaine de l’interface et toute la période d’observation restent incomplètes. Voir [1.5.0 Release](https://github.com/zhouxiaoka/autoclip/releases/tag/v1.5.0).

[Guide d’installation](docs/USER_INSTALLATION_GUIDE.en.md) · [Dépannage](docs/FAQ.en.md)

**Docker / Web**

```bash
git clone https://github.com/zhouxiaoka/autoclip.git
cd autoclip
cp env.example .env
mkdir -p data logs uploads
docker compose up -d --build
```

Ouvrez l’[UI web](http://localhost:3000). Les [docs API](http://localhost:8000/docs) arrivent après le backend. [Guide Docker](docs/DOCKER.en.md).

Sous Linux, si le bind échoue pour les droits, corrigez le propriétaire d’abord :

```bash
docker compose run --rm --no-deps --user root --entrypoint sh autoclip -c 'chown -R autoclip:autoclip /app/data /app/logs /app/uploads'
docker compose up -d
```

Pour une IP LAN ou un domaine personnalisé, ajoutez l’adresse du frontend à `AUTOCLIP_ALLOWED_ORIGINS` dans `.env` (séparées par des virgules).

**CLI / MCP**

Python 3.10+ (3.11 conseillé), FFmpeg et FFprobe dans PATH ; Redis inutile. Téléchargez le [ZIP officiel CLI / MCP](https://github.com/zhouxiaoka/autoclip/releases/download/v1.5.0/autoclip-1.5.0-cli-mcp.zip), extrayez-le et exécutez dans ce dossier :

```bash
python3 -m venv venv
source venv/bin/activate
python -m pip install -r requirements.txt
python -m pip install --force-reinstall --no-deps autoclip-1.5.0-py3-none-any.whl
```

Activation ci-dessus pour macOS / Linux. Sous Windows, créez avec `py -m venv venv` puis activez avec `venv\Scripts\Activate.ps1`. Réinstallez de force le wheel officiel sur les anciens candidats 1.5 ; le numéro de version ne suffit pas.

Enregistrez les modèles d’abord : partagez les réglages du bureau, ou configurez votre dossier depuis l’exemple sans clé du ZIP. [CLI / MCP](docs/CLI_AND_MCP.md) (chinois). `produce` n’utilise pas la surcharge temporaire de `run --provider`. `--srt` évite la transcription.

```bash
autoclip --version
autoclip produce talk.mp4 --srt talk.srt --platform douyin --portrait-style podcast --json
autoclip outputs PROJECT_ID --export-kits
autoclip mcp
autoclip mcp install opencode
```

Remplacez `PROJECT_ID` par l’ID obtenu. MCP utilise `start_quick_output` / `get_quick_output_status` ; `command` est le chemin absolu de `autoclip` dans le venv et `args`, `["mcp"]`. Les anciens `run` / `export` et outils restent disponibles. [CLI / MCP](docs/CLI_AND_MCP.md) (chinois), [OpenCode](docs/OPENCODE.en.md), [Agent skill](skills/autoclip/SKILL.md) (chinois).

## Modèles

| Option | Réglage |
| --- | --- |
| API cloud | Fournisseur et clé dans Réglages. Les services compatibles OpenAI acceptent une Base URL. |
| Ollama | `http://localhost:11434/v1` par défaut, modèle `qwen2.5:7b`, pas de clé. |
| LM Studio | Chargez un modèle et lancez Local Server, `http://localhost:1234/v1` par défaut. |

Dans Docker, `localhost` est le conteneur. Pointez vers une adresse hôte joignable depuis le conteneur.

[Modèles](docs/MULTI_LLM_PROVIDER_GUIDE.md) (chinois) · [Local et conteneurs](docs/CLI_AND_MCP.md) (chinois)

## Sponsors

Merci à ces partenaires. Les deux exposent une API compatible OpenAI : choisissez-les dans Réglages, entrez la clé, les modèles s’affichent.

<table>
  <tr>
    <td align="center" width="140" valign="middle">
      <a href="https://88api.ai/sign-up?aff=2PIc"><img src="docs/sponsors/88api-logo.jpg" alt="88API" width="72"></a><br>
      <a href="https://88api.ai/sign-up?aff=2PIc"><strong>88API</strong></a>
    </td>
    <td valign="middle">
      Agrégateur de tokens : GPT, Claude, Gemini, Grok, DeepSeek, Kimi, GLM, plus image, vidéo et voix. Support, facture, recharge 1:1. Crédit d’essai via le <a href="https://88api.ai/sign-up?aff=2PIc">lien de parrainage</a>. <a href="docs/88API_SETUP.en.md">Guide</a>
    </td>
  </tr>
  <tr>
    <td align="center" width="140" valign="middle">
      <a href="https://www.infistar.cc/register?aff=XLK3BCM6&amp;ref_source=link"><img src="docs/sponsors/infistar-logo.svg" alt="Infistar" width="72"></a><br>
      <a href="https://www.infistar.cc/register?aff=XLK3BCM6&amp;ref_source=link"><strong>Infistar</strong></a>
    </td>
    <td valign="middle">
      API multi-modèles : Claude, GPT, Gemini, DeepSeek et d’autres ; certains à 1 % du tarif officiel, RMB, facture, vérification. 5 $ d’essai via le <a href="https://www.infistar.cc/register?aff=XLK3BCM6&amp;ref_source=link">lien de parrainage</a>. <a href="docs/INFISTAR_SETUP.en.md">Guide</a>
    </td>
  </tr>
</table>

Services, prix et offres viennent des partenaires ; leurs pages font foi.

## FAQ

<details>
<summary>Est-ce gratuit ? Faut-il une clé API ?</summary>

App gratuite sous MIT. Analyse, transcription et images cloud utilisent vos identifiants et les tarifs du fournisseur. La couverture automatique n’appelle pas de génération payante par défaut. Ollama / LM Studio demandent du matériel, pas de clé cloud. Publier exige votre compte Bilibili ou [Upload-Post](https://www.upload-post.com).

</details>

<details>
<summary>Mes vidéos sont-elles envoyées ?</summary>

Coupe et rendu restent sur votre ordinateur. L’analyse cloud envoie les sous-titres et textes utiles ; la compréhension visuelle ou les images avec référence envoie les images échantillonnées nécessaires ; la transcription cloud envoie l’audio. Analyse et transcription locales n’exigent pas l’API cloud correspondante. Les clips sont envoyés aux plateformes liées quand vous choisissez Publier. Statistiques et rapports d’erreur sont désactivables. [Confidentialité](docs/PRIVACY.en.md).

</details>

<details>
<summary>Quelles vidéos conviennent ?</summary>

Interviews, podcasts, cours et vidéos parlées sont les cas principaux validés. Les sous-titres auteur sont les plus rapides ; sinon, transcription locale/cloud. Pour jeux ou peu de dialogue, activez la compréhension visuelle avec un modèle image et contrôlez les moments sélectionnés.

</details>

<details>
<summary>Pourquoi aucun clip ?</summary>

Vérifiez transcription, modèle, FFmpeg, disque et règles de plateforme. YouTube long exige des clips complets d’au moins 180 secondes ; utilisez Shorts/Bilibili pour les sources courtes. Joignez version 1.5.0, OS, durée, modèle et logs expurgés aux [problèmes connus](https://github.com/zhouxiaoka/autoclip/issues/96).

</details>

[Dépannage](docs/FAQ.en.md) · [Problèmes connus](https://github.com/zhouxiaoka/autoclip/issues/96)

## Documentation

| Vous voulez | Docs |
| --- | --- |
| Installer et premiers clips | [Installation](docs/USER_INSTALLATION_GUIDE.en.md) |
| Héberger et automatiser | [Docker](docs/DOCKER.en.md) · [CLI / MCP](docs/CLI_AND_MCP.md) (chinois) · [Agent skill](skills/autoclip/SKILL.md) (chinois) · [OpenCode](docs/OPENCODE.en.md) |
| Modèles et pannes | [Modèles](docs/MULTI_LLM_PROVIDER_GUIDE.md) (chinois) · [FAQ](docs/FAQ.en.md) |
| Versions, feuille de route, confidentialité | [Journal](CHANGELOG.md) · [Feuille de route](ROADMAP.md) (chinois) · [Tableau](docs/COMMUNITY_BOARD.md) (chinois) · [Confidentialité](docs/PRIVACY.en.md) |
| Contribuer et traduire | [Contribuer](CONTRIBUTING.md) (chinois) · [Traductions](docs/i18n.md) (chinois) |

## Contribuer

Correctifs, exemples, retours et traductions sont les bienvenus. Si AutoClip vous aide, une étoile compte.

- **Parler :** [Discussions](https://github.com/zhouxiaoka/autoclip/discussions) · [Premier clip](https://github.com/zhouxiaoka/autoclip/discussions/128) · [Idées](https://github.com/zhouxiaoka/autoclip/discussions/129)
- **Bugs :** [formulaire](https://github.com/zhouxiaoka/autoclip/issues/new/choose) avec OS, version, modèle, étapes et journaux sans secrets
- **Partenariats :** [christine_zhouye@163.com](mailto:christine_zhouye@163.com)

Maintenu par une personne. Pas de support live ni de déploiement individuel.

![Star History](https://api.star-history.com/svg?repos=zhouxiaoka/autoclip&type=Date)

Merci à FastAPI, React, Tauri, FFmpeg, yt-dlp, Whisper, FunASR et à tous les contributeurs. [MIT License](LICENSE).
