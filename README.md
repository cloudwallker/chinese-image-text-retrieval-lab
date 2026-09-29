# Chinese Image–Text Retrieval Lab

A local CPU learning lab for Chinese image–text retrieval.

**Compare caption matching, pretrained image–text similarity, and a simple exclusion-condition experiment on real images. Inspect rankings, export evaluation reports, and record your own observations without a GPU, paid API, or model training.**

English | [中文](README_ZH.md)

[Quick start](#quick-start) · [Methods](#methods) · [Recorded results](#recorded-results) · [Documentation](#documentation)

![Recorded CPU retrieval results on 16 test queries](docs/images/experiment-results.png)

*Evaluation chart from the recorded CPU experiment: 48 images, 16 test queries, and exclusion weight 0.4. This is a results chart, not a screenshot of the web interface.*

## What you can do

- Search with Chinese descriptions using pretrained Chinese-CLIP RN50 on CPU.
- Compare three retrieval methods and inspect the parsed positive and exclusion conditions.
- Run evaluations by query split and category; export real JSON and Markdown reports.
- Save local learning notes about hypotheses, observations, failures, and next experiments.

The included teaching dataset contains **48 real Met Open Access images and 32 Chinese queries**. Every image retains its official source record and CC0 evidence. The web interface is in Chinese and uses local assets without a CDN.

## Quick start

The provided launcher and setup script target **Windows**. The recorded environment used **Python 3.9.25**. Install Python and run these commands from the project directory.

### First-time setup

```powershell
powershell -ExecutionPolicy Bypass -File scripts/setup.ps1
```

The script creates `.venv`, installs the pinned dependencies and CPU PyTorch, downloads approximately 308 MB of official model weights, and checks or downloads the gallery images. Setup needs network access. Once the dependencies, weights, and images are ready, retrieval and experiments run locally offline.

Model files, caches, and personal notes are excluded by `.gitignore`.

### Start the app

Double-click **`start.cmd`**, or run:

```powershell
.\.venv\Scripts\python.exe app.py --open
```

The browser opens `http://127.0.0.1:8765`. Keep the launcher window open; press Ctrl+C or close the window to stop the service.

In the web interface, click **“构建图片向量”** to prepare the model and image index. The first run encodes every gallery image; later runs reuse an index checked against image-content fingerprints. Model loading and initial indexing use CPU and memory, so the first preparation may take several minutes. Before preparation, the caption baseline is available; model methods require a real prepared index.

## Methods

| Method | Input | Purpose |
| --- | --- | --- |
| Caption baseline | Human-written Chinese titles, captions, and tags; TF-IDF lexical matching | Explore vocabulary overlap and caption coverage without an image encoder. |
| Original Chinese-CLIP | Image embeddings and the complete Chinese query embedding | Inspect pretrained cross-modal cosine similarity. |
| Exclusion experiment | Separately encoded positive and excluded descriptions | Test a training-free penalty and examine its failures. |

With L2-normalized embeddings:

```text
Original:  score = cosine(image, query)
Exclusion: score = cosine(image, positive) − weight × cosine(image, negative)
```

Supported exclusion forms include **“杯子，不要红色”** and **“鸟，但不含蓝色”**. The interface shows the conditions actually parsed. This is a teaching implementation of an existing idea, not an original algorithm or a guarantee of general negation understanding. Without an exclusion condition, the exclusion method uses the positive query alone.

The model keeps its official 52-token context, including two special tokens. More than 50 content tokens produces an explicit error rather than silent truncation. The caption baseline accepts up to 300 characters. **Similarity scores are not confidence probabilities.**

## Recorded results

The [full report snapshot](docs/results/cpu-test-report.json) records a CPU experiment on **2026-09-29**, using the complete 48-image gallery and **16 test queries**: 4 object, 6 attribute, and 6 exclusion queries. The exclusion weight was fixed at **0.4**, without training or a parameter search on validation or test.

| Method | Hit@1 | Hit@5 | Recall@5 | mAP@5 |
| --- | ---: | ---: | ---: | ---: |
| Caption baseline | 68.75% | 93.75% | 80.06% | 0.7220 |
| Original Chinese-CLIP | 62.50% | 100.00% | 80.21% | 0.7079 |
| Exclusion experiment, weight 0.4 | 75.00% | 100.00% | 85.42% | 0.7852 |

The exclusion method changed two test queries from an incorrect to a correct Top-1 result. Among the six exclusion queries, its Hit@1 was **33.33%**, versus **0.00%** for original Chinese-CLIP; **four exclusion queries still failed at Top-1**.

For “椅子，不要坐垫” (chair, without a cushion), the exclusion method moved an uncushioned chair to first place. For “杯子，不要碟子” (cup, without a saucer), a cup with a saucer remained first and Recall@5 decreased. See [the experiment analysis](docs/EXPERIMENT_RESULTS.md) for both improvements and regressions.

These are descriptive results on a small, manually annotated teaching dataset of museum objects and artworks, not a standard benchmark or evidence of general retrieval improvement. The caption baseline receives human-written text, while CLIP receives images; their information differs. The recorded timings reuse caches and exclude initial model loading and indexing, so they are not independent cold-start measurements.

### Reproduce the experiment

After setup:

```powershell
.\.venv\Scripts\python.exe scripts/prepare_gallery.py --check
.\.venv\Scripts\python.exe scripts/run_experiment.py --split test --negative-weight 0.4
```

The generated report is saved to `cache/report.json`, with configuration, aggregate and category metrics, relevant image IDs, and per-query rankings. The web interface can also run and export experiments. Model results come from the actual encoder; unavailable model components produce errors rather than simulated CLIP results.

- **Hit@K:** whether at least one annotated relevant image occurs in the first K results, averaged over queries.
- **Recall@K:** relevant images retrieved in the first K results divided by all annotated relevant images for that query.
- **AP@K:** precision accumulated at relevant ranks within K, divided by `min(K, number of relevant images)`; mAP@K averages AP over queries.

The full 32-query set has 16 validation and 16 test queries, both searching the same gallery. If you explore parameters, define your selection rule on validation and freeze it before evaluating test. Learning-note templates are prompts to fill from your own runs, not claims of completed personal work.

## Validation

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
node --check web/app.js
```

With the local service running, check retrieval, report export, and note endpoints:

```powershell
.\.venv\Scripts\python.exe scripts/smoke_test.py
```

The smoke test restores the prior notes after testing. Automated checks cover backend behavior; **there is no recorded visual acceptance evidence for the web interface**.

## Documentation

| Document | Contents |
| --- | --- |
| [Data sources](docs/DATA_SOURCES.md) | Official image sources, CC0 evidence, annotations, and split boundaries. |
| [Experiment results](docs/EXPERIMENT_RESULTS.md) | Actual metrics, successful queries, failed queries, and interpretation limits. |
| [Full report](docs/results/cpu-test-report.json) | Complete recorded configuration and per-query results. |
| [Learning guide](docs/LEARNING_GUIDE.md) | Turn your own runs into hypotheses, evidence, and learning notes. |
| [Research background](docs/RESEARCH.md) | Model choices and related work. |

The main implementation is in `lab/`; `web/` contains the Chinese interface; `data/` contains the teaching gallery and queries; `scripts/` contains setup and experiment commands. The HTTP service listens only on `127.0.0.1`; queries and notes stay in the local service.

## Sources and attribution

- **Model:** [Chinese-CLIP official implementation](https://github.com/OFA-Sys/Chinese-CLIP), [technical report](https://arxiv.org/abs/2211.01335), and [official RN50 weights](https://huggingface.co/OFA-Sys/chinese-clip-rn50). The downloader pins revision `717ba215769231e53b9b7c6b9d329b9cc5944418` and checks the official LFS SHA-256 before accepting the file. This project uses the pretrained model for CPU inference; it does not train CLIP.
- **Images:** [The Met Open Access](https://www.metmuseum.org/hubs/open-access), [official API](https://metmuseum.github.io/), and [CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/). Only records marked public domain with official open image URLs are included. Chinese titles and captions are teaching annotations, not official museum translations.
- **Scope:** this repository supplies a local application, evaluation tools, and a teaching dataset. It does not claim an original retrieval method or reproduce the full experiments of related papers.

Model weights are not included in the repository. Models and images retain the licensing terms of their respective sources.
