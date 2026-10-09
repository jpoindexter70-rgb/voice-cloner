# Engine selection and quality evaluation

The app supports real local adapters for **Chatterbox Original** and **Chatterbox Turbo**, using PyPI `chatterbox-tts==0.1.7` and PyTorch/torchaudio 2.6.0. Original is a provisional English default, **not a measured winner for your voice**. No reference recording from you has been provided. Model downloads in the cloud are currently denied by the egress proxy (HTTP 403). Neither engine has generated speech in this environment yet.

## What was verified from authoritative sources

Sources inspected during implementation:

- [Official Chatterbox README](https://github.com/resemble-ai/chatterbox): Original 500M English; Turbo 350M English, lower compute and memory, native paralinguistic tags. Upstream reports development/testing on Python 3.11 and Debian 11, not certified native Windows support.
- [Official source license](https://github.com/resemble-ai/chatterbox/blob/master/LICENSE): MIT. The upstream source license was retrieved and reviewed. Independent checkpoint model cards/licenses could not be fetched because Hugging Face access is denied; confirm the model cards before redistribution.
- [Published package metadata](https://pypi.org/project/chatterbox-tts/0.1.7/): installed successfully with pinned torch/torchaudio 2.6.0, transformers 5.2.0, diffusers 0.29.0, safetensors 0.5.3. Both engine classes imported successfully on Linux CPU. The packaged Perth watermarker was initialized and exercised. setuptools 78.1.0 is pinned to keep its pkg_resources dependency available. The published package is used, not mutable Git master.
- [Original model repository](https://huggingface.co/ResembleAI/chatterbox) and [Turbo model repository](https://huggingface.co/ResembleAI/chatterbox-turbo): official upstream references; direct availability and model-card verification are pending network access.
- [PyTorch previous versions](https://pytorch.org/get-started/previous-versions/): 2.6.0 CUDA 12.4 wheel index for Windows/Linux. An RTX 2060 is a CUDA-capable Turing GPU; actual installation, driver compatibility, and peak VRAM must be tested on your machine. The system CUDA toolkit is not normally required for these prebuilt wheels.

The current upstream README also describes newer multilingual V3 and Nano options. They are not wired into this pinned package integration or exposed as working controls. For an English personal studio, validate these two existing adapters before adding more engines.

## Alternatives considered

| Engine | Why consider it | Why it is not the initial integration |
|---|---|---|
| Chatterbox Original | Reference conditioning, speaker identity and native expression/CFG controls, open-source MIT code | 500M model; 6 GB fit is not established; no personal quality benchmark yet |
| Chatterbox Turbo | Smaller English model, lower compute/VRAM, native tags | Smaller does not guarantee better identity; CFG and expression controls are ignored upstream, so the UI disables them |
| CosyVoice 3 | Upstream describes 0.5B zero-shot multilingual cloning and improved speaker similarity | More complex runtime; no native-Windows/6 GB validation here; personal samples needed for fair comparison. [Official README](https://github.com/FunAudioLLM/CosyVoice) was retrieved. |
| XTTS v2 | Widely used reference-conditioned multilingual model | Code and checkpoint licenses differ (TTS code MPL-2.0, XTTS weights have their own license). No current Windows/VRAM or sample comparison executed here. [TTS source](https://github.com/coqui-ai/TTS) |
| F5-TTS | Another reference-conditioned open-source architecture | Not installed or benchmarked; checkpoint licensing and Windows compatibility need separate verification. [Official repository](https://github.com/SWivid/F5-TTS) |

Do not interpret upstream benchmark claims as results for your voice. None of the alternative engines has been sample-tested here.

## Repeatable personal comparison

1. Save one clean, unprocessed 10–15 second reference with permission. Avoid music, noise, clipping, heavy denoising, or another speaker. Keep a consistent natural speaking style.
2. Select that same primary reference for both engines. Multiple saved samples let you compare different clean passages; the app does not blend them or fine-tune a model automatically. Original conditions on roughly the first 6 seconds for its speech tokens and first 10 seconds for decoder features; Turbo uses up to 15 seconds/10 seconds respectively.
3. Keep default settings initially. Generate each sentence below and the paragraph three times per engine to assess variability. The installed engine does not expose a reproducibility seed in the UI; retain the actual audio and metadata instead of claiming identical reruns.
4. Listen on the same headphones at comparable loudness. Compare A/B to the original, and have a familiar listener rate blind-labeled exports when possible. Rate similarity first, naturalness second, pronunciation, clarity, and consistency next. Save the five ratings and notes in the app; export them as JSON. Record generation time and peak VRAM externally using Windows Task Manager/NVIDIA tools.
5. Evaluate speaker recognition, accent, cadence, unusual names, numbers, and long-script segment boundaries. Keep the engine with the best identity and naturalness, even if slower. Compare different reference passages before using stronger expression or audio processing.
6. Repeat for each authorized speaker separately. Never use one speaker’s reference to evaluate or generate another profile.

Sentences:

- “Good morning. I’m glad we have a little time to talk today.”
- “Josh, Matthew, and David will meet us at seven thirty on Saturday.”
- “I didn’t say she borrowed the car. I said she asked about it.”
- “The total was twenty-three dollars and forty-five cents.”

Paragraph:

> Yesterday I took a walk through the neighborhood just before sunset. The air had finally cooled, and I could hear someone watering their garden across the street. I stopped for a moment to enjoy the quiet. Sometimes the simplest parts of an ordinary day are the ones I remember best. Tomorrow may be busy, but tonight I’m in no hurry.

No automatic “percent voice match” is supplied: waveform shape, pitch, and loudness are not reliable identity scores. Speaker-embedding models can supplement listening later, but their cosine scores require calibration and must not be presented as recognition guarantees.
