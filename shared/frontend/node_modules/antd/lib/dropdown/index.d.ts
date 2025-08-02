import InternalDropdown from './dropdown';
import DropdownButton from './dropdown-button';
export type { DropdownProps as DropDownProps, DropdownProps } from './dropdown';
export type { DropdownButtonProps, DropdownButtonType } from './dropdown-button';
declare const Dropdown: typeof InternalDropdown & {
    Button: typeof DropdownButton;
};
export default Dropdown;
