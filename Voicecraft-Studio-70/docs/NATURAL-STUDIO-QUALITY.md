# Natural Studio Quality — Voicecraft Studio 70, release 70.2.0

## What was upgraded

This is the existing application and local Chatterbox 0.1.7 runtime, not a replacement application. Both Original and Turbo, voice profiles, authorization, recording/import, styles, voice adjustments, playback and WAV/MP3 export remain. The preferred v70.1.1 launch path is restored; the v70.1.2 opening screen is not used. Historical v70.1.2 helper files remain for source preservation.

New profiles prefer **NATURAL STUDIO QUALITY**. Existing profiles retain their previous settings; select the quality preset to opt in. The preset is not a newly trained model and its name is not a guarantee of subjective quality.

- Speech is planned at sentence/section boundaries; overlong sentences prefer clause boundaries before a bounded word-boundary fallback. Punctuation and questions remain in the model input. Standard generation retains the old 220-character splitting for A/B comparison.
- Conservative English number, quantity and abbreviation expansion is visible using **Review prepared script**. Dates, times, versions and URLs are retained for manual review. User-editable literal pronunciation corrections are saved per profile. These are spoken spellings, not a phoneme/SSML API.
- The actual model uses its reference conditioning and native sampling. Natural mode supplies supported `top_p=0.95` and `repetition_penalty=1.2`; temperature remains adjustable. Original additionally accepts exaggeration and CFG. The recommended Original button selects temperature 0.7, exaggeration 0.5, CFG 0.35 and pause 0.2; it preserves reference, pitch, speed and tone. These are conservative starting settings, not empirically optimal settings for the user's voice.
- Turbo does **not** gain Original's CFG/exaggeration controls. No unsupported word-emphasis, SSML, decoder-step or context API is invented. Per-word stress and exact prosody remain model limitations. The model's punctuation and reference conditioning can influence delivery but cannot guarantee Descript-like acting.
- Short boundary padding is adapted to sentence/section boundaries and existing quiet edges. Only excessive edge padding is shortened; internal breaths and model-generated pauses remain. Sub-millisecond endpoint tapers avoid clicks. There is no pitch/EQ trick standing in for model-level delivery.
- One to three independent seeded takes can be generated. **Keep as Preferred Take** records a choice without deleting other takes; all takes remain independently playable/exportable. **Compare Standard / Natural** uses the same script, engine, reference and seed; the existing engine-comparison control can compare Original and Turbo. Users choose by listening; no automatic perceptual ranking is claimed.
- Full Natural narrations retain per-segment, pre-effect WAV stems. **Regenerate Sentence** synthesizes just the chosen sentence and reuses all other stems, then assembles a new output using the saved settings/reference. Originals remain unchanged. Previews, old Standard audio and manually edited copies lack sentence stems and cannot use this feature. Deleting history removes the corresponding stems. Stems increase recording storage, not shared model storage.
- A short educational reference-reading script encourages conversational questions and explanations without putting on a different voice. Longer existing reading scripts remain available; select a clean section for model conditioning.
- Clean-reference suggestions inspect up to the existing 120-second recording limit. They rank clipping/quietness/energy contrast, not speaker identity or actual speech content. Preview a selected 5.1–20-second section, with conservative edge trimming, bounded level normalization and optional gentle denoising, before saving a new reference. Original recordings and references remain saved. Natural narration asks for a selected section rather than feeding a reference longer than 20 seconds into the model. WAV, MP3, M4A and audio extracted from MP4 are supported (25 MB upload limit).
- Optional Descript benchmark playback uses a local browser Blob URL inside the desktop window. The selected benchmark is not uploaded, persisted, or used for training. No benchmark was supplied during development.

## Local hardware and failure behavior

No cloud inference, account or API key is added. Initial downloads are from the existing official sources; inference reads verified local weights. Models remain shared across profiles. Auto device selection uses CUDA when the installed PyTorch build/driver supports it. Existing CUDA OOM handling unloads the failed model and latches CPU fallback to avoid retrying the same GPU allocation repeatedly. Explicit CUDA selection may return an error; choose Auto/CPU as an alternative.

A conservative system-RAM preflight checks for 8 GB available before an Original model load and 4 GB for Turbo/Seed. These are safety thresholds, **not measured VRAM requirements**. Close other applications or select Turbo when the preflight fails. This reduces avoidable memory failures but is not a hard OS memory reservation or a guarantee against OOM. The app keeps one inference worker; model weights are not duplicated per family member. Job elapsed time updates while inference continues; profile/status requests remain responsive in the blocked-inference test.

The target RTX 2060 6 GB, Windows microphone and actual user voice were not accessible in the cloud. Physical GPU fit, device performance and perceptual similarity cannot be certified here. CPU fallback is slower and remains usable; quality takes priority over speed.

## Versions and official model evaluation (October 15, 2026)

The application retains Python 3.11.9 x64 for Windows, PyTorch/torchaudio 2.6.0 (CUDA 12.4 or CPU), chatterbox-tts 0.1.7, Electron 44.7.0, FastAPI 0.115.12, NumPy 1.26.4 and SoundFile 0.13.1. Constraints remain in requirements-windows-lock.txt. The cloud uses Python 3.11.16 with CPU PyTorch. No speech package or model weights were silently replaced.

| Candidate | Official license/capability evidence | Decision and limits |
| --- | --- | --- |
| Original Chatterbox | MIT; English reference cloning; actual `temperature`, `exaggeration`, `cfg_weight`, `top_p`, `min_p`, repetition controls in installed 0.1.7 | Retained and tested. Recommended as an expressive option, not declared a subjective winner. Exact RTX 2060 fit not measured. |
| Chatterbox Turbo | MIT; 350M upstream description; reference-conditioned English generation, temperature/top-p/top-k/repetition controls; no CFG/exaggeration | Retained and tested. Existing pinned revision/decoder retained; current upstream claims are not substituted for this package's behavior. |
| Chatterbox Nano | Official ResembleAI 110M model, MIT; current upstream uses `ChatterboxTurboTTS.from_pretrained(..., nano=True)` | Investigated, not installed or benchmarked. Installed 0.1.7 `from_local(ckpt_dir, device)` lacks Nano/configuration support. Do not load Nano weights into the 350M loader. A separate compatible runtime/listening test is required; speed claims are upstream claims. |
| Qwen3-TTS 12Hz 0.6B Base | Official card Apache-2.0; local reference voice cloning, multilingual support | License allows commercial use subject to terms. Not installed/ranked. Needs its own dependency/runtime validation. Official examples use BF16/FlashAttention2; RTX 2060 requires a compatible FP16/non-Flash path instead of assuming that acceleration works. No proven Windows/6 GB fit here. |

Sources inspected:
- https://github.com/resemble-ai/chatterbox (README, MIT LICENSE, tts.py and tts_turbo.py)
- https://huggingface.co/ResembleAI/chatterbox
- https://huggingface.co/ResembleAI/chatterbox-turbo
- https://huggingface.co/ResembleAI/chatterbox-nano (official model card)
- https://huggingface.co/Qwen/Qwen3-TTS-12Hz-0.6B-Base
- https://github.com/QwenLM/Qwen3-TTS

The existing Seed-VC conversion/adaptation feature remains separate from narration generation; its prior source/license documentation remains in ENGINE-EVALUATION.md. No new restricted-use model was adopted.

## Backups and installation

Before development, the available repository source and available cloud profile/recording data were copied into private `/workspace/private-backups` ZIPs. These backups are not published in the installer or source ZIP and do not represent a backup of the inaccessible Windows PC.

The Windows installer now runs a standard-library backup script through bundled pythonw.exe before overwriting an existing installation. It stores previous source, launcher settings, profile settings, reference/original recordings and generated audio under `%LOCALAPPDATA%\Voicecraft-Studio-70\upgrade-backups`. Shared model downloads, caches and environments are excluded. The ZIP receives a CRC check, and a failed backup aborts the upgrade before old application files are replaced. A conservative disk-space check reserves room before writing. The most recent path is recorded in `last-upgrade-backup.txt`.

Fresh installation backs up any existing selected data after extracting the new runtime, before launching the application. Data files are not migrated or deleted. This does not replace keeping a separate off-drive backup. Normal installation and operation require no command prompt or PowerShell.

## Listening benchmark still required

The user has not supplied the original microphone reference, exact comparison script or Descript audio in this task. Therefore no claim is made that the new pipeline beats the existing voice, matches the user's identity, improves pronunciation on all words, eliminates omissions/repetitions, or approaches Descript's proprietary model. The implementation and technical tests enable that comparison; they do not replace listening.

Use the exact same script and original authorized reference. Generate a Standard take, a Natural take with the same engine, and an Original-versus-Turbo comparison. Load the Descript recording in the benchmark player. Compare sentence timing, questions, key-word stress, pronunciation, word completeness, accent, voice similarity and transitions at matched playback loudness. Keep the preferred take and regenerate problematic sentences. Document CPU/GPU, generation time and settings with each result.
