import type { GlobalToken, MappingAlgorithm } from './interface';
import defaultAlgorithm from './themes/default';
/** Get current context Design Token. Will be different if you are using nest theme config. */
declare function useToken(): {
    theme: import("@ant-design/cssinjs").Theme<import("./interface").SeedToken, import("./interface").AliasToken>;
    token: GlobalToken;
    hashId: string;
};
export type { GlobalToken, MappingAlgorithm };
declare const _default: {
    /** Default seedToken */
    defaultSeed: import("./interface").SeedToken;
    useToken: typeof useToken;
    defaultAlgorithm: typeof defaultAlgorithm;
    darkAlgorithm: import("@ant-design/cssinjs").DerivativeFunc<import("./interface").SeedToken, import("./interface").MapToken>;
    compactAlgorithm: import("@ant-design/cssinjs").DerivativeFunc<import("./interface").SeedToken, import("./interface").MapToken>;
    getDesignToken: (config?: import("..").ThemeConfig) => import("./interface").AliasToken;
    /**
     * @private Private variable
     * @warring 🔥 Do not use in production. 🔥
     */
    defaultConfig: {
        token: import("./interface").SeedToken;
        override: {
            override: import("./interface").SeedToken;
        };
        hashed: boolean;
    };
    /**
     * @private Private variable
     * @warring 🔥 Do not use in production. 🔥
     */
    _internalContext: React.Context<import("./context").DesignTokenProviderProps>;
};
export default _default;
