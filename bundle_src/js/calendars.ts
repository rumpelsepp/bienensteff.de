import { Temporal } from '@js-temporal/polyfill';
import { Calendar, EventSourceInput } from '@fullcalendar/core';
import calDeLocale from '@fullcalendar/core/locales/de';
import calDayGridPlugin from '@fullcalendar/daygrid'
import calListPlugin from '@fullcalendar/list';
import bootstrap5Plugin from '@fullcalendar/bootstrap5';

import { BeeDates, TUBDates, ZuchtDates } from "./dates";

function getCalender(calElement: HTMLElement, events: Object[], startDate: Temporal.PlainDate, endRange: Temporal.PlainDate): Calendar {
  return new Calendar(calElement, {
    plugins: [calDayGridPlugin, calListPlugin, bootstrap5Plugin],
    themeSystem: 'bootstrap5',
    initialView: 'dayGridMonth',
    firstDay: 1,
    locale: calDeLocale,
    // weekNumbers: true,
    validRange: {
      start: startDate.toString()!,
      end: endRange.toString()!
    },
    headerToolbar: {
      start: 'title',
      center: '',
      end: 'today prev,next dayGridMonth,listYear'
    },
    events: events,
  });
}

abstract class BaseCalendar {
  formElement: HTMLFormElement;
  calElement: HTMLElement;
  dateInput: HTMLInputElement;
  startDate: Temporal.PlainDate;
  calendar: Calendar | null;

  constructor(widgetID: string) {
    const formElement = document.querySelector(`#${widgetID} #date-form`);
    if (formElement === null) {
      throw new Error(`Form element #${widgetID} #date-form not found`);
    }
    this.formElement = formElement as HTMLFormElement;

    const dateInput = document.querySelector(`#${widgetID} #date-form #date-input`);
    if (dateInput === null) {
      throw new Error(`Date input element #${widgetID} #date-form #date-input not found`);
    }
    this.dateInput = dateInput as HTMLInputElement;

    const calElement = document.querySelector(`#${widgetID} #calendar`);
    if (calElement === null) {
      throw new Error(`Calendar element #${widgetID} #calendar not found`);
    }
    this.calElement = calElement as HTMLElement;

    this.startDate = Temporal.PlainDate.from(this.dateInput.value);
    this.calendar = null;
  }

  abstract render(): void;

  registerSubmitHandler() {
    this.formElement.addEventListener("submit", event => {
      event.preventDefault();

      let date = Temporal.Now.plainDateISO();
      if (this.dateInput.value !== "") {
        date = Temporal.PlainDate.from(this.dateInput.value);
      }

      this.startDate = date;
      this.render();

      const url = new URL(window.location.href);
      url.searchParams.set("date", date.toString()!);
      history.replaceState(null, "", url);
    })
  }
}

class BeeStatesCalendar extends BaseCalendar {
  get events(): Object[] {
    const dates = new BeeDates(this.startDate);
    return [
      {
        title: 'Start (X)',
        start: dates.startDate.toString()!,
        allDay: true,
      },
      {
        title: 'Kö schlüpft (X+11)',
        start: dates.schlupfDate.toString()!,
        allDay: true,
      },
      {
        title: 'Kö geschlechtsreif (X+18)',
        start: dates.gReifDate.toString()!,
        allDay: true,
      },
      {
        title: 'Kö in Eilage (X+19)',
        start: dates.eilageDate.toString()!,
        allDay: true,
        color: "gray",
        classNames: ["fst-italic"]
      },
      {
        title: 'brutfrei (X+21)',
        start: dates.brutfreiDate.toString()!,
        allDay: true,
      },
      {
        title: 'verdeckelt (X+28)',
        start: dates.verdeckeltDate.toString()!,
        allDay: true,
        color: "gray",
        classNames: ["fst-italic"]
      },
      {
        title: 'Jungbienen (X+39)',
        start: dates.jungbienenDate.toString()!,
        allDay: true,
        color: "gray",
        classNames: ["fst-italic"]
      },
      {
        start: dates.brutfreiDate.toString()!,
        end: dates.verdeckeltDate.toString()!,
        allDay: true,
        display: 'background',
      }
    ]
  }

  render() {
    if (this.calendar !== null) {
      this.calendar.destroy();
      this.calendar = null;
    }

    const dates = new BeeDates(this.startDate);
    this.calendar = getCalender(this.calElement, this.events, dates.startDate, dates.endRange)
    this.calendar.render();
  }
}

class TUBCalendar extends BaseCalendar {
  get events(): Object[] {
    const dates = new TUBDates(this.startDate);

    return [
      {
        title: 'Start (X)',
        start: dates.startDate.toString()!,
        allDay: true,
      },
      {
        title: 'Fl gebildet (X+2)',
        start: dates.fBehandelnDate.toString()!,
        allDay: true,
      },
      {
        title: 'Fl verdeckelt (X+9)',
        start: dates.fVerdeckelt.toString()!,
        allDay: true,
      },
      {
        title: 'BV Kö schlüpft (X+11)',
        start: dates.bSchlupfDate.toString()!,
        allDay: true,
      },
      {
        title: 'BV brutfrei (X+21)',
        start: dates.bBrutfreiDate.toString()!,
        allDay: true,
      },
      {
        title: 'BV verdeckelt (X+28)',
        start: dates.bVerdeckeltDate.toString()!,
        allDay: true,
        color: "gray",
        classNames: ["fst-italic"]
      },
      {
        title: 'Fl brutfrei',
        start: dates.fBehandelnDate.toString()!,
        end: dates.fVerdeckelt.toString()!,
        allDay: true,
        display: 'background',
      },
      {
        title: 'BV brutfrei',
        start: dates.bBrutfreiDate.toString()!,
        end: dates.bVerdeckeltDate.toString()!,
        allDay: true,
        display: 'background',
      }
    ];
  }

  render() {
    if (this.calendar !== null) {
      this.calendar.destroy();
      this.calendar = null;
    }

    const dates = new TUBDates(this.startDate);

    this.calendar = getCalender(this.calElement, this.events, dates.startDate, dates.endRange)
    this.calendar.render()
  }

}

class ZuchtCalendar extends BaseCalendar {
  get events(): Object[] {
    const dates = new ZuchtDates(this.startDate);

    return [
      {
        title: 'Start (X)',
        start: dates.startDate.toString()!,
        allDay: true,
      },
      {
        title: 'WZ brechen (X+9)',
        start: dates.wzBrechenDate.toString()!,
        allDay: true,
      },
      {
        title: 'ZL geben (X+9)',
        start: dates.wzBrechenDate.toString()!,
        allDay: true,
      },
      {
        title: 'verschulen (X+19)',
        start: dates.verschulenDate.toString()!,
        allDay: true,
      },
      {
        title: 'Kö schlüpft (X+20)',
        start: dates.schlupfDate.toString()!,
        allDay: true,
        color: "gray",
        classNames: ["fst-italic"]
      },
      {
        title: 'PV auflösen (X+21)',
        start: dates.pvAufloesenDate.toString()!,
        allDay: true,
      },
      {
        title: 'WZ verdeckelt',
        start: dates.wzVerdeckelt.toString()!,
        end: dates.schlupfDate.toString()!,
        allDay: true,
        display: 'background',
      },
      {
        title: 'Kö geschlechtsreif (X+27)',
        start: dates.köGeschlechtsreif.toString()!,
        allDay: true,
        color: "gray",
        classNames: ["fst-italic"]
      },
      {
        title: 'Kö in Eilage (X+28)',
        start: dates.köEilage.toString()!,
        allDay: true,
        color: "gray",
        classNames: ["fst-italic"]
      },
      {
        title: 'Brut verdeckelt (X+37)',
        start: dates.brutVerdeckelt.toString()!,
        allDay: true,
        color: "gray",
        classNames: ["fst-italic"]
      },
      {
        title: 'Jungbienen (X+49)',
        start: dates.jungbienen.toString()!,
        allDay: true,
        color: "gray",
        classNames: ["fst-italic"]
      },
    ];
  }

  render() {
    if (this.calendar !== null) {
      this.calendar.destroy();
      this.calendar = null;
    }

    const dates = new ZuchtDates(this.startDate);

    this.calendar = getCalender(this.calElement, this.events, dates.startDate, dates.endRange)
    this.calendar.render()
  }

}

export { BeeStatesCalendar, TUBCalendar, ZuchtCalendar };
