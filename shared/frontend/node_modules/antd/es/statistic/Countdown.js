"use client";

import * as React from 'react';
import { devUseWarning } from '../_util/warning';
import StatisticTimer from './Timer';
const Countdown = props => {
  if (process.env.NODE_ENV !== 'production') {
    const warning = devUseWarning('Countdown');
    warning.deprecated(false, '<Statistic.Countdown />', '<Statistic.Timer type="countdown" />');
  }
  return /*#__PURE__*/React.createElement(StatisticTimer, Object.assign({}, props, {
    type: "countdown"
  }));
};
export default /*#__PURE__*/React.memo(Countdown);