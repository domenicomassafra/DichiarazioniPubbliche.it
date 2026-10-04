# Public data projection

Questa directory è destinata soltanto a piccoli fixture e projection pubbliche
versionabili. La projection runtime canonica è generata dal modulo
`dichiarazioni_pubbliche.public_projection`: questa directory non è un dump del DB.

Può contenere:

- normalized claims;
- finding;
- evidence metadata;
- source URLs;
- timestamps;
- speaker IDs con provenance identity approvata;
- hashes;
- correction history.

Non deve contenere automaticamente:

- MP4;
- audio;
- transcript integrali di contenuti terzi;
- secrets;
- operational database dumps;
- evidence body/excerpt non esplicitamente pubblicabile;
- claim senza speaker provenance approvata;
- finding non passato dall'explicit publication gate.

Quando il dataset diventerà grande, la distribuzione pubblica dovrà spostarsi
in un data repository o release dataset separato dal code repository.
