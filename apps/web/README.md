# Schema Assistant web frontend

Questa cartella ospitera il frontend Angular pubblico.

Quando il progetto Angular verra migrato qui, dovra includere un Dockerfile in
`apps/web/Dockerfile`. La build Cloud Build dedicata e gia predisposta in
`cloudbuild.web.yaml`.

Il servizio Cloud Run web e pubblico. L'agent resta privato e puo essere invocato
server-side dal service account del web.
