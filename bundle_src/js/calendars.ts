import { Calendar, EventSourceInput } from '@fullcalendar/core';
import calDeLocale from '@fullcalendar/core/locales/de';
import calDayGridPlugin from '@fullcalendar/daygrid'
import calListPlugin from '@fullcalendar/list';
import bootstrap5Plugin from '@fullcalendar/bootstrap5';
import { DateTime } from 'luxon';

import { BeeDates, TUBDates, ZuchtDates } from "./dates";

function getCalender(calElement: HTMLElement, events: Object[], startDate: DateTime, endRange: DateTime): Calendar {
    return new Calendar(calElement, {
      plugins: [calDayGridPlugin, calListPlugin, bootstrap5Plugin],
      themeSystem: 'bootstrap5',
      initialView: 'dayGridMonth',
      firstDay: 1,
      locale: calDeLocale,
      // weekNumbers: true,
      validRange: {
        start: startDate.toISODate()!,
        end: endRange.toISODate()!
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
  startDate: DateTime;
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

    this.startDate = DateTime.fromISO(this.dateInput.value);
    this.calendar = null;
  }

  abstract render(): void;

  registerSubmitHandler() {
    this.formElement.addEventListener("submit", event => {
      event.preventDefault();

      let date = DateTime.now().toLocal();
      if (this.dateInput.value !== "") {
        date = DateTime.fromISO(this.dateInput.value).toLocal() as DateTime<true>;
      }

      this.startDate = date;
      this.render();

      const url = new URL(window.location.href);
      url.searchParams.set("date", date.toISODate()!);
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
        classNames: ["fst-italic"]
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
        classNames: ["fst-italic"]
      },
      {
        title: 'Jungbienen (X+39)',
        start: dates.jungbienenDate.toISODate()!,
        allDay: true,
        color: "gray",
        classNames: ["fst-italic"]
      },
      {
        start: dates.brutfreiDate.toISODate()!,
        end: dates.verdeckeltDate.toISODate()!,
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
        title: 'BV Kö schlüpft (X+11)',
        start: dates.bSchlupfDate.toISODate()!,
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
        color: "gray",
        classNames: ["fst-italic"]
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
        start: dates.startDate.toISODate()!,
        allDay: true,
      },
      {
        title: 'WZ brechen (X+9)',
        start: dates.wzBrechenDate.toISODate()!,
        allDay: true,
      },
      {
        title: 'ZL geben (X+9)',
        start: dates.wzBrechenDate.toISODate()!,
        allDay: true,
      },
      {
        title: 'verschulen (X+19)',
        start: dates.verschulenDate.toISODate()!,
        allDay: true,
      },
      {
        title: 'Kö schlüpft (X+20)',
        start: dates.schlupfDate.toISODate()!,
        allDay: true,
        color: "gray",
        classNames: ["fst-italic"]
      },
      {
        title: 'PV auflösen (X+21)',
        start: dates.pvAufloesenDate.toISODate()!,
        allDay: true,
      },
      {
        title: 'WZ verdeckelt',
        start: dates.wzVerdeckelt.toISODate()!,
        end: dates.schlupfDate.toISODate()!,
        allDay: true,
        display: 'background',
      },
      {
        title: 'Kö geschlechtsreif (X+27)',
        start: dates.köGeschlechtsreif.toISODate()!,
        allDay: true,
        color: "gray",
        classNames: ["fst-italic"]
      },
      {
        title: 'Kö in Eilage (X+28)',
        start: dates.köEilage.toISODate()!,
        allDay: true,
        color: "gray",
        classNames: ["fst-italic"]
      },
      {
        title: 'Brut verdeckelt (X+37)',
        start: dates.brutVerdeckelt.toISODate()!,
        allDay: true,
        color: "gray",
        classNames: ["fst-italic"]
      },
      {
        title: 'Jungbienen (X+49)',
        start: dates.jungbienen.toISODate()!,
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
