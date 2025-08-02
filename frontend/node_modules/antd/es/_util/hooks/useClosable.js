"use client";

import React from 'react';
import CloseOutlined from "@ant-design/icons/es/icons/CloseOutlined";
import pickAttrs from "rc-util/es/pickAttrs";
import { useLocale } from '../../locale';
import defaultLocale from '../../locale/en_US';
import extendsObject from '../extendsObject';
export function pickClosable(context) {
  if (!context) {
    return undefined;
  }
  return {
    closable: context.closable,
    closeIcon: context.closeIcon
  };
}
/** Convert `closable` and `closeIcon` to config object */
function useClosableConfig(closableCollection) {
  const {
    closable,
    closeIcon
  } = closableCollection || {};
  return React.useMemo(() => {
    if (
    // If `closable`, whatever rest be should be true
    !closable && (closable === false || closeIcon === false || closeIcon === null)) {
      return false;
    }
    if (closable === undefined && closeIcon === undefined) {
      return null;
    }
    let closableConfig = {
      closeIcon: typeof closeIcon !== 'boolean' && closeIcon !== null ? closeIcon : undefined
    };
    if (closable && typeof closable === 'object') {
      closableConfig = Object.assign(Object.assign({}, closableConfig), closable);
    }
    return closableConfig;
  }, [closable, closeIcon]);
}
/** Use same object to support `useMemo` optimization */
const EmptyFallbackCloseCollection = {};
export default function useClosable(propCloseCollection, contextCloseCollection, fallbackCloseCollection = EmptyFallbackCloseCollection) {
  // Align the `props`, `context` `fallback` to config object first
  const propCloseConfig = useClosableConfig(propCloseCollection);
  const contextCloseConfig = useClosableConfig(contextCloseCollection);
  const [contextLocale] = useLocale('global', defaultLocale.global);
  const closeBtnIsDisabled = typeof propCloseConfig !== 'boolean' ? !!(propCloseConfig === null || propCloseConfig === void 0 ? void 0 : propCloseConfig.disabled) : false;
  const mergedFallbackCloseCollection = React.useMemo(() => Object.assign({
    closeIcon: /*#__PURE__*/React.createElement(CloseOutlined, null)
  }, fallbackCloseCollection), [fallbackCloseCollection]);
  // Use fallback logic to fill the config
  const mergedClosableConfig = React.useMemo(() => {
    // ================ Props First ================
    // Skip if prop is disabled
    if (propCloseConfig === false) {
      return false;
    }
    if (propCloseConfig) {
      return extendsObject(mergedFallbackCloseCollection, contextCloseConfig, propCloseConfig);
    }
    // =============== Context Second ==============
    // Skip if context is disabled
    if (contextCloseConfig === false) {
      return false;
    }
    if (contextCloseConfig) {
      return extendsObject(mergedFallbackCloseCollection, contextCloseConfig);
    }
    // ============= Fallback Default ==============
    return !mergedFallbackCloseCollection.closable ? false : mergedFallbackCloseCollection;
  }, [propCloseConfig, contextCloseConfig, mergedFallbackCloseCollection]);
  // Calculate the final closeIcon
  return React.useMemo(() => {
    if (mergedClosableConfig === false) {
      return [false, null, closeBtnIsDisabled, {}];
    }
    const {
      closeIconRender
    } = mergedFallbackCloseCollection;
    const {
      closeIcon
    } = mergedClosableConfig;
    let mergedCloseIcon = closeIcon;
    // Wrap the closeIcon with aria props
    const ariaOrDataProps = pickAttrs(mergedClosableConfig, true);
    if (mergedCloseIcon !== null && mergedCloseIcon !== undefined) {
      // Wrap the closeIcon if needed
      if (closeIconRender) {
        mergedCloseIcon = closeIconRender(closeIcon);
      }
      mergedCloseIcon = /*#__PURE__*/React.isValidElement(mergedCloseIcon) ? (/*#__PURE__*/React.cloneElement(mergedCloseIcon, Object.assign({
        'aria-label': contextLocale.close
      }, ariaOrDataProps))) : (/*#__PURE__*/React.createElement("span", Object.assign({
        "aria-label": contextLocale.close
      }, ariaOrDataProps), mergedCloseIcon));
    }
    return [true, mergedCloseIcon, closeBtnIsDisabled, ariaOrDataProps];
  }, [mergedClosableConfig, mergedFallbackCloseCollection]);
}