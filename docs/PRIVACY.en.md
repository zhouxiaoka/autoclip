# AutoClip Privacy Policy

*[中文版 →](./PRIVACY.md)*

**Effective Date: June 3, 2026**
**Last Updated: September 21, 2026**

> ⚠️ This is a draft template. Please have legal counsel review it before publishing (see "Clauses Requiring Legal Review" at the end).

AutoClip ("the Software", "we", "us") is a **local-first** desktop video clipping tool. We take your privacy seriously. This policy explains what information we collect, how we use, store, and protect it, and the rights you have.

This policy is drafted with reference to China's Personal Information Protection Law (PIPL), Cybersecurity Law, and Data Security Law. For users in other regions, see "International Transfers" and the compliance notes below.

---

## 1. Core Principle: Local-First

- **Your videos, audio, subtitles, and transcripts are processed and stored entirely on your own device** and are never uploaded to our servers.
- **Third-party API keys you configure** (e.g., Tongyi Qianwen, OpenAI, Gemini) **are stored only on your device**, never uploaded, and never appear in any analytics data.
- We **do not collect** your name, phone number, email, ID documents, or any other directly identifying personal information.

---

## 2. Information We Collect

### 2.1 Anonymous Usage Analytics (currently enabled)

To understand how features are used, find and fix problems, and improve the product, the Software collects **anonymous** usage data via **PostHog**. This data **does not include** your video content, subtitle/transcript text, file contents, or API keys.

| Category | Details | Purpose |
|----------|---------|---------|
| Device & environment | OS type, CPU architecture, app version, system language | Compatibility & troubleshooting |
| Usage behavior | Events such as app launch, page views, video import, clip export, saving settings | Measure feature usage & conversion |
| Outcomes | Success/failure of processing, the failing stage and error code | Improve stability |
| Anonymous identifier | A randomly generated device ID (stored locally, not linked to your real identity) | Distinguish devices, compute retention |

- **Anonymity**: We use a randomly generated device identifier and do not build identifiable user profiles.
- **Recipient**: PostHog Inc., with data stored on its **United States** servers (see Section 6, "International Transfers").
- **Local buffering**: Events are batched locally before sending; network issues do not affect normal use of the Software.

### 2.2 Crash reports (optional, on by default)

To fix crashes, the Software may send stack traces via **Sentry** when a DSN is configured at build time and you have not turned off **Crash reports** in Settings → App. This does **not** include video content, transcripts, or API keys. `send_default_pii` is off. The client does not explicitly set a user identifier or IP field; the recipient can still obtain connection-source information and may infer an approximate region from it.

### 2.3 Information You Provide

- **Third-party platform accounts/cookies**: If you use download or upload features for platforms such as Bilibili or YouTube, the related credentials (cookies, etc.) are **stored only on your device** to perform the actions you initiate. We do not collect or upload them.

### 2.4 Information We Do Not Collect

- Your original video/audio content
- Subtitle or transcript text
- Plaintext third-party API keys
- Name, phone number, email, geolocation, ID documents, or other personally identifying information

---

## 3. How We Use Information

We use the anonymous data above solely to:

1. Measure feature usage and product funnels (e.g., import-to-export conversion);
2. Detect and fix defects, and improve stability and performance;
3. Evaluate the impact of changes and plan product direction.

We **do not** use this data for advertising, and we **do not** sell any of your information.

---

## 4. Your Choices and Rights

### 4.1 Turn Off Usage Analytics

You can disable "Anonymous Usage Analytics" at any time under **Settings → App Settings → Privacy & Data**. Once disabled, the Software **immediately stops sending any usage data**, and this setting persists across restarts.

### 4.2 Your Legal Rights

Where applicable (e.g., under PIPL), you have the right to:

- Be informed, access, and obtain a copy;
- Correct and supplement;
- Delete;
- Withdraw consent (i.e., turn off the analytics switch);
- Deregister (applicable once account features launch).

To exercise these rights or file a complaint, contact us using the details below.

---

## 5. Data Storage and Retention

- **Local data** (projects, videos, subtitles, settings, keys): stored on your device and fully under your control; uninstalling the Software or deleting a project removes it.
- **Anonymous analytics data**: stored by PostHog, retained according to our retention policy (by default no longer than **12 months**), after which it is automatically deleted or anonymized.

---

## 6. International Transfers

Anonymous usage analytics are stored by PostHog on **United States** servers, which may involve transferring data outside of mainland China. We limit transferred data to anonymous, non-identifying information. **[Legal review item: the lawful basis for cross-border transfer (separate consent / standard contract / security assessment) must be confirmed under PIPL Chapter III. For EU/UK users, an appropriate GDPR transfer mechanism must be assessed.]**

---

## 7. Third-Party Services

| Service | Provider | Purpose | Privacy Policy |
|---------|----------|---------|----------------|
| Product analytics | PostHog Inc. | Anonymous usage analytics | https://posthog.com/privacy |
| Third-party AI models (you configure) | Tongyi Qianwen / OpenAI / Google, etc. | Called directly by you; keys stored locally | See each provider's policy |
| Video platforms (you use) | Bilibili / YouTube, etc. | Downloads/uploads you initiate | See each platform's policy |

When you call third-party AI services directly within the Software, the resulting data flows and privacy rules are governed by that provider's privacy policy. We do not relay or retain that data.

---

## 8. Children's Privacy

The Software is intended for adult professional users and is **not directed to children under 14**. We do not knowingly collect children's personal information.

---

## 9. Security Measures

We apply reasonable technical and organizational measures to protect data, including transport encryption (HTTPS), data minimization, anonymization, and keeping keys on-device. However, please understand that no method of internet transmission is completely secure.

---

## 10. Planned Features (not yet enabled)

The following are on our product roadmap and **are not currently active and collect no related data**. Before they go live, we will update this policy, notify you clearly, and **obtain your separate consent** where personal information is involved:

- **Accounts**: optional sign-up/login in the future to sync settings, usage quotas, etc. This would collect necessary account information.
- **Cloud LLM proxy**: in the future, if you opt to use our hosted model proxy, **your subtitle/transcript text would be forwarded through our proxy servers** to perform AI processing. This is optional; until enabled, text never leaves your device.
- **Payments & metering**: we may introduce top-ups, subscriptions, etc., processing transaction information through compliant payment channels.

---

## 11. Policy Updates

When our data practices change, we will update this policy and revise the "Last Updated" date. Material changes will be communicated through means such as in-app notices.

---

## 12. Contact Us

For any questions, comments, or complaints about this Privacy Policy or our handling of personal information, contact:

- Email: **christine95zhouye@gmail.com**
- Website: **https://zhouxiaoka.github.io/autoclip_intro/**

---

---

## Compliance Checklist

| Regulation | Status | Notes |
|-----------|--------|-------|
| PIPL (China) | ⚠️ Partial | Currently anonymous data; cross-border & separate-consent path pending legal review |
| Data Security Law / Cybersecurity Law | ✅ Largely compliant | Local-first, data minimization |
| GDPR (if serving EU users) | ⚠️ To assess | Currently PostHog US region; EU expansion needs lawful basis & EU region |
| CCPA (if serving California users) | ⚠️ To assess | Assess before overseas release |
| COPPA / children | ✅ N/A | Not directed to children |

## Clauses Requiring Legal Review

| Clause | Why | Priority |
|--------|-----|----------|
| Section 6 — Cross-border transfer (PostHog US) | PIPL requires a clear lawful basis (separate consent / standard contract / security assessment) | High |
| "Anonymous" characterization | Whether device ID + behavioral data constitutes identifiable personal information affects whether separate consent is required | High |
| Section 5 — Retention period | Confirm the specific retention duration | Medium |
| Section 10 — Planned features (cloud proxy handling user text) | Must be rewritten as formal terms with separate consent before launch | Medium (before enabling) |
| Overseas release (GDPR/CCPA) | Add corresponding sections before expanding to overseas markets | Low (per Roadmap Phase 3) |

## Implementation Checklist

- [x] Fill in contact email, website, and retention period
- [ ] Legal review of cross-border transfer and "separate consent" path
- [ ] Show privacy policy entry / consent prompt on first launch
- [ ] Publish the same policy on the website and keep versions consistent
- [ ] Add a link to this policy next to the "Privacy & Data" toggle in Settings
- [ ] Configure PostHog data retention policy to match Section 5
- [ ] Update this policy and re-trigger consent before launching accounts / cloud proxy / payments
