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
    const selector = `#${containerId}-date-input`;
    const input = document.querySelector<HTMLInputElement>(selector);
    if (!input) {
        throw new Error(`Date input element ${selector} not found`);
    }
    input.value = getDateParam().toString();

    const form = document.querySelector<HTMLFormElement>(`#${containerId}-date-form`);
    form?.addEventListener("change", () => {
        form.requestSubmit();
    });

    const cal = new CalendarClass(containerId);
    cal.render();
    cal.registerSubmitHandler();
}

export function initAllCalendarWidgets() {
    const widgets = document.querySelectorAll<HTMLElement>('.calendar-widget-container');

    widgets.forEach(container => {
        try {
            const type = container.dataset.widgetType;
            const calendarClass = type ? CALENDAR_REGISTRY[type] : undefined;
            if (!calendarClass) {
                throw new Error(`Unknown calendar widget type: ${type}`);
            }

            renderCalendarWidget(container.id, calendarClass);
        } catch (error) {
            console.error(`Failed to initialize calendar widget #${container.id}:`, error);
        }
    });
}
