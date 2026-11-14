// Money Mentor: every word on the demo page and in the guided tour, in three languages.
// Captions never quote a customer's own amounts or counts: the phone shows live figures
// for whichever demo customer is selected, and a caption must not contradict the screen.

// What each tour step shows in the phone. Index-aligned with `steps` in every language.
// `seconds` is how long the step stays up when the tour advances by itself.
export const STEPS = [
  { route: 'home', highlight: 'home-trainer', seconds: 5 },
  { route: 'bank', highlight: 'bank-trainer', seconds: 4 },
  { route: 'trainer', highlight: 'trainer-hero', seconds: 6 },
  { route: 'trainer', highlight: 'trainer-notices', seconds: 4 },
  { route: 'plan', highlight: 'plan-outlook', seconds: 7 },
  { route: 'replay', highlight: 'replay-chart', seconds: 7 },
  { route: 'replay', highlight: 'replay-levers', seconds: 5 },
  { route: 'ask', highlight: 'ask-trust', seconds: 9, ask: true },
  { route: 'find', highlight: 'find-bar', seconds: 5 },
  // `photo`: the app sends its built-in sample price tag, so the model reads a photo live.
  { route: 'ask', highlight: 'ask-answer', seconds: 10, photo: true },
  { route: 'loan', highlight: 'loan-pillars', seconds: 5 },
];

const en = {
  name: 'Money Mentor',
  tagline: 'Concept for S-mobiili · Junction 2026',
  language: 'Language',
  eyebrow: 'Demo account · made-up data',
  headline: 'A money trainer built into S-mobiili',
  lede: 'It shows what is safe to spend this week and replays your own year with one habit changed. Every number is checked against your payments before you see it.',
  start: 'Start the walkthrough',
  startNote: 'About 1 minute. The phone navigates by itself.',
  open: 'Open the app',
  customer: 'Demo customer',
  customerChange: 'Change demo customer',
  years: '{age} years',
  perMonth: '{amount} a month',
  disclaimer: 'This is a demo account with made-up data. Nothing here is a real customer, and nothing asks you to sign in.',
  walkthrough: 'Walkthrough',
  of: '{n} of {total}',
  back: 'Back',
  next: 'Next',
  finish: 'Finish',
  pause: 'Pause',
  play: 'Play',
  skip: 'Skip to the app',
  keys: 'Arrow keys work too',
  endTag: 'Walkthrough finished',
  endTitle: 'Open the app and try it yourself',
  freeTag: 'The app is open',
  freeTitle: 'The phone is yours',
  endText: 'The phone on the right is live. Tap anything in it, or start with a question.',
  tryAsking: 'Try asking',
  again: 'Watch again',
  phoneLabel: 'A phone running the bank app with the money trainer. Demo data.',
  frameTitle: 'Money Mentor in the bank app (demo)',
  mobileNote: 'Opens full screen on this phone.',
  steps: [
    {
      title: 'It lives inside the bank’s own app',
      text: 'The trainer sits on the home screen people already open every week. Nothing new to download.',
    },
    {
      title: 'One new card on the Bank tab',
      text: 'It sits next to accounts and savings. No separate app and no new sign-in.',
    },
    {
      title: 'Safe to spend this week',
      text: 'The figure is built from the bank’s three baskets. Regular essentials first, then a buffer for the unexpected, and everyday spending is what is left.',
    },
    {
      title: 'The trainer comes to you',
      text: 'Most people never think of a question to ask. So the trainer points out what stands out.',
    },
    {
      title: 'A heads-up before trouble',
      text: 'The trainer lays your usual month over the weeks ahead and marks the day the balance would run out. Then it offers a plan for the next salary, to accept with one tap.',
    },
    {
      title: 'Your own year, replayed',
      text: 'One habit changed, for example your heaviest weeks trimmed to a normal busy week. Not a forecast: these are your real payments.',
    },
    {
      title: 'Levers are personal',
      text: 'For one customer it is trimming the heaviest weeks. For another it is two big purchases a year.',
    },
    {
      title: 'Ask in your own words',
      text: 'The engine finds every matching payment and adds them up, and an open model explains the result. Every number is checked against the payments before it is shown.',
      ask: 'How much did I spend on fast food in the last 3 months?',
    },
    {
      title: 'Find any payment in seconds',
      text: 'Ask “What did I buy on 10 July?” instead of scrolling through the list.',
    },
    {
      title: 'In the shop: can I afford this?',
      text: 'Photograph a price tag and ask. The trainer reads the price and checks it against what is safe to spend.',
    },
    {
      title: 'From first salary to first home',
      text: 'Readiness for a home loan, one step at a time. It is learned from the 200 application outcomes in the challenge data.',
    },
  ],
  questions: [
    'How much did I spend on fast food in the last 3 months?',
    'What is safe for me to spend this week?',
    'Can I afford a 120 euro jacket?',
  ],
  areas: {},
  personas: {},
};

const fi = {
  name: 'Money Mentor',
  tagline: 'Konsepti S-mobiiliin · Junction 2026',
  language: 'Kieli',
  eyebrow: 'Demotili · keksityt tiedot',
  headline: 'Talousvalmentaja suoraan S-mobiilissa',
  lede: 'Se näyttää, paljonko tällä viikolla on turvallista käyttää, ja toistaa oman vuotesi niin, että yksi tapa on muutettu. Jokainen luku tarkistetaan maksuistasi ennen kuin näet sen.',
  start: 'Aloita esittely',
  startNote: 'Noin 1 minuutti. Puhelin etenee itsestään.',
  open: 'Avaa sovellus',
  customer: 'Demoasiakas',
  customerChange: 'Vaihda demoasiakasta',
  years: '{age} v',
  perMonth: '{amount} / kk',
  disclaimer: 'Tämä on demotili, jonka tiedot on keksitty. Kukaan täällä ei ole oikea asiakas, eikä mikään pyydä sinua kirjautumaan.',
  walkthrough: 'Esittely',
  of: '{n} / {total}',
  back: 'Edellinen',
  next: 'Seuraava',
  finish: 'Valmis',
  pause: 'Keskeytä',
  play: 'Jatka',
  skip: 'Siirry sovellukseen',
  keys: 'Myös nuolinäppäimet toimivat',
  endTag: 'Esittely on katsottu',
  endTitle: 'Avaa sovellus ja kokeile itse',
  freeTag: 'Sovellus on auki',
  freeTitle: 'Puhelin on sinun',
  endText: 'Oikealla oleva puhelin toimii oikeasti. Napauta siinä mitä tahansa tai aloita kysymyksellä.',
  tryAsking: 'Kokeile kysyä',
  again: 'Katso uudelleen',
  phoneLabel: 'Puhelin, jossa on pankin sovellus ja Talousvalmentaja. Demotiedot.',
  frameTitle: 'Money Mentor pankin sovelluksessa (demo)',
  mobileNote: 'Avautuu koko näytölle tässä puhelimessa.',
  steps: [
    {
      title: 'Se on pankin omassa sovelluksessa',
      text: 'Talousvalmentaja on etusivulla, jonka asiakkaat avaavat jo joka viikko. Mitään uutta ei tarvitse ladata.',
    },
    {
      title: 'Yksi uusi kortti Pankki-välilehdellä',
      text: 'Se on tilien ja säästöjen vieressä. Ei erillistä sovellusta eikä uutta kirjautumista.',
    },
    {
      title: 'Turvallista käyttää tällä viikolla',
      text: 'Luku rakentuu pankin kolmesta korista. Ensin säännölliset pakolliset, sitten puskuri yllättäville pakollisille, ja jäljelle jää arjen kulutus.',
    },
    {
      title: 'Valmentaja tulee luoksesi',
      text: 'Useimmat eivät keksi, mitä kysyä. Siksi valmentaja nostaa itse esiin sen, mikä erottuu.',
    },
    {
      title: 'Varoitus ennen kuin on myöhäistä',
      text: 'Valmentaja asettaa tavallisen kuukautesi tulevien viikkojen päälle ja näyttää päivän, jona saldo loppuisi. Sitten se ehdottaa suunnitelman seuraavalle palkalle, jonka hyväksyt yhdellä napautuksella.',
    },
    {
      title: 'Oma vuotesi uusintana',
      text: 'Yksi tapa muutettuna: esimerkiksi raskaimmat viikot karsittuna tavallisen vilkkaan viikon tasolle. Tämä ei ole ennuste, vaan omat oikeat maksusi.',
    },
    {
      title: 'Vivut ovat henkilökohtaisia',
      text: 'Yhdelle asiakkaalle tärkeintä on karsia raskaimpia viikkoja. Toiselle ratkaisee kaksi isoa ostosta vuodessa.',
    },
    {
      title: 'Kysy omin sanoin',
      text: 'Moottori etsii jokaisen sopivan maksun ja laskee ne yhteen, ja avoin malli selittää tuloksen. Jokainen luku tarkistetaan maksuista ennen kuin se näytetään.',
      ask: 'Paljonko käytin pikaruokaan viimeisen 3 kuukauden aikana?',
    },
    {
      title: 'Löydä mikä tahansa maksu sekunneissa',
      text: 'Kysy vaikka ”Mitä ostin 10. heinäkuuta?” Selaamista ei tarvita.',
    },
    {
      title: 'Kaupassa: onko minulla varaa tähän?',
      text: 'Kuvaa hintalappu ja kysy. Valmentaja lukee hinnan ja vertaa sitä siihen, mitä on turvallista käyttää.',
    },
    {
      title: 'Ensimmäisestä palkasta ensimmäiseen kotiin',
      text: 'Valmius asuntolainaan, askel kerrallaan. Se on opittu haasteen aineiston 200 lainahakemuksen lopputuloksesta.',
    },
  ],
  questions: [
    'Paljonko käytin pikaruokaan viimeisen 3 kuukauden aikana?',
    'Paljonko minun on turvallista käyttää tällä viikolla?',
    'Onko minulla varaa 120 euron takkiin?',
  ],
  areas: {},
  personas: {
    CUST00728: { label: 'Ensimmäisessä työpaikassa', blurb: 'Alle 25, pienet tulot, paljon pieniä ostoksia' },
    CUST00086: { label: 'Kuun lopussa tiukilla', blurb: 'Saldo käy miinuksella useimpina kuukausina' },
    CUST00255: { label: 'Asunnonostaja, hyväksytty', blurb: 'Haki asuntolainaa ja sai sen' },
    CUST03987: { label: 'Asunnonostaja, hylätty', blurb: 'Asuntolaina hylättiin, koska omaa rahaa oli liian vähän' },
    CUST02396: { label: 'Tasainen säästäjä', blurb: 'Säästää ja sijoittaa joka kuukausi' },
    CUST00874: { label: 'Elämysten etsijä', blurb: 'Kolmannes menoista menee ravintoloihin, huviin ja matkoihin' },
    CUST00006: { label: 'Kahden pankin asiakas', blurb: 'Siirtää suurimman osan palkasta toiseen pankkiin joka kuukausi' },
    CUST01880: { label: 'Eläkeläinen', blurb: 'Yli 65-vuotias, tasainen budjetti, pakolliset ensin' },
  },
};

const sv = {
  name: 'Money Mentor',
  tagline: 'Koncept för S-mobil · Junction 2026',
  language: 'Språk',
  eyebrow: 'Demokonto · påhittade uppgifter',
  headline: 'Ekonomitränaren, inbyggd i S-mobil',
  lede: 'Den visar vad som är tryggt att använda den här veckan och spelar upp ditt eget år med en vana ändrad. Varje siffra kontrolleras mot dina betalningar innan du ser den.',
  start: 'Starta rundturen',
  startNote: 'Ungefär 1 minut. Telefonen navigerar av sig själv.',
  open: 'Öppna appen',
  customer: 'Demokund',
  customerChange: 'Byt demokund',
  years: '{age} år',
  perMonth: '{amount} / mån',
  disclaimer: 'Det här är ett demokonto med påhittade uppgifter. Ingen här är en riktig kund, och ingenting ber dig logga in.',
  walkthrough: 'Rundtur',
  of: '{n} av {total}',
  back: 'Tillbaka',
  next: 'Nästa',
  finish: 'Klar',
  pause: 'Pausa',
  play: 'Fortsätt',
  skip: 'Hoppa till appen',
  keys: 'Piltangenterna fungerar också',
  endTag: 'Rundturen är klar',
  endTitle: 'Öppna appen och prova själv',
  freeTag: 'Appen är öppen',
  freeTitle: 'Telefonen är din',
  endText: 'Telefonen till höger fungerar på riktigt. Tryck på vad som helst i den, eller börja med en fråga.',
  tryAsking: 'Prova att fråga',
  again: 'Se igen',
  phoneLabel: 'En telefon med bankens app och Ekonomitränaren. Demodata.',
  frameTitle: 'Money Mentor i bankens app (demo)',
  mobileNote: 'Öppnas i helskärm på den här telefonen.',
  steps: [
    {
      title: 'Den finns i bankens egen app',
      text: 'Ekonomitränaren ligger på startsidan som kunderna redan öppnar varje vecka. Inget nytt att ladda ner.',
    },
    {
      title: 'Ett nytt kort på fliken Bank',
      text: 'Det ligger bredvid konton och sparande. Ingen separat app och ingen ny inloggning.',
    },
    {
      title: 'Tryggt att använda den här veckan',
      text: 'Siffran byggs av bankens tre korgar. Först regelbundna nödvändiga utgifter, sedan en buffert för det oväntade, och det som blir kvar är vardagskonsumtion.',
    },
    {
      title: 'Tränaren kommer till dig',
      text: 'De flesta kommer aldrig på en fråga. Därför lyfter tränaren själv fram det som sticker ut.',
    },
    {
      title: 'En förvarning innan det blir knapert',
      text: 'Tränaren lägger din vanliga månad över veckorna framåt och visar dagen då saldot skulle ta slut. Sedan föreslår den en plan för nästa lön, som du godkänner med ett tryck.',
    },
    {
      title: 'Ditt eget år i repris',
      text: 'En vana ändrad, till exempel de tyngsta veckorna nedkapade till en vanlig intensiv vecka. Ingen prognos: det här är dina verkliga betalningar.',
    },
    {
      title: 'Spakarna är personliga',
      text: 'För en kund handlar det om att kapa de tyngsta veckorna. För en annan är det två stora köp om året.',
    },
    {
      title: 'Fråga med egna ord',
      text: 'Motorn hittar varje betalning som passar och räknar ihop dem, och en öppen modell förklarar resultatet. Varje siffra kontrolleras mot betalningarna innan den visas.',
      ask: 'Hur mycket lade jag på snabbmat de senaste 3 månaderna?',
    },
    {
      title: 'Hitta vilken betalning som helst på några sekunder',
      text: 'Fråga till exempel ”Vad köpte jag den 10 juli?” Du behöver inte bläddra.',
    },
    {
      title: 'I butiken: har jag råd med det här?',
      text: 'Fotografera en prislapp och fråga. Tränaren läser priset och jämför det med vad som är tryggt att använda.',
    },
    {
      title: 'Från första lönen till första hemmet',
      text: 'Beredskap för bolån, ett steg i taget. Den bygger på de 200 ansökningsutfallen i utmaningens data.',
    },
  ],
  questions: [
    'Hur mycket lade jag på snabbmat de senaste 3 månaderna?',
    'Vad är tryggt för mig att använda den här veckan?',
    'Har jag råd med en jacka för 120 euro?',
  ],
  areas: { Helsinki: 'Helsingfors', Vantaa: 'Vanda', Espoo: 'Esbo' },
  personas: {
    CUST00728: { label: 'Första jobbet', blurb: 'Under 25, låg inkomst, många små köp' },
    CUST00086: { label: 'Knappt i slutet av månaden', blurb: 'Saldot går under noll de flesta månader' },
    CUST00255: { label: 'Bostadsköpare, beviljad', blurb: 'Ansökte om bolån och fick det' },
    CUST03987: { label: 'Bostadsköpare, avslagen', blurb: 'Bolånet avslogs på grund av för liten egen insats' },
    CUST02396: { label: 'Stadig sparare', blurb: 'Sparar och investerar varje månad' },
    CUST00874: { label: 'Upplevelsesökare', blurb: 'En tredjedel av utgifterna går till restauranger, nöjen och resor' },
    CUST00006: { label: 'Kund i två banker', blurb: 'Flyttar det mesta av lönen till en annan bank varje månad' },
    CUST01880: { label: 'Pensionär', blurb: 'Över 65 med en stadig budget, det nödvändiga först' },
  },
};

export const tour = { en, fi, sv };
export { tour as TOUR };
export default tour;
