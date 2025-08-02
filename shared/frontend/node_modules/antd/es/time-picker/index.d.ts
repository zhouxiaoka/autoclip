import * as React from 'react';
import type { Dayjs } from 'dayjs';
import type { PickerRef } from 'rc-picker';
import type { InputStatus } from '../_util/statusUtils';
import type { AnyObject } from '../_util/type';
import type { GenericTimePickerProps, PickerPropsWithMultiple, RangePickerProps } from '../date-picker/generatePicker/interface';
export type PickerTimeProps<DateType extends AnyObject> = PickerPropsWithMultiple<DateType, GenericTimePickerProps<DateType>>;
export type RangePickerTimeProps<DateType extends AnyObject> = Omit<RangePickerProps<DateType>, 'showTime' | 'picker'>;
export interface TimePickerLocale {
    placeholder?: string;
    rangePlaceholder?: [string, string];
}
export interface TimeRangePickerProps extends Omit<RangePickerTimeProps<Dayjs>, 'picker'> {
    popupClassName?: string;
}
declare const RangePicker: React.ForwardRefExoticComponent<TimeRangePickerProps & React.RefAttributes<PickerRef>>;
export interface TimePickerProps extends Omit<PickerTimeProps<Dayjs>, 'picker'> {
    addon?: () => React.ReactNode;
    status?: InputStatus;
    popupClassName?: string;
    rootClassName?: string;
}
declare const TimePicker: React.ForwardRefExoticComponent<Omit<TimePickerProps, "ref"> & React.RefAttributes<PickerRef>>;
declare const PurePanel: (props: AnyObject) => React.JSX.Element;
type MergedTimePicker = typeof TimePicker & {
    RangePicker: typeof RangePicker;
    _InternalPanelDoNotUseOrYouWillBeFired: typeof PurePanel;
};
declare const _default: MergedTimePicker;
export default _default;
