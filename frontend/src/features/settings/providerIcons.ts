/**
 * Provider list icons (OhMyGame / mockups-v6 style).
 * Missing ids fall back to the letter mark in the catalog card.
 */
import openai from '../../assets/providers/openai.svg'
import deepseek from '../../assets/providers/deepseek.svg'
import gemini from '../../assets/providers/gemini.svg'
import xai from '../../assets/providers/xai.svg'
import ollama from '../../assets/providers/ollama.svg'
import lmstudio from '../../assets/providers/lmstudio.svg'
import openrouter from '../../assets/providers/openrouter.svg'
import siliconcloud from '../../assets/providers/siliconcloud.svg'
import azure from '../../assets/providers/azure.svg'
import bedrock from '../../assets/providers/bedrock.svg'
import cloudflare from '../../assets/providers/cloudflare.svg'
import vertexai from '../../assets/providers/vertexai.svg'
import bailian from '../../assets/providers/bailian.svg'
import kimi from '../../assets/providers/kimi.svg'
import moonshot from '../../assets/providers/moonshot.svg'
import zhipu from '../../assets/providers/zhipu.svg'
import bytedance from '../../assets/providers/bytedance.svg'
import volcengine from '../../assets/providers/volcengine.svg'
import hunyuan from '../../assets/providers/hunyuan.svg'
import wenxin from '../../assets/providers/wenxin.svg'
import minimax from '../../assets/providers/minimax.svg'
import mistral from '../../assets/providers/mistral.svg'
import nvidia from '../../assets/providers/nvidia.svg'
import huggingface from '../../assets/providers/huggingface.svg'
import fireworks from '../../assets/providers/fireworks.svg'
import cerebras from '../../assets/providers/cerebras.svg'
import baseten from '../../assets/providers/baseten.svg'
import together from '../../assets/providers/together.svg'
import vercel from '../../assets/providers/vercel.svg'
import anthropic from '../../assets/providers/anthropic.svg'
import antgroup from '../../assets/providers/antgroup.svg'
import groq from '../../assets/providers/groq.svg'
import xiaomimimo from '../../assets/providers/xiaomimimo.svg'
import api88 from '../../assets/providers/api88.jpg'
import infistar from '../../assets/providers/infistar.svg'
import apimart from '../../assets/providers/apimart.svg'

export type ProviderIconTone = 'color' | 'monochrome'

export type ProviderIcon = { src: string; tone: ProviderIconTone }

const color = (src: string): ProviderIcon => ({ src, tone: 'color' })
const mono = (src: string): ProviderIcon => ({ src, tone: 'monochrome' })

/** Catalog provider id → icon (OhMyGame-aligned). */
export const PROVIDER_ICONS: Readonly<Partial<Record<string, ProviderIcon>>> = {
  api88: color(api88),
  infistar: color(infistar),
  apimart: mono(apimart),
  openai: mono(openai),
  deepseek: color(deepseek),
  gemini: color(gemini),
  grok: mono(xai),
  ollama: mono(ollama),
  lmstudio: mono(lmstudio),
  openrouter: mono(openrouter),
  siliconflow: color(siliconcloud),
  'azure-openai': color(azure),
  'amazon-bedrock': color(bedrock),
  'cloudflare-ai-gateway': color(cloudflare),
  'cloudflare-workers-ai': color(cloudflare),
  'google-vertex': color(vertexai),
  dashscope: color(bailian),
  kimi: color(kimi),
  moonshotai: mono(moonshot),
  glm: mono(zhipu),
  seed: color(bytedance),
  'byteplus-modelark': color(bytedance),
  hunyuan: color(hunyuan),
  qianfan: color(wenxin),
  minimax: color(minimax),
  'minimax-cn': color(minimax),
  mistral: color(mistral),
  nvidia: color(nvidia),
  huggingface: color(huggingface),
  fireworks: color(fireworks),
  cerebras: color(cerebras),
  baseten: mono(baseten),
  together: color(together),
  'vercel-ai-gateway': mono(vercel),
  anthropic: mono(anthropic),
  'ant-ling': color(antgroup),
  groq: mono(groq),
  xiaomi: mono(xiaomimimo),
  // Volcengine / 豆包 family often shares seed; keep volcengine for clarity if id appears
  volcengine: color(volcengine),
  'volcengine-ark': color(volcengine),
  // OhMyGame id aliases
  google: color(gemini),
  xai: mono(xai),
  zai: mono(zhipu),
  'kimi-coding': color(kimi),
  'azure-openai-responses': color(azure),
  'qwen-token-plan': color(bailian),
  'qwen-token-plan-cn': color(bailian),
}

export function providerIcon(id?: string | null): ProviderIcon | undefined {
  if (!id) return undefined
  return PROVIDER_ICONS[id]
}
