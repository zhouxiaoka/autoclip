"use strict";

Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var _cssinjs = require("@ant-design/cssinjs");
var _motion = require("../../style/motion/motion");
const floatButtonGroupMotion = token => {
  const {
    componentCls,
    floatButtonSize,
    motionDurationSlow,
    motionEaseInOutCirc,
    calc
  } = token;
  const moveTopIn = new _cssinjs.Keyframes('antFloatButtonMoveTopIn', {
    '0%': {
      transform: `translate3d(0, ${(0, _cssinjs.unit)(floatButtonSize)}, 0)`,
      transformOrigin: '0 0',
      opacity: 0
    },
    '100%': {
      transform: 'translate3d(0, 0, 0)',
      transformOrigin: '0 0',
      opacity: 1
    }
  });
  const moveTopOut = new _cssinjs.Keyframes('antFloatButtonMoveTopOut', {
    '0%': {
      transform: 'translate3d(0, 0, 0)',
      transformOrigin: '0 0',
      opacity: 1
    },
    '100%': {
      transform: `translate3d(0, ${(0, _cssinjs.unit)(floatButtonSize)}, 0)`,
      transformOrigin: '0 0',
      opacity: 0
    }
  });
  const moveRightIn = new _cssinjs.Keyframes('antFloatButtonMoveRightIn', {
    '0%': {
      transform: `translate3d(${(0, _cssinjs.unit)(calc(floatButtonSize).mul(-1).equal())}, 0, 0)`,
      transformOrigin: '0 0',
      opacity: 0
    },
    '100%': {
      transform: 'translate3d(0, 0, 0)',
      transformOrigin: '0 0',
      opacity: 1
    }
  });
  const moveRightOut = new _cssinjs.Keyframes('antFloatButtonMoveRightOut', {
    '0%': {
      transform: 'translate3d(0, 0, 0)',
      transformOrigin: '0 0',
      opacity: 1
    },
    '100%': {
      transform: `translate3d(${(0, _cssinjs.unit)(calc(floatButtonSize).mul(-1).equal())}, 0, 0)`,
      transformOrigin: '0 0',
      opacity: 0
    }
  });
  const moveBottomIn = new _cssinjs.Keyframes('antFloatButtonMoveBottomIn', {
    '0%': {
      transform: `translate3d(0, ${(0, _cssinjs.unit)(calc(floatButtonSize).mul(-1).equal())}, 0)`,
      transformOrigin: '0 0',
      opacity: 0
    },
    '100%': {
      transform: 'translate3d(0, 0, 0)',
      transformOrigin: '0 0',
      opacity: 1
    }
  });
  const moveBottomOut = new _cssinjs.Keyframes('antFloatButtonMoveBottomOut', {
    '0%': {
      transform: 'translate3d(0, 0, 0)',
      transformOrigin: '0 0',
      opacity: 1
    },
    '100%': {
      transform: `translate3d(0, ${(0, _cssinjs.unit)(calc(floatButtonSize).mul(-1).equal())}, 0)`,
      transformOrigin: '0 0',
      opacity: 0
    }
  });
  const moveLeftIn = new _cssinjs.Keyframes('antFloatButtonMoveLeftIn', {
    '0%': {
      transform: `translate3d(${(0, _cssinjs.unit)(floatButtonSize)}, 0, 0)`,
      transformOrigin: '0 0',
      opacity: 0
    },
    '100%': {
      transform: 'translate3d(0, 0, 0)',
      transformOrigin: '0 0',
      opacity: 1
    }
  });
  const moveLeftOut = new _cssinjs.Keyframes('antFloatButtonMoveLeftOut', {
    '0%': {
      transform: 'translate3d(0, 0, 0)',
      transformOrigin: '0 0',
      opacity: 1
    },
    '100%': {
      transform: `translate3d(${(0, _cssinjs.unit)(floatButtonSize)}, 0, 0)`,
      transformOrigin: '0 0',
      opacity: 0
    }
  });
  const groupPrefixCls = `${componentCls}-group`;
  return [{
    [groupPrefixCls]: {
      [`&${groupPrefixCls}-top ${groupPrefixCls}-wrap`]: (0, _motion.initMotion)(`${groupPrefixCls}-wrap`, moveTopIn, moveTopOut, motionDurationSlow, true),
      [`&${groupPrefixCls}-bottom ${groupPrefixCls}-wrap`]: (0, _motion.initMotion)(`${groupPrefixCls}-wrap`, moveBottomIn, moveBottomOut, motionDurationSlow, true),
      [`&${groupPrefixCls}-left ${groupPrefixCls}-wrap`]: (0, _motion.initMotion)(`${groupPrefixCls}-wrap`, moveLeftIn, moveLeftOut, motionDurationSlow, true),
      [`&${groupPrefixCls}-right ${groupPrefixCls}-wrap`]: (0, _motion.initMotion)(`${groupPrefixCls}-wrap`, moveRightIn, moveRightOut, motionDurationSlow, true)
    }
  }, {
    [`${groupPrefixCls}-wrap`]: {
      [`&${groupPrefixCls}-wrap-enter, &${groupPrefixCls}-wrap-appear`]: {
        opacity: 0,
        animationTimingFunction: motionEaseInOutCirc
      },
      [`&${groupPrefixCls}-wrap-leave`]: {
        opacity: 1,
        animationTimingFunction: motionEaseInOutCirc
      }
    }
  }];
};
var _default = exports.default = floatButtonGroupMotion;