import { Temporal } from "@js-temporal/polyfill";

class BeeDatesBase {
  startDate: Temporal.PlainDate;
  endRange: Temporal.PlainDate;

  constructor(date: Temporal.PlainDate | Date) {
    if (date instanceof Date) {
      this.startDate = Temporal.PlainDate.from(date.toISOString());
    } else {
      this.startDate = date;
    }
    
    // Make the type checker happy.
    this.endRange = this.startDate;
  }
}

class BeeDates extends BeeDatesBase {
  schlupfDate: Temporal.PlainDate;
  gReifDate: Temporal.PlainDate;
  eilageDate: Temporal.PlainDate;
  brutfreiDate: Temporal.PlainDate;
  verdeckeltDate: Temporal.PlainDate;
  jungbienenDate: Temporal.PlainDate;

  constructor(date: Temporal.PlainDate | Date) {
    super(date);
    
    this.schlupfDate = this.startDate.add({days: 11});;
    this.gReifDate = this.schlupfDate.add({days: 7});
    this.eilageDate = this.schlupfDate.add({days: 8});
    this.brutfreiDate = this.startDate.add({days: 21});
    this.verdeckeltDate = this.eilageDate.add({days: 9});
    this.jungbienenDate = this.eilageDate.add({days: 21});
    this.endRange = this.eilageDate.add({days: 22});
  }
}

class TUBDates extends BeeDatesBase {
  fBehandelnDate: Temporal.PlainDate;
  fVerdeckelt: Temporal.PlainDate;
  bSchlupfDate: Temporal.PlainDate;
  bBrutfreiDate: Temporal.PlainDate;
  bVerdeckeltDate: Temporal.PlainDate;

  constructor(date: Temporal.PlainDate) {
    super(date);
    
    this.fBehandelnDate = date.add({days: 2});
    this.fVerdeckelt = date.add({days: 9});
    this.bSchlupfDate = this.startDate.add({days: 11});;
    this.bBrutfreiDate = date.add({days: 21});
    this.bVerdeckeltDate = date.add({days: 28});
    this.endRange = date.add({days: 29});
  }
}

class ZuchtDates extends BeeDatesBase {
  wzBrechenDate: Temporal.PlainDate;
  wzVerdeckelt: Temporal.PlainDate;
  verschulenDate: Temporal.PlainDate;
  schlupfDate: Temporal.PlainDate;
  pvAufloesenDate: Temporal.PlainDate;
  köGeschlechtsreif: Temporal.PlainDate;
  köEilage: Temporal.PlainDate;
  brutVerdeckelt: Temporal.PlainDate;
  jungbienen: Temporal.PlainDate;
  
  

  constructor(date: Temporal.PlainDate) {
    super(date);
    
    this.wzBrechenDate = date.add({days: 9});
    this.wzVerdeckelt = this.wzBrechenDate.add({days: 5});
    this.schlupfDate = this.wzBrechenDate.add({days: 11});
    this.verschulenDate = this.schlupfDate.subtract({days: 1});
    this.pvAufloesenDate = date.add({days: 21});
    this.köGeschlechtsreif = this.schlupfDate.add({days: 7});
    this.köEilage = this.köGeschlechtsreif.add({days: 1});
    this.brutVerdeckelt = this.köEilage.add({days: 9});
    this.jungbienen = this.köEilage.add({days: 21});
    this.endRange = this.jungbienen.add({days: 1});
  }
}

export { BeeDates, TUBDates, ZuchtDates };
