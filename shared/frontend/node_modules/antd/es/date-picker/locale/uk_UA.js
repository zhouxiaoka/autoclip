import CalendarLocale from "rc-picker/es/locale/uk_UA";
import TimePickerLocale from '../../time-picker/locale/uk_UA';
// Merge into a locale object
const locale = {
  lang: Object.assign({
    placeholder: 'Оберіть дату',
    yearPlaceholder: 'Оберіть рік',
    quarterPlaceholder: 'Оберіть квартал',
    monthPlaceholder: 'Оберіть місяць',
    weekPlaceholder: 'Оберіть тиждень',
    rangePlaceholder: ['Початкова дата', 'Кінцева дата'],
    rangeYearPlaceholder: ['Початковий рік', 'Кінцевий рік'],
    rangeMonthPlaceholder: ['Початковий місяць', 'Кінцевий місяць'],
    rangeWeekPlaceholder: ['Початковий тиждень', 'Кінцевий тиждень'],
    shortWeekDays: ['Нд', 'Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб'],
    shortMonths: ['Січ', 'Лют', 'Бер', 'Кві', 'Тра', 'Чер', 'Лип', 'Сер', 'Вер', 'Жов', 'Лис', 'Гру']
  }, CalendarLocale),
  timePickerLocale: Object.assign({}, TimePickerLocale)
};
// All settings at:
// https://github.com/ant-design/ant-design/blob/master/components/date-picker/locale/example.json
export default locale;