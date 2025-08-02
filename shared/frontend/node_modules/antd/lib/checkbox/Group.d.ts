import * as React from 'react';
import type { CheckboxChangeEvent } from './Checkbox';
import GroupContext from './GroupContext';
export interface CheckboxOptionType<T = any> {
    label: React.ReactNode;
    value: T;
    style?: React.CSSProperties;
    className?: string;
    disabled?: boolean;
    title?: string;
    id?: string;
    onChange?: (e: CheckboxChangeEvent) => void;
    required?: boolean;
}
export interface AbstractCheckboxGroupProps<T = any> {
    prefixCls?: string;
    className?: string;
    rootClassName?: string;
    options?: (CheckboxOptionType<T> | string | number)[];
    disabled?: boolean;
    style?: React.CSSProperties;
}
export interface CheckboxGroupProps<T = any> extends AbstractCheckboxGroupProps<T> {
    name?: string;
    defaultValue?: T[];
    value?: T[];
    onChange?: (checkedValue: T[]) => void;
    children?: React.ReactNode;
}
export type { CheckboxGroupContext } from './GroupContext';
export { GroupContext };
declare const _default: <T = any>(props: CheckboxGroupProps<T> & React.RefAttributes<HTMLDivElement>) => React.ReactElement;
export default _default;
