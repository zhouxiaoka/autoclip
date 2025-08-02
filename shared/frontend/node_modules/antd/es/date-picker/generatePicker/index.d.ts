import type { GenerateConfig } from 'rc-picker/lib/generate/index';
import type { AnyObject } from '../../_util/type';
export type { PickerLocale, PickerProps } from './interface';
declare const generatePicker: <DateType extends AnyObject = AnyObject>(generateConfig: GenerateConfig<DateType>) => (<ValueType = DateType>(props: import("./interface").PickerPropsWithMultiple<DateType, import("./interface").PickerProps<DateType>, ValueType>) => React.ReactElement) & {
    displayName?: string;
} & {
    displayName?: string;
    WeekPicker: (<ValueType = DateType>(props: import("./interface").PickerPropsWithMultiple<DateType, Omit<import("./interface").PickerProps<DateType>, "picker">, ValueType>) => React.ReactElement) & {
        displayName?: string;
    };
    MonthPicker: (<ValueType = DateType>(props: import("./interface").PickerPropsWithMultiple<DateType, Omit<import("./interface").PickerProps<DateType>, "picker">, ValueType>) => React.ReactElement) & {
        displayName?: string;
    };
    YearPicker: (<ValueType = DateType>(props: import("./interface").PickerPropsWithMultiple<DateType, Omit<import("./interface").PickerProps<DateType>, "picker">, ValueType>) => React.ReactElement) & {
        displayName?: string;
    };
    RangePicker: React.ForwardRefExoticComponent<Omit<import("rc-picker").RangePickerProps<DateType>, "classNames" | "styles" | "locale" | "generateConfig" | "hideHeader"> & {
        locale?: import("./interface").PickerLocale;
        size?: import("../../button").ButtonSize;
        placement?: "bottomLeft" | "bottomRight" | "topLeft" | "topRight";
        bordered?: boolean;
        status?: import("../../_util/statusUtils").InputStatus;
        variant?: import("../../config-provider").Variant;
        dropdownClassName?: string;
        popupClassName?: string;
        rootClassName?: string;
        popupStyle?: React.CSSProperties;
        styles?: import("./interface").PickerStyles;
        classNames?: import("./interface").PickerClassNames;
    } & React.RefAttributes<import("rc-picker").PickerRef>>;
    TimePicker: (<ValueType = DateType>(props: import("./interface").PickerPropsWithMultiple<DateType, Omit<import("./interface").GenericTimePickerProps<DateType>, "picker">, ValueType>) => React.ReactElement) & {
        displayName?: string;
    };
    QuarterPicker: (<ValueType = DateType>(props: import("./interface").PickerPropsWithMultiple<DateType, Omit<import("./interface").PickerProps<DateType>, "picker">, ValueType>) => React.ReactElement) & {
        displayName?: string;
    };
};
export default generatePicker;
