"use strict";

Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var _internal = require("../../theme/internal");
var _token = require("./token");
// =============================== OTP ================================
const genOTPStyle = token => {
  const {
    componentCls,
    paddingXS
  } = token;
  return {
    [componentCls]: {
      display: 'inline-flex',
      alignItems: 'center',
      flexWrap: 'nowrap',
      columnGap: paddingXS,
      [`${componentCls}-input-wrapper`]: {
        position: 'relative',
        [`${componentCls}-mask-icon`]: {
          position: 'absolute',
          zIndex: '1',
          top: '50%',
          right: '50%',
          transform: 'translate(50%, -50%)',
          pointerEvents: 'none'
        },
        [`${componentCls}-mask-input`]: {
          color: 'transparent',
          caretColor: 'var(--ant-color-text)'
        },
        [`${componentCls}-mask-input[type=number]::-webkit-inner-spin-button`]: {
          '-webkit-appearance': 'none',
          margin: 0
        },
        [`${componentCls}-mask-input[type=number]`]: {
          '-moz-appearance': 'textfield'
        }
      },
      '&-rtl': {
        direction: 'rtl'
      },
      [`${componentCls}-input`]: {
        textAlign: 'center',
        paddingInline: token.paddingXXS
      },
      // ================= Size =================
      [`&${componentCls}-sm ${componentCls}-input`]: {
        paddingInline: token.calc(token.paddingXXS).div(2).equal()
      },
      [`&${componentCls}-lg ${componentCls}-input`]: {
        paddingInline: token.paddingXS
      }
    }
  };
};
// ============================== Export ==============================
var _default = exports.default = (0, _internal.genStyleHooks)(['Input', 'OTP'], token => {
  const inputToken = (0, _internal.mergeToken)(token, (0, _token.initInputToken)(token));
  return [genOTPStyle(inputToken)];
}, _token.initComponentToken);