# Schema Assistant web frontend

Questa cartella ospita il frontend Angular pubblico.

Il Dockerfile costruisce Angular e avvia `server.mjs`, un server Node che serve
gli asset statici e inoltra `/api/chat` all'agent privato.

Il browser chiama solo lo stesso dominio del web. Il server usa il service account
Cloud Run per ottenere un ID token e invocare l'agent privato. La cronologia della
chat resta soltanto in memoria nel browser e viene inviata all'agent a ogni richiesta.

Per una prova locale del proxy servono un URL agent e un token di identita:

```powershell
$env:AGENT_SERVICE_URL = 'https://<agent-url>'
$env:AGENT_ID_TOKEN = gcloud auth print-identity-token --audiences=$env:AGENT_SERVICE_URL
$env:FRAME_ANCESTORS = 'https://wp-ndc-dev.apps.cloudpub.testedev.istat.it,https://schema.gov.it'
$env:STATIC_DIR = 'dist/ndc-platform-ai/browser'
npm run start:cloud-run
```

In Cloud Run `AGENT_SERVICE_URL` e configurato da Terraform. Non impostare
`AGENT_ID_TOKEN` nel servizio: il token viene ottenuto automaticamente dal metadata server.

`FRAME_ANCESTORS` contiene una lista separata da virgole delle origini HTTPS che
possono incorporare l'app in un iframe. Sono accettate solo origini esatte, senza
path, slash finale o wildcard. Se la variabile e vuota, la CSP usa
`frame-ancestors 'none'`; una configurazione non valida impedisce l'avvio del
container. `X-Frame-Options` non viene inviato perche non supporta una allowlist
multi-dominio: il controllo e affidato alla direttiva CSP `frame-ancestors`.
