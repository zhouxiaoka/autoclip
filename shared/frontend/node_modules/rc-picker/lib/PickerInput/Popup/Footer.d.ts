import * as React from 'react';
import type { GenerateConfig } from '../../generate';
import type { DisabledDate, InternalMode, PanelMode, SharedPickerProps } from '../../interface';
import type { PopupShowTimeConfig } from '.';
export interface FooterProps<DateType extends object = any> {
    mode: PanelMode;
    internalMode: InternalMode;
    renderExtraFooter?: SharedPickerProps['renderExtraFooter'];
    showNow: boolean;
    generateConfig: GenerateConfig<DateType>;
    disabledDate: DisabledDate<DateType>;
    showTime?: PopupShowTimeConfig<DateType>;
    /** From Footer component used only. Check if can OK button click */
    invalid?: boolean;
    onSubmit: (date?: DateType) => void;
    needConfirm: boolean;
    onNow: (now: DateType) => void;
}
export default function Footer(props: FooterProps): React.JSX.Element;
