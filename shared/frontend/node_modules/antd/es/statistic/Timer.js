"use client";

var __rest = this && this.__rest || function (s, e) {
  var t = {};
  for (var p in s) if (Object.prototype.hasOwnProperty.call(s, p) && e.indexOf(p) < 0) t[p] = s[p];
  if (s != null && typeof Object.getOwnPropertySymbols === "function") for (var i = 0, p = Object.getOwnPropertySymbols(s); i < p.length; i++) {
    if (e.indexOf(p[i]) < 0 && Object.prototype.propertyIsEnumerable.call(s, p[i])) t[p[i]] = s[p[i]];
  }
  return t;
};
import * as React from 'react';
import { useEvent } from 'rc-util';
import raf from "rc-util/es/raf";
import { cloneElement } from '../_util/reactNode';
import Statistic from './Statistic';
import { formatCounter } from './utils';
function getTime(value) {
  return new Date(value).getTime();
}
const StatisticTimer = props => {
  const {
      value,
      format = 'HH:mm:ss',
      onChange,
      onFinish,
      type
    } = props,
    rest = __rest(props, ["value", "format", "onChange", "onFinish", "type"]);
  const down = type === 'countdown';
  // We reuse state here to do same as `forceUpdate`
  const [showTime, setShowTime] = React.useState(null);
  // ======================== Update ========================
  const update = useEvent(() => {
    const now = Date.now();
    const timestamp = getTime(value);
    setShowTime({});
    const timeDiff = !down ? now - timestamp : timestamp - now;
    onChange === null || onChange === void 0 ? void 0 : onChange(timeDiff);
    // Only countdown will trigger `onFinish`
    if (down && timestamp < now) {
      onFinish === null || onFinish === void 0 ? void 0 : onFinish();
      return false;
    }
    return true;
  });
  // Effect trigger
  React.useEffect(() => {
    let rafId;
    const clear = () => raf.cancel(rafId);
    const rafUpdate = () => {
      rafId = raf(() => {
        if (update()) {
          rafUpdate();
        }
      });
    };
    rafUpdate();
    return clear;
  }, [value, down]);
  React.useEffect(() => {
    setShowTime({});
  }, []);
  // ======================== Format ========================
  const formatter = (formatValue, config) => showTime ? formatCounter(formatValue, Object.assign(Object.assign({}, config), {
    format
  }), down) : '-';
  const valueRender = node => cloneElement(node, {
    title: undefined
  });
  // ======================== Render ========================
  return /*#__PURE__*/React.createElement(Statistic, Object.assign({}, rest, {
    value: value,
    valueRender: valueRender,
    formatter: formatter
  }));
};
export default StatisticTimer;