import type { Components } from 'rc-picker/lib/interface';
export default function useComponents(components?: Components): {
    time?: React.ComponentType<import("rc-picker/lib/interface").SharedPanelProps<any>> | undefined;
    date?: React.ComponentType<import("rc-picker/lib/interface").SharedPanelProps<any>> | undefined;
    week?: React.ComponentType<import("rc-picker/lib/interface").SharedPanelProps<any>> | undefined;
    month?: React.ComponentType<import("rc-picker/lib/interface").SharedPanelProps<any>> | undefined;
    quarter?: React.ComponentType<import("rc-picker/lib/interface").SharedPanelProps<any>> | undefined;
    year?: React.ComponentType<import("rc-picker/lib/interface").SharedPanelProps<any>> | undefined;
    decade?: React.ComponentType<import("rc-picker/lib/interface").SharedPanelProps<any>> | undefined;
    datetime?: React.ComponentType<import("rc-picker/lib/interface").SharedPanelProps<any>> | undefined;
    button: string | React.ComponentClass<any, any> | React.FC<Readonly<import("../..").ButtonProps>>;
    input?: React.ComponentType<any> | string;
};
