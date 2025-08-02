"use strict";

Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.prepareComponentToken = exports.default = void 0;
var _cssinjs = require("@ant-design/cssinjs");
var _style = require("../../style");
var _internal = require("../../theme/internal");
// ============================== Mixins ==============================
function getItemDisabledStyle(cls, token) {
  return {
    [`${cls}, ${cls}:hover, ${cls}:focus`]: {
      color: token.colorTextDisabled,
      cursor: 'not-allowed'
    }
  };
}
function getItemSelectedStyle(token) {
  return {
    backgroundColor: token.itemSelectedBg,
    boxShadow: token.boxShadowTertiary
  };
}
const segmentedTextEllipsisCss = Object.assign({
  overflow: 'hidden'
}, _style.textEllipsis);
// ============================== Styles ==============================
const genSegmentedStyle = token => {
  const {
    componentCls
  } = token;
  const labelHeight = token.calc(token.controlHeight).sub(token.calc(token.trackPadding).mul(2)).equal();
  const labelHeightLG = token.calc(token.controlHeightLG).sub(token.calc(token.trackPadding).mul(2)).equal();
  const labelHeightSM = token.calc(token.controlHeightSM).sub(token.calc(token.trackPadding).mul(2)).equal();
  return {
    [componentCls]: Object.assign(Object.assign(Object.assign(Object.assign(Object.assign(Object.assign(Object.assign({}, (0, _style.resetComponent)(token)), {
      display: 'inline-block',
      padding: token.trackPadding,
      color: token.itemColor,
      background: token.trackBg,
      borderRadius: token.borderRadius,
      transition: `all ${token.motionDurationMid} ${token.motionEaseInOut}`
    }), (0, _style.genFocusStyle)(token)), {
      [`${componentCls}-group`]: {
        position: 'relative',
        display: 'flex',
        alignItems: 'stretch',
        justifyItems: 'flex-start',
        flexDirection: 'row',
        width: '100%'
      },
      // RTL styles
      [`&${componentCls}-rtl`]: {
        direction: 'rtl'
      },
      [`&${componentCls}-vertical`]: {
        [`${componentCls}-group`]: {
          flexDirection: 'column'
        },
        [`${componentCls}-thumb`]: {
          width: '100%',
          height: 0,
          padding: `0 ${(0, _cssinjs.unit)(token.paddingXXS)}`
        }
      },
      // block styles
      [`&${componentCls}-block`]: {
        display: 'flex'
      },
      [`&${componentCls}-block ${componentCls}-item`]: {
        flex: 1,
        minWidth: 0
      },
      // item styles
      [`${componentCls}-item`]: {
        position: 'relative',
        textAlign: 'center',
        cursor: 'pointer',
        transition: `color ${token.motionDurationMid} ${token.motionEaseInOut}`,
        borderRadius: token.borderRadiusSM,
        // Fix Safari render bug
        // https://github.com/ant-design/ant-design/issues/45250
        transform: 'translateZ(0)',
        '&-selected': Object.assign(Object.assign({}, getItemSelectedStyle(token)), {
          color: token.itemSelectedColor
        }),
        '&-focused': Object.assign({}, (0, _style.genFocusOutline)(token)),
        '&::after': {
          content: '""',
          position: 'absolute',
          zIndex: -1,
          width: '100%',
          height: '100%',
          top: 0,
          insetInlineStart: 0,
          borderRadius: 'inherit',
          opacity: 0,
          transition: `opacity ${token.motionDurationMid}`,
          // This is mandatory to make it not clickable or hoverable
          // Ref: https://github.com/ant-design/ant-design/issues/40888
          pointerEvents: 'none'
        },
        [`&:hover:not(${componentCls}-item-selected):not(${componentCls}-item-disabled)`]: {
          color: token.itemHoverColor,
          '&::after': {
            opacity: 1,
            backgroundColor: token.itemHoverBg
          }
        },
        [`&:active:not(${componentCls}-item-selected):not(${componentCls}-item-disabled)`]: {
          color: token.itemHoverColor,
          '&::after': {
            opacity: 1,
            backgroundColor: token.itemActiveBg
          }
        },
        '&-label': Object.assign({
          minHeight: labelHeight,
          lineHeight: (0, _cssinjs.unit)(labelHeight),
          padding: `0 ${(0, _cssinjs.unit)(token.segmentedPaddingHorizontal)}`
        }, segmentedTextEllipsisCss),
        // syntactic sugar to add `icon` for Segmented Item
        '&-icon + *': {
          marginInlineStart: token.calc(token.marginSM).div(2).equal()
        },
        '&-input': {
          position: 'absolute',
          insetBlockStart: 0,
          insetInlineStart: 0,
          width: 0,
          height: 0,
          opacity: 0,
          pointerEvents: 'none'
        }
      },
      // thumb styles
      [`${componentCls}-thumb`]: Object.assign(Object.assign({}, getItemSelectedStyle(token)), {
        position: 'absolute',
        insetBlockStart: 0,
        insetInlineStart: 0,
        width: 0,
        height: '100%',
        padding: `${(0, _cssinjs.unit)(token.paddingXXS)} 0`,
        borderRadius: token.borderRadiusSM,
        transition: `transform ${token.motionDurationSlow} ${token.motionEaseInOut}, height ${token.motionDurationSlow} ${token.motionEaseInOut}`,
        [`& ~ ${componentCls}-item:not(${componentCls}-item-selected):not(${componentCls}-item-disabled)::after`]: {
          backgroundColor: 'transparent'
        }
      }),
      // size styles
      [`&${componentCls}-lg`]: {
        borderRadius: token.borderRadiusLG,
        [`${componentCls}-item-label`]: {
          minHeight: labelHeightLG,
          lineHeight: (0, _cssinjs.unit)(labelHeightLG),
          padding: `0 ${(0, _cssinjs.unit)(token.segmentedPaddingHorizontal)}`,
          fontSize: token.fontSizeLG
        },
        [`${componentCls}-item, ${componentCls}-thumb`]: {
          borderRadius: token.borderRadius
        }
      },
      [`&${componentCls}-sm`]: {
        borderRadius: token.borderRadiusSM,
        [`${componentCls}-item-label`]: {
          minHeight: labelHeightSM,
          lineHeight: (0, _cssinjs.unit)(labelHeightSM),
          padding: `0 ${(0, _cssinjs.unit)(token.segmentedPaddingHorizontalSM)}`
        },
        [`${componentCls}-item, ${componentCls}-thumb`]: {
          borderRadius: token.borderRadiusXS
        }
      }
    }), getItemDisabledStyle(`&-disabled ${componentCls}-item`, token)), getItemDisabledStyle(`${componentCls}-item-disabled`, token)), {
      // transition effect when `appear-active`
      [`${componentCls}-thumb-motion-appear-active`]: {
        transition: `transform ${token.motionDurationSlow} ${token.motionEaseInOut}, width ${token.motionDurationSlow} ${token.motionEaseInOut}`,
        willChange: 'transform, width'
      },
      [`&${componentCls}-shape-round`]: {
        borderRadius: 9999,
        [`${componentCls}-item, ${componentCls}-thumb`]: {
          borderRadius: 9999
        }
      }
    })
  };
};
// ============================== Export ==============================
const prepareComponentToken = token => {
  const {
    colorTextLabel,
    colorText,
    colorFillSecondary,
    colorBgElevated,
    colorFill,
    lineWidthBold,
    colorBgLayout
  } = token;
  return {
    trackPadding: lineWidthBold,
    trackBg: colorBgLayout,
    itemColor: colorTextLabel,
    itemHoverColor: colorText,
    itemHoverBg: colorFillSecondary,
    itemSelectedBg: colorBgElevated,
    itemActiveBg: colorFill,
    itemSelectedColor: colorText
  };
};
exports.prepareComponentToken = prepareComponentToken;
var _default = exports.default = (0, _internal.genStyleHooks)('Segmented', token => {
  const {
    lineWidth,
    calc
  } = token;
  const segmentedToken = (0, _internal.mergeToken)(token, {
    segmentedPaddingHorizontal: calc(token.controlPaddingHorizontal).sub(lineWidth).equal(),
    segmentedPaddingHorizontalSM: calc(token.controlPaddingHorizontalSM).sub(lineWidth).equal()
  });
  return [genSegmentedStyle(segmentedToken)];
}, prepareComponentToken);