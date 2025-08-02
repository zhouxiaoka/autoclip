import { unit } from '@ant-design/cssinjs';
import { resetComponent } from '../../style';
import { genStyleHooks } from '../../theme/internal';
export const DotDuration = '--dot-duration';
const genCarouselStyle = token => {
  const {
    componentCls,
    antCls
  } = token;
  return {
    [componentCls]: Object.assign(Object.assign({}, resetComponent(token)), {
      '.slick-slider': {
        position: 'relative',
        display: 'block',
        boxSizing: 'border-box',
        touchAction: 'pan-y',
        WebkitTouchCallout: 'none',
        WebkitTapHighlightColor: 'transparent',
        '.slick-track, .slick-list': {
          transform: 'translate3d(0, 0, 0)',
          touchAction: 'pan-y'
        }
      },
      '.slick-list': {
        position: 'relative',
        display: 'block',
        margin: 0,
        padding: 0,
        overflow: 'hidden',
        '&:focus': {
          outline: 'none'
        },
        '&.dragging': {
          cursor: 'pointer'
        },
        '.slick-slide': {
          pointerEvents: 'none',
          // https://github.com/ant-design/ant-design/issues/23294
          [`input${antCls}-radio-input, input${antCls}-checkbox-input`]: {
            visibility: 'hidden'
          },
          '&.slick-active': {
            pointerEvents: 'auto',
            [`input${antCls}-radio-input, input${antCls}-checkbox-input`]: {
              visibility: 'visible'
            }
          },
          // fix Carousel content height not match parent node
          // when children is empty node
          // https://github.com/ant-design/ant-design/issues/25878
          '> div > div': {
            verticalAlign: 'bottom'
          }
        }
      },
      '.slick-track': {
        position: 'relative',
        top: 0,
        insetInlineStart: 0,
        display: 'block',
        '&::before, &::after': {
          display: 'table',
          content: '""'
        },
        '&::after': {
          clear: 'both'
        }
      },
      '.slick-slide': {
        display: 'none',
        float: 'left',
        height: '100%',
        minHeight: 1,
        img: {
          display: 'block'
        },
        '&.dragging img': {
          pointerEvents: 'none'
        }
      },
      '.slick-initialized .slick-slide': {
        display: 'block'
      },
      '.slick-vertical .slick-slide': {
        display: 'block',
        height: 'auto'
      }
    })
  };
};
const genArrowsStyle = token => {
  const {
    componentCls,
    motionDurationSlow,
    arrowSize,
    arrowOffset
  } = token;
  const arrowLength = token.calc(arrowSize).div(Math.SQRT2).equal();
  return {
    [componentCls]: {
      // Arrows
      '.slick-prev, .slick-next': {
        position: 'absolute',
        top: '50%',
        width: arrowSize,
        height: arrowSize,
        transform: 'translateY(-50%)',
        color: '#fff',
        opacity: 0.4,
        background: 'transparent',
        padding: 0,
        lineHeight: 0,
        border: 0,
        outline: 'none',
        cursor: 'pointer',
        zIndex: 1,
        transition: `opacity ${motionDurationSlow}`,
        '&:hover, &:focus': {
          opacity: 1
        },
        '&.slick-disabled': {
          pointerEvents: 'none',
          opacity: 0
        },
        '&::after': {
          boxSizing: 'border-box',
          position: 'absolute',
          top: token.calc(arrowSize).sub(arrowLength).div(2).equal(),
          insetInlineStart: token.calc(arrowSize).sub(arrowLength).div(2).equal(),
          display: 'inline-block',
          width: arrowLength,
          height: arrowLength,
          border: `0 solid currentcolor`,
          borderInlineStartWidth: 2,
          borderBlockStartWidth: 2,
          borderRadius: 1,
          content: '""'
        }
      },
      '.slick-prev': {
        insetInlineStart: arrowOffset,
        '&::after': {
          transform: 'rotate(-45deg)'
        }
      },
      '.slick-next': {
        insetInlineEnd: arrowOffset,
        '&::after': {
          transform: 'rotate(135deg)'
        }
      }
    }
  };
};
const genDotsStyle = token => {
  const {
    componentCls,
    dotOffset,
    dotWidth,
    dotHeight,
    dotGap,
    colorBgContainer,
    motionDurationSlow
  } = token;
  return {
    [componentCls]: {
      '.slick-dots': {
        position: 'absolute',
        insetInlineEnd: 0,
        bottom: 0,
        insetInlineStart: 0,
        zIndex: 15,
        display: 'flex !important',
        justifyContent: 'center',
        paddingInlineStart: 0,
        margin: 0,
        listStyle: 'none',
        '&-bottom': {
          bottom: dotOffset
        },
        '&-top': {
          top: dotOffset,
          bottom: 'auto'
        },
        li: {
          position: 'relative',
          display: 'inline-block',
          flex: '0 1 auto',
          boxSizing: 'content-box',
          width: dotWidth,
          height: dotHeight,
          marginInline: dotGap,
          padding: 0,
          textAlign: 'center',
          textIndent: -999,
          verticalAlign: 'top',
          transition: `all ${motionDurationSlow}`,
          borderRadius: dotHeight,
          overflow: 'hidden',
          '&::after': {
            display: 'block',
            position: 'absolute',
            top: 0,
            insetInlineStart: 0,
            width: '100%',
            height: dotHeight,
            content: '""',
            background: colorBgContainer,
            borderRadius: dotHeight,
            opacity: 1,
            outline: 'none',
            cursor: 'pointer',
            overflow: 'hidden',
            transform: 'translate3d(-100%, 0, 0)'
          },
          button: {
            position: 'relative',
            display: 'block',
            width: '100%',
            height: dotHeight,
            padding: 0,
            color: 'transparent',
            fontSize: 0,
            background: colorBgContainer,
            border: 0,
            borderRadius: dotHeight,
            outline: 'none',
            cursor: 'pointer',
            opacity: 0.2,
            transition: `all ${motionDurationSlow}`,
            overflow: 'hidden',
            '&:hover': {
              opacity: 0.75
            },
            '&::after': {
              position: 'absolute',
              inset: token.calc(dotGap).mul(-1).equal(),
              content: '""'
            }
          },
          '&.slick-active': {
            width: token.dotActiveWidth,
            position: 'relative',
            '&:hover': {
              opacity: 1
            },
            '&::after': {
              transform: 'translate3d(0, 0, 0)',
              transition: `transform var(${DotDuration}) ease-out`
            }
          }
        }
      }
    }
  };
};
const genCarouselVerticalStyle = token => {
  const {
    componentCls,
    dotOffset,
    arrowOffset,
    marginXXS
  } = token;
  const reverseSizeOfDot = {
    width: token.dotHeight,
    height: token.dotWidth
  };
  return {
    [`${componentCls}-vertical`]: {
      '.slick-prev, .slick-next': {
        insetInlineStart: '50%',
        marginBlockStart: 'unset',
        transform: 'translateX(-50%)'
      },
      '.slick-prev': {
        insetBlockStart: arrowOffset,
        insetInlineStart: '50%',
        '&::after': {
          transform: 'rotate(45deg)'
        }
      },
      '.slick-next': {
        insetBlockStart: 'auto',
        insetBlockEnd: arrowOffset,
        '&::after': {
          transform: 'rotate(-135deg)'
        }
      },
      '.slick-dots': {
        top: '50%',
        bottom: 'auto',
        flexDirection: 'column',
        width: token.dotHeight,
        height: 'auto',
        margin: 0,
        transform: 'translateY(-50%)',
        '&-left': {
          insetInlineEnd: 'auto',
          insetInlineStart: dotOffset
        },
        '&-right': {
          insetInlineEnd: dotOffset,
          insetInlineStart: 'auto'
        },
        li: Object.assign(Object.assign({}, reverseSizeOfDot), {
          margin: `${unit(marginXXS)} 0`,
          verticalAlign: 'baseline',
          button: reverseSizeOfDot,
          '&::after': Object.assign(Object.assign({}, reverseSizeOfDot), {
            height: 0
          }),
          '&.slick-active': Object.assign(Object.assign({}, reverseSizeOfDot), {
            button: reverseSizeOfDot,
            '&::after': Object.assign(Object.assign({}, reverseSizeOfDot), {
              transition: `height var(${DotDuration}) ease-out`
            })
          })
        })
      }
    }
  };
};
const genCarouselRtlStyle = token => {
  const {
    componentCls
  } = token;
  return [{
    [`${componentCls}-rtl`]: {
      direction: 'rtl',
      // Dots
      '.slick-dots': {
        [`${componentCls}-rtl&`]: {
          flexDirection: 'row-reverse'
        }
      }
    }
  }, {
    [`${componentCls}-vertical`]: {
      '.slick-dots': {
        [`${componentCls}-rtl&`]: {
          flexDirection: 'column'
        }
      }
    }
  }];
};
export const prepareComponentToken = token => {
  const dotActiveWidth = 24;
  return {
    arrowSize: 16,
    arrowOffset: token.marginXS,
    dotWidth: 16,
    dotHeight: 3,
    dotGap: token.marginXXS,
    dotOffset: 12,
    dotWidthActive: dotActiveWidth,
    dotActiveWidth
  };
};
// ============================== Export ==============================
export default genStyleHooks('Carousel', token => [genCarouselStyle(token), genArrowsStyle(token), genDotsStyle(token), genCarouselVerticalStyle(token), genCarouselRtlStyle(token)], prepareComponentToken, {
  deprecatedTokens: [['dotWidthActive', 'dotActiveWidth']]
});