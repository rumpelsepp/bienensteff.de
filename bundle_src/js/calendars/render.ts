import { BaseCalendar, BeeStatesCalendar, TUBCalendar, ZuchtCalendar } from "./calendars";
import { getDateParam } from "../helpers";

const CALENDAR_REGISTRY: Record<string, new (id: string) => BaseCalendar> = {
    "zucht": ZuchtCalendar,
    "beestate": BeeStatesCalendar,
    "tub": TUBCalendar,
};

function renderCalendarWidget(
    containerId: string,
    CalendarClass: new (id: string) => BaseCalendar
) {
    const selector = `#${containerId} #date-input`;
    const input = document.querySelector<HTMLInputElement>(selector)!;
    input.value = getDateParam().toString();

    const cal = new CalendarClass(containerId);
    cal.render();
    cal.registerSubmitHandler();
}

export function initAllCalendarWidgets() {
    const widgets = document.querySelectorAll<HTMLElement>('.calendar-widget-container');

    widgets.forEach(container => {
        const type = container.dataset.widgetType!;
        const calendarClass = CALENDAR_REGISTRY[type]!;

        renderCalendarWidget(container.id, calendarClass);
    });
}
