import Group from './Group';
import InternalInput from './Input';
import OTP from './OTP';
import Password from './Password';
import Search from './Search';
import TextArea from './TextArea';
export type { GroupProps } from './Group';
export type { InputProps, InputRef } from './Input';
export type { PasswordProps } from './Password';
export type { SearchProps } from './Search';
export type { TextAreaProps } from './TextArea';
type CompoundedComponent = typeof InternalInput & {
    /** @deprecated Please use `Space.Compact` */
    Group: typeof Group;
    Search: typeof Search;
    TextArea: typeof TextArea;
    Password: typeof Password;
    OTP: typeof OTP;
};
declare const Input: CompoundedComponent;
export default Input;
