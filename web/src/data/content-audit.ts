import type { ContentAuditFixture } from "../lib/types";

export const demoContentAudit: ContentAuditFixture = {
  slug: "intervista-servizi-pubblici",
  title: "Intervista: servizi pubblici, lavoro e territorio",
  source: "Rete Civica — contenuto dimostrativo",
  date: "2026-09-18",
  duration: "32:15",
  description:
    "Un esempio di ContentAudit costruito con contenuti fittizi per validare media, tempi, claim e fonti senza attribuire dichiarazioni inventate a persone reali.",
  moments: [
    {
      id: "moment-1",
      timestamp: "03:12",
      seconds: 192,
      claim: "I tempi medi di attesa sono diminuiti in tutte le aree del territorio.",
      assessment: "INSUFFICIENT_EVIDENCE",
      summary:
        "La riduzione emerge in alcune aree e prestazioni, ma non è uniforme nel periodo osservato.",
      sources: [
        { publisher: "Osservatorio sanitario", label: "Rapporto trimestrale" },
        { publisher: "Ufficio statistico", label: "Serie storica territoriale" }
      ]
    },
    {
      id: "moment-2",
      timestamp: "08:46",
      seconds: 526,
      claim: "Il programma di borse di studio ha raggiunto tutti i posti previsti.",
      assessment: "SUPPORTED",
      summary:
        "I dati pubblicati riportano una copertura coerente con l'obiettivo dichiarato per il periodo.",
      sources: [
        { publisher: "Ente per il diritto allo studio", label: "Rendiconto annuale" }
      ]
    },
    {
      id: "moment-3",
      timestamp: "14:05",
      seconds: 845,
      claim: "La rete locale copre già quasi tutto il fabbisogno energetico.",
      assessment: "UNRESOLVED",
      summary:
        "Le fonti pubbliche disponibili non consentono di ricostruire una misura comparabile e aggiornata.",
      sources: [
        { publisher: "Agenzia energia", label: "Bilancio energetico provvisorio" }
      ]
    },
    {
      id: "moment-4",
      timestamp: "21:38",
      seconds: 1298,
      claim: "Gli interventi sulla rete hanno dimezzato i tempi medi di percorrenza.",
      assessment: "FACTUALLY_FALSE",
      summary:
        "La serie disponibile mostra un miglioramento più contenuto rispetto a quello dichiarato.",
      sources: [
        { publisher: "Agenzia mobilità", label: "Monitoraggio tempi di percorrenza" }
      ]
    },
    {
      id: "moment-5",
      timestamp: "27:44",
      seconds: 1664,
      claim: "La spesa di manutenzione è aumentata rispetto all'anno precedente.",
      assessment: "SUPPORTED",
      summary:
        "Il rendiconto mostra un aumento nominale nel periodo indicato.",
      sources: [
        { publisher: "Bilancio aperto", label: "Rendiconto di gestione" }
      ]
    }
  ]
};
