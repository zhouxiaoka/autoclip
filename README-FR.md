<div align="center">

<img src="src-tauri/icons/128x128.png" alt="AutoClip" width="72" height="72">

# AutoClip

### Un lien. Un clic.

Open source, gratuit, sur votre ordinateur. Collez un lien, dépensez quelques centimes, et recevez <b>plus de 10 clips prêts à publier</b>,<br>
chacun avec couverture, titre, description et hashtags pour Douyin, Xiaohongshu, TikTok, Reels ou YouTube Shorts.<br>
Pas d’éditeur. Pas d’allers-retours avec un chat IA.

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

## Vrais clips

![Clips verticaux AutoClip : interview Xiaohongshu, podcast TikTok, interview Douyin, podcast Shorts](docs/images/v2/demo-wall.webp)

Chaque source n’était qu’un lien. Chaque clip ci-dessus est la sortie brute d’AutoClip — choix, cadrage, traduction, habillage — sans retouche. **[Voir avec le son dans la bibliothèque →](https://zhouxiaoka.github.io/autoclip_intro/cases/)**

Chaque clip livre le kit de publication : vidéo verticale, couverture, titre, description, hashtags. La bibliothèque est mise à jour ; [envoyez les vôtres](https://github.com/zhouxiaoka/autoclip/discussions/new?category=show-and-tell).

Les droits de l’original restent aux auteurs. Exemples : [Dwarkesh Patel — Dario Amodei](https://www.youtube.com/watch?v=n1E9IZfvGMA) · [Y Combinator — Sam Altman](https://www.youtube.com/watch?v=ZIaOBAjvc38) · [WIRED — Hideo Kojima](https://www.youtube.com/watch?v=02Ah5VQrzvA)

## Ce que ça fait

### Collez un lien, c’est tout
Pas d’éditeur ni de chat IA. Choisissez la plateforme, générez au bon format. Couverture, titre, description et hashtags inclus.

### L’habillage est inclus
Style interview pour Douyin / Xiaohongshu ; style podcast pour TikTok / Reels / Shorts. Le cadre suit le locuteur ; une source étrangère reçoit un titre local et des sous-titres bilingues.

### Ça reste sur votre machine
Coupe et rendu sont locaux. Vous choisissez le modèle, n’ouvrez l’éditeur que pour ajuster, et passez par CLI / MCP pour les lots.

## Rapide et peu cher

Un lien entre, **plus de 10** clips prêts sortent, chacun avec couverture, titre, description et hashtags.

| Version | Source | Sortie | Coût |
| --- | --- | ---: | ---: |
| **Nouvelle · avec sous-titres** | Jensen · 1h43 (EN → Xiaohongshu) | **7,5 min / 10 clips** | **¥0,09** |
| Nouvelle · sans sous-titres | TIM × Luo Yonghao · 2h52 (ZH → Douyin) | 29,5 min / 10 clips | ¥0,20 |
| Ancienne | MrBeast · 2h06 (EN → TikTok) | 65 min | ¥0,64 |

Une interview de 2–3 h coûte en général ¥0,1–0,2. Sans sous-titres auteur, la reconnaissance vocale est locale et plus longue ; la vidéo ne quitte pas la machine.

<details>
<summary>Comment ces chiffres ont été mesurés</summary>

1er octobre 2026, le même Mac Apple Silicon, modèle d’analyse qwen-plus (¥0,8 / ¥2 par million de tokens entrée / sortie, tarif tiers Aliyun Bailian). Le coût ne compte que les appels modèle.

Les 7,5 min de Jensen : ~1 min de téléchargement, pas d’ASR grâce aux sous-titres auteur, 25 s de sélection, ~2,5 min coupe / cadre / habillage, ~3 min pour rendre 10 clips. L’ancienne version passait 35 min rien que sur la sélection.

Cette version change quatre choses : une passe sur toute la transcription ; appels en parallèle ; saute l’ASR local s’il y a des sous-titres auteur ; ne rend que le top 10 par défaut.

</details>

## Face aux outils cloud mensuels

| | AutoClip | Outils cloud mensuels |
| --- | --- | --- |
| Coût | L’app est gratuite ; le modèle se paie à l’usage, ~¥0,1–0,2 pour 2–3 h | Abonnement mensuel, au temps de traitement |
| Où va la vidéo | Votre ordinateur ; le cloud ne voit que le texte | Envoi vers le cloud du fournisseur |
| Modèles | À vous de choisir, y compris local | Imposés par la plateforme |
| Plateformes chinoises | Modèles Douyin, Xiaohongshu, Bilibili | Surtout internationales |
| Code | MIT, modifiable, auto-hébergeable | Fermé |

La colonne de droite suit les pages publiques de produits cloud similaires en octobre 2026 ; vérifiez chaque produit.

## Démarrage

| Vous voulez | Utilisez | Il faut |
| --- | --- | --- |
| Faire des clips sur cet ordi | **Bureau** | macOS Apple Silicon ou Windows x64 |
| Auto-héberger / Linux | **Docker** | Docker et Compose v2 |
| Lots / agents | **CLI / MCP** | Python 3.10+ (3.11 conseillé) et FFmpeg |

### Bureau

1. **Installer.** Depuis [Releases](https://github.com/zhouxiaoka/autoclip/releases/latest). macOS Apple Silicon : `.dmg`. Windows 10 / 11 x64 : `-setup.exe`. Python et FFmpeg sont inclus.
2. **Configurer un modèle.** Choisissez un fournisseur dans Réglages et entrez la clé ; le modèle d’analyse se choisit tout seul. En local, lancez d’abord Ollama ou LM Studio.
3. **Collez un lien, choisissez la plateforme.** Commencez par une interview ou un podcast de 10–30 min avec sous-titres. Sans eux, préparez Whisper ou SenseVoice dans Réglages.
4. **Récupérez les clips.** Regardez les 10 premiers, retouchez si besoin, téléchargez ou publiez.

Les installeurs n’ont pas encore la notarisation Apple ni la signature Windows. Sur macOS, premier lancement via clic droit → Ouvrir. Sur Windows, Plus d’infos → Exécuter quand même.

[Guide d’installation](docs/USER_INSTALLATION_GUIDE.en.md) · [Dépannage](docs/FAQ.en.md)

**Docker / Web**

```bash
git clone https://github.com/zhouxiaoka/autoclip.git
cd autoclip
cp env.example .env          # 选择 LLM_PROVIDER，填 API Key 和模型名；也可以启动后在设置页配置
mkdir -p data logs uploads
docker compose up -d --build
```

Ouvrez l’[UI web](http://localhost:3000). Les [docs API](http://localhost:8000/docs) arrivent après le backend. [Guide Docker](docs/DOCKER.en.md).

Sous Linux, si le bind échoue pour les droits, corrigez le propriétaire d’abord :

```bash
docker compose run --rm --no-deps --user root --entrypoint sh autoclip -c 'chown -R autoclip:autoclip /app/data /app/logs /app/uploads'
docker compose up -d
```

**CLI / MCP**

Il faut Python 3.10+ (3.11 conseillé) et FFmpeg dans le PATH. Le CLI local n’a pas besoin de Redis.

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

Dans le client MCP, `command` est le chemin absolu de `autoclip` dans le venv et `args` vaut `["mcp"]`. [CLI / MCP](docs/CLI_AND_MCP.md) (chinois), [OpenCode](docs/OPENCODE.en.md), [Agent skill](skills/autoclip/SKILL.md) (chinois).

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
<summary>C’est gratuit ? Faut-il une API Key ?</summary>

AutoClip est gratuit et MIT. Les modèles cloud sont facturés par le fournisseur et demandent votre clé ; une interview de 1 h 43 a coûté environ ¥0,09. Ollama / LM Studio n’ont pas besoin de clé cloud, mais du matériel. Publier à l’étranger demande votre compte [Upload-Post](https://www.upload-post.com).

</details>

<details>
<summary>Mes vidéos sont-elles envoyées ?</summary>

Coupe et rendu restent sur l’appareil. Les modèles cloud reçoivent le texte. Le clip ne part qu’après Publier, vers les plateformes que vous avez liées. Analytique et rapports d’erreur se coupent dans Réglages. [Confidentialité](docs/PRIVACY.en.md).

</details>

<details>
<summary>Quelles vidéos marchent le mieux ?</summary>

L’analyse s’appuie surtout sur la transcription : interviews, podcasts, cours, talking-head. Les sous-titres auteur sont les plus rapides ; sans eux, transcription locale d’abord. Action ou musique seules sont limitées.

</details>

<details>
<summary>Pourquoi aucun clip ?</summary>

Regardez l’étape en échec : sous-titres vides, connexion modèle, FFmpeg ou disque. Essayez un modèle plus fort. Sinon, type, durée et modèle sur [problèmes connus](https://github.com/zhouxiaoka/autoclip/issues/96).

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
