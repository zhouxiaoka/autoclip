"use client";

var __rest = this && this.__rest || function (s, e) {
  var t = {};
  for (var p in s) if (Object.prototype.hasOwnProperty.call(s, p) && e.indexOf(p) < 0) t[p] = s[p];
  if (s != null && typeof Object.getOwnPropertySymbols === "function") for (var i = 0, p = Object.getOwnPropertySymbols(s); i < p.length; i++) {
    if (e.indexOf(p[i]) < 0 && Object.prototype.propertyIsEnumerable.call(s, p[i])) t[p[i]] = s[p[i]];
  }
  return t;
};
import * as React from 'react';
import DoubleLeftOutlined from "@ant-design/icons/es/icons/DoubleLeftOutlined";
import DoubleRightOutlined from "@ant-design/icons/es/icons/DoubleRightOutlined";
import LeftOutlined from "@ant-design/icons/es/icons/LeftOutlined";
import RightOutlined from "@ant-design/icons/es/icons/RightOutlined";
import classNames from 'classnames';
import RcPagination from 'rc-pagination';
import enUS from "rc-pagination/es/locale/en_US";
import { devUseWarning } from '../_util/warning';
import { useComponentConfig } from '../config-provider/context';
import useSize from '../config-provider/hooks/useSize';
import useBreakpoint from '../grid/hooks/useBreakpoint';
import { useLocale } from '../locale';
import Select from '../select';
import { useToken } from '../theme/internal';
import useStyle from './style';
import BorderedStyle from './style/bordered';
import useShowSizeChanger from './useShowSizeChanger';
const Pagination = props => {
  const {
      align,
      prefixCls: customizePrefixCls,
      selectPrefixCls: customizeSelectPrefixCls,
      className,
      rootClassName,
      style,
      size: customizeSize,
      locale: customLocale,
      responsive,
      showSizeChanger,
      selectComponentClass,
      pageSizeOptions
    } = props,
    restProps = __rest(props, ["align", "prefixCls", "selectPrefixCls", "className", "rootClassName", "style", "size", "locale", "responsive", "showSizeChanger", "selectComponentClass", "pageSizeOptions"]);
  const {
    xs
  } = useBreakpoint(responsive);
  const [, token] = useToken();
  const {
    getPrefixCls,
    direction,
    showSizeChanger: contextShowSizeChangerConfig,
    className: contextClassName,
    style: contextStyle
  } = useComponentConfig('pagination');
  const prefixCls = getPrefixCls('pagination', customizePrefixCls);
  // Style
  const [wrapCSSVar, hashId, cssVarCls] = useStyle(prefixCls);
  // ============================== Size ==============================
  const mergedSize = useSize(customizeSize);
  const isSmall = mergedSize === 'small' || !!(xs && !mergedSize && responsive);
  // ============================= Locale =============================
  const [contextLocale] = useLocale('Pagination', enUS);
  const locale = Object.assign(Object.assign({}, contextLocale), customLocale);
  // ========================== Size Changer ==========================
  // Merge the props showSizeChanger
  const [propShowSizeChanger, propSizeChangerSelectProps] = useShowSizeChanger(showSizeChanger);
  const [contextShowSizeChanger, contextSizeChangerSelectProps] = useShowSizeChanger(contextShowSizeChangerConfig);
  const mergedShowSizeChanger = propShowSizeChanger !== null && propShowSizeChanger !== void 0 ? propShowSizeChanger : contextShowSizeChanger;
  const mergedShowSizeChangerSelectProps = propSizeChangerSelectProps !== null && propSizeChangerSelectProps !== void 0 ? propSizeChangerSelectProps : contextSizeChangerSelectProps;
  const SizeChanger = selectComponentClass || Select;
  // Generate options
  const mergedPageSizeOptions = React.useMemo(() => {
    return pageSizeOptions ? pageSizeOptions.map(option => Number(option)) : undefined;
  }, [pageSizeOptions]);
  // Render size changer
  const sizeChangerRender = info => {
    var _a;
    const {
      disabled,
      size: pageSize,
      onSizeChange,
      'aria-label': ariaLabel,
      className: sizeChangerClassName,
      options
    } = info;
    const {
      className: propSizeChangerClassName,
      onChange: propSizeChangerOnChange
    } = mergedShowSizeChangerSelectProps || {};
    // Origin Select is using Select.Option,
    // So it make the option value must be string
    // Just for compatible
    const selectedValue = (_a = options.find(option => String(option.value) === String(pageSize))) === null || _a === void 0 ? void 0 : _a.value;
    return /*#__PURE__*/React.createElement(SizeChanger, Object.assign({
      disabled: disabled,
      showSearch: true,
      popupMatchSelectWidth: false,
      getPopupContainer: triggerNode => triggerNode.parentNode,
      "aria-label": ariaLabel,
      options: options
    }, mergedShowSizeChangerSelectProps, {
      value: selectedValue,
      onChange: (nextSize, option) => {
        onSizeChange === null || onSizeChange === void 0 ? void 0 : onSizeChange(nextSize);
        propSizeChangerOnChange === null || propSizeChangerOnChange === void 0 ? void 0 : propSizeChangerOnChange(nextSize, option);
      },
      size: isSmall ? 'small' : 'middle',
      className: classNames(sizeChangerClassName, propSizeChangerClassName)
    }));
  };
  if (process.env.NODE_ENV !== 'production') {
    const warning = devUseWarning('Pagination');
    process.env.NODE_ENV !== "production" ? warning(!selectComponentClass, 'usage', '`selectComponentClass` is not official api which will be removed.') : void 0;
  }
  // ============================= Render =============================
  const iconsProps = React.useMemo(() => {
    const ellipsis = /*#__PURE__*/React.createElement("span", {
      className: `${prefixCls}-item-ellipsis`
    }, "\u2022\u2022\u2022");
    const prevIcon = /*#__PURE__*/React.createElement("button", {
      className: `${prefixCls}-item-link`,
      type: "button",
      tabIndex: -1
    }, direction === 'rtl' ? /*#__PURE__*/React.createElement(RightOutlined, null) : /*#__PURE__*/React.createElement(LeftOutlined, null));
    const nextIcon = /*#__PURE__*/React.createElement("button", {
      className: `${prefixCls}-item-link`,
      type: "button",
      tabIndex: -1
    }, direction === 'rtl' ? /*#__PURE__*/React.createElement(LeftOutlined, null) : /*#__PURE__*/React.createElement(RightOutlined, null));
    const jumpPrevIcon =
    /*#__PURE__*/
    // biome-ignore lint/a11y/useValidAnchor: it is hard to refactor
    React.createElement("a", {
      className: `${prefixCls}-item-link`
    }, /*#__PURE__*/React.createElement("div", {
      className: `${prefixCls}-item-container`
    }, direction === 'rtl' ? (/*#__PURE__*/React.createElement(DoubleRightOutlined, {
      className: `${prefixCls}-item-link-icon`
    })) : (/*#__PURE__*/React.createElement(DoubleLeftOutlined, {
      className: `${prefixCls}-item-link-icon`
    })), ellipsis));
    const jumpNextIcon =
    /*#__PURE__*/
    // biome-ignore lint/a11y/useValidAnchor: it is hard to refactor
    React.createElement("a", {
      className: `${prefixCls}-item-link`
    }, /*#__PURE__*/React.createElement("div", {
      className: `${prefixCls}-item-container`
    }, direction === 'rtl' ? (/*#__PURE__*/React.createElement(DoubleLeftOutlined, {
      className: `${prefixCls}-item-link-icon`
    })) : (/*#__PURE__*/React.createElement(DoubleRightOutlined, {
      className: `${prefixCls}-item-link-icon`
    })), ellipsis));
    return {
      prevIcon,
      nextIcon,
      jumpPrevIcon,
      jumpNextIcon
    };
  }, [direction, prefixCls]);
  const selectPrefixCls = getPrefixCls('select', customizeSelectPrefixCls);
  const extendedClassName = classNames({
    [`${prefixCls}-${align}`]: !!align,
    [`${prefixCls}-mini`]: isSmall,
    [`${prefixCls}-rtl`]: direction === 'rtl',
    [`${prefixCls}-bordered`]: token.wireframe
  }, contextClassName, className, rootClassName, hashId, cssVarCls);
  const mergedStyle = Object.assign(Object.assign({}, contextStyle), style);
  return wrapCSSVar(/*#__PURE__*/React.createElement(React.Fragment, null, token.wireframe && /*#__PURE__*/React.createElement(BorderedStyle, {
    prefixCls: prefixCls
  }), /*#__PURE__*/React.createElement(RcPagination, Object.assign({}, iconsProps, restProps, {
    style: mergedStyle,
    prefixCls: prefixCls,
    selectPrefixCls: selectPrefixCls,
    className: extendedClassName,
    locale: locale,
    pageSizeOptions: mergedPageSizeOptions,
    showSizeChanger: mergedShowSizeChanger,
    sizeChangerRender: sizeChangerRender
  }))));
};
if (process.env.NODE_ENV !== 'production') {
  Pagination.displayName = 'Pagination';
}
export default Pagination;