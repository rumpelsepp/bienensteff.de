import { DateTime } from "luxon";
import 'sortable-tablesort/sortable.min.js';
//import { Calendar } from 'fullcalendar';
import { Calendar } from '@fullcalendar/core';
import calDeLocale from '@fullcalendar/core/locales/de';
import calDayGridPlugin from '@fullcalendar/daygrid'
import calListPlugin from '@fullcalendar/list';

function getParam(name: string): string {
  const urlParams = new URLSearchParams(window.location.search);
  return urlParams.get(name);
}

function getDateParam(): DateTime {
  const dateParam = getParam("date");

  if (dateParam != null) {
    return DateTime.fromISO(dateParam).toLocal();
  }
  return DateTime.now().toLocal();
}

export { AnalysisTable } from "./beetable";
export { DataTable } from "./beetable";
export { Beetable } from "./beetable";
export { TUBTable } from "./beetable";
export { DateTime } from "luxon";
export { getDateParam };
export { getParam };

export { Calendar, calDeLocale, calDayGridPlugin, calListPlugin };