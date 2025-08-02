import _objectSpread from "@babel/runtime/helpers/esm/objectSpread2";
import { commonLocale } from "./common";
var locale = _objectSpread(_objectSpread({}, commonLocale), {}, {
  locale: 'uk_UA',
  today: 'Сьогодні',
  now: 'Зараз',
  backToToday: 'Поточна дата',
  ok: 'OK',
  clear: 'Очистити',
  week: 'Тиждень',
  month: 'Місяць',
  year: 'Рік',
  timeSelect: 'Обрати час',
  dateSelect: 'Обрати дату',
  monthSelect: 'Обрати місяць',
  yearSelect: 'Обрати рік',
  decadeSelect: 'Обрати десятиріччя',
  dateFormat: 'D-M-YYYY',
  dateTimeFormat: 'D-M-YYYY HH:mm:ss',
  previousMonth: 'Попередній місяць (PageUp)',
  nextMonth: 'Наступний місяць (PageDown)',
  previousYear: 'Попередній рік (Control + left)',
  nextYear: 'Наступний рік (Control + right)',
  previousDecade: 'Попереднє десятиріччя',
  nextDecade: 'Наступне десятиріччя',
  previousCentury: 'Попереднє століття',
  nextCentury: 'Наступне століття'
});
export default locale;