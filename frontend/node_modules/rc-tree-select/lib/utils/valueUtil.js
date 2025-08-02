"use strict";

Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.toArray = exports.isNil = exports.isCheckDisabled = exports.getAllKeys = exports.fillFieldNames = void 0;
var toArray = exports.toArray = function toArray(value) {
  return Array.isArray(value) ? value : value !== undefined ? [value] : [];
};
var fillFieldNames = exports.fillFieldNames = function fillFieldNames(fieldNames) {
  var _ref = fieldNames || {},
    label = _ref.label,
    value = _ref.value,
    children = _ref.children;
  return {
    _title: label ? [label] : ['title', 'label'],
    value: value || 'value',
    key: value || 'value',
    children: children || 'children'
  };
};
var isCheckDisabled = exports.isCheckDisabled = function isCheckDisabled(node) {
  return !node || node.disabled || node.disableCheckbox || node.checkable === false;
};
var getAllKeys = exports.getAllKeys = function getAllKeys(treeData, fieldNames) {
  var keys = [];
  var dig = function dig(list) {
    list.forEach(function (item) {
      var children = item[fieldNames.children];
      if (children) {
        keys.push(item[fieldNames.value]);
        dig(children);
      }
    });
  };
  dig(treeData);
  return keys;
};
var isNil = exports.isNil = function isNil(val) {
  return val === null || val === undefined;
};