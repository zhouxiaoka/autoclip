import type { ValidateStatus } from '../form/FormItem';
declare const _InputStatuses: readonly ["warning", "error", ""];
export type InputStatus = (typeof _InputStatuses)[number];
export declare function getStatusClassNames(prefixCls: string, status?: ValidateStatus, hasFeedback?: boolean): string;
export declare const getMergedStatus: (contextStatus?: ValidateStatus, customStatus?: InputStatus) => "" | "success" | "error" | "warning" | "validating" | undefined;
export {};
