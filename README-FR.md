<div align="center">

<img src="src-tauri/icons/128x128.png" alt="AutoClip" width="72" height="72">

# AutoClip

### Outil open source de découpage des temps forts vidéo par IA

Transformez vos longues vidéos en moments à partager.

[![GitHub release](https://img.shields.io/github/v/release/zhouxiaoka/autoclip?style=flat-square)](https://github.com/zhouxiaoka/autoclip/releases/latest)
[![GitHub stars](https://img.shields.io/github/stars/zhouxiaoka/autoclip?style=flat-square)](https://github.com/zhouxiaoka/autoclip/stargazers)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue?style=flat-square)](LICENSE)

<p align="center">
  <a href="https://trendshift.io/repositories/25801"><img src="https://trendshift.io/api/badge/repositories/25801" alt="AutoClip — GitHub Trending" width="250" height="55"></a>
  <a href="https://trendshift.io/repositories/25801"><img src="https://trendshift.io/api/badge/trendshift/repositories/25801/daily?language=Python" alt="AutoClip — Trendshift Python daily ranking" width="250" height="55"></a>
  <a href="https://trendshift.io/repositories/25801"><img src="https://trendshift.io/api/badge/trendshift/repositories/25801/daily" alt="AutoClip — Trendshift daily ranking, all languages" width="250" height="55"></a>
</p>

**[Télécharger l’application](https://github.com/zhouxiaoka/autoclip/releases/latest)** · [Démarrage rapide](#quick-start) · [Site web](https://zhouxiaoka.github.io/autoclip_intro/) · [Documentation](#documentation) · [Signaler un problème](https://github.com/zhouxiaoka/autoclip/issues/new/choose)

[简体中文](README.md) · [English](README-EN.md) · [日本語](README-JA.md) · [한국어](README-KO.md) · [Español](README-ES.md) · [Português](README-PT.md) · [Русский](README-RU.md) · **Français**

</div>

AutoClip utilise l’IA pour analyser les sous-titres, repérer les temps forts, créer des titres et générer automatiquement des extraits et des compilations. Adapté aux entretiens, podcasts, cours et rediffusions de directs, il propose une application de bureau, une interface web via Docker et un accès CLI / MCP.

## Aperçu de l’interface

![Importation et gestion des projets](docs/images/home-v1.4.0.png)

<table>
  <tr>
    <td width="50%" align="center"><strong>Extraits générés par l’IA</strong></td>
    <td width="50%" align="center"><strong>Aperçu et montage dans Studio</strong></td>
  </tr>
  <tr>
    <td><a href="docs/images/clips-v1.4.0.png"><img src="docs/images/clips-v1.4.0.png" alt="Extraits générés par l’IA" width="100%"></a></td>
    <td><a href="docs/images/studio-v1.4.0.png"><img src="docs/images/studio-v1.4.0.png" alt="Aperçu et montage dans Studio" width="100%"></a></td>
  </tr>
</table>

<sub>Interface réelle de la v1.4.0 avec les correctifs Studio ultérieurs : importez des vidéos, consultez les extraits réellement générés et modifiez-les dans Studio. L’interface est en chinois ; la transcription et les titres de l’exemple sont en anglais.</sub>

[Version des captures et source de l’exemple (chinois)](docs/images/README.md)

## Remerciements ❤️

<table>
  <tr>
    <td align="center" width="140">
      <a href="https://88api.ai/sign-up?aff=2PIc"><img src="docs/sponsors/88api-logo.jpg" alt="88API" width="88"></a><br>
      <a href="https://88api.ai/sign-up?aff=2PIc"><strong>88API</strong></a>
    </td>
    <td>
      Merci à <strong>88API</strong> de sponsoriser AutoClip ! La plateforme réunit GPT, Claude, Gemini, Grok, DeepSeek, Kimi et GLM pour analyser les transcriptions, sélectionner les temps forts et générer des titres.<br>
      🎨 <strong>Multimédia</strong> : Modèles d’image, de vidéo et d’audio, dont GPT-Image, Seedance, Veo, MiniMax Hailuo H3, Kling, Whisper et TTS. AutoClip utilise les API compatibles d’analyse, de couverture et de transcription.<br>
      🏷️ <strong>Service et facturation</strong> : Le partenaire indique être exploité par une société à l’étranger et proposer une assistance humaine, des factures et un ratio de recharge de 1:1 ; les conditions de la plateforme s’appliquent.<br>
      🎁 <strong>Nouveaux utilisateurs</strong> : Recevez un crédit d’essai pour tester les modèles via le <a href="https://88api.ai/sign-up?aff=2PIc">lien de parrainage</a>, selon les conditions de la promotion. <a href="docs/88API_SETUP.en.md">Guide de configuration (anglais)</a>
    </td>
  </tr>
  <tr>
    <td align="center" width="140">
      <a href="https://www.infistar.cc/register?aff=XLK3BCM6&amp;ref_source=link"><img src="docs/sponsors/infistar-logo.svg" alt="Infistar" width="88"></a><br>
      <a href="https://www.infistar.cc/register?aff=XLK3BCM6&amp;ref_source=link"><strong>Infistar.cc</strong></a>
    </td>
    <td>
      Merci à <strong>Infistar.cc</strong> de sponsoriser AutoClip ! Son API multimodèle peut servir à analyser les transcriptions de longues vidéos, sélectionner les temps forts et générer des titres.<br>
      ⚙️ <strong>Configuration compatible</strong> : Dans AutoClip, choisissez le fournisseur compatible avec OpenAI et renseignez la Base URL, votre clé API et un modèle disponible.<br>
      🧩 <strong>Choix des modèles</strong> : Le partenaire propose Claude, GPT, Gemini, DeepSeek et d’autres familles. Choisissez des modèles prenant en charge le point d’accès compatible pour comparer l’analyse des transcriptions et la sélection des temps forts.<br>
      🏷️ <strong>Tarifs et services</strong> : Selon le partenaire, certains modèles sont proposés dès <strong>1 % du tarif officiel</strong>, avec facturation en RMB, émission de factures et vérification de l’authenticité des modèles. Consultez la plateforme pour les modèles, tarifs et conditions en vigueur.<br>
      🎁 <strong>Offre AutoClip</strong> : Les nouveaux utilisateurs peuvent recevoir <strong>$5 de crédit d’essai</strong> via le <a href="https://www.infistar.cc/register?aff=XLK3BCM6&amp;ref_source=link">lien de parrainage</a>, selon les conditions de la promotion. <a href="docs/INFISTAR_SETUP.en.md">Guide de configuration (anglais)</a>
    </td>
  </tr>
</table>

## Fonctionnalités

Cliquez sur une miniature pour voir l’image en grand.

<table>
  <tr>
    <td width="50%" valign="top">
      <h4>Importer des vidéos</h4>
      <p>Utilisez des fichiers locaux ou des liens YouTube et Bilibili, avec des sous-titres SRT facultatifs.</p>
      <a href="docs/images/feature-import.png"><img src="docs/images/feature-import.png" alt="Importer des vidéos" width="420"></a>
    </td>
    <td width="50%" valign="top">
      <h4>Repérer les temps forts</h4>
      <p>Extrayez des plans, des plages temporelles par sujet, des scores et des titres à partir des sous-titres.</p>
      <a href="docs/images/clips-v1.4.0.png"><img src="docs/images/clips-v1.4.0.png" alt="Repérer les temps forts" width="260"></a>
    </td>
  </tr>
  <tr>
    <td width="50%" valign="top">
      <h4>Créer des extraits et des compilations</h4>
      <p>Générez des extraits et des compilations suggérées, puis ajustez leur ordre manuellement.</p>
      <a href="docs/images/feature-collections.png"><img src="docs/images/feature-collections.png" alt="Créer des extraits et des compilations" width="420"></a>
    </td>
    <td width="50%" valign="top">
      <h4>Exporter pour publier</h4>
      <p>Profils pour Douyin, Xiaohongshu, YouTube Shorts et Bilibili, avec sous-titres incrustés et cartons de titre.</p>
      <a href="docs/images/feature-export.png"><img src="docs/images/feature-export.png" alt="Exporter pour publier" width="420"></a>
    </td>
  </tr>
  <tr>
    <td width="50%" valign="top">
      <h4>Couvertures et publication</h4>
      <p>Depuis la v1.3.2, générez des couvertures et publiez immédiatement ou à une date programmée. Connectez les plateformes internationales via votre compte Upload-Post ; Bilibili se configure séparément.</p>
      <a href="docs/images/feature-publish.png"><img src="docs/images/feature-publish.png" alt="Couvertures et publication" width="200"></a>
      <a href="docs/images/feature-cover.png"><img src="docs/images/feature-cover.png" alt="Couvertures et publication" width="200"></a>
      <p><sub>Aucun compte de publication n’est connecté dans cette démonstration. Les images montrent l’accès à la publication et les réglages de couverture, pas des publications effectuées.</sub></p>
    </td>
    <td width="50%" valign="top">
      <h4>Gestion des publications</h4>
      <p>Consultez l’historique et le calendrier, gérez les publications en attente ou téléchargez simplement vos extraits.</p>
      <a href="docs/images/feature-calendar.png"><img src="docs/images/feature-calendar.png" alt="Gestion des publications" width="420"></a>
    </td>
  </tr>
  <tr>
    <td width="50%" valign="top">
      <h4>Choix des modèles</h4>
      <p>Qwen, API compatibles avec OpenAI, Gemini et autres services cloud, ou modèles locaux via Ollama / LM Studio.</p>
      <a href="docs/images/feature-models.png"><img src="docs/images/feature-models.png" alt="Choix des modèles" width="420"></a>
    </td>
    <td width="50%" valign="top">
      <h4>Automatiser les tâches</h4>
      <p>Orchestrez les traitements avec la CLI ou appelez le même pipeline depuis un client MCP.</p>
      <a href="docs/images/feature-cli.png"><img src="docs/images/feature-cli.png" alt="Automatiser les tâches" width="420"></a>
      <p><sub>CLI / MCP n’a pas d’interface graphique : cette capture montre une page affichant la sortie réelle de l’aide des commandes.</sub></p>
    </td>
  </tr>
  <tr>
    <td colspan="2" align="center" valign="top">
      <h4>Interface multilingue</h4>
      <p>Depuis la v1.3.1, l’application, le site et le README sont disponibles en chinois, anglais, japonais, coréen, espagnol, portugais, russe et français. Choisissez la langue dans l’en-tête ou suivez celle du système. Vos médias et le contenu généré conservent leur langue d’origine.</p>
      <a href="docs/images/feature-languages.png"><img src="docs/images/feature-languages.png" alt="Interface multilingue" width="420"></a>
      <p><sub>Interface en anglais et menu des langues ; les médias et le contenu généré conservent leur langue d’origine.</sub></p>
    </td>
  </tr>
</table>

<details>
<summary>Plateformes, comptes requis et détails d’exportation</summary>

Quand les extraits sont prêts, ouvrez Publier sur un extrait. Disponible dans la **v1.3.2**. À l’étranger, ce sont les plateformes reliées à votre propre compte Upload-Post : TikTok, Instagram, YouTube, Facebook, LinkedIn, X, Threads, Pinterest, Bluesky, Discord, Telegram et Google Business, selon ce que ce compte a relié. Bilibili, c’est un seul compte : collez un Cookie une fois dans les réglages. Il doit contenir SESSDATA, bili_jct et DedeUserID.

Publiez maintenant ou planifiez. Le titre et la description sont facultatifs et reprennent le titre de l’extrait s’ils sont vides. Les sous-titres incrustés sont activés par défaut, comme le carton de titre d’environ 4 secondes. La visibilité par défaut est moi seul / private là où la plateforme le prend en charge.

AutoClip ne le promet que pour TikTok, YouTube et Bilibili. Vous pouvez aussi télécharger sans publier. La page du projet montre l’historique et le calendrier, et permet d’annuler une planification qui n’est pas encore partie. « Planifier la semaine » ne concerne que l’étranger : lundi, mercredi et vendredi à 09:00, sans Bilibili. Les comptes verticaux sont rendus en 9:16, sans coupe à 60 secondes.

Bilibili seul utilise le paysage. LinkedIn ou X seul garde le cadrage d’origine. Vertical et Bilibili dans le même envoi sont rendus séparément.

À la publication, une couverture peut être générée automatiquement, pour que Bilibili ne refuse pas une couverture vide. Le détail de la couverture et du carton de titre par défaut suit la notice de cet installeur.

Disponible dans la **v1.3.2**.

</details>


> Importer une vidéo → Sous-titres / transcription → Analyse et évaluation par IA → Extraits et compilations → Export

<a id="quick-start"></a>

## Démarrage rapide

| Usage | Option conseillée | Prérequis |
| --- | --- | --- |
| Monter sur votre ordinateur | **Application de bureau** | macOS Apple Silicon / Windows x64 |
| Auto-hébergement / Linux | **Docker** | Docker + Compose v2 |
| Traitement par lots / agents | **CLI / MCP** | Python 3.10+ (3.11 conseillé) + FFmpeg |

### Application : vos premiers extraits

1. **Installez.** Téléchargez depuis [Releases](https://github.com/zhouxiaoka/autoclip/releases/latest) le `.dmg` pour macOS Apple Silicon ou `-setup.exe` pour Windows 10 / 11 x64. Python et FFmpeg sont inclus. Pour Intel Mac / Linux, utilisez Docker ou la CLI. Consultez les prérequis du fichier de version.
2. **Configurez un modèle.** Dans les paramètres, choisissez un fournisseur, saisissez votre clé API et le modèle, testez la connexion puis enregistrez. Pour les modèles locaux, démarrez d’abord Ollama ou LM Studio.
3. **Importez une vidéo.** Commencez par un échantillon de 3 à 5 minutes, avec un fichier SRT si disponible. Sans sous-titres, préparez d’abord les composants locaux de Whisper et le modèle vocal dans les paramètres.
4. **Vérifiez et exportez.** Contrôlez les limites des extraits, les titres et le contenu, puis choisissez un préréglage d’exportation ou connectez un compte pour publier.

[Guide complet d’installation (anglais)](docs/USER_INSTALLATION_GUIDE.en.md) · [Dépannage (anglais)](docs/FAQ.en.md)

<details>
<summary><strong>Docker / Web</strong></summary>

Docker et Docker Compose v2 sont nécessaires. Exécutez ces commandes à la racine du dépôt :

```bash
git clone https://github.com/zhouxiaoka/autoclip.git
cd autoclip
```

```bash
cp env.example .env
```

Avant de démarrer, modifiez `.env` : choisissez `LLM_PROVIDER` et renseignez la clé API et le nom du modèle correspondants. Vous pouvez aussi configurer le fournisseur dans l’interface après le démarrage.

```bash
mkdir -p data logs uploads
docker compose up -d --build
```

Ouvrez l’[interface web](http://localhost:3000). La [documentation de l’API](http://localhost:8000/docs) est accessible après le démarrage du backend. Consultez le [guide Docker](DOCKER.md) (en chinois) pour les détails.

Sous Linux, si les répertoires montés provoquent des erreurs de permissions, corrigez le propriétaire des répertoires de données du projet avec cette commande, puis redémarrez les services :

```bash
docker compose run --rm --no-deps --user root --entrypoint sh autoclip -c 'chown -R autoclip:autoclip /app/data /app/logs /app/uploads'
docker compose up -d
```

</details>

<details>
<summary><strong>CLI / MCP</strong></summary>

Python 3.10 ou supérieur (3.11 recommandé) et FFmpeg dans le PATH sont nécessaires. L’exemple utilise un shell macOS / Linux ; sous Windows PowerShell, activez l’environnement avec `venv\Scripts\Activate.ps1`. Le traitement local par CLI ne nécessite pas Redis.

```bash
git clone https://github.com/zhouxiaoka/autoclip.git
cd autoclip
python3 -m venv venv
source venv/bin/activate
python -m pip install -r requirements.txt
python -m pip install -e .
```

Exemple avec un modèle local : installez et démarrez Ollama, puis téléchargez un modèle. Les vidéos sans sous-titres nécessitent `faster-whisper` ; le modèle vocal est téléchargé à la première utilisation. Pour fournir des sous-titres existants, ajoutez `--srt talk.srt`.

La **production rapide de la version 1.5** utilise les paramètres des modèles enregistrés dans l’application de bureau pour générer des vidéos par plateforme, des couvertures, des textes de publication et des kits ZIP :

```bash
autoclip --version
autoclip produce talk.mp4 --srt talk.srt --platform douyin --portrait-style podcast --json
autoclip outputs PROJECT_ID --export-kits
```

Avec MCP, utilisez `start_quick_output` + `get_quick_output_status` avec les mêmes plateformes et mises en page verticales. Consultez le [rapport de validation de la version 1.5](docs/RELEASE_1_5.md) (en chinois) pour l’installation et les tests entre collègues.

```bash
ollama pull qwen2.5:7b
python -m pip install faster-whisper
autoclip doctor --provider ollama
autoclip run talk.mp4 --provider ollama --json
```

Remplacez `PROJECT_ID` par l’identifiant du projet renvoyé après le traitement pour exporter au format Shorts. Lancez le serveur MCP via stdio avec `autoclip mcp` :

```bash
autoclip export PROJECT_ID --preset shorts
autoclip mcp
```

Dans votre client MCP, définissez `command` avec le chemin absolu de `autoclip` dans l’environnement virtuel et `args` avec `["mcp"]`. Consultez le [guide CLI / MCP](docs/CLI_AND_MCP.md) et la [skill pour agents](skills/autoclip/SKILL.md) (en chinois).

</details>

## Configuration des modèles

| Option | Configuration |
| --- | --- |
| Modèles cloud | Choisissez un fournisseur dans les paramètres et renseignez votre clé API et le modèle. Les services compatibles avec OpenAI acceptent aussi une Base URL personnalisée. |
| Ollama | Adresse par défaut : `http://localhost:11434/v1` ; modèle : `qwen2.5:7b`. Aucune clé API nécessaire. |
| LM Studio | Chargez un modèle et démarrez Local Server, par défaut sur `http://localhost:1234/v1`. Sélectionnez un modèle disponible sur votre serveur. |

Dans Docker, `localhost` désigne le conteneur lui-même. Pour utiliser un modèle sur l’hôte, configurez une adresse accessible depuis le conteneur ; voir le guide CLI / MCP. Le découpage vidéo est local, mais l’analyse par un modèle cloud envoie le texte des sous-titres au fournisseur choisi. Le téléchargement des vidéos et modèles nécessite une connexion internet.

[Infistar · Guide de configuration (anglais)](docs/INFISTAR_SETUP.en.md)

## Questions fréquentes

<details>
<summary>Est-ce gratuit ? Faut-il une clé API ?</summary>

AutoClip lui-même reste gratuit et open source sous MIT. Les fournisseurs cloud facturent l’utilisation de leurs modèles et nécessitent votre clé API. Ollama / LM Studio n’exigent pas de clé cloud, mais nécessitent des modèles et un matériel adapté. Depuis la **v1.3.2**, la publication à l’étranger demande votre propre compte [Upload-Post](https://www.upload-post.com). Les offres gratuites et payantes, ainsi que les plafonds quotidiens de TikTok, YouTube, Instagram et des autres plateformes, suivent les pages d’Upload-Post. Ce ne sont pas des promesses d’AutoClip.

</details>

<details>
<summary>Mes vidéos sont-elles envoyées sur un serveur ?</summary>

Le montage reste sur votre appareil. Les modèles cloud reçoivent le texte des sous-titres. L’extrait terminé ne quitte la machine qu’après un clic sur Publier, et seulement vers les plateformes que vous avez reliées. Vous pouvez aussi le télécharger sans publier. Cette page Publier est disponible dans la **v1.3.2**. Les statistiques et rapports d’erreurs dépendent de la version et des paramètres ; consultez les notes de confidentialité.

</details>

<details>
<summary>Puis-je utiliser une vidéo sans sous-titres ?</summary>

Oui, après avoir préparé les composants locaux de Whisper et un modèle vocal. Vous pouvez aussi importer un SRT existant. Des sous-titres précis peuvent réduire l’attente et les erreurs de transcription.

</details>

<details>
<summary>Pourquoi aucun extrait n’a-t-il été généré ?</summary>

Vérifiez l’étape en échec : sous-titres vides, connexion au modèle, seuil trop élevé, FFmpeg ou espace disque. Vous pouvez essayer de réduire le seuil de 0.7 à 0.5, sans garantie de génération.

</details>

<details>
<summary>Quelles vidéos conviennent et combien de temps faut-il ?</summary>

L’analyse repose principalement sur les sous-titres : entretiens, podcasts, cours et commentaires parlés conviennent bien. L’action visuelle ou la musique peuvent donner des résultats limités. Le temps dépend de la durée, du matériel, du modèle et de l’export ; commencez par un court exemple.

Consultez le [guide des premiers extraits (anglais)](docs/USER_INSTALLATION_GUIDE.en.md) pour préparer un échantillon et trouver des exemples publics.

</details>

[Guide complet de dépannage (anglais)](docs/FAQ.en.md) · [Problèmes connus](https://github.com/zhouxiaoka/autoclip/issues/96)

<a id="documentation"></a>

## Documentation

| Sujet | Documentation |
| --- | --- |
| Premiers pas | [Installation (anglais)](docs/USER_INSTALLATION_GUIDE.en.md) |
| Hébergement et automatisation | [Docker (anglais)](docs/DOCKER.en.md) · [CLI / MCP (chinois)](docs/CLI_AND_MCP.md) · [Agent skill (chinois)](skills/autoclip/SKILL.md) |
| Modèles et dépannage | [Configuration des modèles (chinois)](docs/MULTI_LLM_PROVIDER_GUIDE.md) · [Dépannage (anglais)](docs/FAQ.en.md) |
| Versions et confidentialité | [Historique des modifications](CHANGELOG.md) · [Confidentialité (anglais)](docs/PRIVACY.en.md) |
| Développement et traduction | [Contribution (chinois)](CONTRIBUTING.md) · [Maintenance des traductions (chinois)](docs/i18n.md) |
| Configuration du sponsor | [Infistar](docs/INFISTAR_SETUP.en.md) |

Le README est disponible en huit langues. Les guides d’installation, Docker et de dépannage existent en anglais ; les autres références détaillées sont principalement en chinois.

## Contribuer et nous contacter

Les corrections, retours et améliorations des traductions sont les bienvenus. Pour signaler un bug, indiquez le système, la version, le modèle, les étapes de reproduction et les journaux d’erreurs sans données sensibles.

Projet maintenu par une personne sur son temps libre. Les délais de réponse varient ; aucune assistance immédiate ou individuelle au déploiement n’est proposée. Consultez la FAQ et les problèmes connus avant de nous contacter.

Les idées, les usages et les demandes de modèles vont dans les [GitHub Discussions](https://github.com/zhouxiaoka/autoclip/discussions). Les bugs reproductibles passent par le [formulaire d’issue](https://github.com/zhouxiaoka/autoclip/issues/new/choose). Règles du tableau : [community board](docs/COMMUNITY_BOARD.md) (en chinois).

- [Accueil et catégories](https://github.com/zhouxiaoka/autoclip/discussions/127)
- [Questions sur le premier extrait](https://github.com/zhouxiaoka/autoclip/discussions/128)
- [Idées](https://github.com/zhouxiaoka/autoclip/discussions/129)

- E-mail: [christine_zhouye@163.com](mailto:christine_zhouye@163.com)

Merci à FastAPI, React, Tauri, FFmpeg, yt-dlp, Whisper et à toutes les personnes qui contribuent. Distribué sous [licence MIT](LICENSE). Si AutoClip vous est utile, vous pouvez soutenir le projet avec une étoile.

<details>
<summary>Reconnaissance de la communauté · Star History</summary>

Ces badges sont fournis par Trendshift. Cliquez pour consulter les résultats enregistrés d’AutoClip. GitHub Trending et Trendshift sont deux classements distincts ; les badges indiquent des résultats enregistrés, pas une position en temps réel.

[![Star History](https://api.star-history.com/svg?repos=zhouxiaoka/autoclip&type=Date)](https://star-history.com/#zhouxiaoka/autoclip&Date)

</details>
