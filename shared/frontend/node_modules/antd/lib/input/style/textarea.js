"use strict";

Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
Object.defineProperty(exports, "initComponentToken", {
  enumerable: true,
  get: function () {
    return _token.initComponentToken;
  }
});
Object.defineProperty(exports, "initInputToken", {
  enumerable: true,
  get: function () {
    return _token.initInputToken;
  }
});
var _internal = require("../../theme/internal");
var _token = require("./token");
const genTextAreaStyle = token => {
  const {
    componentCls,
    paddingLG
  } = token;
  const textareaPrefixCls = `${componentCls}-textarea`;
  return {
    // Raw Textarea
    [`textarea${componentCls}`]: {
      maxWidth: '100%',
      // prevent textarea resize from coming out of its container
      height: 'auto',
      minHeight: token.controlHeight,
      lineHeight: token.lineHeight,
      verticalAlign: 'bottom',
      transition: `all ${token.motionDurationSlow}`,
      resize: 'vertical',
      [`&${componentCls}-mouse-active`]: {
        transition: `all ${token.motionDurationSlow}, height 0s, width 0s`
      }
    },
    // Wrapper for resize
    [`${componentCls}-textarea-affix-wrapper-resize-dirty`]: {
      width: 'auto'
    },
    [textareaPrefixCls]: {
      position: 'relative',
      '&-show-count': {
        [`${componentCls}-data-count`]: {
          position: 'absolute',
          bottom: token.calc(token.fontSize).mul(token.lineHeight).mul(-1).equal(),
          insetInlineEnd: 0,
          color: token.colorTextDescription,
          whiteSpace: 'nowrap',
          pointerEvents: 'none'
        }
      },
      [`
        &-allow-clear > ${componentCls},
        &-affix-wrapper${textareaPrefixCls}-has-feedback ${componentCls}
      `]: {
        paddingInlineEnd: paddingLG
      },
      [`&-affix-wrapper${componentCls}-affix-wrapper`]: {
        padding: 0,
        [`> textarea${componentCls}`]: {
          fontSize: 'inherit',
          border: 'none',
          outline: 'none',
          background: 'transparent',
          minHeight: token.calc(token.controlHeight).sub(token.calc(token.lineWidth).mul(2)).equal(),
          '&:focus': {
            boxShadow: 'none !important'
          }
        },
        [`${componentCls}-suffix`]: {
          margin: 0,
          '> *:not(:last-child)': {
            marginInline: 0
          },
          // Clear Icon
          [`${componentCls}-clear-icon`]: {
            position: 'absolute',
            insetInlineEnd: token.paddingInline,
            insetBlockStart: token.paddingXS
          },
          // Feedback Icon
          [`${textareaPrefixCls}-suffix`]: {
            position: 'absolute',
            top: 0,
            insetInlineEnd: token.paddingInline,
            bottom: 0,
            zIndex: 1,
            display: 'inline-flex',
            alignItems: 'center',
            margin: 'auto',
            pointerEvents: 'none'
          }
        }
      },
      [`&-affix-wrapper${componentCls}-affix-wrapper-rtl`]: {
        [`${componentCls}-suffix`]: {
          [`${componentCls}-data-count`]: {
            direction: 'ltr',
            insetInlineStart: 0
          }
        }
      },
      [`&-affix-wrapper${componentCls}-affix-wrapper-sm`]: {
        [`${componentCls}-suffix`]: {
          [`${componentCls}-clear-icon`]: {
            insetInlineEnd: token.paddingInlineSM
          }
        }
      }
    }
  };
};
// ============================== Export ==============================
var _default = exports.default = (0, _internal.genStyleHooks)(['Input', 'TextArea'], token => {
  const inputToken = (0, _internal.mergeToken)(token, (0, _token.initInputToken)(token));
  return [genTextAreaStyle(inputToken)];
}, _token.initComponentToken, {
  resetFont: false
});