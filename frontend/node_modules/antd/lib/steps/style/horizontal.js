"use strict";

Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
const genHorizontalStyle = token => {
  const {
    componentCls
  } = token;
  const stepsItemCls = `${componentCls}-item`; // .ant-steps-item
  return {
    [`${componentCls}-horizontal`]: {
      [`${stepsItemCls}-tail`]: {
        transform: 'translateY(-50%)'
      }
    }
  };
};
var _default = exports.default = genHorizontalStyle;