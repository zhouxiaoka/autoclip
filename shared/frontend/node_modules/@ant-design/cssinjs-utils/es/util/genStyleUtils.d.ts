import React from 'react';
import type { CSSInterpolation, CSSObject, TokenType } from '@ant-design/cssinjs';
import { useStyleRegister } from '@ant-design/cssinjs';
import type { ComponentTokenKey, GlobalTokenWithComponent, TokenMap, TokenMapKey, UseComponentStyleResult } from '../interface';
import type AbstractCalculator from './calc/calculator';
import type { UseCSP } from '../hooks/useCSP';
import type { UsePrefix } from '../hooks/usePrefix';
import type { UseToken } from '../hooks/useToken';
type LayerConfig = Parameters<typeof useStyleRegister>[0]['layer'];
export interface StyleInfo {
    hashId: string;
    prefixCls: string;
    rootPrefixCls: string;
    iconPrefixCls: string;
}
export type CSSUtil = {
    calc: (number: any) => AbstractCalculator;
    max: (...values: (number | string)[]) => number | string;
    min: (...values: (number | string)[]) => number | string;
};
export type TokenWithCommonCls<T> = T & {
    /** Wrap component class with `.` prefix */
    componentCls: string;
    /** Origin prefix which do not have `.` prefix */
    prefixCls: string;
    /** Wrap icon class with `.` prefix */
    iconCls: string;
    /** Wrap ant prefixCls class with `.` prefix */
    antCls: string;
} & CSSUtil;
export type FullToken<CompTokenMap extends TokenMap, AliasToken extends TokenType, C extends TokenMapKey<CompTokenMap>> = TokenWithCommonCls<GlobalTokenWithComponent<CompTokenMap, AliasToken, C>>;
export type GenStyleFn<CompTokenMap extends TokenMap, AliasToken extends TokenType, C extends TokenMapKey<CompTokenMap>> = (token: FullToken<CompTokenMap, AliasToken, C>, info: StyleInfo) => CSSInterpolation;
export type GetDefaultTokenFn<CompTokenMap extends TokenMap, AliasToken extends TokenType, C extends TokenMapKey<CompTokenMap>> = (token: AliasToken & Partial<CompTokenMap[C]>) => CompTokenMap[C];
export type GetDefaultToken<CompTokenMap extends TokenMap, AliasToken extends TokenType, C extends TokenMapKey<CompTokenMap>> = null | CompTokenMap[C] | GetDefaultTokenFn<CompTokenMap, AliasToken, C>;
export interface SubStyleComponentProps {
    prefixCls: string;
    rootCls?: string;
}
export type CSSVarRegisterProps = {
    rootCls: string;
    component: string;
    cssVar: {
        prefix?: string;
        key?: string;
    };
};
type GetResetStylesConfig = {
    prefix: ReturnType<UsePrefix>;
    csp: ReturnType<UseCSP>;
};
export type GetResetStyles<AliasToken extends TokenType> = (token: AliasToken, config?: GetResetStylesConfig) => CSSInterpolation;
export type GetCompUnitless<CompTokenMap extends TokenMap, AliasToken extends TokenType> = <C extends TokenMapKey<CompTokenMap>>(component: C | [C, string]) => Partial<Record<ComponentTokenKey<CompTokenMap, AliasToken, C>, boolean>>;
declare function genStyleUtils<CompTokenMap extends TokenMap, AliasToken extends TokenType, DesignToken extends TokenType>(config: {
    usePrefix: UsePrefix;
    useToken: UseToken<CompTokenMap, AliasToken, DesignToken>;
    useCSP?: UseCSP;
    getResetStyles?: GetResetStyles<AliasToken>;
    getCommonStyle?: (token: AliasToken, componentPrefixCls: string, rootCls?: string, resetFont?: boolean) => CSSObject;
    getCompUnitless?: GetCompUnitless<CompTokenMap, AliasToken>;
    layer?: LayerConfig;
}): {
    genStyleHooks: <C extends TokenMapKey<CompTokenMap>>(component: C | [C, string], styleFn: GenStyleFn<CompTokenMap, AliasToken, C>, getDefaultToken?: GetDefaultToken<CompTokenMap, AliasToken, C>, options?: {
        resetStyle?: boolean;
        resetFont?: boolean;
        deprecatedTokens?: [keyof Exclude<import("../interface").OverrideTokenMap<CompTokenMap, AliasToken>[C], undefined>, keyof Exclude<import("../interface").OverrideTokenMap<CompTokenMap, AliasToken>[C], undefined>][];
        /**
         * Component tokens that do not need unit.
         */
        unitless?: Partial<Record<keyof Exclude<import("../interface").OverrideTokenMap<CompTokenMap, AliasToken>[C], undefined>, boolean>>;
        /**
         * Only use component style in client side. Ignore in SSR.
         */
        clientOnly?: boolean;
        /**
         * Set order of component style.
         * @default -999
         */
        order?: number;
        /**
         * Whether generate styles
         * @default true
         */
        injectStyle?: boolean;
    }) => (prefixCls: string, rootCls?: string) => readonly [(node: React.ReactElement) => React.ReactElement, string, string];
    genSubStyleComponent: <C_1 extends TokenMapKey<CompTokenMap>>(componentName: C_1 | [C_1, string], styleFn: GenStyleFn<CompTokenMap, AliasToken, C_1>, getDefaultToken?: GetDefaultToken<CompTokenMap, AliasToken, C_1>, options?: {
        resetStyle?: boolean;
        resetFont?: boolean;
        deprecatedTokens?: [keyof Exclude<import("../interface").OverrideTokenMap<CompTokenMap, AliasToken>[C_1], undefined>, keyof Exclude<import("../interface").OverrideTokenMap<CompTokenMap, AliasToken>[C_1], undefined>][];
        /**
         * Only use component style in client side. Ignore in SSR.
         */
        clientOnly?: boolean;
        /**
         * Set order of component style. Default is -999.
         */
        order?: number;
        injectStyle?: boolean;
        unitless?: Partial<Record<keyof Exclude<import("../interface").OverrideTokenMap<CompTokenMap, AliasToken>[C_1], undefined>, boolean>>;
    }) => React.FunctionComponent<SubStyleComponentProps>;
    genComponentStyleHook: <C_2 extends TokenMapKey<CompTokenMap>>(componentName: C_2 | [C_2, string], styleFn: GenStyleFn<CompTokenMap, AliasToken, C_2>, getDefaultToken?: GetDefaultToken<CompTokenMap, AliasToken, C_2>, options?: {
        resetStyle?: boolean;
        resetFont?: boolean;
        deprecatedTokens?: [keyof Exclude<import("../interface").OverrideTokenMap<CompTokenMap, AliasToken>[C_2], undefined>, keyof Exclude<import("../interface").OverrideTokenMap<CompTokenMap, AliasToken>[C_2], undefined>][];
        /**
         * Only use component style in client side. Ignore in SSR.
         */
        clientOnly?: boolean;
        /**
         * Set order of component style. Default is -999.
         */
        order?: number;
        injectStyle?: boolean;
        unitless?: Partial<Record<keyof Exclude<import("../interface").OverrideTokenMap<CompTokenMap, AliasToken>[C_2], undefined>, boolean>>;
    }) => (prefixCls: string, rootCls?: string) => UseComponentStyleResult;
};
export default genStyleUtils;
