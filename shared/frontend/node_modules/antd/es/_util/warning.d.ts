import * as React from 'react';
export declare function noop(): void;
export declare function resetWarned(): void;
type Warning = (valid: boolean, component: string, message?: string) => void;
declare let warning: Warning;
type BaseTypeWarning = (valid: boolean, 
/**
 * - deprecated: Some API will be removed in future but still support now.
 * - usage: Some API usage is not correct.
 * - breaking: Breaking change like API is removed.
 */
type: 'deprecated' | 'usage' | 'breaking', message?: string) => void;
type TypeWarning = BaseTypeWarning & {
    deprecated: (valid: boolean, oldProp: string, newProp: string, message?: string) => void;
};
export interface WarningContextProps {
    /**
     * @descCN 设置警告等级，设置 `false` 时会将废弃相关信息聚合为单条信息。
     * @descEN Set the warning level. When set to `false`, discard related information will be aggregated into a single message.
     * @since 5.10.0
     */
    strict?: boolean;
}
export declare const WarningContext: React.Context<WarningContextProps>;
/**
 * This is a hook but we not named as `useWarning`
 * since this is only used in development.
 * We should always wrap this in `if (process.env.NODE_ENV !== 'production')` condition
 */
export declare const devUseWarning: (component: string) => TypeWarning;
export default warning;
