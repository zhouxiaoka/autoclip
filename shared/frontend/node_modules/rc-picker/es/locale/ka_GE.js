import _objectSpread from "@babel/runtime/helpers/esm/objectSpread2";
import { commonLocale } from "./common";
var locale = _objectSpread(_objectSpread({}, commonLocale), {}, {
  locale: 'ka_GE',
  today: 'დღეს',
  now: 'ახლა',
  backToToday: 'მიმდინარე თარიღი',
  ok: 'OK',
  clear: 'გასუფთავება',
  week: 'კვირა',
  month: 'თვე',
  year: 'წელი',
  timeSelect: 'დროის არჩევა',
  dateSelect: 'თარიღის არჩევა',
  weekSelect: 'კვირის არჩევა',
  monthSelect: 'თვის არჩევა',
  yearSelect: 'წლის არჩევა',
  decadeSelect: 'ათწლეულის არჩევა',
  dateFormat: 'M/D/YYYY',
  dateTimeFormat: 'M/D/YYYY HH:mm:ss',
  previousMonth: 'წინა თვე (PageUp)',
  nextMonth: 'მომდევნო თვე (PageDown)',
  previousYear: 'წინა წელი (Control + left)',
  nextYear: 'მომდევნო წელი (Control + right)',
  previousDecade: 'წინა ათწლეული',
  nextDecade: 'მომდევნო ათწლეული',
  previousCentury: 'გასული საუკუნე',
  nextCentury: 'მომდევნო საუკუნე'
});
export default locale;