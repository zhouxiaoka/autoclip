import { getDOM } from "rc-util/es/Dom/findDOMNode";

// Copy from `rc-util/Dom/css.js`
export function getOffset(node) {
  var element = getDOM(node);
  var box = element.getBoundingClientRect();
  var docElem = document.documentElement;

  // < ie8 not support win.pageXOffset, use docElem.scrollLeft instead
  return {
    left: box.left + (window.pageXOffset || docElem.scrollLeft) - (docElem.clientLeft || document.body.clientLeft || 0),
    top: box.top + (window.pageYOffset || docElem.scrollTop) - (docElem.clientTop || document.body.clientTop || 0)
  };
}