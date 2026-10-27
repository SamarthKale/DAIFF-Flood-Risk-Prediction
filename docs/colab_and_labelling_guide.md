# Guide: labelling the reference points and running the Colab notebooks

## Part 1: labelling the 739 reference points (human-only work, FR-F1 / FR-F2)

**Why:** forest accuracy (overall accuracy ≥ 90 %, forest F1 ≥ 0.85, loss F1 ≥ 0.70) is measured
against *your* labels, so they must be honest and independent. Claude never labels points.

**Start the dashboard:**

```bash
uv run daiff serve -c configs/kopili.yaml
```

Open http://localhost:8000 and go to the **Labelling** tab.

**Who labels:** SRS 7.3 needs two team members labelling every point **independently** (Interpreter A
and Interpreter B) and a third person (Adjudicator) who resolves the points where they disagree.
Cohen's kappa between A and B is reported. One person cannot be both A and B and still count as
independent: you can start as A now, and a teammate does B later.

**For every point you answer two questions** (the page shows the point number and lat/lon):

| Question | Meaning |
|---|---|
| **t0** | Was there forest at this spot in the **2017-18 dry season** (the baseline)? |
| **latest** | Is there forest at this spot in the **2025-26 dry season**? |

Each answer is **Forest**, **Non-forest** or **Unsure** (plus an optional note).

- **Forest = tree canopy of 30 % or more** over the small area around the point (about the 30 m
  cell the point sits in). Plantations (tea, rubber, areca) with trees count as forest only if the
  canopy is dense enough to meet that 30 %. Say so in the note if you are unsure.
- **Non-forest:** crops, grass, bare soil, built-up, water, scrub with under 30 % trees.
- **Unsure:** cloud, shadow or imagery too poor to decide. Unsure points are excluded from the
  accuracy numbers, so use it only when you really cannot tell. Do not guess.
- A point that is forest at t0 and non-forest in the latest year is a **loss** point; the reverse
  is a gain. You do not label "loss" directly: it follows from your two answers.

**How to look:** use the **Imagery** dropdown on the left. It has Esri high-resolution (sharp but
undated) and Sentinel-2 true-colour for each dry season (dated, coarser). Compare the 2017-18 and
2025-26 Sentinel-2 views, and use Esri for fine detail. Zoom in and out around the yellow marker.
The page does **not** show what the forest map predicted: label from the imagery only, and do not
look at the other interpreter's labels.

**Target:** at least 600 points labelled by both A and B (all 739 is better; 150 or more must be
loss points, which the sample already has). Expect about 1-2 minutes per point.
Progress saves automatically to `reference/forest_labels_kopili.csv`; commit that file with
`git add reference && git commit && git push` when you stop, so teammates keep your work.

When enough points are labelled, tell Claude: it runs `daiff validate -c configs/kopili.yaml --what forest`.

## Part 2: running the Colab notebooks (U-Net challenger, free GPU)

Two notebooks in `notebooks/colab/`: **unet_train.ipynb** then **unet_infer.ipynb**. Open each in
Chrome: https://colab.research.google.com → File → Open notebook → GitHub tab →
`SamarthKale/DAIFF-Flood-Risk-Prediction`.

1. **Runtime → Change runtime type → T4 GPU** (free). Never train on the laptop GPU.
2. In the first code cell, replace `YOUR-EARTH-ENGINE-PROJECT-ID` with your Earth Engine project
   (`premium-state-512715-q9`). Run the cells top to bottom; Google asks you to sign in (Earth Engine)
   and to allow Drive access.
3. **Quota warning:** Earth Engine is already over its monthly allowance. In `unet_train`, set
   `N_PER_YEAR = 20` first, check your usage in the Earth Engine console, and only then raise it
   (150 per year is the full run). Everything is saved to `My Drive/DAIFF/`, so a disconnect only
   loses the current epoch; re-run the training cell to resume.
4. `unet_infer` step 3 writes `unet_points.csv` (predictions at the reference points). Step 4 (full
   10 m maps) is heavy: test with the small `WINDOW` first and run it only if the points look good.
5. Download `My Drive/DAIFF/unet_out/` to the laptop and run:

```bash
uv run daiff forest import-unet -c configs/kopili.yaml --dir <the downloaded folder>
```

Selection rule (D-14): whichever classifier, Random Forest or U-Net, has the higher forest F1 on the
labelled reference sample becomes the pipeline input. The choice is logged in `docs/decisions.md`.
