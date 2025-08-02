"use strict";
"use client";

var _interopRequireWildcard = require("@babel/runtime/helpers/interopRequireWildcard").default;
var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = EllipsisMeasure;
var _toConsumableArray2 = _interopRequireDefault(require("@babel/runtime/helpers/toConsumableArray"));
var React = _interopRequireWildcard(require("react"));
var _toArray = _interopRequireDefault(require("rc-util/lib/Children/toArray"));
var _useLayoutEffect = _interopRequireDefault(require("rc-util/lib/hooks/useLayoutEffect"));
var _util = require("./util");
const MeasureText = /*#__PURE__*/React.forwardRef(({
  style,
  children
}, ref) => {
  const spanRef = React.useRef(null);
  React.useImperativeHandle(ref, () => ({
    isExceed: () => {
      const span = spanRef.current;
      return span.scrollHeight > span.clientHeight;
    },
    getHeight: () => spanRef.current.clientHeight
  }));
  return /*#__PURE__*/React.createElement("span", {
    "aria-hidden": true,
    ref: spanRef,
    style: Object.assign({
      position: 'fixed',
      display: 'block',
      left: 0,
      top: 0,
      pointerEvents: 'none',
      backgroundColor: 'rgba(255, 0, 0, 0.65)'
    }, style)
  }, children);
});
const getNodesLen = nodeList => nodeList.reduce((totalLen, node) => totalLen + ((0, _util.isValidText)(node) ? String(node).length : 1), 0);
function sliceNodes(nodeList, len) {
  let currLen = 0;
  const currentNodeList = [];
  for (let i = 0; i < nodeList.length; i += 1) {
    // Match to return
    if (currLen === len) {
      return currentNodeList;
    }
    const node = nodeList[i];
    const canCut = (0, _util.isValidText)(node);
    const nodeLen = canCut ? String(node).length : 1;
    const nextLen = currLen + nodeLen;
    // Exceed but current not which means we need cut this
    // This will not happen on validate ReactElement
    if (nextLen > len) {
      const restLen = len - currLen;
      currentNodeList.push(String(node).slice(0, restLen));
      return currentNodeList;
    }
    currentNodeList.push(node);
    currLen = nextLen;
  }
  return nodeList;
}
// Measure for the `text` is exceed the `rows` or not
const STATUS_MEASURE_NONE = 0;
const STATUS_MEASURE_PREPARE = 1;
const STATUS_MEASURE_START = 2;
const STATUS_MEASURE_NEED_ELLIPSIS = 3;
const STATUS_MEASURE_NO_NEED_ELLIPSIS = 4;
const lineClipStyle = {
  display: '-webkit-box',
  overflow: 'hidden',
  WebkitBoxOrient: 'vertical'
};
function EllipsisMeasure(props) {
  const {
    enableMeasure,
    width,
    text,
    children,
    rows,
    expanded,
    miscDeps,
    onEllipsis
  } = props;
  const nodeList = React.useMemo(() => (0, _toArray.default)(text), [text]);
  const nodeLen = React.useMemo(() => getNodesLen(nodeList), [text]);
  // ========================= Full Content =========================
  // Used for measure only, which means it's always render as no need ellipsis
  const fullContent = React.useMemo(() => children(nodeList, false), [text]);
  // ========================= Cut Content ==========================
  const [ellipsisCutIndex, setEllipsisCutIndex] = React.useState(null);
  const cutMidRef = React.useRef(null);
  // ========================= NeedEllipsis =========================
  const measureWhiteSpaceRef = React.useRef(null);
  const needEllipsisRef = React.useRef(null);
  // Measure for `rows-1` height, to avoid operation exceed the line height
  const descRowsEllipsisRef = React.useRef(null);
  const symbolRowEllipsisRef = React.useRef(null);
  const [canEllipsis, setCanEllipsis] = React.useState(false);
  const [needEllipsis, setNeedEllipsis] = React.useState(STATUS_MEASURE_NONE);
  const [ellipsisHeight, setEllipsisHeight] = React.useState(0);
  const [parentWhiteSpace, setParentWhiteSpace] = React.useState(null);
  // Trigger start measure
  (0, _useLayoutEffect.default)(() => {
    if (enableMeasure && width && nodeLen) {
      setNeedEllipsis(STATUS_MEASURE_PREPARE);
    } else {
      setNeedEllipsis(STATUS_MEASURE_NONE);
    }
  }, [width, text, rows, enableMeasure, nodeList]);
  // Measure process
  (0, _useLayoutEffect.default)(() => {
    var _a, _b, _c, _d;
    if (needEllipsis === STATUS_MEASURE_PREPARE) {
      setNeedEllipsis(STATUS_MEASURE_START);
      // Parent ref `white-space`
      const nextWhiteSpace = measureWhiteSpaceRef.current && getComputedStyle(measureWhiteSpaceRef.current).whiteSpace;
      setParentWhiteSpace(nextWhiteSpace);
    } else if (needEllipsis === STATUS_MEASURE_START) {
      const isOverflow = !!((_a = needEllipsisRef.current) === null || _a === void 0 ? void 0 : _a.isExceed());
      setNeedEllipsis(isOverflow ? STATUS_MEASURE_NEED_ELLIPSIS : STATUS_MEASURE_NO_NEED_ELLIPSIS);
      setEllipsisCutIndex(isOverflow ? [0, nodeLen] : null);
      setCanEllipsis(isOverflow);
      // Get the basic height of ellipsis rows
      const baseRowsEllipsisHeight = ((_b = needEllipsisRef.current) === null || _b === void 0 ? void 0 : _b.getHeight()) || 0;
      // Get the height of `rows - 1` + symbol height
      const descRowsEllipsisHeight = rows === 1 ? 0 : ((_c = descRowsEllipsisRef.current) === null || _c === void 0 ? void 0 : _c.getHeight()) || 0;
      const symbolRowEllipsisHeight = ((_d = symbolRowEllipsisRef.current) === null || _d === void 0 ? void 0 : _d.getHeight()) || 0;
      const maxRowsHeight = Math.max(baseRowsEllipsisHeight,
      // height of rows with ellipsis
      descRowsEllipsisHeight + symbolRowEllipsisHeight);
      setEllipsisHeight(maxRowsHeight + 1);
      onEllipsis(isOverflow);
    }
  }, [needEllipsis]);
  // ========================= Cut Measure ==========================
  const cutMidIndex = ellipsisCutIndex ? Math.ceil((ellipsisCutIndex[0] + ellipsisCutIndex[1]) / 2) : 0;
  (0, _useLayoutEffect.default)(() => {
    var _a;
    const [minIndex, maxIndex] = ellipsisCutIndex || [0, 0];
    if (minIndex !== maxIndex) {
      const midHeight = ((_a = cutMidRef.current) === null || _a === void 0 ? void 0 : _a.getHeight()) || 0;
      const isOverflow = midHeight > ellipsisHeight;
      let targetMidIndex = cutMidIndex;
      if (maxIndex - minIndex === 1) {
        targetMidIndex = isOverflow ? minIndex : maxIndex;
      }
      setEllipsisCutIndex(isOverflow ? [minIndex, targetMidIndex] : [targetMidIndex, maxIndex]);
    }
  }, [ellipsisCutIndex, cutMidIndex]);
  // ========================= Text Content =========================
  const finalContent = React.useMemo(() => {
    // Skip everything if `enableMeasure` is disabled
    if (!enableMeasure) {
      return children(nodeList, false);
    }
    if (needEllipsis !== STATUS_MEASURE_NEED_ELLIPSIS || !ellipsisCutIndex || ellipsisCutIndex[0] !== ellipsisCutIndex[1]) {
      const content = children(nodeList, false);
      // Limit the max line count to avoid scrollbar blink unless no need ellipsis
      // https://github.com/ant-design/ant-design/issues/42958
      if ([STATUS_MEASURE_NO_NEED_ELLIPSIS, STATUS_MEASURE_NONE].includes(needEllipsis)) {
        return content;
      }
      return /*#__PURE__*/React.createElement("span", {
        style: Object.assign(Object.assign({}, lineClipStyle), {
          WebkitLineClamp: rows
        })
      }, content);
    }
    return children(expanded ? nodeList : sliceNodes(nodeList, ellipsisCutIndex[0]), canEllipsis);
  }, [expanded, needEllipsis, ellipsisCutIndex, nodeList].concat((0, _toConsumableArray2.default)(miscDeps)));
  // ============================ Render ============================
  const measureStyle = {
    width,
    margin: 0,
    padding: 0,
    whiteSpace: parentWhiteSpace === 'nowrap' ? 'normal' : 'inherit'
  };
  return /*#__PURE__*/React.createElement(React.Fragment, null, finalContent, needEllipsis === STATUS_MEASURE_START && (/*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(MeasureText, {
    style: Object.assign(Object.assign(Object.assign({}, measureStyle), lineClipStyle), {
      WebkitLineClamp: rows
    }),
    ref: needEllipsisRef
  }, fullContent), /*#__PURE__*/React.createElement(MeasureText, {
    style: Object.assign(Object.assign(Object.assign({}, measureStyle), lineClipStyle), {
      WebkitLineClamp: rows - 1
    }),
    ref: descRowsEllipsisRef
  }, fullContent), /*#__PURE__*/React.createElement(MeasureText, {
    style: Object.assign(Object.assign(Object.assign({}, measureStyle), lineClipStyle), {
      WebkitLineClamp: 1
    }),
    ref: symbolRowEllipsisRef
  }, children([], true)))), needEllipsis === STATUS_MEASURE_NEED_ELLIPSIS && ellipsisCutIndex && ellipsisCutIndex[0] !== ellipsisCutIndex[1] && (/*#__PURE__*/React.createElement(MeasureText, {
    style: Object.assign(Object.assign({}, measureStyle), {
      top: 400
    }),
    ref: cutMidRef
  }, children(sliceNodes(nodeList, cutMidIndex), true))), needEllipsis === STATUS_MEASURE_PREPARE && (/*#__PURE__*/React.createElement("span", {
    style: {
      whiteSpace: 'inherit'
    },
    ref: measureWhiteSpaceRef
  })));
}