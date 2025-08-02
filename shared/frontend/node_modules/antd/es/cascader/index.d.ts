import * as React from 'react';
import type { BaseOptionType, DefaultOptionType, FieldNames, CascaderProps as RcCascaderProps } from 'rc-cascader';
import type { SelectCommonPlacement } from '../_util/motion';
import type { InputStatus } from '../_util/statusUtils';
import type { Variant } from '../config-provider';
import type { SizeType } from '../config-provider/SizeContext';
import CascaderPanel from './Panel';
export type { BaseOptionType, DefaultOptionType };
export type FieldNamesType = FieldNames;
export type FilledFieldNamesType = Required<FieldNamesType>;
type SemanticName = 'root';
type PopupSemantic = 'root';
declare const SHOW_CHILD: "SHOW_CHILD", SHOW_PARENT: "SHOW_PARENT";
export interface CascaderProps<OptionType extends DefaultOptionType = DefaultOptionType, ValueField extends keyof OptionType = keyof OptionType, Multiple extends boolean = boolean> extends Omit<RcCascaderProps<OptionType, ValueField, Multiple>, 'checkable'> {
    multiple?: Multiple;
    size?: SizeType;
    /**
     * @deprecated `showArrow` is deprecated which will be removed in next major version. It will be a
     *   default behavior, you can hide it by setting `suffixIcon` to null.
     */
    showArrow?: boolean;
    disabled?: boolean;
    /** @deprecated Use `variant` instead. */
    bordered?: boolean;
    placement?: SelectCommonPlacement;
    suffixIcon?: React.ReactNode;
    options?: OptionType[];
    status?: InputStatus;
    autoClearSearchValue?: boolean;
    rootClassName?: string;
    /** @deprecated Please use `classNames.popup.root` instead */
    popupClassName?: string;
    /** @deprecated Please use `classNames.popup.root` instead */
    dropdownClassName?: string;
    /** @deprecated Please use `styles.popup.root` instead */
    dropdownStyle?: React.CSSProperties;
    /** @deprecated Please use `popupRender` instead */
    dropdownRender?: (menu: React.ReactElement) => React.ReactElement;
    popupRender?: (menu: React.ReactElement) => React.ReactElement;
    /** @deprecated Please use `popupMenuColumnStyle` instead */
    dropdownMenuColumnStyle?: React.CSSProperties;
    popupMenuColumnStyle?: React.CSSProperties;
    /** @deprecated Please use `onOpenChange` instead */
    onDropdownVisibleChange?: (visible: boolean) => void;
    onOpenChange?: (visible: boolean) => void;
    /**
     * @since 5.13.0
     * @default "outlined"
     */
    variant?: Variant;
    classNames?: Partial<Record<SemanticName, string>> & {
        popup?: Partial<Record<PopupSemantic, string>>;
    };
    styles?: Partial<Record<SemanticName, React.CSSProperties>> & {
        popup?: Partial<Record<PopupSemantic, React.CSSProperties>>;
    };
}
export type CascaderAutoProps<OptionType extends DefaultOptionType = DefaultOptionType, ValueField extends keyof OptionType = keyof OptionType> = (CascaderProps<OptionType, ValueField> & {
    multiple?: false;
}) | (CascaderProps<OptionType, ValueField, true> & {
    multiple: true;
});
export interface CascaderRef {
    focus: () => void;
    blur: () => void;
}
declare const Cascader: (<OptionType extends DefaultOptionType = DefaultOptionType, ValueField extends keyof OptionType = keyof OptionType>(props: React.PropsWithChildren<CascaderAutoProps<OptionType, ValueField>> & React.RefAttributes<CascaderRef>) => React.ReactElement) & {
    displayName: string;
    SHOW_PARENT: typeof SHOW_PARENT;
    SHOW_CHILD: typeof SHOW_CHILD;
    Panel: typeof CascaderPanel;
    _InternalPanelDoNotUseOrYouWillBeFired: typeof PurePanel;
};
declare const PurePanel: (props: import("../_util/type").AnyObject) => React.JSX.Element;
export default Cascader;
