import { generate } from '@ant-design/colors';
import defaultAlgorithm from '../default';
import { defaultPresetColors } from '../seed';
import genColorMapToken from '../shared/genColorMapToken';
import { generateColorPalettes, generateNeutralColorPalettes } from './colors';
const derivative = (token, mapToken) => {
  const colorPalettes = Object.keys(defaultPresetColors).map(colorKey => {
    const colors = generate(token[colorKey], {
      theme: 'dark'
    });
    return Array.from({
      length: 10
    }, () => 1).reduce((prev, _, i) => {
      prev[`${colorKey}-${i + 1}`] = colors[i];
      prev[`${colorKey}${i + 1}`] = colors[i];
      return prev;
    }, {});
  }).reduce((prev, cur) => {
    // biome-ignore lint/style/noParameterAssign: it is a reduce
    prev = Object.assign(Object.assign({}, prev), cur);
    return prev;
  }, {});
  const mergedMapToken = mapToken !== null && mapToken !== void 0 ? mapToken : defaultAlgorithm(token);
  const colorMapToken = genColorMapToken(token, {
    generateColorPalettes,
    generateNeutralColorPalettes
  });
  return Object.assign(Object.assign(Object.assign(Object.assign({}, mergedMapToken), colorPalettes), colorMapToken), {
    // Customize selected item background color
    // https://github.com/ant-design/ant-design/issues/30524#issuecomment-871961867
    colorPrimaryBg: colorMapToken.colorPrimaryBorder,
    colorPrimaryBgHover: colorMapToken.colorPrimaryBorderHover
  });
};
export default derivative;