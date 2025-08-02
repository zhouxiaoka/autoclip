import { useStyleRegister } from '@ant-design/cssinjs';
import { genCalc as calc, mergeToken, statisticToken, statistic } from '@ant-design/cssinjs-utils';
import { PresetColors } from './interface';
import { getLineHeight } from './themes/shared/genFontSizes';
import useToken from './useToken';
import { genComponentStyleHook, genStyleHooks, genSubStyleComponent } from './util/genStyleUtils';
import genPresetColor from './util/genPresetColor';
import useResetIconStyle from './util/useResetIconStyle';
export { DesignTokenContext, defaultConfig } from './context';
export {
// generators
genComponentStyleHook, genSubStyleComponent, genPresetColor, genStyleHooks,
// utils
mergeToken, statisticToken, calc, getLineHeight,
// hooks
useResetIconStyle, useStyleRegister, useToken,
// constant
PresetColors, statistic };