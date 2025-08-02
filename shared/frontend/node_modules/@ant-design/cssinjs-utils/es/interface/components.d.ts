import type { TokenType } from '@ant-design/cssinjs';
export type TokenMap = Record<PropertyKey, any>;
export type TokenMapKey<CompTokenMap extends TokenMap> = Extract<keyof CompTokenMap, string>;
export type GlobalToken<CompTokenMap extends TokenMap, AliasToken extends TokenType> = AliasToken & CompTokenMap;
export type OverrideTokenMap<CompTokenMap extends TokenMap, AliasToken extends TokenType> = {
    [key in keyof CompTokenMap]: Partial<CompTokenMap[key]> & Partial<AliasToken>;
};
export type GlobalTokenWithComponent<CompTokenMap extends TokenMap, AliasToken extends TokenType, C extends TokenMapKey<CompTokenMap>> = GlobalToken<CompTokenMap, AliasToken> & CompTokenMap[C];
export type ComponentToken<CompTokenMap extends TokenMap, AliasToken extends TokenType, C extends TokenMapKey<CompTokenMap>> = Exclude<OverrideTokenMap<CompTokenMap, AliasToken>[C], undefined>;
export type ComponentTokenKey<CompTokenMap extends TokenMap, AliasToken extends TokenType, C extends TokenMapKey<CompTokenMap>> = keyof ComponentToken<CompTokenMap, AliasToken, C>;
