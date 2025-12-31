# Datasette — sesso (progetto minimale)

## Avvio rapido (Windows)
1. Assicurati di avere Python e Datasette installati:
   - `pip install datasette`
2. Doppio clic su `run_dashboard.bat`

## URL
- Se i certificati Tailscale esistono in:
  - `C:\ProgramData\Tailscale\certs\daniele.tail6b4058.ts.net.crt`
  - `C:\ProgramData\Tailscale\certs\daniele.tail6b4058.ts.net.key`
  allora aprirà: `https://daniele.tail6b4058.ts.net:8015/sesso`

- In caso contrario aprirà: `http://127.0.0.1:8015/sesso`

## Auto-reload
Ogni modifica in:
- `templates/`
- `static/custom/`
- `plugins/`
causa il riavvio automatico di Datasette.

## Comportamento richiesto
Dopo il submit del form (anche premendo Invio), la pagina reindirizza alla tabella:
`/cassaforte/sesso?_sort_desc=id`
