export const studioSessions = [
  {
    id: "session-servizi",
    title: "Intervista: servizi pubblici e territorio",
    type: "Video",
    updated: "2 ore fa",
    state: "Trascrizione completata · 8 claim · fonti 5/8",
    group: "In corso"
  },
  {
    id: "session-lavoro",
    title: "Podcast: lavoro e formazione",
    type: "Podcast",
    updated: "5 ore fa",
    state: "Claim rilevate · verifica in corso",
    group: "In corso"
  },
  {
    id: "session-documento",
    title: "Documento: piano trasporti 2027",
    type: "Documento",
    updated: "ieri",
    state: "In attesa di revisione",
    group: "In corso"
  },
  {
    id: "session-energia",
    title: "Audizione: energia e reti locali",
    type: "Video",
    updated: "3 giorni fa",
    state: "Verifica completata · 6 claim",
    group: "Recenti"
  },
  {
    id: "session-scuola",
    title: "Intervista: borse di studio",
    type: "Audio",
    updated: "5 giorni fa",
    state: "Verifica completata · 4 claim",
    group: "Recenti"
  }
];

export const studioWorkspace = {
  id: "session-servizi",
  title: "Intervista: servizi pubblici e territorio",
  pipeline: "Trascrizione ✓ · 8 claim · Fonti 5/8 · Verificate 3/8",
  transcript: [
    { time: "00:18", text: "Il programma parte da una fotografia aggiornata dei servizi." },
    { time: "03:12", text: "I tempi medi di attesa sono diminuiti in tutte le aree del territorio." },
    { time: "08:46", text: "Il programma di borse di studio ha raggiunto tutti i posti previsti." },
    { time: "14:05", text: "La rete locale copre già quasi tutto il fabbisogno energetico." },
    { time: "21:38", text: "Gli interventi sulla rete hanno dimezzato i tempi medi di percorrenza." },
    { time: "27:44", text: "La spesa di manutenzione è aumentata rispetto all'anno precedente." }
  ],
  claims: [
    {
      id: "claim-wait",
      time: "03:12",
      statement: "I tempi medi di attesa sono diminuiti in tutte le aree del territorio.",
      state: "In revisione",
      normalized: "I tempi medi di attesa sono diminuiti uniformemente nel territorio.",
      observation: "I dati mostrano una riduzione per alcune prestazioni e aree, ma non una diminuzione uniforme.",
      evidence: [
        { source: "Osservatorio sanitario", date: "18 set 2026", state: "Approvata" },
        { source: "Ufficio statistico", date: "15 set 2026", state: "Approvata" },
        { source: "Rapporto territoriale", date: "10 set 2026", state: "Recuperata" }
      ]
    },
    {
      id: "claim-study",
      time: "08:46",
      statement: "Il programma di borse di studio ha raggiunto tutti i posti previsti.",
      state: "Verificata",
      normalized: "Il programma ha coperto il numero di borse pianificato per il periodo.",
      observation: "Il rendiconto pubblicato è coerente con l'obiettivo numerico indicato.",
      evidence: [
        { source: "Ente diritto allo studio", date: "14 set 2026", state: "Approvata" },
        { source: "Rendiconto programma", date: "12 set 2026", state: "Approvata" }
      ]
    },
    {
      id: "claim-energy",
      time: "14:05",
      statement: "La rete locale copre già quasi tutto il fabbisogno energetico.",
      state: "Fonti insufficienti",
      normalized: "La produzione locale copre una quota prossima al totale del fabbisogno.",
      observation: "Le serie disponibili hanno perimetri diversi e non consentono un confronto affidabile.",
      evidence: [
        { source: "Bilancio energetico provvisorio", date: "11 set 2026", state: "Recuperata" }
      ]
    },
    {
      id: "claim-mobility",
      time: "21:38",
      statement: "Gli interventi sulla rete hanno dimezzato i tempi medi di percorrenza.",
      state: "Da verificare",
      normalized: "Gli interventi hanno ridotto del 50% i tempi medi di percorrenza.",
      observation: "Sono disponibili serie di monitoraggio, ma la verifica non è ancora chiusa.",
      evidence: [
        { source: "Agenzia mobilità", date: "19 set 2026", state: "Recuperata" }
      ]
    }
  ]
};
