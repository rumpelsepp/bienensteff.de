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
    
    // Make the type checker happy.
    this.endRange = this.startDate;
  }
}

class BeeDates extends BeeDatesBase {
  schlupfDate: DateTime;
  gReifDate: DateTime;
  eilageDate: DateTime;
  brutfreiDate: DateTime;
  verdeckeltDate: DateTime;
  jungbienenDate: DateTime;

  constructor(date: DateTime | Date) {
    super(date);
    
    this.schlupfDate = this.startDate.plus({days: 11});;
    this.gReifDate = this.schlupfDate.plus({days: 7});
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
  bSchlupfDate: DateTime;
  bBrutfreiDate: DateTime;
  bVerdeckeltDate: DateTime;

  constructor(date: DateTime) {
    super(date);
    
    this.fBehandelnDate = date.plus({days: 2});
    this.fVerdeckelt = date.plus({days: 9});
    this.bSchlupfDate = this.startDate.plus({days: 11});;
    this.bBrutfreiDate = date.plus({days: 21});
    this.bVerdeckeltDate = date.plus({days: 28});
    this.endRange = date.plus({days: 29});
  }
}

class ZuchtDates extends BeeDatesBase {
  wzBrechenDate: DateTime;
  wzVerdeckelt: DateTime;
  verschulenDate: DateTime;
  schlupfDate: DateTime;
  pvAufloesenDate: DateTime;
  köGeschlechtsreif: DateTime;
  köEilage: DateTime;
  brutVerdeckelt: DateTime;
  jungbienen: DateTime;
  
  

  constructor(date: DateTime) {
    super(date);
    
    this.wzBrechenDate = date.plus({days: 9});
    this.wzVerdeckelt = this.wzBrechenDate.plus({days: 5});
    this.schlupfDate = this.wzBrechenDate.plus({days: 11});
    this.verschulenDate = this.schlupfDate.minus({days: 1});
    this.pvAufloesenDate = date.plus({days: 21});
    this.köGeschlechtsreif = this.schlupfDate.plus({days: 7});
    this.köEilage = this.köGeschlechtsreif.plus({days: 1});
    this.brutVerdeckelt = this.köEilage.plus({days: 9});
    this.jungbienen = this.köEilage.plus({days: 21});
    this.endRange = this.jungbienen.plus({days: 1});
  }
}

export { BeeDates, TUBDates, ZuchtDates };
