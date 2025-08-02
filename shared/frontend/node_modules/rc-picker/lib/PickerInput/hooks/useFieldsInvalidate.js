"use strict";

var _interopRequireWildcard = require("@babel/runtime/helpers/interopRequireWildcard").default;
var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = useFieldsInvalidate;
var _slicedToArray2 = _interopRequireDefault(require("@babel/runtime/helpers/slicedToArray"));
var _miscUtil = require("../../utils/miscUtil");
var React = _interopRequireWildcard(require("react"));
/**
 * Used to control each fields invalidate status
 */
function useFieldsInvalidate(calendarValue, isInvalidateDate) {
  var allowEmpty = arguments.length > 2 && arguments[2] !== undefined ? arguments[2] : [];
  var _React$useState = React.useState([false, false]),
    _React$useState2 = (0, _slicedToArray2.default)(_React$useState, 2),
    fieldsInvalidates = _React$useState2[0],
    setFieldsInvalidates = _React$useState2[1];
  var onSelectorInvalid = function onSelectorInvalid(invalid, index) {
    setFieldsInvalidates(function (ori) {
      return (0, _miscUtil.fillIndex)(ori, index, invalid);
    });
  };

  /**
   * For the Selector Input to mark as `aria-disabled`
   */
  var submitInvalidates = React.useMemo(function () {
    return fieldsInvalidates.map(function (invalid, index) {
      // If typing invalidate
      if (invalid) {
        return true;
      }
      var current = calendarValue[index];

      // Not check if all empty
      if (!current) {
        return false;
      }

      // Not allow empty
      if (!allowEmpty[index] && !current) {
        return true;
      }

      // Invalidate
      if (current && isInvalidateDate(current, {
        activeIndex: index
      })) {
        return true;
      }
      return false;
    });
  }, [calendarValue, fieldsInvalidates, isInvalidateDate, allowEmpty]);
  return [submitInvalidates, onSelectorInvalid];
}