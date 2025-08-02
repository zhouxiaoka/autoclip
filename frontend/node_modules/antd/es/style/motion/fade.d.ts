import type { CSSInterpolation } from '@ant-design/cssinjs';
import { Keyframes } from '@ant-design/cssinjs';
import type { AliasToken, TokenWithCommonCls } from '../../theme/internal';
export declare const fadeIn: Keyframes;
export declare const fadeOut: Keyframes;
export declare const initFadeMotion: (token: TokenWithCommonCls<AliasToken>, sameLevel?: boolean) => CSSInterpolation;
