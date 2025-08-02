import _objectSpread from "@babel/runtime/helpers/esm/objectSpread2";
import { commonLocale } from "./common";
var locale = _objectSpread(_objectSpread({}, commonLocale), {}, {
  locale: 'by_BY',
  today: 'Сёння',
  now: 'Зараз',
  backToToday: 'Дадзеная дата',
  ok: 'OK',
  clear: 'Ачысціць',
  week: 'Тыдзень',
  month: 'Месяц',
  year: 'Год',
  timeSelect: 'Выбраць час',
  dateSelect: 'Выбраць дату',
  weekSelect: 'Выбраць тыдзень',
  monthSelect: 'Выбраць месяц',
  yearSelect: 'Выбраць год',
  decadeSelect: 'Выбраць дзесяцігоддзе',
  dateFormat: 'D-M-YYYY',
  dateTimeFormat: 'D-M-YYYY HH:mm:ss',
  previousMonth: 'Папярэдні месяц (PageUp)',
  nextMonth: 'Наступны месяц (PageDown)',
  previousYear: 'Папярэдні год (Control + left)',
  nextYear: 'Наступны год (Control + right)',
  previousDecade: 'Папярэдняе дзесяцігоддзе',
  nextDecade: 'Наступнае дзесяцігоддзе',
  previousCentury: 'Папярэдні век',
  nextCentury: 'Наступны век'
});
export default locale;