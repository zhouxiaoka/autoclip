import type { TokenMap } from '../interface';
/**
 * This function will do as `Object.assign` in production. But will use Object.defineProperty:get to
 * pass all value access in development. To support statistic field usage with alias token.
 */
export declare function merge<CompTokenMap extends TokenMap>(...objs: Partial<CompTokenMap>[]): CompTokenMap;
/** @internal Internal Usage. Not use in your production. */
export declare const statistic: Record<string, {
    global: string[];
    component: Record<string, string | number>;
}>;
/** @internal Internal Usage. Not use in your production. */
export declare const _statistic_build_: typeof statistic;
/** Statistic token usage case. Should use `merge` function if you do not want spread record. */
declare const statisticToken: <CompTokenMap extends TokenMap>(token: CompTokenMap) => {
    token: CompTokenMap;
    keys: Set<string>;
    flush: (componentName: string, componentToken: Record<string, string | number>) => void;
};
export default statisticToken;
