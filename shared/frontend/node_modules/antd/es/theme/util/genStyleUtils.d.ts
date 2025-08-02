import type { AliasToken, ComponentTokenMap } from '../interface';
export declare const genStyleHooks: <C extends keyof ComponentTokenMap>(component: C | [C, string], styleFn: import("@ant-design/cssinjs-utils").GenStyleFn<ComponentTokenMap, AliasToken, C>, getDefaultToken?: import("@ant-design/cssinjs-utils").GetDefaultToken<ComponentTokenMap, AliasToken, C> | undefined, options?: {
    resetStyle?: boolean;
    resetFont?: boolean;
    deprecatedTokens?: [keyof Exclude<import("@ant-design/cssinjs-utils").OverrideTokenMap<ComponentTokenMap, AliasToken>[C], undefined>, keyof Exclude<import("@ant-design/cssinjs-utils").OverrideTokenMap<ComponentTokenMap, AliasToken>[C], undefined>][] | undefined;
    unitless?: Partial<Record<keyof Exclude<import("@ant-design/cssinjs-utils").OverrideTokenMap<ComponentTokenMap, AliasToken>[C], undefined>, boolean>> | undefined;
    clientOnly?: boolean;
    order?: number;
    injectStyle?: boolean;
} | undefined) => (prefixCls: string, rootCls?: string) => readonly [(node: React.ReactElement) => React.ReactElement, string, string], genComponentStyleHook: <C_2 extends keyof ComponentTokenMap>(componentName: C_2 | [C_2, string], styleFn: import("@ant-design/cssinjs-utils").GenStyleFn<ComponentTokenMap, AliasToken, C_2>, getDefaultToken?: import("@ant-design/cssinjs-utils").GetDefaultToken<ComponentTokenMap, AliasToken, C_2> | undefined, options?: {
    resetStyle?: boolean;
    resetFont?: boolean;
    deprecatedTokens?: [keyof Exclude<import("@ant-design/cssinjs-utils").OverrideTokenMap<ComponentTokenMap, AliasToken>[C_2], undefined>, keyof Exclude<import("@ant-design/cssinjs-utils").OverrideTokenMap<ComponentTokenMap, AliasToken>[C_2], undefined>][] | undefined;
    clientOnly?: boolean;
    order?: number;
    injectStyle?: boolean;
    unitless?: Partial<Record<keyof Exclude<import("@ant-design/cssinjs-utils").OverrideTokenMap<ComponentTokenMap, AliasToken>[C_2], undefined>, boolean>> | undefined;
} | undefined) => (prefixCls: string, rootCls?: string) => import("@ant-design/cssinjs-utils/lib/interface").UseComponentStyleResult, genSubStyleComponent: <C_1 extends keyof ComponentTokenMap>(componentName: C_1 | [C_1, string], styleFn: import("@ant-design/cssinjs-utils").GenStyleFn<ComponentTokenMap, AliasToken, C_1>, getDefaultToken?: import("@ant-design/cssinjs-utils").GetDefaultToken<ComponentTokenMap, AliasToken, C_1> | undefined, options?: {
    resetStyle?: boolean;
    resetFont?: boolean;
    deprecatedTokens?: [keyof Exclude<import("@ant-design/cssinjs-utils").OverrideTokenMap<ComponentTokenMap, AliasToken>[C_1], undefined>, keyof Exclude<import("@ant-design/cssinjs-utils").OverrideTokenMap<ComponentTokenMap, AliasToken>[C_1], undefined>][] | undefined;
    clientOnly?: boolean;
    order?: number;
    injectStyle?: boolean;
    unitless?: Partial<Record<keyof Exclude<import("@ant-design/cssinjs-utils").OverrideTokenMap<ComponentTokenMap, AliasToken>[C_1], undefined>, boolean>> | undefined;
} | undefined) => React.FunctionComponent<import("@ant-design/cssinjs-utils/lib/util/genStyleUtils").SubStyleComponentProps>;
