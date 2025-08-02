import defaultAlgorithm from '../default';
import genControlHeight from '../shared/genControlHeight';
import genFontMapToken from '../shared/genFontMapToken';
import genCompactSizeMapToken from './genCompactSizeMapToken';
const derivative = (token, mapToken) => {
  const mergedMapToken = mapToken !== null && mapToken !== void 0 ? mapToken : defaultAlgorithm(token);
  const fontSize = mergedMapToken.fontSizeSM; // Smaller size font-size as base
  const controlHeight = mergedMapToken.controlHeight - 4;
  return Object.assign(Object.assign(Object.assign(Object.assign(Object.assign({}, mergedMapToken), genCompactSizeMapToken(mapToken !== null && mapToken !== void 0 ? mapToken : token)), genFontMapToken(fontSize)), {
    // controlHeight
    controlHeight
  }), genControlHeight(Object.assign(Object.assign({}, mergedMapToken), {
    controlHeight
  })));
};
export default derivative;