import _objectSpread from "@babel/runtime/helpers/esm/objectSpread2";
import { commonLocale } from "./common";
var locale = _objectSpread(_objectSpread({}, commonLocale), {}, {
  locale: 'kk_KZ',
  today: 'Бүгін',
  now: 'Қазір',
  backToToday: 'Ағымдағы күн',
  ok: 'Таңдау',
  clear: 'Таза',
  week: 'Апта',
  month: 'Ай',
  year: 'Жыл',
  timeSelect: 'Уақытты таңдау',
  dateSelect: 'Күнді таңдау',
  monthSelect: 'Айды таңдаңыз',
  yearSelect: 'Жылды таңдаңыз',
  decadeSelect: 'Онжылды таңдаңыз',
  dateFormat: 'D-M-YYYY',
  dateTimeFormat: 'D-M-YYYY HH:mm:ss',
  previousMonth: 'Алдыңғы ай (PageUp)',
  nextMonth: 'Келесі ай (PageDown)',
  previousYear: 'Алдыңғы жыл (Control + left)',
  nextYear: 'Келесі жыл (Control + right)',
  previousDecade: 'Алдыңғы онжылдық',
  nextDecade: 'Келесі онжылдық',
  previousCentury: 'Алдыңғы ғасыр',
  nextCentury: 'Келесі ғасыр'
});
export default locale;