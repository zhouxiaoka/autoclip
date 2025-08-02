"use strict";
"use client";

/* eslint-disable react/no-array-index-key */
var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
var _interopRequireWildcard = require("@babel/runtime/helpers/interopRequireWildcard").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var _react = _interopRequireWildcard(require("react"));
var _classnames = _interopRequireDefault(require("classnames"));
var _rcResizeObserver = _interopRequireDefault(require("rc-resize-observer"));
var _useEvent = _interopRequireDefault(require("rc-util/lib/hooks/useEvent"));
var _warning = require("../_util/warning");
var _context = require("../config-provider/context");
var _useCSSVarCls = _interopRequireDefault(require("../config-provider/hooks/useCSSVarCls"));
var _useItems = _interopRequireDefault(require("./hooks/useItems"));
var _useResizable = _interopRequireDefault(require("./hooks/useResizable"));
var _useResize = _interopRequireDefault(require("./hooks/useResize"));
var _useSizes = _interopRequireDefault(require("./hooks/useSizes"));
var _Panel = require("./Panel");
var _SplitBar = _interopRequireDefault(require("./SplitBar"));
var _style = _interopRequireDefault(require("./style"));
const Splitter = props => {
  const {
    prefixCls: customizePrefixCls,
    className,
    style,
    layout = 'horizontal',
    children,
    rootClassName,
    onResizeStart,
    onResize,
    onResizeEnd,
    lazy
  } = props;
  const {
    getPrefixCls,
    direction,
    className: contextClassName,
    style: contextStyle
  } = (0, _context.useComponentConfig)('splitter');
  const prefixCls = getPrefixCls('splitter', customizePrefixCls);
  const rootCls = (0, _useCSSVarCls.default)(prefixCls);
  const [wrapCSSVar, hashId, cssVarCls] = (0, _style.default)(prefixCls, rootCls);
  // ======================== Direct ========================
  const isVertical = layout === 'vertical';
  const isRTL = direction === 'rtl';
  const reverse = !isVertical && isRTL;
  // ====================== Items Data ======================
  const items = (0, _useItems.default)(children);
  // >>> Warning for uncontrolled
  if (process.env.NODE_ENV !== 'production') {
    const warning = (0, _warning.devUseWarning)('Splitter');
    let existSize = false;
    let existUndefinedSize = false;
    items.forEach(item => {
      if (item.size !== undefined) {
        existSize = true;
      } else {
        existUndefinedSize = true;
      }
    });
    if (existSize && existUndefinedSize && !onResize) {
      process.env.NODE_ENV !== "production" ? warning(false, 'usage', 'When part of `Splitter.Panel` has `size`, `onResize` is required or change `size` to `defaultSize`.') : void 0;
    }
  }
  // ====================== Container =======================
  const [containerSize, setContainerSize] = (0, _react.useState)();
  const onContainerResize = size => {
    const {
      offsetWidth,
      offsetHeight
    } = size;
    const containerSize = isVertical ? offsetHeight : offsetWidth;
    // Skip when container has no size, Such as nested in a hidden tab panel
    // to fix: https://github.com/ant-design/ant-design/issues/51106
    if (containerSize === 0) {
      return;
    }
    setContainerSize(containerSize);
  };
  // ========================= Size =========================
  const [panelSizes, itemPxSizes, itemPtgSizes, itemPtgMinSizes, itemPtgMaxSizes, updateSizes] = (0, _useSizes.default)(items, containerSize);
  // ====================== Resizable =======================
  const resizableInfos = (0, _useResizable.default)(items, itemPxSizes, isRTL);
  const [onOffsetStart, onOffsetUpdate, onOffsetEnd, onCollapse, movingIndex] = (0, _useResize.default)(items, resizableInfos, itemPtgSizes, containerSize, updateSizes, isRTL);
  // ======================== Events ========================
  const onInternalResizeStart = (0, _useEvent.default)(index => {
    onOffsetStart(index);
    onResizeStart === null || onResizeStart === void 0 ? void 0 : onResizeStart(itemPxSizes);
  });
  const onInternalResizeUpdate = (0, _useEvent.default)((index, offset, lazyEnd) => {
    const nextSizes = onOffsetUpdate(index, offset);
    if (lazyEnd) {
      onResizeEnd === null || onResizeEnd === void 0 ? void 0 : onResizeEnd(nextSizes);
    } else {
      onResize === null || onResize === void 0 ? void 0 : onResize(nextSizes);
    }
  });
  const onInternalResizeEnd = (0, _useEvent.default)(lazyEnd => {
    onOffsetEnd();
    if (!lazyEnd) {
      onResizeEnd === null || onResizeEnd === void 0 ? void 0 : onResizeEnd(itemPxSizes);
    }
  });
  const onInternalCollapse = (0, _useEvent.default)((index, type) => {
    const nextSizes = onCollapse(index, type);
    onResize === null || onResize === void 0 ? void 0 : onResize(nextSizes);
    onResizeEnd === null || onResizeEnd === void 0 ? void 0 : onResizeEnd(nextSizes);
  });
  // ======================== Styles ========================
  const containerClassName = (0, _classnames.default)(prefixCls, className, `${prefixCls}-${layout}`, {
    [`${prefixCls}-rtl`]: isRTL
  }, rootClassName, contextClassName, cssVarCls, rootCls, hashId);
  // ======================== Render ========================
  const maskCls = `${prefixCls}-mask`;
  const stackSizes = _react.default.useMemo(() => {
    const mergedSizes = [];
    let stack = 0;
    for (let i = 0; i < items.length; i += 1) {
      stack += itemPtgSizes[i];
      mergedSizes.push(stack);
    }
    return mergedSizes;
  }, [itemPtgSizes]);
  const mergedStyle = Object.assign(Object.assign({}, contextStyle), style);
  return wrapCSSVar(/*#__PURE__*/_react.default.createElement(_rcResizeObserver.default, {
    onResize: onContainerResize
  }, /*#__PURE__*/_react.default.createElement("div", {
    style: mergedStyle,
    className: containerClassName
  }, items.map((item, idx) => {
    // Panel
    const panel = /*#__PURE__*/_react.default.createElement(_Panel.InternalPanel, Object.assign({}, item, {
      prefixCls: prefixCls,
      size: panelSizes[idx]
    }));
    // Split Bar
    let splitBar = null;
    const resizableInfo = resizableInfos[idx];
    if (resizableInfo) {
      const ariaMinStart = (stackSizes[idx - 1] || 0) + itemPtgMinSizes[idx];
      const ariaMinEnd = (stackSizes[idx + 1] || 100) - itemPtgMaxSizes[idx + 1];
      const ariaMaxStart = (stackSizes[idx - 1] || 0) + itemPtgMaxSizes[idx];
      const ariaMaxEnd = (stackSizes[idx + 1] || 100) - itemPtgMinSizes[idx + 1];
      splitBar = /*#__PURE__*/_react.default.createElement(_SplitBar.default, {
        lazy: lazy,
        index: idx,
        active: movingIndex === idx,
        prefixCls: prefixCls,
        vertical: isVertical,
        resizable: resizableInfo.resizable,
        ariaNow: stackSizes[idx] * 100,
        ariaMin: Math.max(ariaMinStart, ariaMinEnd) * 100,
        ariaMax: Math.min(ariaMaxStart, ariaMaxEnd) * 100,
        startCollapsible: resizableInfo.startCollapsible,
        endCollapsible: resizableInfo.endCollapsible,
        onOffsetStart: onInternalResizeStart,
        onOffsetUpdate: (index, offsetX, offsetY, lazyEnd) => {
          let offset = isVertical ? offsetY : offsetX;
          if (reverse) {
            offset = -offset;
          }
          onInternalResizeUpdate(index, offset, lazyEnd);
        },
        onOffsetEnd: onInternalResizeEnd,
        onCollapse: onInternalCollapse,
        containerSize: containerSize || 0
      });
    }
    return /*#__PURE__*/_react.default.createElement(_react.default.Fragment, {
      key: `split-panel-${idx}`
    }, panel, splitBar);
  }), typeof movingIndex === 'number' && (/*#__PURE__*/_react.default.createElement("div", {
    "aria-hidden": true,
    className: (0, _classnames.default)(maskCls, `${maskCls}-${layout}`)
  })))));
};
if (process.env.NODE_ENV !== 'production') {
  Splitter.displayName = 'Splitter';
}
var _default = exports.default = Splitter;