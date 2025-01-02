//import { Calendar } from 'fullcalendar';
import { Calendar } from '@fullcalendar/core';
import calDeLocale from '@fullcalendar/core/locales/de';
import calDayGridPlugin from '@fullcalendar/daygrid'
import calListPlugin from '@fullcalendar/list';
import { createEvents} from 'ics';

import { BeeDates, TUBDates } from "./dates";
import { getDateParam } from "./helpers";

function renderBeeCalendar(id: string) {
  let date = getDateParam();
  let dates = new BeeDates(date);
  
  const calendarEl = document.getElementById(id);
  const calendar = new Calendar(calendarEl, {
    plugins: [calDayGridPlugin, calListPlugin],
    initialView: 'dayGridMonth',
    firstDay: 1,
    locale: calDeLocale,
    weekNumbers: true,
    validRange: {
      start: dates.startDate.toISO(),
      end: dates.endRange.toISO(),
    },
    headerToolbar: {
      start: 'title',
      center: '',
      end: 'today prev,next dayGridMonth,listYear'
    },
    events: [
    {
      title: 'Start (X)',
      start: dates.startDate.toISO(),
      allDay: true,
    },
    {
      title: 'Kö schlüpft (X+11)',
      start: dates.schlupfDate.toISO(),
      allDay: true,
    },
    {
      title: 'Kö in Eilage (X+18)',
      start: dates.eilageDate.toISO(),
      allDay: true,
    },
    {
      title: 'brutfrei (X+21)',
      start: dates.brutfreiDate.toISO(),
      allDay: true,
    },
    {
      title: 'verdeckelt (X+28)',
      start: dates.verdeckeltDate.toISO(),
      allDay: true,
    },
    {
      title: 'Jungbienen (X+39)',
      start: dates.jungbienenDate.toISO(),
      allDay: true,
    },
    {
      start: dates.brutfreiDate.toISO(),
      end: dates.verdeckeltDate.toISO(),
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
      start: dates.startDate.toISO(),
      allDay: true,
    },
    {
      title: 'Fl gebildet (X+2)',
      start: dates.fBehandelnDate.toISO(),
      allDay: true,
    },
    {
      title: 'Fl verdeckelt (X+9)',
      start: dates.fVerdeckelt.toISO(),
      allDay: true,
    },
    {
      title: 'BV brutfrei (X+21)',
      start: dates.bBrutfreiDate.toISO(),
      allDay: true,
    },
    {
      title: 'BV verdeckelt (X+28)',
      start: dates.bVerdeckeltDate.toISO(),
      allDay: true,
    },
    {
      title: 'Fl brutfrei',
      start: dates.fBehandelnDate.toISO(),
      end: dates.fVerdeckelt.toISO(),
      allDay: true,
      display: 'background',
    },
    {
      title: 'BV brutfrei',
      start: dates.bBrutfreiDate.toISO(),
      end: dates.bVerdeckeltDate.toISO(),
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
  const calendar = new Calendar(calendarEl, {
    plugins: [calDayGridPlugin, calListPlugin],
    initialView: 'dayGridMonth',
    firstDay: 1,
    locale: calDeLocale,
    weekNumbers: true,
    validRange: {
      start: dates.startDate.toISO(),
      end: dates.endRange.toISO(),
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


function genICS(events, filename: string) {
  return async function () {
    const file = await new Promise((resolve, reject) => {
        resolve(new File([events], filename, { type: 'text/calendar' }))
      })

    const url = URL.createObjectURL(file);

    // trying to assign the file URL to a window could cause cross-site
    // issues so this is a workaround using HTML5
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = filename;

    document.body.appendChild(anchor);
    anchor.click();
    document.body.removeChild(anchor);

    URL.revokeObjectURL(url);
  }
}

function genTUB_ICS() {
  let date = getDateParam();
  let rawEvents = getTUBEvents();
  let events = [];

  for ( const rawEvent of rawEvents) {
    let event = {
      title: rawEvent.title,
      start: rawEvent.start,
      end: rawEvent.start,
    }

    events.push(event);
  }

  const { error, value } = createEvents(events);

  if (error) {
    console.log(error)
    return
  }

  document.getElementById("dowloadICS").onclick=async function() {
    await genICS(value, "tub-events.ics")();
  };
}

export { renderBeeCalendar, renderTUBCalendar, genTUB_ICS };