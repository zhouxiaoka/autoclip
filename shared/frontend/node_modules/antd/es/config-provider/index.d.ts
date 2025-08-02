import * as React from 'react';
import type { WarningContextProps } from '../_util/warning';
import type { Locale } from '../locale';
import type { AlertConfig, BadgeConfig, ButtonConfig, CardConfig, CascaderConfig, CollapseConfig, ComponentStyleConfig, ConfigConsumerProps, CSPConfig, DatePickerConfig, DirectionType, DrawerConfig, EmptyConfig, FlexConfig, FloatButtonGroupConfig, FormConfig, ImageConfig, InputConfig, InputNumberConfig, ListConfig, MentionsConfig, MenuConfig, ModalConfig, NotificationConfig, PaginationConfig, PopconfirmConfig, PopoverConfig, PopupOverflow, RangePickerConfig, SelectConfig, SpaceConfig, SpinConfig, TableConfig, TabsConfig, TagConfig, TextAreaConfig, Theme, ThemeConfig, TimePickerConfig, TooltipConfig, TourConfig, TransferConfig, TreeSelectConfig, Variant, WaveConfig } from './context';
import { ConfigConsumer, ConfigContext, defaultIconPrefixCls, defaultPrefixCls, Variants } from './context';
import type { RenderEmptyHandler } from './defaultRenderEmpty';
import useConfig from './hooks/useConfig';
import type { SizeType } from './SizeContext';
import SizeContext from './SizeContext';
export type { Variant };
export { Variants };
export declare const warnContext: (componentName: string) => void;
export { ConfigConsumer, ConfigContext, defaultPrefixCls, defaultIconPrefixCls, type ConfigConsumerProps, type CSPConfig, type DirectionType, type RenderEmptyHandler, type ThemeConfig, };
export declare const configConsumerProps: string[];
export interface ConfigProviderProps {
    getTargetContainer?: () => HTMLElement | Window;
    getPopupContainer?: (triggerNode?: HTMLElement) => HTMLElement;
    prefixCls?: string;
    iconPrefixCls?: string;
    children?: React.ReactNode;
    renderEmpty?: RenderEmptyHandler;
    csp?: CSPConfig;
    /** @deprecated Please use `{ button: { autoInsertSpace: boolean }}` instead */
    autoInsertSpaceInButton?: boolean;
    variant?: Variant;
    form?: FormConfig;
    input?: InputConfig;
    inputNumber?: InputNumberConfig;
    textArea?: TextAreaConfig;
    select?: SelectConfig;
    pagination?: PaginationConfig;
    /**
     * @descCN 语言包配置，语言包可到 `antd/locale` 目录下寻找。
     * @descEN Language package setting, you can find the packages in `antd/locale`.
     */
    locale?: Locale;
    componentSize?: SizeType;
    componentDisabled?: boolean;
    /**
     * @descCN 设置布局展示方向。
     * @descEN Set direction of layout.
     * @default ltr
     */
    direction?: DirectionType;
    space?: SpaceConfig;
    splitter?: ComponentStyleConfig;
    /**
     * @descCN 设置 `false` 时关闭虚拟滚动。
     * @descEN Close the virtual scrolling when setting `false`.
     * @default true
     */
    virtual?: boolean;
    /** @deprecated Please use `popupMatchSelectWidth` instead */
    dropdownMatchSelectWidth?: boolean;
    popupMatchSelectWidth?: boolean;
    popupOverflow?: PopupOverflow;
    theme?: ThemeConfig;
    warning?: WarningContextProps;
    alert?: AlertConfig;
    anchor?: ComponentStyleConfig;
    button?: ButtonConfig;
    calendar?: ComponentStyleConfig;
    carousel?: ComponentStyleConfig;
    cascader?: CascaderConfig;
    treeSelect?: TreeSelectConfig;
    collapse?: CollapseConfig;
    divider?: ComponentStyleConfig;
    drawer?: DrawerConfig;
    typography?: ComponentStyleConfig;
    skeleton?: ComponentStyleConfig;
    spin?: SpinConfig;
    segmented?: ComponentStyleConfig;
    statistic?: ComponentStyleConfig;
    steps?: ComponentStyleConfig;
    image?: ImageConfig;
    layout?: ComponentStyleConfig;
    list?: ListConfig;
    mentions?: MentionsConfig;
    modal?: ModalConfig;
    progress?: ComponentStyleConfig;
    result?: ComponentStyleConfig;
    slider?: ComponentStyleConfig;
    breadcrumb?: ComponentStyleConfig;
    menu?: MenuConfig;
    floatButtonGroup?: FloatButtonGroupConfig;
    checkbox?: ComponentStyleConfig;
    descriptions?: ComponentStyleConfig;
    empty?: EmptyConfig;
    badge?: BadgeConfig;
    radio?: ComponentStyleConfig;
    rate?: ComponentStyleConfig;
    switch?: ComponentStyleConfig;
    transfer?: TransferConfig;
    avatar?: ComponentStyleConfig;
    message?: ComponentStyleConfig;
    tag?: TagConfig;
    table?: TableConfig;
    card?: CardConfig;
    tabs?: TabsConfig;
    timeline?: ComponentStyleConfig;
    timePicker?: TimePickerConfig;
    upload?: ComponentStyleConfig;
    notification?: NotificationConfig;
    tree?: ComponentStyleConfig;
    colorPicker?: ComponentStyleConfig;
    datePicker?: DatePickerConfig;
    rangePicker?: RangePickerConfig;
    dropdown?: ComponentStyleConfig;
    flex?: FlexConfig;
    /**
     * Wave is special component which only patch on the effect of component interaction.
     */
    wave?: WaveConfig;
    tour?: TourConfig;
    tooltip?: TooltipConfig;
    popover?: PopoverConfig;
    popconfirm?: PopconfirmConfig;
}
type holderRenderType = (children: React.ReactNode) => React.ReactNode;
declare function getGlobalIconPrefixCls(): string;
export interface GlobalConfigProps {
    prefixCls?: string;
    iconPrefixCls?: string;
    theme?: Theme | ThemeConfig;
    holderRender?: holderRenderType;
}
declare const setGlobalConfig: (props: GlobalConfigProps) => void;
export declare const globalConfig: () => {
    getPrefixCls: (suffixCls?: string, customizePrefixCls?: string) => string;
    getIconPrefixCls: typeof getGlobalIconPrefixCls;
    getRootPrefixCls: () => string;
    getTheme: () => ThemeConfig;
    holderRender: holderRenderType | undefined;
};
declare const ConfigProvider: React.FC<ConfigProviderProps> & {
    /** @private internal Usage. do not use in your production */
    ConfigContext: typeof ConfigContext;
    /** @deprecated Please use `ConfigProvider.useConfig().componentSize` instead */
    SizeContext: typeof SizeContext;
    config: typeof setGlobalConfig;
    useConfig: typeof useConfig;
};
export default ConfigProvider;
