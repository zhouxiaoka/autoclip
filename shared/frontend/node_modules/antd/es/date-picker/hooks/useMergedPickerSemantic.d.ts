import * as React from 'react';
import type { PickerClassNames, PickerStyles, RequiredSemanticPicker } from '../generatePicker/interface';
declare const useMergedPickerSemantic: (pickerType: "timePicker" | "datePicker", classNames?: PickerClassNames, styles?: PickerStyles, popupClassName?: string, popupStyle?: React.CSSProperties) => RequiredSemanticPicker;
export default useMergedPickerSemantic;
