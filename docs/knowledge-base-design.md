# Knowledge base storage design

La knowledge base usa due servizi Google Cloud:

- Cloud Storage conserva file originali e versioni processate.
- Firestore conserva metadati, chunk testuali e embedding vettoriali.

La chat resta stateless. La memoria utente vive solo nel browser; Firestore non
viene usato per salvare conversazioni.

## Cloud Storage

I prefissi sono separati per rendere chiaro cosa e stato caricato dagli
operatori, cosa e stato scaricato e cosa e stato processato:

```text
incoming/docs/{filename}
raw/github/{ente}/{risorsa}/{source_hash}/{path_file}
raw/docs/{source_hash}/{filename}
processed/{ente}/{risorsa}/{source_hash}.json
reports/ingestion/{timestamp}.json
```

`incoming/docs/` e la sorgente dei PDF e CSV gestiti manualmente. Il job li
scarica in `/tmp`, senza incorporarli nell'immagine Docker. `raw/docs/` resta
disponibile per eventuali documenti locali usati in sviluppo. Questa struttura
permette di aggiornare un documento o una risorsa senza ricostruire tutto il
bucket.

## Firestore

I chunk sono salvati in sotto-collection, con shard stabili derivati dalla source.
Questo evita collection troppo grandi sotto un singolo documento ente.

```text
entities/{ente}
entities/{ente}/resources/{risorsa}
entities/{ente}/resources/{risorsa}/sources/{source_hash}
entities/{ente}/resources/{risorsa}/source_index/{source_uri_hash}
entities/{ente}/resources/{risorsa}/asset_index/{source_uri_hash}
entities/{ente}/resources/{risorsa}/shards/{shard}/chunks/{chunk_id}
```

Il nome della collection group dei chunk e sempre `chunks`. L'indice vettoriale
viene quindi creato una sola volta sulla collection group `chunks`, campo
`embedding`.

`source_uri` identifica logicamente il file, mentre `source_hash` identifica la
versione del contenuto. Il job usa `source_index/{source_uri_hash}` per saltare
una source gia completata con lo stesso hash. Se il file cambia, l'hash cambia e
la source viene processata di nuovo.

`asset_index/{source_uri_hash}` contiene metadata sintetici per ogni asset:
titolo, percorso, formato, label estratte, keyword e puntatori agli oggetti su
Cloud Storage. Questo indice serve alle domande deterministiche, ad esempio
elenchi, confronti e conteggi. Il job aggiorna `asset_index` anche quando una
source viene saltata perche gia processata; in questo modo e possibile popolare
il nuovo indice rilanciando l'ingestion senza rigenerare embedding per file
invariati.

## Dimensione embedding

Firestore supporta indici vettoriali fino a 2048 dimensioni. Per questo
`EMBEDDING_DIMENSION` e fissato a `2048`, anche se il modello Vertex puo
produrre vettori piu grandi.

## Query

La query vettoriale lavora sulla collection group `chunks`. Quando il routing
individua un ente, un tipo di risorsa o entrambi, Firestore applica il filtro
prima della ricerca di vicinanza. Gli indici compositi su `entity_id`,
`resource_id` ed `embedding` evitano di leggere risultati globali non
pertinenti per poi scartarli nell'applicazione.

Per domande di elenco o conteggio l'agent usa prima `asset_index`, se la domanda
contiene abbastanza segnali per individuare ente e tipo risorsa. Il vector search
resta il canale principale per domande semantiche o descrittive, mentre
`asset_index` riduce i casi in cui una domanda di catalogo viene trattata come
una ricerca testuale generica.

Quando il routing restringe la ricerca a un ente o a una risorsa, l'agent esegue
anche una ricerca documentale secondaria limitata su
`catalog/context_documents`. Usa lo stesso embedding della domanda e recupera
al massimo pochi chunk aggiuntivi, cosi una guida pertinente non viene esclusa
dal filtro principale.

Il routing usa due livelli:

- `config/resources.json` definisce le risorse tecniche disponibili.
- `config/routing_lexicon.json` contiene sinonimi e termini di dominio, come
  classificazioni, benefici, prestazioni SIUSS e superstiti, insieme ai segnali
  storici per associare una domanda a un ente. I termini generici non bastano a
  restringere la ricerca: servono solo i segnali distintivi.

## Ingestion

Il job manuale legge `config/entities_config.json`, clona i repository GitHub in
`/tmp`, carica i file raw su Cloud Storage, salva il JSON processato e scrive i
chunk con embedding in Firestore.

Per i repository GitHub mantiene la logica storica degli asset NDC: per ogni
cartella concetto cerca prima `latest/` e prende solo i file supportati presenti
li. Se una cartella concetto non ha `latest/`, viene usato il fallback ricorsivo
per gestire repository non allineati a quella convenzione.

I documenti statici PDF/CSV vanno caricati nel prefisso GCS
`incoming/docs/`. I PDF senza un livello testuale vengono segnalati come errori
perche richiedono OCR; i PDF parzialmente leggibili producono un warning con il
numero di pagine estratte. `INGESTION_DOCS_DIR` resta disponibile solo per test
locali mirati.

La re-ingestion e incrementale: le source con stesso URI, stesso hash e stato
`completed` vengono saltate. Le source in stato `processing`, ad esempio dopo un
crash o OOM, vengono invece riprocessate.
