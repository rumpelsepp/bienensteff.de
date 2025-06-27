import { Calendar } from '@fullcalendar/core';
import calDeLocale from '@fullcalendar/core/locales/de';
import calDayGridPlugin from '@fullcalendar/daygrid'
import calListPlugin from '@fullcalendar/list';
import bootstrap5Plugin from '@fullcalendar/bootstrap5';

import { BeeDates, TUBDates } from "./dates";
import { getDateParam } from "./helpers";

function renderBeeCalendar(id: string) {
  let date = getDateParam();
  let dates = new BeeDates(date);

  const calendarEl = document.getElementById(id);
  if (!calendarEl) {
    throw new Error(`Calendar element with id ${id} not found.`);
  }

  const calendar = new Calendar(calendarEl, {
    plugins: [calDayGridPlugin, calListPlugin, bootstrap5Plugin],
    themeSystem: 'bootstrap5',
    initialView: 'dayGridMonth',
    firstDay: 1,
    locale: calDeLocale,
    // weekNumbers: true,
    validRange: {
      start: dates.startDate.toISODate()!,
      end: dates.endRange.toISODate()!
    },
    headerToolbar: {
      start: 'title',
      center: '',
      end: 'today prev,next dayGridMonth,listYear'
    },
    events: [
    {
      title: 'Start (X)',
      start: dates.startDate.toISODate()!,
      allDay: true,
    },
    {
      title: 'Kö schlüpft (X+11)',
      start: dates.schlupfDate.toISODate()!,
      allDay: true,
    },
    {
      title: 'Kö geschlechtsreif (X+18)',
      start: dates.gReifDate.toISODate()!,
      allDay: true,
    },
    {
      title: 'Kö in Eilage (X+19)',
      start: dates.eilageDate.toISODate()!,
      allDay: true,
      color: "gray",
    },
    {
      title: 'brutfrei (X+21)',
      start: dates.brutfreiDate.toISODate()!,
      allDay: true,
    },
    {
      title: 'verdeckelt (X+28)',
      start: dates.verdeckeltDate.toISODate()!,
      allDay: true,
      color: "gray",
    },
    {
      title: 'Jungbienen (X+39)',
      start: dates.jungbienenDate.toISODate()!,
      allDay: true,
      color: "gray",
    },
    {
      start: dates.brutfreiDate.toISODate()!,
      end: dates.verdeckeltDate.toISODate()!,
      allDay: true,
      display: 'background',
    }
  ]
  })
  calendar.render()
}

function getTUBEvents() {
  let date = getDateParam();
  let dates = new TUBDates(date);
  let events = [
    {
      title: 'Start (X)',
      start: dates.startDate.toISODate()!,
      allDay: true,
    },
    {
      title: 'Fl gebildet (X+2)',
      start: dates.fBehandelnDate.toISODate()!,
      allDay: true,
    },
    {
      title: 'Fl verdeckelt (X+9)',
      start: dates.fVerdeckelt.toISODate()!,
      allDay: true,
    },
    {
      title: 'BV brutfrei (X+21)',
      start: dates.bBrutfreiDate.toISODate()!,
      allDay: true,
    },
    {
      title: 'BV verdeckelt (X+28)',
      start: dates.bVerdeckeltDate.toISODate()!,
      allDay: true,
    },
    {
      title: 'Fl brutfrei',
      start: dates.fBehandelnDate.toISODate()!,
      end: dates.fVerdeckelt.toISODate()!,
      allDay: true,
      display: 'background',
    },
    {
      title: 'BV brutfrei',
      start: dates.bBrutfreiDate.toISODate()!,
      end: dates.bVerdeckeltDate.toISODate()!,
      allDay: true,
      display: 'background',
    }
  ]
  
  return events;
}

function renderTUBCalendar(id: string) {
  let date = getDateParam();
  let dates = new TUBDates(date);
  
  const calendarEl = document.getElementById(id)
  if (!calendarEl) {
    throw new Error(`Calendar element with id ${id} not found.`);
  }

  const calendar = new Calendar(calendarEl, {
    plugins: [calDayGridPlugin, calListPlugin, bootstrap5Plugin],
    initialView: 'dayGridMonth',
    themeSystem: 'bootstrap5',
    firstDay: 1,
    locale: calDeLocale,
    // weekNumbers: true,
    validRange: {
      start: dates.startDate.toISODate()!,
      end: dates.endRange.toISODate()!,
    },
    headerToolbar: {
      start: 'title',
      center: '',
      end: 'today prev,next dayGridMonth,listYear'
    },
    events: getTUBEvents(),
  })

  calendar.render()
}

export { renderBeeCalendar, renderTUBCalendar };
