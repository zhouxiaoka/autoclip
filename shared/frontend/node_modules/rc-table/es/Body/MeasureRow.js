import * as React from 'react';
import ResizeObserver from 'rc-resize-observer';
import MeasureCell from "./MeasureCell";
import isVisible from "rc-util/es/Dom/isVisible";
export default function MeasureRow(_ref) {
  var prefixCls = _ref.prefixCls,
    columnsKey = _ref.columnsKey,
    onColumnResize = _ref.onColumnResize;
  var ref = React.useRef(null);
  return /*#__PURE__*/React.createElement("tr", {
    "aria-hidden": "true",
    className: "".concat(prefixCls, "-measure-row"),
    style: {
      height: 0,
      fontSize: 0
    },
    ref: ref
  }, /*#__PURE__*/React.createElement(ResizeObserver.Collection, {
    onBatchResize: function onBatchResize(infoList) {
      if (isVisible(ref.current)) {
        infoList.forEach(function (_ref2) {
          var columnKey = _ref2.data,
            size = _ref2.size;
          onColumnResize(columnKey, size.offsetWidth);
        });
      }
    }
  }, columnsKey.map(function (columnKey) {
    return /*#__PURE__*/React.createElement(MeasureCell, {
      key: columnKey,
      columnKey: columnKey,
      onColumnResize: onColumnResize
    });
  })));
}