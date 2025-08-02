import extractStyle from "./extractStyle";
import useCacheToken, { getComputedToken } from "./hooks/useCacheToken";
import useCSSVarRegister from "./hooks/useCSSVarRegister";
import useStyleRegister from "./hooks/useStyleRegister";
import Keyframes from "./Keyframes";
import { legacyNotSelectorLinter, logicalPropertiesLinter, NaNLinter, parentSelectorLinter } from "./linters";
import StyleContext, { createCache, StyleProvider } from "./StyleContext";
import { createTheme, genCalc, Theme } from "./theme";
import legacyLogicalPropertiesTransformer from "./transformers/legacyLogicalProperties";
import px2remTransformer from "./transformers/px2rem";
import { supportLogicProps, supportWhere, unit } from "./util";
import { token2CSSVar } from "./util/css-variables";
export { Theme, createTheme, useStyleRegister, useCSSVarRegister, useCacheToken, createCache, StyleProvider, StyleContext, Keyframes, extractStyle, getComputedToken,
// Transformer
legacyLogicalPropertiesTransformer, px2remTransformer,
// Linters
logicalPropertiesLinter, legacyNotSelectorLinter, parentSelectorLinter, NaNLinter,
// util
token2CSSVar, unit, genCalc };
export var _experimental = {
  supportModernCSS: function supportModernCSS() {
    return supportWhere() && supportLogicProps();
  }
};