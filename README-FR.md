<div align="center">

<img src="src-tauri/icons/128x128.png" alt="AutoClip" width="80" height="80">

# AutoClip

**Repérez les meilleurs moments de vos vidéos avec l’IA et générez des clips courts en HD en un clic.**

[简体中文](README.md) · [English](README-EN.md) · [日本語](README-JA.md) · [한국어](README-KO.md) · [Español](README-ES.md) · [Português](README-PT.md) · [Русский](README-RU.md) · **Français**

[![GitHub release](https://img.shields.io/github/v/release/zhouxiaoka/autoclip?style=flat-square)](https://github.com/zhouxiaoka/autoclip/releases/latest)
[![GitHub stars](https://img.shields.io/github/stars/zhouxiaoka/autoclip?style=flat-square)](https://github.com/zhouxiaoka/autoclip/stargazers)
[![GitHub forks](https://img.shields.io/github/forks/zhouxiaoka/autoclip?style=flat-square)](https://github.com/zhouxiaoka/autoclip/forks)
[![GitHub issues](https://img.shields.io/github/issues/zhouxiaoka/autoclip?style=flat-square)](https://github.com/zhouxiaoka/autoclip/issues)
[![License: MIT](https://img.shields.io/github/license/zhouxiaoka/autoclip?style=flat-square)](LICENSE)

<p align="center">
  <a href="https://trendshift.io/repositories/25801"><img src="https://trendshift.io/api/badge/repositories/25801" alt="AutoClip — Trendshift" width="250" height="55"></a>
</p>

Gratuit et open source · Montage local · Modèles locaux et cloud

[Site du projet](https://zhouxiaoka.github.io/autoclip_intro/) · [Discussions](https://github.com/zhouxiaoka/autoclip/discussions) · [Signaler un problème](https://github.com/zhouxiaoka/autoclip/issues)

**Programmes d’installation: [macOS · Apple Silicon](https://github.com/zhouxiaoka/autoclip/releases/latest) · [Windows · x64](https://github.com/zhouxiaoka/autoclip/releases/latest)**

[Installation et premiers extraits (English)](docs/USER_INSTALLATION_GUIDE.en.md) · [Guide complet de dépannage (anglais)](docs/FAQ.en.md)

</div>

Transformez vos interviews, podcasts, cours et rediffusions en clips courts. AutoClip repère les moments forts, génère des titres et crée des clips et des compilations que vous pouvez ajuster puis exporter.

## Aperçu

![Écran d’importation d’AutoClip](docs/images/import-local.jpg)

Importez une vidéo locale avec, si besoin, des sous-titres SRT. La capture montre l’interface en chinois.

## Fonctionnalités

| Fonction | Description |
| --- | --- |
| Importer des vidéos | Fichiers locaux et liens YouTube ou Bilibili. |
| Repérer les moments forts | Analyse des sous-titres pour sélectionner des passages, générer des titres et organiser les sujets sur une chronologie. |
| Monter des clips | Création de clips et de compilations ; ajustement du début, de la fin, du texte et du format d’image. |
| Moments de jeu | Détection d’événements dans les parties enregistrées. Configurez un modèle visuel et activez l’analyse de jeu ; les appels cloud sont facturés par le fournisseur. [Configuration (chinois)](docs/MULTI_LLM_PROVIDER_GUIDE.md). |
| Exporter et publier | Vidéos horizontales ou verticales, sous-titres, cartons de titre, couvertures automatiques et publication immédiate ou programmée. [Guide de publication (chinois)](docs/PUBLISH_UPLOAD_POST.md). |
| Modèles et automatisation | Qwen, OpenAI, Gemini, DeepSeek et d’autres modèles cloud, ou modèles locaux via Ollama / LM Studio. Accès CLI et MCP. |

> Importer → Confirmer le type de vidéo → Analyse et montage par IA → Ajuster et exporter

## Démarrage rapide

1. **Installer.** Téléchargez le `.dmg` pour macOS Apple Silicon ou le `-setup.exe` pour Windows x64 depuis [GitHub Releases](https://github.com/zhouxiaoka/autoclip/releases/latest). Python et FFmpeg sont inclus.
2. **Configurer un modèle.** Dans les paramètres, saisissez votre clé API ou connectez un modèle local, testez la connexion et enregistrez.
3. **Créer des clips.** Importez une vidéo et confirmez son type pour lancer l’analyse et le montage. Vérifiez le résultat, ajustez-le et exportez.

L’installation, l’importation et l’enregistrement sur une machine Windows physique restent à valider. Sur Intel Mac et Linux, utilisez Docker ou la CLI.

[Installation (anglais)](docs/USER_INSTALLATION_GUIDE.en.md) · [Dépannage (anglais)](docs/FAQ.en.md)

<details>
<summary>Docker / Web, CLI et MCP</summary>

- **Docker / Web :** Hébergez l’interface web avec le [guide Docker (anglais)](docs/DOCKER.en.md).
- **CLI :** Traitement par lots et scripts ; consultez le [guide CLI (chinois)](docs/CLI_AND_MCP.md).
- **MCP :** Connectez un client avec ce même guide ou utilisez l’[Agent skill (chinois)](skills/autoclip/SKILL.md).

</details>

## Questions fréquentes

<details>
<summary>Combien cela coûte-t-il ?</summary>

AutoClip est gratuit et open source sous licence MIT. Les modèles cloud nécessitent votre propre clé API et sont facturés par leur fournisseur. Les modèles locaux Ollama / LM Studio n’exigent pas de clé cloud. La publication sur les plateformes internationales nécessite votre compte [Upload-Post](https://www.upload-post.com) ; consultez son site pour les tarifs et limites.

</details>

<details>
<summary>Ma vidéo est-elle envoyée en ligne ?</summary>

Le montage et le rendu s’effectuent sur votre machine. L’analyse cloud des sous-titres envoie le texte utile ; l’analyse visuelle envoie des images échantillonnées et le texte nécessaire. La publication envoie la vidéo finale aux plateformes connectées. Vous pouvez aussi exporter uniquement en local. [Confidentialité (anglais)](docs/PRIVACY.en.md).

</details>

<details>
<summary>Puis-je utiliser une vidéo sans sous-titres ?</summary>

Oui. Configurez Whisper en local et un modèle vocal pour la transcription, ou importez un fichier SRT existant. Pour commencer, essayez une courte vidéo sous-titrée avec le [guide de démarrage (anglais)](docs/USER_INSTALLATION_GUIDE.en.md).

</details>

<details>
<summary>Quels contenus conviennent le mieux ? Peut-on exporter en HD ?</summary>

L’analyse des sous-titres convient aux interviews, podcasts, cours et contenus parlés. Les parties enregistrées peuvent utiliser l’analyse visuelle. L’export horizontal et vertical en 1080p est pris en charge ; la qualité dépend de la source et des réglages. Le temps de traitement varie selon la durée, le modèle et le matériel.

</details>

## Soutenir le projet

Les entreprises et les particuliers peuvent sponsoriser AutoClip pour soutenir son développement et sa maintenance. Les entreprises sponsors peuvent présenter leur marque et leurs services dans le README.

Contact pour le sponsoring : [christine_zhouye@163.com](mailto:christine_zhouye@163.com)

## Documentation et communauté

- [Installation (anglais)](docs/USER_INSTALLATION_GUIDE.en.md) · [Modèles (chinois)](docs/MULTI_LLM_PROVIDER_GUIDE.md) · [Dépannage (anglais)](docs/FAQ.en.md)
- [Historique des versions (chinois)](CHANGELOG.md) · [Documentation (chinois)](docs/README.md)
- Posez vos questions et partagez vos idées dans [Discussions](https://github.com/zhouxiaoka/autoclip/discussions), et signalez les bugs dans [Issues](https://github.com/zhouxiaoka/autoclip/issues/new/choose).
- Les contributions au code, à la documentation et aux traductions sont les bienvenues. [Guide de contribution (chinois)](CONTRIBUTING.md).
- Contact et sponsoring : [christine_zhouye@163.com](mailto:christine_zhouye@163.com)

Merci à toutes les personnes qui contribuent et aux projets FastAPI, React, Tauri, FFmpeg, yt-dlp et Whisper. Si AutoClip vous aide, vous pouvez le soutenir avec une Star.

[![Star History](https://api.star-history.com/svg?repos=zhouxiaoka/autoclip&type=Date)](https://star-history.com/#zhouxiaoka/autoclip&Date)
