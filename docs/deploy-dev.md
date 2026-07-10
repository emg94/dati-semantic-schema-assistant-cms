# Dev deployment runbook

Questa guida contiene solo comandi da lanciare manualmente. Terraform gestisce
infrastruttura, IAM, configurazione Cloud Run e servizi Google Cloud. I deploy
applicativi passano da Cloud Build e `gcloud run services update`.

## 1. Prerequisiti locali

Installa o verifica:

```powershell
uv --version
gcloud version
terraform version
```

Ambiente Python locale:

```powershell
uv venv .venv --python 3.12
.\.venv\Scripts\Activate.ps1
uv sync --all-extras
```

Autenticati con Google Cloud:

```powershell
gcloud auth login
gcloud auth application-default login
gcloud config set project istat-ndc-schema-ass-cms-dev
```

Bootstrap una tantum. Terraform gestira le altre API, ma Service Usage deve
essere gia attiva per permettere a Terraform di abilitarle.

```powershell
gcloud services enable serviceusage.googleapis.com cloudresourcemanager.googleapis.com --project istat-ndc-schema-ass-cms-dev
```

## 2. Configurazione Terraform dev

Copia il file di esempio e inserisci la tua email:

```powershell
Copy-Item infra\envs\dev\dev.tfvars.example infra\envs\dev\dev.tfvars
notepad infra\envs\dev\dev.tfvars
```

Nel file usa il formato IAM:

```hcl
developer_invokers = [
  "user:nome.cognome@example.com"
]
```

## 3. Terraform plan/apply

Formatta e inizializza:

```powershell
terraform fmt -recursive infra
terraform -chdir=infra\envs\dev init
terraform -chdir=infra\envs\dev validate
```

Se il progetto ha gia un database Firestore `(default)`, il `plan` potrebbe
chiedere un import invece di una creazione. In quel caso fermati e importa la
risorsa prima di applicare modifiche:

```powershell
terraform -chdir=infra\envs\dev import -var-file=dev.tfvars module.foundation.google_firestore_database.default "projects/istat-ndc-schema-ass-cms-dev/databases/(default)"
```

Genera il piano:

```powershell
terraform -chdir=infra\envs\dev plan -var-file=dev.tfvars -out=dev.tfplan
```

Applica solo dopo aver controllato il piano:

```powershell
terraform -chdir=infra\envs\dev apply dev.tfplan
```

## 4. Verifiche post-apply

Recupera gli output:

```powershell
terraform -chdir=infra\envs\dev output
$AGENT_URL = terraform -chdir=infra\envs\dev output -raw agent_url
```

Per ora l'agent usa una immagine placeholder, quindi questo test verifica IAM e
Cloud Run, non ancora la logica chat:

```powershell
$TOKEN = gcloud auth print-identity-token --audiences=$AGENT_URL
curl.exe -H "Authorization: Bearer $TOKEN" $AGENT_URL
```

Senza token la chiamata deve fallire con `401` o `403`:

```powershell
curl.exe $AGENT_URL
```

## 5. Note operative

- L'agent Cloud Run non e pubblico: solo i membri in `developer_invokers` hanno
  `roles/run.invoker`.
- Il job ingestion e manuale. In questa fase usa una immagine placeholder e non
  va eseguito per processare dati.
- Firestore usa `deletion_policy = "ABANDON"` per evitare cancellazioni
  accidentali durante `terraform destroy`.
- Il bucket ha accesso uniforme, public access prevention e versioning.
- Le immagini applicative sono aggiornate con Cloud Build e `gcloud`. Terraform
  ignora i cambi immagine per evitare drift durante lo sviluppo.

## 6. Build e deploy immagine agent

Questi comandi sostituiscono il placeholder Cloud Run con l'agent FastAPI reale.
Lanciali solo dopo aver validato l'infrastruttura base.

### Opzione A: Cloud Build + update diretto Cloud Run

Questa e l'opzione dev standard: Terraform resta owner dell'infrastruttura,
mentre Cloud Build e `gcloud` aggiornano solo l'immagine applicativa.

Se Cloud Build non ha ancora permessi sul repository, concedili una sola volta
al service account indicato dall'errore. Nel tuo progetto il formato e quello
del Compute Engine default service account usato da Cloud Build:

```powershell
gcloud projects add-iam-policy-binding istat-ndc-schema-ass-cms-dev `
  --member "serviceAccount:371903100831-compute@developer.gserviceaccount.com" `
  --role roles/cloudbuild.builds.builder

gcloud artifacts repositories add-iam-policy-binding schema-assistant `
  --project istat-ndc-schema-ass-cms-dev `
  --location europe-west8 `
  --member "serviceAccount:371903100831-compute@developer.gserviceaccount.com" `
  --role roles/artifactregistry.writer
```

Gli stessi permessi sono gestiti anche da Terraform nel modulo `foundation`.
Se preferisci tenere tutto tracciato prima di riprovare la build:

```powershell
terraform -chdir=infra\envs\dev plan -var-file=dev.tfvars -out=dev-cloudbuild-iam.tfplan
terraform -chdir=infra\envs\dev apply dev-cloudbuild-iam.tfplan
```

```powershell
gcloud builds submit `
  --project istat-ndc-schema-ass-cms-dev `
  --region europe-west8 `
  --config cloudbuild.agent.yaml `
  --substitutions _IMAGE=europe-west8-docker.pkg.dev/istat-ndc-schema-ass-cms-dev/schema-assistant/agent:dev `
  .

gcloud run services update schema-assistant-agent-dev `
  --project istat-ndc-schema-ass-cms-dev `
  --region europe-west8 `
  --image europe-west8-docker.pkg.dev/istat-ndc-schema-ass-cms-dev/schema-assistant/agent:dev
```

### Opzione B: Docker locale

Usala se vuoi buildare dalla tua macchina invece che con Cloud Build. Dopo il
push, aggiorna Cloud Run con lo stesso comando `gcloud run services update`.

```powershell
gcloud auth configure-docker europe-west8-docker.pkg.dev

$IMAGE = "europe-west8-docker.pkg.dev/istat-ndc-schema-ass-cms-dev/schema-assistant/agent:dev"

docker build -f services\agent\Dockerfile -t $IMAGE .
docker push $IMAGE

gcloud run services update schema-assistant-agent-dev `
  --project istat-ndc-schema-ass-cms-dev `
  --region europe-west8 `
  --image $IMAGE
```

Test autenticato:

```powershell
$AGENT_URL = terraform -chdir=infra\envs\dev output -raw agent_url
$TOKEN = gcloud auth print-identity-token --audiences=$AGENT_URL

curl.exe -i -H "Authorization: Bearer $TOKEN" $AGENT_URL/health

curl.exe -i `
  -H "Authorization: Bearer $TOKEN" `
  -H "Content-Type: application/json" `
  -d '{"message":"Ciao, chi sei?","history":[]}' `
  $AGENT_URL/api/chat
```

L'agent usa `THINKING_BUDGET=512` e `MAX_OUTPUT_TOKENS=2048` di default. Il
thinking resta disponibile, ma con un budget esplicito: in dev e nel futuro RAG
vogliamo ragionamento, risposte complete e costi prevedibili nello stesso
momento.

Con la knowledge base popolata, l'agent usa `RAG_ENABLED=true`: genera embedding
della domanda, cerca i chunk su Firestore Vector e passa al modello solo il
contesto recuperato. Le fonti sono restituite nel campo `sources`.

## 7. Firestore Vector e Storage Knowledge Base

La Fase 3 aggiunge la struttura della knowledge base, ma lascia `RAG_ENABLED=false`. In questo
modo possiamo validare bucket, Firestore e indice vettoriale prima di cambiare
il comportamento della chat.

Applica l'infrastruttura aggiornata:

```powershell
terraform fmt -recursive infra
terraform -chdir=infra\envs\dev validate
terraform -chdir=infra\envs\dev plan -var-file=dev.tfvars -out=dev-knowledge-base.tfplan
terraform -chdir=infra\envs\dev apply dev-knowledge-base.tfplan
```

Verifica che l'indice vettoriale sia presente. La creazione puo richiedere
qualche minuto:

```powershell
gcloud firestore indexes composite list `
  --project istat-ndc-schema-ass-cms-dev `
  --database="(default)"
```

Il valore atteso e:

```text
collection group: chunks
query scope: COLLECTION_GROUP
vector field: embedding
dimension: 2048
```

La documentazione di dettaglio e in `docs/knowledge-base-design.md`.

## 8. Build e deploy job ingestion

Il job ingestion e manuale: non esiste scheduler. Il container clona i repo
GitHub in `/tmp`, salva raw e processed assets su Cloud Storage, genera
embedding con Vertex AI e scrive i chunk in Firestore.

Il container usa la virtualenv creata da `uv sync`; il `PATH` punta quindi a
`/app/.venv/bin` per rendere importabile il package `schema_assistant`.

Le scritture Firestore dei chunk usano batch piccole
`INGESTION_FIRESTORE_WRITE_BATCH_SIZE=50`: i vettori a 2048 dimensioni rendono
ogni documento piu pesante e batch troppo grandi superano il limite payload
dell'API.

La memoria del job e impostata a `4Gi`. I vocabolari grandi, come ATECO, possono
richiedere molta RAM durante il parsing RDF; il codice scrive comunque i chunk a
batch piccoli per evitare di accumulare embedding e documenti Firestore in
memoria.

Il job usa `source_hash` per saltare le source gia completate. Se un file TTL,
YAML, PDF o CSV cambia, cambia anche l'hash e quella source viene processata di
nuovo.

Oltre ai chunk vettoriali, il job aggiorna anche
`entities/{ente}/resources/{risorsa}/asset_index/{source_uri_hash}`. Questo
indice contiene metadata sintetici usati dall'agent per rispondere meglio a
domande di elenco, confronto e conteggio. Dopo modifiche al parser o al routing
metadata, rilancia il job: le source gia completate vengono saltate lato
embedding, ma l'`asset_index` viene comunque aggiornato.

Build dell'immagine:

```powershell
gcloud builds submit `
  --project istat-ndc-schema-ass-cms-dev `
  --region europe-west8 `
  --config cloudbuild.ingestion.yaml `
  --substitutions _IMAGE=europe-west8-docker.pkg.dev/istat-ndc-schema-ass-cms-dev/schema-assistant/ingestion:dev `
  .
```

Aggiorna il Cloud Run Job:

```powershell
gcloud run jobs update schema-assistant-ingestion-dev `
  --project istat-ndc-schema-ass-cms-dev `
  --region europe-west8 `
  --image europe-west8-docker.pkg.dev/istat-ndc-schema-ass-cms-dev/schema-assistant/ingestion:dev
```

Esecuzione manuale:

```powershell
gcloud run jobs execute schema-assistant-ingestion-dev `
  --project istat-ndc-schema-ass-cms-dev `
  --region europe-west8 `
  --wait
```

Per controllare le ultime execution:

```powershell
gcloud run jobs executions list `
  --job schema-assistant-ingestion-dev `
  --project istat-ndc-schema-ass-cms-dev `
  --region europe-west8
```

Per fare una prova senza scrivere su Storage/Firestore, usa temporaneamente:

```powershell
gcloud run jobs update schema-assistant-ingestion-dev `
  --project istat-ndc-schema-ass-cms-dev `
  --region europe-west8 `
  --set-env-vars INGESTION_DRY_RUN=true
```

Riporta poi il valore operativo:

```powershell
gcloud run jobs update schema-assistant-ingestion-dev `
  --project istat-ndc-schema-ass-cms-dev `
  --region europe-west8 `
  --set-env-vars INGESTION_DRY_RUN=false
```

La configurazione ordinaria resta in Terraform: usa questi override solo per
prove operative mirate.

## 9. Frontend web pubblico

Il frontend Angular e ospitato in `apps/web/` e deployato come servizio Cloud Run
separato dall'agent. Il servizio web e pubblico, mentre l'agent resta privato: il
service account del web e autorizzato a invocare l'agent tramite IAM.

Il container web serve l'app Angular e include un proxy server-side per
`/api/chat`. Il browser non conosce l'URL dell'agent e non riceve token IAM; il
proxy ottiene invece un ID token dal metadata server Cloud Run e invoca l'agent
privato. La cronologia della chat resta nella memoria del browser e non viene
salvata dal servizio web o da Firestore.

Per creare il servizio web placeholder:

```powershell
terraform fmt -recursive infra
terraform -chdir=infra\envs\dev validate
terraform -chdir=infra\envs\dev plan -var-file=dev.tfvars -out=dev-web.tfplan
terraform -chdir=infra\envs\dev apply dev-web.tfplan
```

L'URL pubblico viene esposto da Terraform:

```powershell
terraform -chdir=infra\envs\dev output -raw web_url
```

Builda e deploya solo il web:

```powershell
gcloud builds submit `
  --project istat-ndc-schema-ass-cms-dev `
  --region europe-west8 `
  --config cloudbuild.web.yaml `
  --substitutions _IMAGE=europe-west8-docker.pkg.dev/istat-ndc-schema-ass-cms-dev/schema-assistant/web:dev `
  .

gcloud run services update schema-assistant-web-dev `
  --project istat-ndc-schema-ass-cms-dev `
  --region europe-west8 `
  --image europe-west8-docker.pkg.dev/istat-ndc-schema-ass-cms-dev/schema-assistant/web:dev
```

Kill switch temporaneo per costi o manutenzione:

```powershell
gcloud run services update schema-assistant-agent-dev `
  --project istat-ndc-schema-ass-cms-dev `
  --region europe-west8 `
  --set-env-vars COST_STATUS=blocked
```

Per riaprire:

```powershell
gcloud run services update schema-assistant-agent-dev `
  --project istat-ndc-schema-ass-cms-dev `
  --region europe-west8 `
  --set-env-vars COST_STATUS=green
```

Questo intervento e pensato per emergenza. La configurazione ordinaria rimane in
Terraform.
