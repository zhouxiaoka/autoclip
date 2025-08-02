"use strict";
"use client";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
var _interopRequireWildcard = require("@babel/runtime/helpers/interopRequireWildcard").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var React = _interopRequireWildcard(require("react"));
var _classnames = _interopRequireDefault(require("classnames"));
var _rcUtil = require("rc-util");
var _useLayoutEffect = _interopRequireDefault(require("rc-util/lib/hooks/useLayoutEffect"));
var _col = _interopRequireDefault(require("../grid/col"));
var _context = require("./context");
var _ErrorList = _interopRequireDefault(require("./ErrorList"));
var _fallbackCmp = _interopRequireDefault(require("./style/fallbackCmp"));
var __rest = void 0 && (void 0).__rest || function (s, e) {
  var t = {};
  for (var p in s) if (Object.prototype.hasOwnProperty.call(s, p) && e.indexOf(p) < 0) t[p] = s[p];
  if (s != null && typeof Object.getOwnPropertySymbols === "function") for (var i = 0, p = Object.getOwnPropertySymbols(s); i < p.length; i++) {
    if (e.indexOf(p[i]) < 0 && Object.prototype.propertyIsEnumerable.call(s, p[i])) t[p[i]] = s[p[i]];
  }
  return t;
};
const GRID_MAX = 24;
const FormItemInput = props => {
  const {
    prefixCls,
    status,
    labelCol,
    wrapperCol,
    children,
    errors,
    warnings,
    _internalItemRender: formItemRender,
    extra,
    help,
    fieldId,
    marginBottom,
    onErrorVisibleChanged,
    label
  } = props;
  const baseClassName = `${prefixCls}-item`;
  const formContext = React.useContext(_context.FormContext);
  const mergedWrapperCol = React.useMemo(() => {
    let mergedWrapper = Object.assign({}, wrapperCol || formContext.wrapperCol || {});
    if (label === null && !labelCol && !wrapperCol && formContext.labelCol) {
      const list = [undefined, 'xs', 'sm', 'md', 'lg', 'xl', 'xxl'];
      list.forEach(size => {
        const _size = size ? [size] : [];
        const formLabel = (0, _rcUtil.get)(formContext.labelCol, _size);
        const formLabelObj = typeof formLabel === 'object' ? formLabel : {};
        const wrapper = (0, _rcUtil.get)(mergedWrapper, _size);
        const wrapperObj = typeof wrapper === 'object' ? wrapper : {};
        if ('span' in formLabelObj && !('offset' in wrapperObj) && formLabelObj.span < GRID_MAX) {
          mergedWrapper = (0, _rcUtil.set)(mergedWrapper, [].concat(_size, ['offset']), formLabelObj.span);
        }
      });
    }
    return mergedWrapper;
  }, [wrapperCol, formContext]);
  const className = (0, _classnames.default)(`${baseClassName}-control`, mergedWrapperCol.className);
  // Pass to sub FormItem should not with col info
  const subFormContext = React.useMemo(() => {
    const {
        labelCol,
        wrapperCol
      } = formContext,
      rest = __rest(formContext, ["labelCol", "wrapperCol"]);
    return rest;
  }, [formContext]);
  const extraRef = React.useRef(null);
  const [extraHeight, setExtraHeight] = React.useState(0);
  (0, _useLayoutEffect.default)(() => {
    if (extra && extraRef.current) {
      setExtraHeight(extraRef.current.clientHeight);
    } else {
      setExtraHeight(0);
    }
  }, [extra]);
  const inputDom = /*#__PURE__*/React.createElement("div", {
    className: `${baseClassName}-control-input`
  }, /*#__PURE__*/React.createElement("div", {
    className: `${baseClassName}-control-input-content`
  }, children));
  const formItemContext = React.useMemo(() => ({
    prefixCls,
    status
  }), [prefixCls, status]);
  const errorListDom = marginBottom !== null || errors.length || warnings.length ? (/*#__PURE__*/React.createElement(_context.FormItemPrefixContext.Provider, {
    value: formItemContext
  }, /*#__PURE__*/React.createElement(_ErrorList.default, {
    fieldId: fieldId,
    errors: errors,
    warnings: warnings,
    help: help,
    helpStatus: status,
    className: `${baseClassName}-explain-connected`,
    onVisibleChanged: onErrorVisibleChanged
  }))) : null;
  const extraProps = {};
  if (fieldId) {
    extraProps.id = `${fieldId}_extra`;
  }
  // If extra = 0, && will goes wrong
  // 0&&error -> 0
  const extraDom = extra ? (/*#__PURE__*/React.createElement("div", Object.assign({}, extraProps, {
    className: `${baseClassName}-extra`,
    ref: extraRef
  }), extra)) : null;
  const additionalDom = errorListDom || extraDom ? (/*#__PURE__*/React.createElement("div", {
    className: `${baseClassName}-additional`,
    style: marginBottom ? {
      minHeight: marginBottom + extraHeight
    } : {}
  }, errorListDom, extraDom)) : null;
  const dom = formItemRender && formItemRender.mark === 'pro_table_render' && formItemRender.render ? formItemRender.render(props, {
    input: inputDom,
    errorList: errorListDom,
    extra: extraDom
  }) : (/*#__PURE__*/React.createElement(React.Fragment, null, inputDom, additionalDom));
  return /*#__PURE__*/React.createElement(_context.FormContext.Provider, {
    value: subFormContext
  }, /*#__PURE__*/React.createElement(_col.default, Object.assign({}, mergedWrapperCol, {
    className: className
  }), dom), /*#__PURE__*/React.createElement(_fallbackCmp.default, {
    prefixCls: prefixCls
  }));
};
var _default = exports.default = FormItemInput;