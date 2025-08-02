import _objectSpread from "@babel/runtime/helpers/esm/objectSpread2";
import { commonLocale } from "./common";
var locale = _objectSpread(_objectSpread({}, commonLocale), {}, {
  locale: 'is_IS',
  today: 'Í dag',
  now: 'Núna',
  backToToday: 'Til baka til dagsins í dag',
  ok: 'Í lagi',
  clear: 'Hreinsa',
  week: 'Vika',
  month: 'Mánuður',
  year: 'Ár',
  timeSelect: 'Velja tíma',
  dateSelect: 'Velja dag',
  monthSelect: 'Velja mánuð',
  yearSelect: 'Velja ár',
  decadeSelect: 'Velja áratug',
  dateFormat: 'D/M/YYYY',
  dateTimeFormat: 'D/M/YYYY HH:mm:ss',
  previousMonth: 'Fyrri mánuður (PageUp)',
  nextMonth: 'Næsti mánuður (PageDown)',
  previousYear: 'Fyrra ár (Control + left)',
  nextYear: 'Næsta ár (Control + right)',
  previousDecade: 'Fyrri áratugur',
  nextDecade: 'Næsti áratugur',
  previousCentury: 'Fyrri öld',
  nextCentury: 'Næsta öld'
});
export default locale;