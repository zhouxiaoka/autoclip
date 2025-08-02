import type { Theme, TokenType } from '@ant-design/cssinjs';
import type { OverrideTokenMap, TokenMap, GlobalToken } from '../interface';
export type TokenMapWithTheme<CompTokenMap extends TokenMap, AliasToken extends TokenType, DesignToken extends TokenType> = {
    [key in keyof OverrideTokenMap<CompTokenMap, AliasToken>]?: OverrideTokenMap<CompTokenMap, AliasToken>[key] & {
        theme?: Theme<DesignToken, AliasToken>;
    };
};
export interface UseTokenReturn<CompTokenMap extends TokenMap, AliasToken extends TokenType, DesignToken extends TokenType> {
    token: GlobalToken<CompTokenMap, AliasToken>;
    realToken?: GlobalToken<CompTokenMap, AliasToken>;
    theme?: Theme<DesignToken, AliasToken>;
    components?: TokenMapWithTheme<CompTokenMap, DesignToken, AliasToken>;
    hashId?: string;
    hashed?: string | boolean;
    cssVar?: {
        prefix?: string;
        key?: string;
    };
}
export type UseToken<CompTokenMap extends TokenMap, DesignToken extends TokenType, AliasToken extends TokenType> = () => UseTokenReturn<CompTokenMap, DesignToken, AliasToken>;
