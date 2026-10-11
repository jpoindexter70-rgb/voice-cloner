# Engine evaluation for Studio 2.0

This is a new adapter implementation using maintained upstream packages, not the old application code. Selection was based on current official package/model documentation, supported quality controls, CPU compatibility, a plausible 6 GB GPU budget and an actual conversion API. Exact RTX 2060 fit is unverified.

| Engine | License | Evidence / suitability | Limit |
| --- | --- | --- | --- |
| Chatterbox Expressive (Original, 500M) | MIT | Current chatterbox-tts 0.1.7 package; actual expression/CFG controls, zero-shot reference cloning and shared S3 recorded conversion. Real CPU synthesis and conversion passed. | English; 3.0 GB of checkpoints. Human naturalness/similarity requires listening to authorized references. |
| Chatterbox Turbo (350M upstream description) | MIT | Current 0.1.7 package; faster token generation and two-step decoder. Real CPU reference-conditioned synthesis passed. | English; no expression/CFG controls; reference >5 seconds. 2.8 GB of checkpoints. |
| Qwen3-TTS 0.6B Base | Apache 2.0 | Current official model metadata confirms voice cloning, ten language tags and ~2.5 GB stored artifacts. Worth future multilingual evaluation. | Not installed or benchmarked; cannot rank its subjective quality or claim 6 GB Windows fit. No selected native recorded-conversion API was established. |
| Chatterbox Multilingual V3 | MIT model card | Current official model card recommends V3 for 23+ languages and improved similarity/stability. | Separate checkpoint/runtime compatibility needs validation; not silently substituted into English adapters. |

Sources: https://pypi.org/project/chatterbox-tts/ ; https://huggingface.co/ResembleAI/chatterbox ; https://huggingface.co/ResembleAI/chatterbox-turbo ; https://huggingface.co/Qwen/Qwen3-TTS-12Hz-0.6B-Base . Upstream promotional preferences are not our listening-test results.

Original model revision: `5bb1f6ee58e50c3b8d408bc82a6d3740c2db6e18`. Turbo revision: `749d1c1a46eb10492095d68fbcf55691ccf137cd`. Every large checkpoint was checked against upstream SHA-256; small files against their Git blob hashes. Per-install manifests retain revision/hash/size. Runtime verifies manifests before loading.

Observed Linux CPU, four torch threads, packaged synthetic reference: Expressive 2.72 seconds output in 19.3 seconds; recorded conversion 11.36 seconds output in 23.1 seconds; Turbo 1.96 seconds output in 11.4 seconds including a model switch. These small samples are not general latency benchmarks. Recorded conversion ran slower than real time here, so these Expressive measurements do not establish streaming readiness. Seed live conversion uses its own current-device benchmark.

No family speech was supplied. Tests establish actual inference and transport, not identity accuracy, listening quality, accent preservation or Windows/GPU behavior. Default watermarking remains enabled. Strong post-processing can affect quality; no numeric setting guarantees naturalness.

Seed-VC tiny XLSR/HiFT is installed as a separate conversion adapter. Vendored architecture revision: `51383efd921027683c89e5348211d93ff12ac2a8`, GPL-3.0. Four official asset repositories are pinned in `studio/seed_assets.py`, verified before loading, and shared across profiles (~1.52 GB). Real CPU test: 2.995 seconds converted in 2.25 seconds after loading; two experimental final-head adaptation steps saved a 714,936-byte safetensors checkpoint, then real adapted conversion passed. This is not a subjective quality comparison or RTX 2060 benchmark. Upstream full fine-tuning uses different augmentation/training machinery. Upstream real-time examples use other GPUs; our stream uses measured 0.25/0.5/1 second blocks, 2.5 seconds of input context, 40 ms crossfade and a fresh CUDA readiness gate. Source: https://github.com/Plachtaa/seed-vc .
