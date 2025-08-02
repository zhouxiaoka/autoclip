import * as React from 'react';
import { List, useWatch } from 'rc-field-form';
import type { FormProps as RcFormProps } from 'rc-field-form/lib/Form';
import type { FormRef } from 'rc-field-form/lib/interface';
import type { Variant } from '../config-provider';
import type { SizeType } from '../config-provider/SizeContext';
import type { ColProps } from '../grid/col';
import type { FeedbackIcons } from './FormItem';
import useForm from './hooks/useForm';
import type { FormInstance } from './hooks/useForm';
import type { FormLabelAlign, ScrollFocusOptions } from './interface';
export type RequiredMark = boolean | 'optional' | ((labelNode: React.ReactNode, info: {
    required: boolean;
}) => React.ReactNode);
export type FormLayout = 'horizontal' | 'inline' | 'vertical';
export type FormItemLayout = 'horizontal' | 'vertical';
export type { ScrollFocusOptions };
export interface FormProps<Values = any> extends Omit<RcFormProps<Values>, 'form'> {
    prefixCls?: string;
    colon?: boolean;
    name?: string;
    layout?: FormLayout;
    labelAlign?: FormLabelAlign;
    labelWrap?: boolean;
    labelCol?: ColProps;
    wrapperCol?: ColProps;
    form?: FormInstance<Values>;
    feedbackIcons?: FeedbackIcons;
    size?: SizeType;
    disabled?: boolean;
    scrollToFirstError?: ScrollFocusOptions | boolean;
    requiredMark?: RequiredMark;
    /** @deprecated Will warning in future branch. Pls use `requiredMark` instead. */
    hideRequiredMark?: boolean;
    rootClassName?: string;
    variant?: Variant;
}
declare const Form: (<Values = any>(props: React.PropsWithChildren<FormProps<Values>> & React.RefAttributes<FormRef<Values>>) => React.ReactElement) & Pick<React.FC, "displayName">;
export { List, useForm, useWatch, type FormInstance };
export default Form;
