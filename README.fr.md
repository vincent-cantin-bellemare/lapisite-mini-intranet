# lapisite-mini-intranet (français)

Petite application d'exemple pour l'[API Lapisite](https://docs.lapisite.com/docs/en/quickstart), avec le SDK Python
officiel. Elle ne tourne que contre l'**environnement de test** (clés `lps_test_`) : rien de ce qu'elle fait n'est réel.

Elle montre comment créer un site et suivre sa génération, le publier, enregistrer un point d'accès webhook sans
écrire son secret dans un fichier, et recevoir des webhooks en vérifiant leur signature avec le SDK.

Prérequis : Python 3.11+ et une clé de **test** (`lps_test_`), créée par un propriétaire ou un administrateur dans
l'écran **Clés d'API** du portail (affichée une seule fois).

## Mise en route

```bash
cp .env.example .env     # puis : LAPISITE_API_KEY=lps_test_...
python -m mini_intranet create-site
python -m mini_intranet follow <job_id>
python -m mini_intranet publish <site_id>
python -m mini_intranet demo            # tout le parcours
```

L'outil refuse de tourner si la clé ne commence pas par `lps_test_`. Les données sont fictives
(`boulangerie-exemple.example`).

## Webhooks

```bash
export LAPISITE_WEBHOOK_SECRET='whsec_...'
python -m mini_intranet serve                 # écoute 127.0.0.1:8787
cloudflared tunnel --url http://127.0.0.1:8787
python -m mini_intranet webhook-endpoint https://<votre-tunnel>.trycloudflare.com
```

Le récepteur vérifie la signature (`Lapisite-Webhook-Signature`, tolérance de 5 minutes), répond `400` si elle est
fausse ou trop vieille, journalise le type d'événement et le site, puis répond `204` tout de suite.

Attention : créer un point d'accès par l'API demande une clé live ; une clé de test reçoit `403 sandbox_only`. Pour
essayer le récepteur sans clé live, créez le point d'accès dans le portail (**Webhooks**) et utilisez son
**Simulateur** (envoi d'un événement `webhook.test` signé).

## Tests

`make test` (sans réseau ni secret), `make lint`.

## Licence

MIT (voir `LICENSE`). Le SDK copié dans `vendor/lapisite/` garde ses propres conditions de licence.
