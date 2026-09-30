import { t } from '../../i18n'

export type ProviderKey = 'dashscope' | 'openai' | 'compatible' | 'infistar' | 'api88' | 'gemini' | 'deepseek' | 'seed' | 'kimi' | 'glm' | 'grok' | 'ollama' | 'lmstudio'
type LocalPreset = { baseUrl: string; defaultModel: string; docsUrl: string; app: string }
type CloudPreset = { baseUrl: string; defaultModel: string }
export type SponsorId = 'infistar' | 'api88'
type Sponsor = { id: SponsorId; registerUrl: string; guideUrl: string; offer: string; description: string }
// 提供商会越来越多：下拉按组展示、可搜索，新增一家只在 PROVIDERS 里加一条并标 group
type ProviderGroup = 'sponsor' | 'cloud' | 'compatible' | 'local'
const PROVIDER_GROUPS: Array<{ key: ProviderGroup; label: () => string }> = [
  { key: 'sponsor', label: () => t('推荐') },
  { key: 'cloud', label: () => t("官方供应商") },
  { key: 'compatible', label: () => t("兼容接口") },
  { key: 'local', label: () => t("本机运行") },
]
export const PROVIDERS: Record<ProviderKey, { name: string; short: string; hint: string; apiKeyField: string; placeholder: string; keyUrl: string; group: ProviderGroup; local?: LocalPreset; cloud?: CloudPreset; sponsor?: Sponsor }> = {
  dashscope: { get name() { return t("阿里云百炼") }, get short() { return t("阿里云百炼") }, get hint() { return t("阿里云百炼官方服务，接口地址已预设。") }, group: 'cloud', apiKeyField: 'dashscope_api_key', placeholder: 'sk-…', keyUrl: 'https://bailian.console.aliyun.com/' },
  openai: { name: 'OpenAI', short: 'OpenAI', get hint() { return t('OpenAI 官方服务，接口地址已预设。') }, group: 'cloud', apiKeyField: 'openai_api_key', placeholder: 'sk-…', keyUrl: 'https://platform.openai.com/api-keys' },
  compatible: { get name() { return t('自定义 OpenAI 兼容接口') }, get short() { return t('自定义兼容接口') }, get hint() { return t('适用于 OpenRouter、第三方网关或自建服务。') }, group: 'compatible', apiKeyField: 'openai_api_key', get placeholder() { return t('sk-…（自建服务可留空）') }, keyUrl: '' },
  // 赞助合作伙伴（docs/INFISTAR_SETUP.md）。多模型网关，型号随账号而定：不预设默认模型，填好 key 后实时拉取
  api88: { get name() { return t('88API Token聚合平台') }, short: '88API', get hint() { return t('赞助合作伙伴。聚合语言、图片与语音模型，接口地址已预设。') }, group: 'sponsor', apiKeyField: 'api88_api_key', placeholder: 'sk-…', keyUrl: 'https://88api.ai/sign-up?aff=2PIc', cloud: { baseUrl: 'https://88api.ai/v1', defaultModel: '' }, sponsor: { id: 'api88', registerUrl: 'https://88api.ai/sign-up?aff=2PIc', guideUrl: 'https://github.com/zhouxiaoka/autoclip/blob/main/docs/88API_SETUP.md', get offer() { return t('新用户体验额度') }, get description() { return t('新用户通过专属链接注册可获体验额度；站内提供人工客服。') } } },
  infistar: { get name() { return t("Infistar 无限星河") }, short: 'Infistar', get hint() { return t("赞助合作伙伴。一个 Key 调用 Claude、GPT、Gemini、DeepSeek 等模型，接口地址已预设。") }, group: 'sponsor', apiKeyField: 'infistar_api_key', placeholder: 'sk-…', keyUrl: 'https://www.infistar.cc/register?aff=XLK3BCM6&ref_source=link', cloud: { baseUrl: 'https://infistar.cc/v1', defaultModel: '' }, sponsor: { id: 'infistar', get offer() { return t('$5 免费体验额度') }, get description() { return t('通过专属链接注册，可领取 $5 免费体验额度。') }, registerUrl: 'https://www.infistar.cc/register?aff=XLK3BCM6&ref_source=link', guideUrl: 'https://github.com/zhouxiaoka/autoclip/blob/main/docs/INFISTAR_SETUP.md' } },
  gemini: { name: 'Google Gemini', short: 'Gemini', get hint() { return t("Google AI Studio 的 Gemini 系列。") }, group: 'cloud', apiKeyField: 'gemini_api_key', placeholder: 'AIza…', keyUrl: 'https://aistudio.google.com/apikey' },
  deepseek: { name: 'DeepSeek', short: 'DeepSeek', get hint() { return t("DeepSeek 官方。国内直连，deepseek-flash 是当前 V4.1。") }, group: 'cloud', apiKeyField: 'deepseek_api_key', placeholder: 'sk-…', keyUrl: 'https://platform.deepseek.com/api_keys', cloud: { baseUrl: 'https://api.deepseek.com', defaultModel: 'deepseek-flash' } },
  seed: { name: 'Seed', short: 'Seed', get hint() { return t("火山方舟 Seed。国内直连，豆包 Seed 2.1 系列。") }, group: 'cloud', apiKeyField: 'seed_api_key', placeholder: '…', keyUrl: 'https://console.volcengine.com/ark/region:ark+cn-beijing/apiKey', cloud: { baseUrl: 'https://ark.cn-beijing.volces.com/api/v3', defaultModel: 'doubao-seed-2-1-lite-260915' } },
  kimi: { name: 'Kimi', short: 'Kimi', get hint() { return t("月之暗面 Kimi。国内直连，适合长字幕分析。") }, group: 'cloud', apiKeyField: 'kimi_api_key', placeholder: 'sk-…', keyUrl: 'https://platform.moonshot.cn/console/api-keys', cloud: { baseUrl: 'https://api.moonshot.cn/v1', defaultModel: 'kimi-k2.6' } },
  glm: { get name() { return t("智谱 GLM") }, get short() { return 'GLM' }, get hint() { return t("智谱开放平台。国内直连，glm-5.3 是当前旗舰。") }, group: 'cloud', apiKeyField: 'glm_api_key', placeholder: '…', keyUrl: 'https://open.bigmodel.cn/usercenter/apikeys', cloud: { baseUrl: 'https://open.bigmodel.cn/api/paas/v4', defaultModel: 'glm-5.3' } },
  grok: { name: 'Grok', short: 'Grok', get hint() { return t("xAI Grok。需要 xAI 账号。") }, group: 'cloud', apiKeyField: 'grok_api_key', placeholder: 'xai-…', keyUrl: 'https://console.x.ai', cloud: { baseUrl: 'https://api.x.ai/v1', defaultModel: 'grok-4.6' } },
  // 本地预设：底层是 openai 兼容 + base_url，后端 core/local_presets.py 负责还原；无需密钥、不花钱、离线可用
  ollama: { name: 'Ollama', short: 'Ollama', get hint() { return t("本机运行的 Ollama，免费、离线。推荐 ollama pull qwen2.5:7b。") }, group: 'local', apiKeyField: 'openai_api_key', placeholder: '', keyUrl: 'https://ollama.com/download', local: { baseUrl: 'http://localhost:11434/v1', defaultModel: 'qwen2.5:7b', docsUrl: 'https://ollama.com/download', app: 'Ollama' } },
  lmstudio: { name: 'LM Studio', short: 'LM Studio', get hint() { return t("本机 LM Studio 的 Local Server，免费、离线。在 LM Studio 里加载模型并启动服务。") }, group: 'local', apiKeyField: 'openai_api_key', placeholder: '', keyUrl: 'https://lmstudio.ai', local: { baseUrl: 'http://localhost:1234/v1', defaultModel: '', docsUrl: 'https://lmstudio.ai', app: 'LM Studio' } },
}
export const providerPickerOptions = () => PROVIDER_GROUPS
  .map((group) => ({
    label: group.label(),
    options: (Object.keys(PROVIDERS) as ProviderKey[])
      .filter((key) => PROVIDERS[key].group === group.key)
      .map((key) => ({
        value: key,
        label: PROVIDERS[key].short,
        search: `${key} ${PROVIDERS[key].short} ${PROVIDERS[key].name}`.toLowerCase(),
        title: PROVIDERS[key].name,
      })),
  }))
  .filter((group) => group.options.length)
