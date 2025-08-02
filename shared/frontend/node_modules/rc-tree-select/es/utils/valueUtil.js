export var toArray = function toArray(value) {
  return Array.isArray(value) ? value : value !== undefined ? [value] : [];
};
export var fillFieldNames = function fillFieldNames(fieldNames) {
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
export var isCheckDisabled = function isCheckDisabled(node) {
  return !node || node.disabled || node.disableCheckbox || node.checkable === false;
};
export var getAllKeys = function getAllKeys(treeData, fieldNames) {
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
export var isNil = function isNil(val) {
  return val === null || val === undefined;
};