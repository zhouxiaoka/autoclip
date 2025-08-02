import * as React from 'react';
import type { GenerateConfig } from 'rc-picker/lib/generate/index';
import type { AnyObject } from '../../_util/type';
import type { GenericTimePickerProps, PickerProps, PickerPropsWithMultiple } from './interface';
declare const generatePicker: <DateType extends AnyObject = AnyObject>(generateConfig: GenerateConfig<DateType>) => {
    DatePicker: (<ValueType = DateType>(props: PickerPropsWithMultiple<DateType, PickerProps<DateType>, ValueType>) => React.ReactElement) & {
        displayName?: string;
    };
    WeekPicker: (<ValueType = DateType>(props: PickerPropsWithMultiple<DateType, Omit<PickerProps<DateType>, "picker">, ValueType>) => React.ReactElement) & {
        displayName?: string;
    };
    MonthPicker: (<ValueType = DateType>(props: PickerPropsWithMultiple<DateType, Omit<PickerProps<DateType>, "picker">, ValueType>) => React.ReactElement) & {
        displayName?: string;
    };
    YearPicker: (<ValueType = DateType>(props: PickerPropsWithMultiple<DateType, Omit<PickerProps<DateType>, "picker">, ValueType>) => React.ReactElement) & {
        displayName?: string;
    };
    TimePicker: (<ValueType = DateType>(props: PickerPropsWithMultiple<DateType, Omit<GenericTimePickerProps<DateType>, "picker">, ValueType>) => React.ReactElement) & {
        displayName?: string;
    };
    QuarterPicker: (<ValueType = DateType>(props: PickerPropsWithMultiple<DateType, Omit<PickerProps<DateType>, "picker">, ValueType>) => React.ReactElement) & {
        displayName?: string;
    };
};
export default generatePicker;
