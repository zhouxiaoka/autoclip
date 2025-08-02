import React from 'react';
import type { CheckboxOptionType } from './Group';
export interface CheckboxGroupContext<T = any> {
    name?: string;
    toggleOption?: (option: CheckboxOptionType<T>) => void;
    value?: any;
    disabled?: boolean;
    registerValue: (val: T) => void;
    cancelValue: (val: T) => void;
}
declare const GroupContext: React.Context<CheckboxGroupContext<any> | null>;
export default GroupContext;
