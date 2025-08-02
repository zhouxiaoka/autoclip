"use strict";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
var _interopRequireWildcard = require("@babel/runtime/helpers/interopRequireWildcard").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = useForm;
var React = _interopRequireWildcard(require("react"));
var _rcFieldForm = require("rc-field-form");
var _findDOMNode = require("rc-util/lib/Dom/findDOMNode");
var _scrollIntoViewIfNeeded = _interopRequireDefault(require("scroll-into-view-if-needed"));
var _util = require("../util");
var __rest = void 0 && (void 0).__rest || function (s, e) {
  var t = {};
  for (var p in s) if (Object.prototype.hasOwnProperty.call(s, p) && e.indexOf(p) < 0) t[p] = s[p];
  if (s != null && typeof Object.getOwnPropertySymbols === "function") for (var i = 0, p = Object.getOwnPropertySymbols(s); i < p.length; i++) {
    if (e.indexOf(p[i]) < 0 && Object.prototype.propertyIsEnumerable.call(s, p[i])) t[p[i]] = s[p[i]];
  }
  return t;
};
function toNamePathStr(name) {
  const namePath = (0, _util.toArray)(name);
  return namePath.join('_');
}
function getFieldDOMNode(name, wrapForm) {
  const field = wrapForm.getFieldInstance(name);
  const fieldDom = (0, _findDOMNode.getDOM)(field);
  if (fieldDom) {
    return fieldDom;
  }
  const fieldId = (0, _util.getFieldId)((0, _util.toArray)(name), wrapForm.__INTERNAL__.name);
  if (fieldId) {
    return document.getElementById(fieldId);
  }
}
function useForm(form) {
  const [rcForm] = (0, _rcFieldForm.useForm)();
  const itemsRef = React.useRef({});
  const wrapForm = React.useMemo(() => form !== null && form !== void 0 ? form : Object.assign(Object.assign({}, rcForm), {
    __INTERNAL__: {
      itemRef: name => node => {
        const namePathStr = toNamePathStr(name);
        if (node) {
          itemsRef.current[namePathStr] = node;
        } else {
          delete itemsRef.current[namePathStr];
        }
      }
    },
    scrollToField: (name, options = {}) => {
      const {
          focus
        } = options,
        restOpt = __rest(options, ["focus"]);
      const node = getFieldDOMNode(name, wrapForm);
      if (node) {
        (0, _scrollIntoViewIfNeeded.default)(node, Object.assign({
          scrollMode: 'if-needed',
          block: 'nearest'
        }, restOpt));
        // Focus if scroll success
        if (focus) {
          wrapForm.focusField(name);
        }
      }
    },
    focusField: name => {
      var _a, _b;
      const itemRef = wrapForm.getFieldInstance(name);
      if (typeof (itemRef === null || itemRef === void 0 ? void 0 : itemRef.focus) === 'function') {
        itemRef.focus();
      } else {
        (_b = (_a = getFieldDOMNode(name, wrapForm)) === null || _a === void 0 ? void 0 : _a.focus) === null || _b === void 0 ? void 0 : _b.call(_a);
      }
    },
    getFieldInstance: name => {
      const namePathStr = toNamePathStr(name);
      return itemsRef.current[namePathStr];
    }
  }), [form, rcForm]);
  return [wrapForm];
}