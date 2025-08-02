import _objectSpread from "@babel/runtime/helpers/esm/objectSpread2";
import { commonLocale } from "./common";
var locale = _objectSpread(_objectSpread({}, commonLocale), {}, {
  locale: 'fa_IR',
  today: 'امروز',
  now: 'اکنون',
  backToToday: 'بازگشت به روز',
  ok: 'باشه',
  clear: 'پاک کردن',
  week: 'هفته',
  month: 'ماه',
  year: 'سال',
  timeSelect: 'انتخاب زمان',
  dateSelect: 'انتخاب تاریخ',
  monthSelect: 'یک ماه را انتخاب کنید',
  yearSelect: 'یک سال را انتخاب کنید',
  decadeSelect: 'یک دهه را انتخاب کنید',
  dateFormat: 'M/D/YYYY',
  dateTimeFormat: 'M/D/YYYY HH:mm:ss',
  previousMonth: 'ماه قبل (PageUp)',
  nextMonth: 'ماه بعد (PageDown)',
  previousYear: 'سال قبل (Control + left)',
  nextYear: 'سال بعد (Control + right)',
  previousDecade: 'دهه قبل',
  nextDecade: 'دهه بعد',
  previousCentury: 'قرن قبل',
  nextCentury: 'قرن بعد'
});
export default locale;