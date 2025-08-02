import type { CSSInterpolation } from '@ant-design/cssinjs';
import type { AliasToken, TokenWithCommonCls } from '../theme/internal';
import type { ArrowToken } from './roundedArrow';
export declare const MAX_VERTICAL_CONTENT_RADIUS = 8;
export interface ArrowOffsetToken {
}
export declare function getArrowOffsetToken(options: {
    contentRadius: number;
    limitVerticalRadius?: boolean;
}): ArrowOffsetToken;
export default function getArrowStyle<Token extends TokenWithCommonCls<AliasToken> & ArrowOffsetToken & ArrowToken>(token: Token, colorBg: string, options?: {
    arrowDistance?: number;
    arrowPlacement?: {
        left?: boolean;
        right?: boolean;
        top?: boolean;
        bottom?: boolean;
    };
}): CSSInterpolation;
