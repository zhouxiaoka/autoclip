import _objectSpread from "@babel/runtime/helpers/esm/objectSpread2";
import { commonLocale } from "./common";
var locale = _objectSpread(_objectSpread({}, commonLocale), {}, {
  locale: 'bg_BG',
  today: 'Днес',
  now: 'Сега',
  backToToday: 'Към днес',
  ok: 'Добре',
  clear: 'Изчистване',
  week: 'Седмица',
  month: 'Месец',
  year: 'Година',
  timeSelect: 'Избор на час',
  dateSelect: 'Избор на дата',
  monthSelect: 'Избор на месец',
  yearSelect: 'Избор на година',
  decadeSelect: 'Десетилетие',
  dateFormat: 'D M YYYY',
  dateTimeFormat: 'D M YYYY HH:mm:ss',
  previousMonth: 'Предишен месец (PageUp)',
  nextMonth: 'Следващ месец (PageDown)',
  previousYear: 'Последна година (Control + left)',
  nextYear: 'Следваща година (Control + right)',
  previousDecade: 'Предишно десетилетие',
  nextDecade: 'Следващо десетилетие',
  previousCentury: 'Последен век',
  nextCentury: 'Следващ век'
});
export default locale;