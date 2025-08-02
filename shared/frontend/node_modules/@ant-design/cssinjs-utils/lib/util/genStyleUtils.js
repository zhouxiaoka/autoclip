"use strict";

var _interopRequireWildcard = require("@babel/runtime/helpers/interopRequireWildcard").default;
var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var _typeof2 = _interopRequireDefault(require("@babel/runtime/helpers/typeof"));
var _slicedToArray2 = _interopRequireDefault(require("@babel/runtime/helpers/slicedToArray"));
var _defineProperty2 = _interopRequireDefault(require("@babel/runtime/helpers/defineProperty"));
var _objectSpread3 = _interopRequireDefault(require("@babel/runtime/helpers/objectSpread2"));
var _react = _interopRequireDefault(require("react"));
var _cssinjs = require("@ant-design/cssinjs");
var _calc = _interopRequireDefault(require("./calc"));
var _getCompVarPrefix = _interopRequireDefault(require("./getCompVarPrefix"));
var _getComponentToken = _interopRequireDefault(require("./getComponentToken"));
var _getDefaultComponentToken = _interopRequireDefault(require("./getDefaultComponentToken"));
var _maxmin = _interopRequireDefault(require("./maxmin"));
var _statistic = _interopRequireWildcard(require("./statistic"));
var _useUniqueMemo = _interopRequireDefault(require("../_util/hooks/useUniqueMemo"));
var _useCSP = _interopRequireDefault(require("../hooks/useCSP"));
function genStyleUtils(config) {
  // Dependency inversion for preparing basic config.
  var _config$useCSP = config.useCSP,
    useCSP = _config$useCSP === void 0 ? _useCSP.default : _config$useCSP,
    useToken = config.useToken,
    usePrefix = config.usePrefix,
    getResetStyles = config.getResetStyles,
    getCommonStyle = config.getCommonStyle,
    getCompUnitless = config.getCompUnitless;
  function genStyleHooks(component, styleFn, getDefaultToken, options) {
    var componentName = Array.isArray(component) ? component[0] : component;
    function prefixToken(key) {
      return "".concat(String(componentName)).concat(key.slice(0, 1).toUpperCase()).concat(key.slice(1));
    }

    // Fill unitless
    var originUnitless = (options === null || options === void 0 ? void 0 : options.unitless) || {};
    var originCompUnitless = typeof getCompUnitless === 'function' ? getCompUnitless(component) : {};
    var compUnitless = (0, _objectSpread3.default)((0, _objectSpread3.default)({}, originCompUnitless), {}, (0, _defineProperty2.default)({}, prefixToken('zIndexPopup'), true));
    Object.keys(originUnitless).forEach(function (key) {
      compUnitless[prefixToken(key)] = originUnitless[key];
    });

    // Options
    var mergedOptions = (0, _objectSpread3.default)((0, _objectSpread3.default)({}, options), {}, {
      unitless: compUnitless,
      prefixToken: prefixToken
    });

    // Hooks
    var useStyle = genComponentStyleHook(component, styleFn, getDefaultToken, mergedOptions);
    var useCSSVar = genCSSVarRegister(componentName, getDefaultToken, mergedOptions);
    return function (prefixCls) {
      var rootCls = arguments.length > 1 && arguments[1] !== undefined ? arguments[1] : prefixCls;
      var _useStyle = useStyle(prefixCls, rootCls),
        _useStyle2 = (0, _slicedToArray2.default)(_useStyle, 2),
        hashId = _useStyle2[1];
      var _useCSSVar = useCSSVar(rootCls),
        _useCSSVar2 = (0, _slicedToArray2.default)(_useCSSVar, 2),
        wrapCSSVar = _useCSSVar2[0],
        cssVarCls = _useCSSVar2[1];
      return [wrapCSSVar, hashId, cssVarCls];
    };
  }
  function genCSSVarRegister(component, getDefaultToken, options) {
    var compUnitless = options.unitless,
      _options$injectStyle = options.injectStyle,
      injectStyle = _options$injectStyle === void 0 ? true : _options$injectStyle,
      prefixToken = options.prefixToken,
      ignore = options.ignore;
    var CSSVarRegister = function CSSVarRegister(_ref) {
      var rootCls = _ref.rootCls,
        _ref$cssVar = _ref.cssVar,
        cssVar = _ref$cssVar === void 0 ? {} : _ref$cssVar;
      var _useToken = useToken(),
        realToken = _useToken.realToken;
      (0, _cssinjs.useCSSVarRegister)({
        path: [component],
        prefix: cssVar.prefix,
        key: cssVar.key,
        unitless: compUnitless,
        ignore: ignore,
        token: realToken,
        scope: rootCls
      }, function () {
        var defaultToken = (0, _getDefaultComponentToken.default)(component, realToken, getDefaultToken);
        var componentToken = (0, _getComponentToken.default)(component, realToken, defaultToken, {
          deprecatedTokens: options === null || options === void 0 ? void 0 : options.deprecatedTokens
        });
        Object.keys(defaultToken).forEach(function (key) {
          componentToken[prefixToken(key)] = componentToken[key];
          delete componentToken[key];
        });
        return componentToken;
      });
      return null;
    };
    var useCSSVar = function useCSSVar(rootCls) {
      var _useToken2 = useToken(),
        cssVar = _useToken2.cssVar;
      return [function (node) {
        return injectStyle && cssVar ? /*#__PURE__*/_react.default.createElement(_react.default.Fragment, null, /*#__PURE__*/_react.default.createElement(CSSVarRegister, {
          rootCls: rootCls,
          cssVar: cssVar,
          component: component
        }), node) : node;
      }, cssVar === null || cssVar === void 0 ? void 0 : cssVar.key];
    };
    return useCSSVar;
  }
  function genComponentStyleHook(componentName, styleFn, getDefaultToken) {
    var options = arguments.length > 3 && arguments[3] !== undefined ? arguments[3] : {};
    var cells = Array.isArray(componentName) ? componentName : [componentName, componentName];
    var _cells = (0, _slicedToArray2.default)(cells, 1),
      component = _cells[0];
    var concatComponent = cells.join('-');
    var mergedLayer = config.layer || {
      name: 'antd'
    };

    // Return new style hook
    return function (prefixCls) {
      var rootCls = arguments.length > 1 && arguments[1] !== undefined ? arguments[1] : prefixCls;
      var _useToken3 = useToken(),
        theme = _useToken3.theme,
        realToken = _useToken3.realToken,
        hashId = _useToken3.hashId,
        token = _useToken3.token,
        cssVar = _useToken3.cssVar;
      var _usePrefix = usePrefix(),
        rootPrefixCls = _usePrefix.rootPrefixCls,
        iconPrefixCls = _usePrefix.iconPrefixCls;
      var csp = useCSP();
      var type = cssVar ? 'css' : 'js';

      // Use unique memo to share the result across all instances
      var calc = (0, _useUniqueMemo.default)(function () {
        var unitlessCssVar = new Set();
        if (cssVar) {
          Object.keys(options.unitless || {}).forEach(function (key) {
            // Some component proxy the AliasToken (e.g. Image) and some not (e.g. Modal)
            // We should both pass in `unitlessCssVar` to make sure the CSSVar can be unitless.
            unitlessCssVar.add((0, _cssinjs.token2CSSVar)(key, cssVar.prefix));
            unitlessCssVar.add((0, _cssinjs.token2CSSVar)(key, (0, _getCompVarPrefix.default)(component, cssVar.prefix)));
          });
        }
        return (0, _calc.default)(type, unitlessCssVar);
      }, [type, component, cssVar === null || cssVar === void 0 ? void 0 : cssVar.prefix]);
      var _genMaxMin = (0, _maxmin.default)(type),
        max = _genMaxMin.max,
        min = _genMaxMin.min;

      // Shared config
      var sharedConfig = {
        theme: theme,
        token: token,
        hashId: hashId,
        nonce: function nonce() {
          return csp.nonce;
        },
        clientOnly: options.clientOnly,
        layer: mergedLayer,
        // antd is always at top of styles
        order: options.order || -999
      };

      // This if statement is safe, as it will only be used if the generator has the function. It's not dynamic.
      if (typeof getResetStyles === 'function') {
        // Generate style for all need reset tags.
        (0, _cssinjs.useStyleRegister)((0, _objectSpread3.default)((0, _objectSpread3.default)({}, sharedConfig), {}, {
          clientOnly: false,
          path: ['Shared', rootPrefixCls]
        }), function () {
          return getResetStyles(token, {
            prefix: {
              rootPrefixCls: rootPrefixCls,
              iconPrefixCls: iconPrefixCls
            },
            csp: csp
          });
        });
      }
      var wrapSSR = (0, _cssinjs.useStyleRegister)((0, _objectSpread3.default)((0, _objectSpread3.default)({}, sharedConfig), {}, {
        path: [concatComponent, prefixCls, iconPrefixCls]
      }), function () {
        if (options.injectStyle === false) {
          return [];
        }
        var _statisticToken = (0, _statistic.default)(token),
          proxyToken = _statisticToken.token,
          flush = _statisticToken.flush;
        var defaultComponentToken = (0, _getDefaultComponentToken.default)(component, realToken, getDefaultToken);
        var componentCls = ".".concat(prefixCls);
        var componentToken = (0, _getComponentToken.default)(component, realToken, defaultComponentToken, {
          deprecatedTokens: options.deprecatedTokens
        });
        if (cssVar && defaultComponentToken && (0, _typeof2.default)(defaultComponentToken) === 'object') {
          Object.keys(defaultComponentToken).forEach(function (key) {
            defaultComponentToken[key] = "var(".concat((0, _cssinjs.token2CSSVar)(key, (0, _getCompVarPrefix.default)(component, cssVar.prefix)), ")");
          });
        }
        var mergedToken = (0, _statistic.merge)(proxyToken, {
          componentCls: componentCls,
          prefixCls: prefixCls,
          iconCls: ".".concat(iconPrefixCls),
          antCls: ".".concat(rootPrefixCls),
          calc: calc,
          // @ts-ignore
          max: max,
          // @ts-ignore
          min: min
        }, cssVar ? defaultComponentToken : componentToken);
        var styleInterpolation = styleFn(mergedToken, {
          hashId: hashId,
          prefixCls: prefixCls,
          rootPrefixCls: rootPrefixCls,
          iconPrefixCls: iconPrefixCls
        });
        flush(component, componentToken);
        var commonStyle = typeof getCommonStyle === 'function' ? getCommonStyle(mergedToken, prefixCls, rootCls, options.resetFont) : null;
        return [options.resetStyle === false ? null : commonStyle, styleInterpolation];
      });
      return [wrapSSR, hashId];
    };
  }
  function genSubStyleComponent(componentName, styleFn, getDefaultToken) {
    var options = arguments.length > 3 && arguments[3] !== undefined ? arguments[3] : {};
    var useStyle = genComponentStyleHook(componentName, styleFn, getDefaultToken, (0, _objectSpread3.default)({
      resetStyle: false,
      // Sub Style should default after root one
      order: -998
    }, options));
    var StyledComponent = function StyledComponent(_ref2) {
      var prefixCls = _ref2.prefixCls,
        _ref2$rootCls = _ref2.rootCls,
        rootCls = _ref2$rootCls === void 0 ? prefixCls : _ref2$rootCls;
      useStyle(prefixCls, rootCls);
      return null;
    };
    if (process.env.NODE_ENV !== 'production') {
      StyledComponent.displayName = "SubStyle_".concat(String(Array.isArray(componentName) ? componentName.join('.') : componentName));
    }
    return StyledComponent;
  }
  return {
    genStyleHooks: genStyleHooks,
    genSubStyleComponent: genSubStyleComponent,
    genComponentStyleHook: genComponentStyleHook
  };
}
var _default = exports.default = genStyleUtils;