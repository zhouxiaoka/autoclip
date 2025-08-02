"use strict";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.genActiveStyle = exports.default = void 0;
var _cssinjs = require("@ant-design/cssinjs");
var _compactItem = require("../../style/compact-item");
var _internal = require("../../theme/internal");
var _colorBlock = _interopRequireDefault(require("./color-block"));
var _input = _interopRequireDefault(require("./input"));
var _picker = _interopRequireDefault(require("./picker"));
var _presets = _interopRequireDefault(require("./presets"));
var _slider = _interopRequireDefault(require("./slider"));
const genActiveStyle = (token, borderColor, outlineColor) => ({
  borderInlineEndWidth: token.lineWidth,
  borderColor,
  boxShadow: `0 0 0 ${(0, _cssinjs.unit)(token.controlOutlineWidth)} ${outlineColor}`,
  outline: 0
});
exports.genActiveStyle = genActiveStyle;
const genRtlStyle = token => {
  const {
    componentCls
  } = token;
  return {
    '&-rtl': {
      [`${componentCls}-presets-color`]: {
        '&::after': {
          direction: 'ltr'
        }
      },
      [`${componentCls}-clear`]: {
        '&::after': {
          direction: 'ltr'
        }
      }
    }
  };
};
const genClearStyle = (token, size, extraStyle) => {
  const {
    componentCls,
    borderRadiusSM,
    lineWidth,
    colorSplit,
    colorBorder,
    red6
  } = token;
  return {
    [`${componentCls}-clear`]: Object.assign(Object.assign({
      width: size,
      height: size,
      borderRadius: borderRadiusSM,
      border: `${(0, _cssinjs.unit)(lineWidth)} solid ${colorSplit}`,
      position: 'relative',
      overflow: 'hidden',
      cursor: 'inherit',
      transition: `all ${token.motionDurationFast}`
    }, extraStyle), {
      '&::after': {
        content: '""',
        position: 'absolute',
        insetInlineEnd: token.calc(lineWidth).mul(-1).equal(),
        top: token.calc(lineWidth).mul(-1).equal(),
        display: 'block',
        width: 40,
        // maximum
        height: 2,
        // fixed
        transformOrigin: `calc(100% - 1px) 1px`,
        transform: 'rotate(-45deg)',
        backgroundColor: red6
      },
      '&:hover': {
        borderColor: colorBorder
      }
    })
  };
};
const genStatusStyle = token => {
  const {
    componentCls,
    colorError,
    colorWarning,
    colorErrorHover,
    colorWarningHover,
    colorErrorOutline,
    colorWarningOutline
  } = token;
  return {
    [`&${componentCls}-status-error`]: {
      borderColor: colorError,
      '&:hover': {
        borderColor: colorErrorHover
      },
      [`&${componentCls}-trigger-active`]: Object.assign({}, genActiveStyle(token, colorError, colorErrorOutline))
    },
    [`&${componentCls}-status-warning`]: {
      borderColor: colorWarning,
      '&:hover': {
        borderColor: colorWarningHover
      },
      [`&${componentCls}-trigger-active`]: Object.assign({}, genActiveStyle(token, colorWarning, colorWarningOutline))
    }
  };
};
const genSizeStyle = token => {
  const {
    componentCls,
    controlHeightLG,
    controlHeightSM,
    controlHeight,
    controlHeightXS,
    borderRadius,
    borderRadiusSM,
    borderRadiusXS,
    borderRadiusLG,
    fontSizeLG
  } = token;
  return {
    [`&${componentCls}-lg`]: {
      minWidth: controlHeightLG,
      minHeight: controlHeightLG,
      borderRadius: borderRadiusLG,
      [`${componentCls}-color-block, ${componentCls}-clear`]: {
        width: controlHeight,
        height: controlHeight,
        borderRadius
      },
      [`${componentCls}-trigger-text`]: {
        fontSize: fontSizeLG
      }
    },
    [`&${componentCls}-sm`]: {
      minWidth: controlHeightSM,
      minHeight: controlHeightSM,
      borderRadius: borderRadiusSM,
      [`${componentCls}-color-block, ${componentCls}-clear`]: {
        width: controlHeightXS,
        height: controlHeightXS,
        borderRadius: borderRadiusXS
      },
      [`${componentCls}-trigger-text`]: {
        lineHeight: (0, _cssinjs.unit)(controlHeightXS)
      }
    }
  };
};
const genColorPickerStyle = token => {
  const {
    antCls,
    componentCls,
    colorPickerWidth,
    colorPrimary,
    motionDurationMid,
    colorBgElevated,
    colorTextDisabled,
    colorText,
    colorBgContainerDisabled,
    borderRadius,
    marginXS,
    marginSM,
    controlHeight,
    controlHeightSM,
    colorBgTextActive,
    colorPickerPresetColorSize,
    colorPickerPreviewSize,
    lineWidth,
    colorBorder,
    paddingXXS,
    fontSize,
    colorPrimaryHover,
    controlOutline
  } = token;
  return [{
    [componentCls]: Object.assign({
      [`${componentCls}-inner`]: Object.assign(Object.assign(Object.assign(Object.assign(Object.assign(Object.assign({
        '&-content': {
          display: 'flex',
          flexDirection: 'column',
          width: colorPickerWidth,
          [`& > ${antCls}-divider`]: {
            margin: `${(0, _cssinjs.unit)(marginSM)} 0 ${(0, _cssinjs.unit)(marginXS)}`
          }
        },
        [`${componentCls}-panel`]: Object.assign({}, (0, _picker.default)(token))
      }, (0, _slider.default)(token)), (0, _colorBlock.default)(token, colorPickerPreviewSize)), (0, _input.default)(token)), (0, _presets.default)(token)), genClearStyle(token, colorPickerPresetColorSize, {
        marginInlineStart: 'auto'
      })), {
        // Operation bar
        [`${componentCls}-operation`]: {
          display: 'flex',
          justifyContent: 'space-between',
          marginBottom: marginXS
        }
      }),
      '&-trigger': Object.assign(Object.assign(Object.assign(Object.assign({
        minWidth: controlHeight,
        minHeight: controlHeight,
        borderRadius,
        border: `${(0, _cssinjs.unit)(lineWidth)} solid ${colorBorder}`,
        cursor: 'pointer',
        display: 'inline-flex',
        alignItems: 'flex-start',
        justifyContent: 'center',
        transition: `all ${motionDurationMid}`,
        background: colorBgElevated,
        padding: token.calc(paddingXXS).sub(lineWidth).equal(),
        [`${componentCls}-trigger-text`]: {
          marginInlineStart: marginXS,
          marginInlineEnd: token.calc(marginXS).sub(token.calc(paddingXXS).sub(lineWidth)).equal(),
          fontSize,
          color: colorText,
          alignSelf: 'center',
          '&-cell': {
            '&:not(:last-child):after': {
              content: '", "'
            },
            '&-inactive': {
              color: colorTextDisabled
            }
          }
        },
        '&:hover': {
          borderColor: colorPrimaryHover
        },
        [`&${componentCls}-trigger-active`]: Object.assign({}, genActiveStyle(token, colorPrimary, controlOutline)),
        '&-disabled': {
          color: colorTextDisabled,
          background: colorBgContainerDisabled,
          cursor: 'not-allowed',
          '&:hover': {
            borderColor: colorBgTextActive
          },
          [`${componentCls}-trigger-text`]: {
            color: colorTextDisabled
          }
        }
      }, genClearStyle(token, controlHeightSM)), (0, _colorBlock.default)(token, controlHeightSM)), genStatusStyle(token)), genSizeStyle(token))
    }, genRtlStyle(token))
  }, (0, _compactItem.genCompactItemStyle)(token, {
    focusElCls: `${componentCls}-trigger-active`
  })];
};
var _default = exports.default = (0, _internal.genStyleHooks)('ColorPicker', token => {
  const {
    colorTextQuaternary,
    marginSM
  } = token;
  const colorPickerSliderHeight = 8;
  const colorPickerToken = (0, _internal.mergeToken)(token, {
    colorPickerWidth: 234,
    colorPickerHandlerSize: 16,
    colorPickerHandlerSizeSM: 12,
    colorPickerAlphaInputWidth: 44,
    colorPickerInputNumberHandleWidth: 16,
    colorPickerPresetColorSize: 24,
    colorPickerInsetShadow: `inset 0 0 1px 0 ${colorTextQuaternary}`,
    colorPickerSliderHeight,
    colorPickerPreviewSize: token.calc(colorPickerSliderHeight).mul(2).add(marginSM).equal()
  });
  return [genColorPickerStyle(colorPickerToken)];
});