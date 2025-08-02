"use strict";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
var _interopRequireWildcard = require("@babel/runtime/helpers/interopRequireWildcard").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var React = _interopRequireWildcard(require("react"));
var _classnames = _interopRequireDefault(require("classnames"));
var _useMergeSemantic = _interopRequireDefault(require("../../_util/hooks/useMergeSemantic"));
var _context = require("../../config-provider/context");
const useMergedPickerSemantic = (pickerType, classNames, styles, popupClassName, popupStyle) => {
  const {
    classNames: contextClassNames,
    styles: contextStyles
  } = (0, _context.useComponentConfig)(pickerType);
  const [mergedClassNames, mergedStyles] = (0, _useMergeSemantic.default)([contextClassNames, classNames], [contextStyles, styles], {
    popup: {
      _default: 'root'
    }
  });
  return React.useMemo(() => {
    var _a, _b;
    // ClassNames
    const filledClassNames = Object.assign(Object.assign({}, mergedClassNames), {
      popup: Object.assign(Object.assign({}, mergedClassNames.popup), {
        root: (0, _classnames.default)((_a = mergedClassNames.popup) === null || _a === void 0 ? void 0 : _a.root, popupClassName)
      })
    });
    // Styles
    const filledStyles = Object.assign(Object.assign({}, mergedStyles), {
      popup: Object.assign(Object.assign({}, mergedStyles.popup), {
        root: Object.assign(Object.assign({}, (_b = mergedStyles.popup) === null || _b === void 0 ? void 0 : _b.root), popupStyle)
      })
    });
    // Return
    return [filledClassNames, filledStyles];
  }, [mergedClassNames, mergedStyles, popupClassName, popupStyle]);
};
var _default = exports.default = useMergedPickerSemantic;