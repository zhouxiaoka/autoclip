"use client";

import _toConsumableArray from "@babel/runtime/helpers/esm/toConsumableArray";
import * as React from 'react';
import classNames from 'classnames';
import CSSMotion, { CSSMotionList } from 'rc-motion';
import initCollapseMotion from '../_util/motion';
import useCSSVarCls from '../config-provider/hooks/useCSSVarCls';
import { FormItemPrefixContext } from './context';
import useDebounce from './hooks/useDebounce';
import useStyle from './style';
const EMPTY_LIST = [];
function toErrorEntity(error, prefix, errorStatus, index = 0) {
  return {
    key: typeof error === 'string' ? error : `${prefix}-${index}`,
    error,
    errorStatus
  };
}
const ErrorList = ({
  help,
  helpStatus,
  errors = EMPTY_LIST,
  warnings = EMPTY_LIST,
  className: rootClassName,
  fieldId,
  onVisibleChanged
}) => {
  const {
    prefixCls
  } = React.useContext(FormItemPrefixContext);
  const baseClassName = `${prefixCls}-item-explain`;
  const rootCls = useCSSVarCls(prefixCls);
  const [wrapCSSVar, hashId, cssVarCls] = useStyle(prefixCls, rootCls);
  const collapseMotion = React.useMemo(() => initCollapseMotion(prefixCls), [prefixCls]);
  // We have to debounce here again since somewhere use ErrorList directly still need no shaking
  // ref: https://github.com/ant-design/ant-design/issues/36336
  const debounceErrors = useDebounce(errors);
  const debounceWarnings = useDebounce(warnings);
  const fullKeyList = React.useMemo(() => {
    if (help !== undefined && help !== null) {
      return [toErrorEntity(help, 'help', helpStatus)];
    }
    return [].concat(_toConsumableArray(debounceErrors.map((error, index) => toErrorEntity(error, 'error', 'error', index))), _toConsumableArray(debounceWarnings.map((warning, index) => toErrorEntity(warning, 'warning', 'warning', index))));
  }, [help, helpStatus, debounceErrors, debounceWarnings]);
  const filledKeyFullKeyList = React.useMemo(() => {
    const keysCount = {};
    fullKeyList.forEach(({
      key
    }) => {
      keysCount[key] = (keysCount[key] || 0) + 1;
    });
    return fullKeyList.map((entity, index) => Object.assign(Object.assign({}, entity), {
      key: keysCount[entity.key] > 1 ? `${entity.key}-fallback-${index}` : entity.key
    }));
  }, [fullKeyList]);
  const helpProps = {};
  if (fieldId) {
    helpProps.id = `${fieldId}_help`;
  }
  return wrapCSSVar(/*#__PURE__*/React.createElement(CSSMotion, {
    motionDeadline: collapseMotion.motionDeadline,
    motionName: `${prefixCls}-show-help`,
    visible: !!filledKeyFullKeyList.length,
    onVisibleChanged: onVisibleChanged
  }, holderProps => {
    const {
      className: holderClassName,
      style: holderStyle
    } = holderProps;
    return /*#__PURE__*/React.createElement("div", Object.assign({}, helpProps, {
      className: classNames(baseClassName, holderClassName, cssVarCls, rootCls, rootClassName, hashId),
      style: holderStyle
    }), /*#__PURE__*/React.createElement(CSSMotionList, Object.assign({
      keys: filledKeyFullKeyList
    }, initCollapseMotion(prefixCls), {
      motionName: `${prefixCls}-show-help-item`,
      component: false
    }), itemProps => {
      const {
        key,
        error,
        errorStatus,
        className: itemClassName,
        style: itemStyle
      } = itemProps;
      return /*#__PURE__*/React.createElement("div", {
        key: key,
        className: classNames(itemClassName, {
          [`${baseClassName}-${errorStatus}`]: errorStatus
        }),
        style: itemStyle
      }, error);
    }));
  }));
};
export default ErrorList;