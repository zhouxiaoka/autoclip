import _objectSpread from "@babel/runtime/helpers/esm/objectSpread2";
import { commonLocale } from "./common";
var locale = _objectSpread(_objectSpread({}, commonLocale), {}, {
  locale: 'sl_SI',
  today: 'Danes',
  now: 'Trenutno',
  backToToday: 'Nazaj na danes',
  ok: 'V redu',
  clear: 'Počisti',
  week: 'Teden',
  month: 'Mesec',
  year: 'Leto',
  timeSelect: 'Izberite čas',
  dateSelect: 'Izberite datum',
  monthSelect: 'Izberite mesec',
  yearSelect: 'Izberite leto',
  decadeSelect: 'Izberite desetletje',
  dateFormat: 'DD.MM.YYYY',
  dateTimeFormat: 'DD.MM.YYYY HH:mm:ss',
  previousMonth: 'Prejšnji mesec (PageUp)',
  nextMonth: 'Naslednji mesec (PageDown)',
  previousYear: 'Prejšnje leto (Control + left)',
  nextYear: 'Naslednje leto (Control + right)',
  previousDecade: 'Prejšnje desetletje',
  nextDecade: 'Naslednje desetletje',
  previousCentury: 'Prejšnje stoletje',
  nextCentury: 'Naslednje stoletje'
});
export default locale;