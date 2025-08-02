import { FastColor } from '@ant-design/fast-color';
export const getAlphaColor = (baseColor, alpha) => new FastColor(baseColor).setA(alpha).toRgbString();
export const getSolidColor = (baseColor, brightness) => {
  const instance = new FastColor(baseColor);
  return instance.lighten(brightness).toHexString();
};