import * as React from 'react';
import type { PickerRef } from 'rc-picker';
import type { GenerateConfig } from 'rc-picker/lib/generate/index';
import type { AnyObject } from '../../_util/type';
declare const generateRangePicker: <DateType extends AnyObject = AnyObject>(generateConfig: GenerateConfig<DateType>) => React.ForwardRefExoticComponent<Omit<import("rc-picker").RangePickerProps<DateType>, "classNames" | "styles" | "locale" | "generateConfig" | "hideHeader"> & {
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
} & React.RefAttributes<PickerRef>>;
export default generateRangePicker;
