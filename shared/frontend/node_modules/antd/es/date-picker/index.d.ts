import type { Dayjs } from 'dayjs';
import generatePicker from './generatePicker';
import type { RangePickerProps as BaseRangePickerProps, PickerProps, PickerPropsWithMultiple } from './generatePicker/interface';
export type DatePickerProps<ValueType = Dayjs | Dayjs> = PickerPropsWithMultiple<Dayjs, PickerProps<Dayjs>, ValueType>;
export type MonthPickerProps<ValueType = Dayjs | Dayjs> = Omit<DatePickerProps<ValueType>, 'picker'>;
export type WeekPickerProps<ValueType = Dayjs | Dayjs> = Omit<DatePickerProps<ValueType>, 'picker'>;
export type RangePickerProps = BaseRangePickerProps<Dayjs>;
declare const DatePicker: (<ValueType = Dayjs>(props: PickerPropsWithMultiple<Dayjs, PickerProps<Dayjs>, ValueType>) => React.ReactElement) & {
    displayName?: string;
} & {
    displayName?: string;
    WeekPicker: (<ValueType = Dayjs>(props: PickerPropsWithMultiple<Dayjs, Omit<PickerProps<Dayjs>, "picker">, ValueType>) => React.ReactElement) & {
        displayName?: string;
    };
    MonthPicker: (<ValueType = Dayjs>(props: PickerPropsWithMultiple<Dayjs, Omit<PickerProps<Dayjs>, "picker">, ValueType>) => React.ReactElement) & {
        displayName?: string;
    };
    YearPicker: (<ValueType = Dayjs>(props: PickerPropsWithMultiple<Dayjs, Omit<PickerProps<Dayjs>, "picker">, ValueType>) => React.ReactElement) & {
        displayName?: string;
    };
    RangePicker: React.ForwardRefExoticComponent<Omit<import("rc-picker").RangePickerProps<Dayjs>, "classNames" | "styles" | "locale" | "generateConfig" | "hideHeader"> & {
        locale?: import("./generatePicker").PickerLocale;
        size?: import("../button").ButtonSize;
        placement?: "bottomLeft" | "bottomRight" | "topLeft" | "topRight";
        bordered?: boolean;
        status?: import("../_util/statusUtils").InputStatus;
        variant?: import("../config-provider").Variant;
        dropdownClassName?: string;
        popupClassName?: string;
        rootClassName?: string;
        popupStyle?: React.CSSProperties;
        styles?: import("./generatePicker/interface").PickerStyles;
        classNames?: import("./generatePicker/interface").PickerClassNames;
    } & React.RefAttributes<import("rc-picker").PickerRef>>;
    TimePicker: (<ValueType = Dayjs>(props: PickerPropsWithMultiple<Dayjs, Omit<import("./generatePicker/interface").GenericTimePickerProps<Dayjs>, "picker">, ValueType>) => React.ReactElement) & {
        displayName?: string;
    };
    QuarterPicker: (<ValueType = Dayjs>(props: PickerPropsWithMultiple<Dayjs, Omit<PickerProps<Dayjs>, "picker">, ValueType>) => React.ReactElement) & {
        displayName?: string;
    };
};
export type DatePickerType = typeof DatePicker & {
    _InternalPanelDoNotUseOrYouWillBeFired: typeof PurePanel;
    _InternalRangePanelDoNotUseOrYouWillBeFired: typeof PureRangePanel;
    generatePicker: typeof generatePicker;
};
declare const PurePanel: (props: import("../_util/type").AnyObject) => React.JSX.Element;
declare const PureRangePanel: (props: import("../_util/type").AnyObject) => React.JSX.Element;
declare const _default: DatePickerType;
export default _default;
