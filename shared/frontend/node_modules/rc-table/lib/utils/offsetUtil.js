"use strict";

Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.getOffset = getOffset;
var _findDOMNode = require("rc-util/lib/Dom/findDOMNode");
// Copy from `rc-util/Dom/css.js`
function getOffset(node) {
  var element = (0, _findDOMNode.getDOM)(node);
  var box = element.getBoundingClientRect();
  var docElem = document.documentElement;

  // < ie8 not support win.pageXOffset, use docElem.scrollLeft instead
  return {
    left: box.left + (window.pageXOffset || docElem.scrollLeft) - (docElem.clientLeft || document.body.clientLeft || 0),
    top: box.top + (window.pageYOffset || docElem.scrollTop) - (docElem.clientTop || document.body.clientTop || 0)
  };
}