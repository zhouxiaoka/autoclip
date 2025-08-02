import _objectSpread from "@babel/runtime/helpers/esm/objectSpread2";
import { commonLocale } from "./common";
var locale = _objectSpread(_objectSpread({}, commonLocale), {}, {
  locale: 'sv_SE',
  today: 'I dag',
  now: 'Nu',
  backToToday: 'Till idag',
  ok: 'OK',
  clear: 'Avbryt',
  week: 'Vecka',
  month: 'Månad',
  year: 'År',
  timeSelect: 'Välj tidpunkt',
  dateSelect: 'Välj datum',
  monthSelect: 'Välj månad',
  yearSelect: 'Välj år',
  decadeSelect: 'Välj årtionde',
  dateFormat: 'YYYY-MM-DD',
  dateTimeFormat: 'YYYY-MM-DD H:mm:ss',
  previousMonth: 'Förra månaden (PageUp)',
  nextMonth: 'Nästa månad (PageDown)',
  previousYear: 'Föreg år (Control + left)',
  nextYear: 'Nästa år (Control + right)',
  previousDecade: 'Föreg årtionde',
  nextDecade: 'Nästa årtionde',
  previousCentury: 'Föreg århundrade',
  nextCentury: 'Nästa århundrade'
});
export default locale;