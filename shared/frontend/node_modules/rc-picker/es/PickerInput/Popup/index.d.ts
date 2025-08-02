import * as React from 'react';
import type { RangeTimeProps, SharedPickerProps, SharedTimeProps, ValueDate } from '../../interface';
import { type FooterProps } from './Footer';
import { type PopupPanelProps } from './PopupPanel';
export type PopupShowTimeConfig<DateType extends object = any> = Omit<RangeTimeProps<DateType>, 'defaultValue' | 'defaultOpenValue' | 'disabledTime'> & Pick<SharedTimeProps<DateType>, 'disabledTime'>;
export interface PopupProps<DateType extends object = any, PresetValue = DateType> extends Pick<React.InputHTMLAttributes<HTMLDivElement>, 'onFocus' | 'onBlur'>, FooterProps<DateType>, PopupPanelProps<DateType> {
    panelRender?: SharedPickerProps['panelRender'];
    presets: ValueDate<DateType>[];
    onPresetHover: (presetValue: PresetValue) => void;
    onPresetSubmit: (presetValue: PresetValue) => void;
    activeInfo?: [activeInputLeft: number, activeInputRight: number, selectorWidth: number];
    direction?: 'ltr' | 'rtl';
    /** TimePicker or showTime only */
    defaultOpenValue: DateType;
    needConfirm: boolean;
    isInvalid: (date: DateType | DateType[]) => boolean;
    onOk: VoidFunction;
    onPanelMouseDown?: React.MouseEventHandler<HTMLDivElement>;
}
export default function Popup<DateType extends object = any>(props: PopupProps<DateType>): React.JSX.Element;
