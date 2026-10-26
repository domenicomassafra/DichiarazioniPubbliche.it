# DP-461: private Italian WAV and independent word timing (2026-10-26)

This is a source-specific private research asset for DP-165/DP-359. It grants no right to publish a quote, identify a speaker or expose the media. It is a linguistic pronunciation recording, not a public statement by an identified public figure.

## Primary source and legal review

- Original: https://commons.wikimedia.org/wiki/File:It-a_buon_mercato.ogg . Commons identifies an Italian pronunciation recorded by Marta Carbone for Association Shtooka, with a speaker from Milan, dated 2009-07-10, uploaded on 2010-01-17 13:14 UTC. Geographic and identity metadata are attribution only; no biometric inference is made.
- Original OGG: https://upload.wikimedia.org/wikipedia/commons/d/de/It-a_buon_mercato.ogg . Retrieved on 2026-10-26; SHA-256 0ea14ab4c7318e2e7dc4ab83c469dabba16923da5add9794744d1c96a2294e7a; 20782 bytes; ETag 17619e0aa5c66e173c480cbc06f40162; Last-Modified Mon 07 Oct 2013 08:40:30 GMT. The content hash pins the observed version.
- Original file license: CC BY 3.0 US, https://creativecommons.org/licenses/by/3.0/us/deed.en and https://creativecommons.org/licenses/by/3.0/us/legalcode . The source author permits copying and adaptation subject to attribution: credit Marta Carbone / Association Shtooka and Wikimedia Commons, link original/license, and disclose conversion from OGG to WAV.
- Copyright/license finding: local private capture, retention and ASR alignment of this particular publication fall within licensed copying/adaptation with attribution. The licence is not a waiver of privacy or publicity rights. This sample has a lexical phrase rather than statements about third parties; no minor, sensitive content or inferred speaker trait is part of the data. Any credible source-rights change, privacy complaint, takedown or adverse new finding revokes this private clearance.
- Rights uses for this one content version: FETCH, STORE_BODY, ASR_MEDIA. Agent review 2026-10-26, expires within 30 days; private retention through 2026-11-25. Revocation marks the private record REVOKED and requires ending use and removing the stored media, subject to relevant retention duties. The pinned canary record is not a live DP-305 production registry grant.

## Private artifact and annotation

Private protected root on Mac Studio:
/Users/domenico/.local/share/dichiarazioni-pubbliche-captures/dp461/v1/

Owner-only files: source.ogg, source.wav, gold-v1.json, rights-audit-v1.json, annotation-provenance-v1.json and manifest-v1.json. Original OGG was converted locally with FFmpeg to mono 16 kHz 16-bit signed PCM WAV. Duration 1.750 s, WAV SHA-256 3e7f5b6a0aef39a077d78d5d6b08dc11d74668ae456a23e39148abc74e087aad.

The gold has three exact lexical tokens from the Commons original title and word starts/ends in integer milliseconds. It was produced independently of WhisperX by inspecting the original 16 kHz WAV amplitude in 20 ms bins. Estimated speech onset is about 280 ms, word transitions about 400 and 775 ms, and speech ends about 1230 ms. Comparison tolerance is 250 ms maximum.

Evidence limitation: the public source confirms the utterance but supplies no word-level annotation. The stored reference is therefore an independent, agent-generated acoustic annotation, with no separate listening-based correction. It is a provisional reference, not a published manually verified timing corpus. The authentic acoustic comparison and further timing acceptance belong to existing issue #463, after #462 provides the licensed CTC model. No acoustic accuracy score can be inferred from the present files.

SHA-256 fences:
- Canonical gold object (same canonical JSON computation as existing canary): cc8615584fb67832f06ab25d8c8f21e57c7938b8e689bdb4685a1328e10887d2
- gold-v1.json file: d6213f0898fe842eb214659d3aaefd22fe2e8af8afa58002a076b7bd920d810b
- rights-audit-v1.json file: bf53ffcaea601dedeb8a2263e5587b7ecf25f9f8f8d6ec9740b3f219d00bab00
- manifest-v1.json file: dbd9e10878f40cbff367ed52a6ba42f550e2d0eb56f66fd2300f503cc4ccc237
- Private scoped rights receipt: receipt:dp461:sha256:bf53ffcaea601dedeb8a2263e5587b7ecf25f9f8f8d6ec9740b3f219d00bab00

The manifest pins original source, hashes, private rights expiry, model-receipt path owned by #462, and the independent reference. Its reference.source points to this explanation; the private annotation is in gold-v1.json. An arbitrary URL string is not proof of independent timing.

## Reproducible existing fail-closed command

Run in a Mac Studio repository checkout, through the resource guard, with Python 3.14:

    PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=poc python3 /Users/domenico/.local/share/controlcenter/resource-guard/workload_launcher.py build -- /opt/homebrew/bin/python3.14 tools/dp165_alignment_canary.py --manifest /Users/domenico/.local/share/dichiarazioni-pubbliche-captures/dp461/v1/manifest-v1.json

The verified manifest produces HELD / WHISPERX_HOST_OR_OPT_IN_REQUIRED, exit 2 and publication_blocked=true on the Mac Studio, where local acoustic inference is not supported. The model is also pending #462. Private ephemeral manifest variants prove missing reference -> MANIFEST_REFERENCE_REQUIRED, exit 3; missing rights -> MANIFEST_ROOT_INVALID, exit 3; revoked rights -> SOURCE_USE_REVOKED, exit 2. None prints audio, transcript or a private pathname.

The same six private artifacts were installed on the MiniPC under
/home/udodo/.local/share/dichiarazioni-pubbliche-captures/dp461/v1/.
The consumer manifest differs only in absolute audio/model locations and has SHA-256
bfdfb0e3492c0f5aa43a7f9bb927cf870676e9bb65eed43109ae0f924a2d1ac2.
The installed Linux canary read back HELD / WHISPERX_HOST_OR_OPT_IN_REQUIRED
(exit 2), with rights record rights:dp461:commons-a-buon-mercato:v1 and
publication_blocked=true. The running web service reported status=ok,
contract_status=DRAFT and dossier_count=0. No acoustic inference was attempted.

This records the source-and-reference input tranche for #461. Issue #462 owns model licensing and #463 owns independent acoustic measurement, resource metrics and authentic consumer inference.
