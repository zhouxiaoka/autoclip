"use strict";
"use client";

var _interopRequireWildcard = require("@babel/runtime/helpers/interopRequireWildcard").default;
var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = confirm;
exports.modalGlobalConfig = modalGlobalConfig;
exports.withConfirm = withConfirm;
exports.withError = withError;
exports.withInfo = withInfo;
exports.withSuccess = withSuccess;
exports.withWarn = withWarn;
var _toConsumableArray2 = _interopRequireDefault(require("@babel/runtime/helpers/toConsumableArray"));
var _react = _interopRequireWildcard(require("react"));
var _warning = _interopRequireDefault(require("../_util/warning"));
var _configProvider = _interopRequireWildcard(require("../config-provider"));
var _UnstableContext = require("../config-provider/UnstableContext");
var _ConfirmDialog = _interopRequireDefault(require("./ConfirmDialog"));
var _destroyFns = _interopRequireDefault(require("./destroyFns"));
var _locale = require("./locale");
let defaultRootPrefixCls = '';
function getRootPrefixCls() {
  return defaultRootPrefixCls;
}
const ConfirmDialogWrapper = props => {
  var _a, _b;
  const {
    prefixCls: customizePrefixCls,
    getContainer,
    direction
  } = props;
  const runtimeLocale = (0, _locale.getConfirmLocale)();
  const config = (0, _react.useContext)(_configProvider.ConfigContext);
  const rootPrefixCls = getRootPrefixCls() || config.getPrefixCls();
  // because Modal.config set rootPrefixCls, which is different from other components
  const prefixCls = customizePrefixCls || `${rootPrefixCls}-modal`;
  let mergedGetContainer = getContainer;
  if (mergedGetContainer === false) {
    mergedGetContainer = undefined;
    if (process.env.NODE_ENV !== 'production') {
      process.env.NODE_ENV !== "production" ? (0, _warning.default)(false, 'Modal', 'Static method not support `getContainer` to be `false` since it do not have context env.') : void 0;
    }
  }
  return /*#__PURE__*/_react.default.createElement(_ConfirmDialog.default, Object.assign({}, props, {
    rootPrefixCls: rootPrefixCls,
    prefixCls: prefixCls,
    iconPrefixCls: config.iconPrefixCls,
    theme: config.theme,
    direction: direction !== null && direction !== void 0 ? direction : config.direction,
    locale: (_b = (_a = config.locale) === null || _a === void 0 ? void 0 : _a.Modal) !== null && _b !== void 0 ? _b : runtimeLocale,
    getContainer: mergedGetContainer
  }));
};
function confirm(config) {
  const global = (0, _configProvider.globalConfig)();
  if (process.env.NODE_ENV !== 'production' && !global.holderRender) {
    (0, _configProvider.warnContext)('Modal');
  }
  const container = document.createDocumentFragment();
  let currentConfig = Object.assign(Object.assign({}, config), {
    close,
    open: true
  });
  let timeoutId;
  let reactUnmount;
  function destroy(...args) {
    var _a;
    const triggerCancel = args.some(param => param === null || param === void 0 ? void 0 : param.triggerCancel);
    if (triggerCancel) {
      var _a2;
      (_a = config.onCancel) === null || _a === void 0 ? void 0 : (_a2 = _a).call.apply(_a2, [config, () => {}].concat((0, _toConsumableArray2.default)(args.slice(1))));
    }
    for (let i = 0; i < _destroyFns.default.length; i++) {
      const fn = _destroyFns.default[i];
      if (fn === close) {
        _destroyFns.default.splice(i, 1);
        break;
      }
    }
    reactUnmount();
  }
  function render(props) {
    clearTimeout(timeoutId);
    /**
     * https://github.com/ant-design/ant-design/issues/23623
     *
     * Sync render blocks React event. Let's make this async.
     */
    timeoutId = setTimeout(() => {
      const rootPrefixCls = global.getPrefixCls(undefined, getRootPrefixCls());
      const iconPrefixCls = global.getIconPrefixCls();
      const theme = global.getTheme();
      const dom = /*#__PURE__*/_react.default.createElement(ConfirmDialogWrapper, Object.assign({}, props));
      const reactRender = (0, _UnstableContext.unstableSetRender)();
      reactUnmount = reactRender(/*#__PURE__*/_react.default.createElement(_configProvider.default, {
        prefixCls: rootPrefixCls,
        iconPrefixCls: iconPrefixCls,
        theme: theme
      }, global.holderRender ? global.holderRender(dom) : dom), container);
    });
  }
  function close(...args) {
    currentConfig = Object.assign(Object.assign({}, currentConfig), {
      open: false,
      afterClose: () => {
        if (typeof config.afterClose === 'function') {
          config.afterClose();
        }
        // @ts-ignore
        destroy.apply(this, args);
      }
    });
    // Legacy support
    if (currentConfig.visible) {
      delete currentConfig.visible;
    }
    render(currentConfig);
  }
  function update(configUpdate) {
    if (typeof configUpdate === 'function') {
      currentConfig = configUpdate(currentConfig);
    } else {
      currentConfig = Object.assign(Object.assign({}, currentConfig), configUpdate);
    }
    render(currentConfig);
  }
  render(currentConfig);
  _destroyFns.default.push(close);
  return {
    destroy: close,
    update
  };
}
function withWarn(props) {
  return Object.assign(Object.assign({}, props), {
    type: 'warning'
  });
}
function withInfo(props) {
  return Object.assign(Object.assign({}, props), {
    type: 'info'
  });
}
function withSuccess(props) {
  return Object.assign(Object.assign({}, props), {
    type: 'success'
  });
}
function withError(props) {
  return Object.assign(Object.assign({}, props), {
    type: 'error'
  });
}
function withConfirm(props) {
  return Object.assign(Object.assign({}, props), {
    type: 'confirm'
  });
}
function modalGlobalConfig({
  rootPrefixCls
}) {
  process.env.NODE_ENV !== "production" ? (0, _warning.default)(false, 'Modal', 'Modal.config is deprecated. Please use ConfigProvider.config instead.') : void 0;
  defaultRootPrefixCls = rootPrefixCls;
}