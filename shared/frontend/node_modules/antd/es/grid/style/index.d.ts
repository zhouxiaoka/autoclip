import type { AliasToken, GetDefaultToken } from '../../theme/internal';
export interface ComponentToken {
}
export declare const prepareRowComponentToken: GetDefaultToken<'Grid'>;
export declare const prepareColComponentToken: GetDefaultToken<'Grid'>;
export declare const useRowStyle: (prefixCls: string, rootCls?: string) => readonly [(node: React.ReactElement) => React.ReactElement, string, string];
export declare const getMediaSize: (token: AliasToken) => {
    readonly xs: number;
    readonly sm: number;
    readonly md: number;
    readonly lg: number;
    readonly xl: number;
    readonly xxl: number;
};
export declare const useColStyle: (prefixCls: string, rootCls?: string) => readonly [(node: React.ReactElement) => React.ReactElement, string, string];
