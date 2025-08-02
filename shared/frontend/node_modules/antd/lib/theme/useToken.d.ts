import type { Theme } from '@ant-design/cssinjs';
import type { DesignTokenProviderProps } from './context';
import type { AliasToken, GlobalToken, SeedToken } from './interface';
export declare const unitless: {
    [key in keyof AliasToken]?: boolean;
};
export declare const ignore: {
    [key in keyof AliasToken]?: boolean;
};
export declare const getComputedToken: (originToken: SeedToken, overrideToken: DesignTokenProviderProps["components"] & {
    override?: Partial<AliasToken>;
}, theme: Theme<any, any>) => any;
export default function useToken(): [
    theme: Theme<SeedToken, AliasToken>,
    token: GlobalToken,
    hashId: string,
    realToken: GlobalToken,
    cssVar?: DesignTokenProviderProps['cssVar']
];
