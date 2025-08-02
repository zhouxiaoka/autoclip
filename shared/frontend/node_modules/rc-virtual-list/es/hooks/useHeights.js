import _slicedToArray from "@babel/runtime/helpers/esm/slicedToArray";
import * as React from 'react';
import { useEffect, useRef } from 'react';
import CacheMap from "../utils/CacheMap";
function parseNumber(value) {
  var num = parseFloat(value);
  return isNaN(num) ? 0 : num;
}
export default function useHeights(getKey, onItemAdd, onItemRemove) {
  var _React$useState = React.useState(0),
    _React$useState2 = _slicedToArray(_React$useState, 2),
    updatedMark = _React$useState2[0],
    setUpdatedMark = _React$useState2[1];
  var instanceRef = useRef(new Map());
  var heightsRef = useRef(new CacheMap());
  var promiseIdRef = useRef(0);
  function cancelRaf() {
    promiseIdRef.current += 1;
  }
  function collectHeight() {
    var sync = arguments.length > 0 && arguments[0] !== undefined ? arguments[0] : false;
    cancelRaf();
    var doCollect = function doCollect() {
      var changed = false;
      instanceRef.current.forEach(function (element, key) {
        if (element && element.offsetParent) {
          var offsetHeight = element.offsetHeight;
          var _getComputedStyle = getComputedStyle(element),
            marginTop = _getComputedStyle.marginTop,
            marginBottom = _getComputedStyle.marginBottom;
          var marginTopNum = parseNumber(marginTop);
          var marginBottomNum = parseNumber(marginBottom);
          var totalHeight = offsetHeight + marginTopNum + marginBottomNum;
          if (heightsRef.current.get(key) !== totalHeight) {
            heightsRef.current.set(key, totalHeight);
            changed = true;
          }
        }
      });

      // Always trigger update mark to tell parent that should re-calculate heights when resized
      if (changed) {
        setUpdatedMark(function (c) {
          return c + 1;
        });
      }
    };
    if (sync) {
      doCollect();
    } else {
      promiseIdRef.current += 1;
      var id = promiseIdRef.current;
      Promise.resolve().then(function () {
        if (id === promiseIdRef.current) {
          doCollect();
        }
      });
    }
  }
  function setInstanceRef(item, instance) {
    var key = getKey(item);
    var origin = instanceRef.current.get(key);
    if (instance) {
      instanceRef.current.set(key, instance);
      collectHeight();
    } else {
      instanceRef.current.delete(key);
    }

    // Instance changed
    if (!origin !== !instance) {
      if (instance) {
        onItemAdd === null || onItemAdd === void 0 || onItemAdd(item);
      } else {
        onItemRemove === null || onItemRemove === void 0 || onItemRemove(item);
      }
    }
  }
  useEffect(function () {
    return cancelRaf;
  }, []);
  return [setInstanceRef, collectHeight, heightsRef.current, updatedMark];
}