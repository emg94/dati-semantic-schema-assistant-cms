# Knowledge base storage design

La knowledge base usa due servizi Google Cloud:

- Cloud Storage conserva file originali e versioni processate.
- Firestore conserva metadati, chunk testuali e embedding vettoriali.

La chat resta stateless. La memoria utente vive solo nel browser; Firestore non
viene usato per salvare conversazioni.

## Cloud Storage

I prefissi sono separati per rendere chiaro cosa e stato scaricato, cosa e stato
processato e cosa arriva dai documenti statici:

```text
raw/github/{ente}/{risorsa}/{source_hash}/{path_file}
raw/docs/{source_hash}/{filename}
processed/{ente}/{risorsa}/{source_hash}.json
reports/ingestion/{timestamp}.json
```

Questa struttura permette di ricaricare un solo ente o una sola risorsa senza
riscrivere tutto il bucket.

## Firestore

I chunk sono salvati in sotto-collection, con shard stabili derivati dalla source.
Questo evita collection troppo grandi sotto un singolo documento ente.

```text
entities/{ente}
entities/{ente}/resources/{risorsa}
entities/{ente}/resources/{risorsa}/sources/{source_hash}
entities/{ente}/resources/{risorsa}/source_index/{source_uri_hash}
entities/{ente}/resources/{risorsa}/shards/{shard}/chunks/{chunk_id}
```

Il nome della collection group dei chunk e sempre `chunks`. L'indice vettoriale
viene quindi creato una sola volta sulla collection group `chunks`, campo
`embedding`.

`source_uri` identifica logicamente il file, mentre `source_hash` identifica la
versione del contenuto. Il job usa `source_index/{source_uri_hash}` per saltare
una source gia completata con lo stesso hash. Se il file cambia, l'hash cambia e
la source viene processata di nuovo.

## Dimensione embedding

Firestore supporta indici vettoriali fino a 2048 dimensioni. Per questo
`EMBEDDING_DIMENSION` e fissato a `2048`, anche se il modello Vertex puo
produrre vettori piu grandi.

## Query

La query vettoriale iniziale lavora sulla collection group `chunks`. Il filtro
per ente e tipo risorsa viene applicato nel codice sui candidati restituiti.
Quando avremo dati reali e misure di costo/qualita, potremo aggiungere indici
compositi con pre-filter Firestore per i percorsi piu frequenti.

## Ingestion

Il job manuale legge `config/entities_config.json`, clona i repository GitHub in
`/tmp`, carica i file raw su Cloud Storage, salva il JSON processato e scrive i
chunk con embedding in Firestore.

Per i repository GitHub mantiene la logica storica degli asset NDC: per ogni
cartella concetto cerca prima `latest/` e prende solo i file supportati presenti
li. Se una cartella concetto non ha `latest/`, viene usato il fallback ricorsivo
per gestire repository non allineati a quella convenzione.

I documenti statici PDF/CSV vanno messi in `knowledge_base_docs/`. La cartella
puo restare vuota: il job continua a processare i repository GitHub.

La re-ingestion e incrementale: le source con stesso URI, stesso hash e stato
`completed` vengono saltate. Le source in stato `processing`, ad esempio dopo un
crash o OOM, vengono invece riprocessate.
