# This fork

A fork of [Gamer92000/echo-dot-assist](https://github.com/Gamer92000/echo-dot-assist). Everything here is meant to
go upstream; this file says what has not yet, and how the branches are kept so that it can.

## Branches

- **`main`**: a mirror of upstream's `main`, nothing else. Never commit to it; bring it up to date with
  `git fetch upstream && git merge --ff-only upstream/main` (and `git push origin main`). It is what every branch for
  upstream starts from.
- **`develop`**: where the work happens and what the Echos here run. `main` plus every branch below merged in, and
  whatever is tried out. Rebuilt on `main` whenever `main` moves (merge `main` into it, or merge the still-open
  branches again onto a fresh `main`).
- **One branch per pull request**, cut from `main`, never from `develop`: `feat/<name>` or `fix/<name>`, a single
  commit each where it can be (fixups squashed with `git rebase -i --autosquash`), rebased on `main` before the pull
  request is opened or updated. Merged into `develop` too, so the Echos get it before upstream takes it.
- **`local/echo`**: device-only. `develop` plus what is specific to the Echos here (keys, hosts, trial builds).
  Never pushed anywhere.

Once upstream merges a pull request, `main` is fast-forwarded, the branch is deleted, and `develop` is rebuilt on
`main`: its commits are then upstream's.

## What this fork has that upstream does not (2026-11-13)

Merged upstream and gone from this list: #168 (Echo Show 5: Wi-Fi no longer drops every few minutes), #169 (the
clock on an idle Echo Show screen), #170 (more languages for the Echo's own words, Romanian among them).

- **Listening again after a failed request** (`feat/retry-after-error`, not yet proposed upstream). Setting "Listen
  again after a failed request" (off by default) and "Tries after a failed request" (1 to 5): when Home Assistant
  answers with one of its own error sentences ("Sorry, I couldn't understand that", a device, area or floor it does
  not know, not exposed, several by that name, timers, an unexpected error; recognised in the fourteen languages
  Home Assistant has them in) or speech-to-text or the agent failed, the Echo listens again without the wake word, as
  it does after a question. "Stop" or a word of giving up ("never mind", "cancel", "renunță", "vergiss es"...) said on
  such a try ends it quietly without sending it on. Test: `tests/fake_ha_retry.py`.
- **Wi-Fi motion survives Wi-Fi going off and on** (`fix/wifi-motion-rehook`, pull request to be opened). Android
  reloads the Wi-Fi driver whenever Wi-Fi is switched off and on, and the kernel module's hook went with the old
  driver: no frame was counted any more and the sensor stayed "unknown" for good. The module now hooks the driver
  again each time it comes back (a module notifier), and hassmic reports a counter that stopped for a minute and
  shows the sensor as unknown instead of staying silent. Needs a restart of the Echo once (the old module cannot
  be unloaded).

What each pull request should say, and the commands to push them, are kept outside the repository.
