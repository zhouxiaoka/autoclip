"use client";

import Group from './Group';
import InternalInput from './Input';
import OTP from './OTP';
import Password from './Password';
import Search from './Search';
import TextArea from './TextArea';
const Input = InternalInput;
Input.Group = Group;
Input.Search = Search;
Input.TextArea = TextArea;
Input.Password = Password;
Input.OTP = OTP;
export default Input;