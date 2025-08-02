import any from "./any";
import array from "./array";
import boolean from "./boolean";
import date from "./date";
import enumValidator from "./enum";
import float from "./float";
import integer from "./integer";
import method from "./method";
import number from "./number";
import object from "./object";
import pattern from "./pattern";
import regexp from "./regexp";
import required from "./required";
import string from "./string";
import type from "./type";
export default {
  string: string,
  method: method,
  number: number,
  boolean: boolean,
  regexp: regexp,
  integer: integer,
  float: float,
  array: array,
  object: object,
  enum: enumValidator,
  pattern: pattern,
  date: date,
  url: type,
  hex: type,
  email: type,
  required: required,
  any: any
};