import _objectSpread from "@babel/runtime/helpers/esm/objectSpread2";
import { commonLocale } from "./common";
var locale = _objectSpread(_objectSpread({}, commonLocale), {}, {
  locale: 'ga_IE',
  today: 'inniu',
  now: 'anois',
  backToToday: 'Ar ais inniu',
  ok: 'ceart go leor',
  clear: 'soiléir',
  week: 'seachtain',
  month: 'mhí',
  year: 'bhliain',
  timeSelect: 'roghnaigh am',
  dateSelect: 'roghnaigh dáta',
  weekSelect: 'Roghnaigh seachtain',
  monthSelect: 'Roghnaigh mí',
  yearSelect: 'Roghnaigh bliain',
  decadeSelect: 'Roghnaigh deich mbliana',
  dateFormat: 'D/M/YYYY',
  dateTimeFormat: 'D/M/YYYY HH:mm:ss',
  previousMonth: 'An mhí roimhe seo (PageUp)',
  nextMonth: 'An mhí seo chugainn (PageDown)',
  previousYear: 'Anuraidh (Control + left)',
  nextYear: 'An bhliain seo chugainn (Control + right)',
  previousDecade: 'Le deich mbliana anuas',
  nextDecade: 'Deich mbliana amach romhainn',
  previousCentury: 'An chéid seo caite',
  nextCentury: 'An chéad aois eile'
});
export default locale;