import * as React from 'react';
export declare const IconMap: {
    success: React.ForwardRefExoticComponent<Omit<import("@ant-design/icons/lib/components/AntdIcon").AntdIconProps, "ref"> & React.RefAttributes<HTMLSpanElement>>;
    error: React.ForwardRefExoticComponent<Omit<import("@ant-design/icons/lib/components/AntdIcon").AntdIconProps, "ref"> & React.RefAttributes<HTMLSpanElement>>;
    info: React.ForwardRefExoticComponent<Omit<import("@ant-design/icons/lib/components/AntdIcon").AntdIconProps, "ref"> & React.RefAttributes<HTMLSpanElement>>;
    warning: React.ForwardRefExoticComponent<Omit<import("@ant-design/icons/lib/components/AntdIcon").AntdIconProps, "ref"> & React.RefAttributes<HTMLSpanElement>>;
};
export declare const ExceptionMap: {
    '404': React.FC<{}>;
    '500': React.FC<{}>;
    '403': React.FC<{}>;
};
export type ExceptionStatusType = 403 | 404 | 500 | '403' | '404' | '500';
export type ResultStatusType = ExceptionStatusType | keyof typeof IconMap;
export interface ResultProps {
    icon?: React.ReactNode;
    status?: ResultStatusType;
    title?: React.ReactNode;
    subTitle?: React.ReactNode;
    extra?: React.ReactNode;
    prefixCls?: string;
    className?: string;
    rootClassName?: string;
    style?: React.CSSProperties;
    children?: React.ReactNode;
}
export interface ResultType extends React.FC<ResultProps> {
    PRESENTED_IMAGE_404: React.FC;
    PRESENTED_IMAGE_403: React.FC;
    PRESENTED_IMAGE_500: React.FC;
}
declare const Result: ResultType;
export default Result;
