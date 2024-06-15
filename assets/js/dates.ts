import { DateTime } from "luxon";

class BeeDatesBase {
  startDate: DateTime;
  endRange: DateTime;

  constructor(date: DateTime | Date) {
    if (date instanceof Date) {
      this.startDate = DateTime.fromJSDate(date);
    } else {
      this.startDate = date;
    }
  }
}

class BeeDates extends BeeDatesBase {
  schlupfDate: DateTime;
  eilageDate: DateTime;
  brutfreiDate: DateTime;
  verdeckeltDate: DateTime;
  jungbienenDate: DateTime;

  constructor(date: DateTime | Date) {
    super(date);
    
    this.schlupfDate = this.startDate.plus({days: 11});;
    this.eilageDate = this.schlupfDate.plus({days: 8});
    this.brutfreiDate = this.startDate.plus({days: 21});
    this.verdeckeltDate = this.eilageDate.plus({days: 9});
    this.jungbienenDate = this.eilageDate.plus({days: 21});
    this.endRange = this.eilageDate.plus({days: 22});
  }
}

class TUBDates extends BeeDatesBase {
  fBehandelnDate: DateTime;
  fVerdeckelt: DateTime;
  bBrutfreiDate: DateTime;
  bVerdeckeltDate: DateTime;

  constructor(date: DateTime) {
    super(date);
    
    this.fBehandelnDate = date.plus({days: 2});
    this.fVerdeckelt = date.plus({days: 9});
    this.bBrutfreiDate = date.plus({days: 21});
    this.bVerdeckeltDate = date.plus({days: 28});
    this.endRange = date.plus({days: 29});
  }
}

export { BeeDates, TUBDates };