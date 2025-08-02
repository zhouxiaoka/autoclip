import { genCompactItemStyle } from '../../style/compact-item';
import { genCompactItemVerticalStyle } from '../../style/compact-item-vertical';
import { genSubStyleComponent } from '../../theme/internal';
import { prepareComponentToken, prepareToken } from './token';
const genButtonCompactStyle = token => {
  const {
    componentCls,
    colorPrimaryHover,
    lineWidth,
    calc
  } = token;
  const insetOffset = calc(lineWidth).mul(-1).equal();
  const getCompactBorderStyle = vertical => {
    const selector = `${componentCls}-compact${vertical ? '-vertical' : ''}-item${componentCls}-primary:not([disabled])`;
    return {
      [`${selector} + ${selector}::before`]: {
        position: 'absolute',
        top: vertical ? insetOffset : 0,
        insetInlineStart: vertical ? 0 : insetOffset,
        backgroundColor: colorPrimaryHover,
        content: '""',
        width: vertical ? '100%' : lineWidth,
        height: vertical ? lineWidth : '100%'
      }
    };
  };
  // Special styles for Primary Button
  return Object.assign(Object.assign({}, getCompactBorderStyle()), getCompactBorderStyle(true));
};
// ============================== Export ==============================
export default genSubStyleComponent(['Button', 'compact'], token => {
  const buttonToken = prepareToken(token);
  return [
  // Space Compact
  genCompactItemStyle(buttonToken), genCompactItemVerticalStyle(buttonToken), genButtonCompactStyle(buttonToken)];
}, prepareComponentToken);