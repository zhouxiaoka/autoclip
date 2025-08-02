import * as React from 'react';
import type { Store, FormInstance, FieldData, ValidateMessages, Callbacks, FormRef } from './interface';
type BaseFormProps = Omit<React.FormHTMLAttributes<HTMLFormElement>, 'onSubmit' | 'children'>;
type RenderProps = (values: Store, form: FormInstance) => JSX.Element | React.ReactNode;
export interface FormProps<Values = any> extends BaseFormProps {
    initialValues?: Store;
    form?: FormInstance<Values>;
    children?: RenderProps | React.ReactNode;
    component?: false | string | React.FC<any> | React.ComponentClass<any>;
    fields?: FieldData[];
    name?: string;
    validateMessages?: ValidateMessages;
    onValuesChange?: Callbacks<Values>['onValuesChange'];
    onFieldsChange?: Callbacks<Values>['onFieldsChange'];
    onFinish?: Callbacks<Values>['onFinish'];
    onFinishFailed?: Callbacks<Values>['onFinishFailed'];
    validateTrigger?: string | string[] | false;
    preserve?: boolean;
    clearOnDestroy?: boolean;
}
declare const Form: React.ForwardRefRenderFunction<FormRef, FormProps>;
export default Form;
