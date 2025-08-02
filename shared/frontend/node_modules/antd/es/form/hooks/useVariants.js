import * as React from 'react';
import { VariantContext } from '../context';
import { ConfigContext, Variants } from '../../config-provider';
/**
 * Compatible for legacy `bordered` prop.
 */
const useVariant = (component, variant, legacyBordered = undefined) => {
  var _a, _b;
  const {
    variant: configVariant,
    [component]: componentConfig
  } = React.useContext(ConfigContext);
  const ctxVariant = React.useContext(VariantContext);
  const configComponentVariant = componentConfig === null || componentConfig === void 0 ? void 0 : componentConfig.variant;
  let mergedVariant;
  if (typeof variant !== 'undefined') {
    mergedVariant = variant;
  } else if (legacyBordered === false) {
    mergedVariant = 'borderless';
  } else {
    // form variant > component global variant > global variant
    mergedVariant = (_b = (_a = ctxVariant !== null && ctxVariant !== void 0 ? ctxVariant : configComponentVariant) !== null && _a !== void 0 ? _a : configVariant) !== null && _b !== void 0 ? _b : 'outlined';
  }
  const enableVariantCls = Variants.includes(mergedVariant);
  return [mergedVariant, enableVariantCls];
};
export default useVariant;