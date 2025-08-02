import _objectSpread from "@babel/runtime/helpers/esm/objectSpread2";
import { commonLocale } from "./common";
var locale = _objectSpread(_objectSpread({}, commonLocale), {}, {
  locale: 'ru_RU',
  today: 'Сегодня',
  now: 'Сейчас',
  backToToday: 'Текущая дата',
  ok: 'ОК',
  clear: 'Очистить',
  week: 'Неделя',
  month: 'Месяц',
  year: 'Год',
  timeSelect: 'Выбрать время',
  dateSelect: 'Выбрать дату',
  monthSelect: 'Выбрать месяц',
  yearSelect: 'Выбрать год',
  decadeSelect: 'Выбрать десятилетие',
  dateFormat: 'D-M-YYYY',
  dateTimeFormat: 'D-M-YYYY HH:mm:ss',
  previousMonth: 'Предыдущий месяц (PageUp)',
  nextMonth: 'Следующий месяц (PageDown)',
  previousYear: 'Предыдущий год (Control + left)',
  nextYear: 'Следующий год (Control + right)',
  previousDecade: 'Предыдущее десятилетие',
  nextDecade: 'Следущее десятилетие',
  previousCentury: 'Предыдущий век',
  nextCentury: 'Следующий век'
});
export default locale;