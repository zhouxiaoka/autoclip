"use strict";

var _interopRequireWildcard = require("@babel/runtime/helpers/interopRequireWildcard").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var React = _interopRequireWildcard(require("react"));
var _context = require("../context");
var _configProvider = require("../../config-provider");
/**
 * Compatible for legacy `bordered` prop.
 */
const useVariant = (component, variant, legacyBordered = undefined) => {
  var _a, _b;
  const {
    variant: configVariant,
    [component]: componentConfig
  } = React.useContext(_configProvider.ConfigContext);
  const ctxVariant = React.useContext(_context.VariantContext);
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
  const enableVariantCls = _configProvider.Variants.includes(mergedVariant);
  return [mergedVariant, enableVariantCls];
};
var _default = exports.default = useVariant;