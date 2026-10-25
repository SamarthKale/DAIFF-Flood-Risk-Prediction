# Google Earth Engine setup (every teammate, once)

DAIFF reads all satellite and reference data through Google Earth Engine (decision D-01). Each
teammate uses **their own free non-commercial Cloud project**. Nobody else can do these steps for
you — they involve your Google account.

## 1. Register

1. Open https://code.earthengine.google.com/register and sign in with your Google account.
2. Choose **Use with a Cloud project → Unpaid usage → Academia & research**.
3. Create a new Cloud project (suggested ID: `daiff-<yourname>`). No billing account is needed for
   non-commercial use. Google may ask you to confirm non-commercial eligibility — answer truthfully
   (student research project, HPC Research Internship).
4. Finish the form and wait until the project shows Earth Engine as enabled (usually minutes).

## 2. Connect your machine

```bash
uv sync --extra dev
uv run earthengine authenticate
```

A browser opens; sign in with the **same** Google account and allow access. The token is stored in
your user profile (never in the repository).

Copy `.env.example` to `.env` and set:

```
DAIFF_GEE_PROJECT=<your-project-id>
```

## 3. Smoke test

```bash
uv run python -c "import ee; ee.Initialize(project='<your-project-id>'); print(ee.Number(1).add(1).getInfo())"
```

It prints `2`. From P3 on you can also run `uv run daiff gee check -c configs/kopili.yaml`.

## 4. Google Colab (GPU work)

```python
import ee
ee.Authenticate()
ee.Initialize(project="<your-project-id>")
```

## Notes

- **Quota:** non-commercial projects have a monthly compute quota. DAIFF keeps exports small
  (30 m products, 10 m binary forest maps), but avoid re-running full exports needlessly — the
  pipeline skips assets that already exist.
- **Sharing:** exported assets live under `projects/<your-project-id>/assets/daiff/`. You can share
  them read-only with teammates in the Code Editor's Assets tab so they can skip re-exporting.
- **Troubleshooting**
  - `ee.Initialize` fails with *project not registered*: finish step 1 for that project, or check
    the project ID spelling in `.env`.
  - *Permission denied / wrong account*: run `uv run earthengine authenticate --force` and pick the
    account that owns the project.
  - Corporate/college networks blocking the browser flow: try `earthengine authenticate --auth_mode=notebook`.
