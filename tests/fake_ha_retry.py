#!/usr/bin/env python3
"""Listening again after a failed request (setting retry_after_error, off by default; main.c retry_ask).  Home Assistant
tells the Echo of a failed request in two ways: its own error responses ("Sorry, I couldn't understand that", "Sorry, I am
not aware of any device called X", not exposed, several by that name...) said as any reply (TTS_START's text, no flag
anywhere else; known by a phrase per language), or an ERROR event with a code.  On: after the sentence, or at once on an stt-/intent- code,
the Echo listens again without the wake word, as it does for continue_conversation, and says so in the log; as many
tries per request as retry_tries allows (1), so a failed last try ends the turn, as does silence (stt-no-text-recognized).  Off: as before.  Codes a
second request does not mend (wake-*) keep the error path."""
import asyncio, os, threading
from http.server import ThreadingHTTPServer
from aioesphomeapi import VoiceAssistantEventType as Ev
from arbecho import Echo, HA, check, until, start, run
from esphome_common import Handler

HTTP = 16985
e = Echo("Echo Study", 16983, 500)
NOT_UNDERSTOOD = "Sorry, I couldn't understand that"
NOT_UNDERSTOOD_RO = "Îmi pare rău, nu am înțeles cererea. Poți, te rog, să repeți?"


async def main():
    httpd = ThreadingHTTPServer(("127.0.0.1", HTTP), Handler); threading.Thread(target=httpd.serve_forever, daemon=True).start()
    ha = HA([e]); await start((e,), ha)
    check(await until(lambda: "voice assistant: subscribed" in e.text(), 5), "Home Assistant's voice assistant subscribed")
    url = f"http://127.0.0.1:{HTTP}/reply.wav"                 # 0.5 s of audio: the reply
    play = os.path.join(e.state, "play.raw")
    size = lambda: os.path.getsize(play) if os.path.exists(play) else 0
    again = lambda: e.text().count("listening again")

    async def woke():
        n = len(e.starts); e.wake(); check(await until(lambda: len(e.starts) == n + 1, 3), "  the wake word starts a run"); return n + 1

    async def reply(text, spoken=True):
        """what Home Assistant sends for a request answered with text: STT_END, INTENT_END, TTS_START with the words,
        TTS_END with the audio (spoken) and RUN_END; waits for the reply to be played and what follows it to start"""
        e.cli.send_voice_assistant_event(Ev.VOICE_ASSISTANT_STT_END, {"text": "turn on the lamp"})
        e.cli.send_voice_assistant_event(Ev.VOICE_ASSISTANT_INTENT_END, {"conversation_id": "c", "continue_conversation": "0"})
        e.cli.send_voice_assistant_event(Ev.VOICE_ASSISTANT_TTS_START, {"text": text})
        s = size()
        if spoken: e.cli.send_voice_assistant_event(Ev.VOICE_ASSISTANT_TTS_END, {"url": url})
        e.cli.send_voice_assistant_event(Ev.VOICE_ASSISTANT_RUN_END, None)
        if spoken: check(await until(lambda: size() > s, 3), "  the reply was played")
        await asyncio.sleep(1.5)

    async def failed(code):
        e.cli.send_voice_assistant_event(Ev.VOICE_ASSISTANT_ERROR, {"code": code, "message": "test"}); await asyncio.sleep(1)

    async def nothing_said():                       # the run open ends quietly: HA heard nothing
        n, a = len(e.starts), again()
        await failed("stt-no-text-recognized")
        check(len(e.starts) == n and again() == a and "pipeline: nothing said" in e.text(), "  silence in that run ends the turn quietly, no third run")

    # --- off (the default): as before
    n, a = await woke(), again(); await reply(NOT_UNDERSTOOD)
    check(len(e.starts) == n and again() == a, 'off: "couldn\'t understand" is said and nothing listens afterwards')
    n = await woke(); await failed("stt-stream-failed")
    check(len(e.starts) == n and again() == a, "off: a speech-to-text failure ends the turn, nothing listens")

    e.page.set(retry_after_error="on")
    check("retry_after_error=on" in open(os.path.join(e.state, "config")).read(), "on: set from the settings page, kept in state/config")

    # the sentence, spoken: once it is said the Echo listens again; silence then ends it
    n, a = await woke(), again(); await reply(NOT_UNDERSTOOD)
    check(len(e.starts) == n + 1 and again() == a + 1 and "pipeline: not understood: listening again" in e.text(),
          f'on: "couldn\'t understand" said, then a new run listens ({len(e.starts) - n} started)')
    await nothing_said()
    # a second try that is not understood either: the turn ends, no loop
    n, a = await woke(), again(); await reply(NOT_UNDERSTOOD)
    check(len(e.starts) == n + 1 and again() == a + 1, "on: not understood: the second try listens")
    await reply(NOT_UNDERSTOOD)
    check(len(e.starts) == n + 1 and again() == a + 1, "on: not understood twice: no third try")
    # a request understood after the second try: nothing more; and the next request may be retried again
    n, a = await woke(), again(); await reply(NOT_UNDERSTOOD); await reply("The lamp is on")
    check(len(e.starts) == n + 1 and again() == a + 1, "on: the second try understood: the turn ends")
    n, a = await woke(), again(); await reply(NOT_UNDERSTOOD)
    check(len(e.starts) == n + 1 and again() == a + 1, "on: the next request is retried as well (the one try is per request)")
    await nothing_said()
    # Home Assistant's Romanian sentence, and the sentence without audio (TTS off: RUN_END comes at once)
    n, a = await woke(), again(); await reply(NOT_UNDERSTOOD_RO)
    check(len(e.starts) == n + 1 and again() == a + 1, "on: the Romanian sentence is one too")
    await nothing_said()
    n, a = await woke(), again(); await reply(NOT_UNDERSTOOD, spoken=False)
    check(len(e.starts) == n + 1 and again() == a + 1, "on: the sentence with no audio: the new run starts at RUN_END")
    await nothing_said()
    # an ordinary reply: no retry; Home Assistant's other error responses (a device, area or floor it does not know,
    # one not exposed, several by that name), in languages whose sentence opens with the name: a retry each
    n, a = await woke(), again(); await reply("The lamp is on")
    check(len(e.starts) == n and again() == a, "on: an ordinary reply: nothing listens afterwards")
    n, a = await woke(), again(); await reply("Turned on the light. Sorry about the delay")
    check(len(e.starts) == n and again() == a, "on: a reply with a sorry inside: nothing listens afterwards")
    for text in ("Sorry, I am not aware of any device called lamb", "Îmi pare rău, nu cunosc nicio entitate numită lampă",
                 "Lampe existiert nicht", "Küche har ingen enhet eller entitet som heter lampa", "Lampa nie została udostępniona",
                 "すみません、ランプという名前のデバイスが複数あります"):
        n, a = await woke(), again(); await reply(text)
        check(len(e.starts) == n + 1 and again() == a + 1, f"on: {text[:32]!r}: an unknown device, area or name: listens again")
        await nothing_said()
    # errors with a code: speech-to-text or the agent failed: at once; a wake word failure: the error path
    n, a = await woke(), again(); await failed("stt-stream-failed")
    check(len(e.starts) == n + 1 and again() == a + 1 and "pipeline: stt-stream-failed: listening again" in e.text(),
          "on: speech-to-text failed: listens again at once")
    await nothing_said()
    n, a = await woke(), again(); await failed("intent-failed")
    check(len(e.starts) == n + 1 and again() == a + 1, "on: the agent failed: listens again at once")
    await failed("intent-failed")
    check(len(e.starts) == n + 1 and again() == a + 1, "on: the agent failed twice: no third try")
    n, a = await woke(), again(); await failed("wake-word-timeout")
    check(len(e.starts) == n and again() == a, "on: a wake word failure is not retried")
    # more tries (setting retry_tries): two retries, a third failure ends the turn; the number is per request
    e.page.set(retry_tries="2")
    check("retry_tries=2" in open(os.path.join(e.state, "config")).read(), "tries 2: set from the settings page, kept in state/config")
    n, a = await woke(), again(); await reply(NOT_UNDERSTOOD)
    check(len(e.starts) == n + 1 and again() == a + 1 and "listening again (try 1 of 2)" in e.text(), "tries 2: the first failure: listens again")
    await reply(NOT_UNDERSTOOD)
    check(len(e.starts) == n + 2 and again() == a + 2 and "listening again (try 2 of 2)" in e.text(), "tries 2: the second failure: listens once more")
    await reply(NOT_UNDERSTOOD)
    check(len(e.starts) == n + 2 and again() == a + 2, "tries 2: the third failure ends the turn, no fourth run")
    n, a = await woke(), again(); await failed("intent-failed"); await failed("intent-failed")
    check(len(e.starts) == n + 2 and again() == a + 2, "tries 2: the agent failing twice: two more runs")
    await nothing_said()
    e.page.set(retry_tries="1")
    n, a = await woke(), again(); await reply(NOT_UNDERSTOOD); await reply(NOT_UNDERSTOOD)
    check(len(e.starts) == n + 1 and again() == a + 1, "tries 1 again: one retry, as before")
    # getting out of a try: "stop" (the keyword, or said) and words of giving up end it quietly, as the button; the
    # words are not sent on as one more request (which would fail and be tried again)
    e.page.set(retry_tries="3")
    async def withdrawn(text):
        n, a = await woke(), again(); await reply(NOT_UNDERSTOOD)
        check(len(e.starts) == n + 1, f"  the try listens")
        e.cli.send_voice_assistant_event(Ev.VOICE_ASSISTANT_STT_END, {"text": text})
        check(await until(lambda: "withdrawn, listening ended" in e.text()[-400:], 3), f'  "{text}" said on the try: listening ended')
        await asyncio.sleep(1)
        check(len(e.starts) == n + 1 and again() == a + 1, f'  "{text}": no further try')
    for text in ("renunță", "Renunta.", "Anulează", "stop", "never mind", "Vergiss es", "nic"): await withdrawn(text)
    n, a = await woke(), again(); await reply(NOT_UNDERSTOOD)
    e.stop(); check(await until(lambda: "stop: listening ended (the try after a failed request)" in e.text(), 3), 'the "stop" keyword on a try: listening ended')
    await asyncio.sleep(1); check(len(e.starts) == n + 1 and again() == a + 1, "  no further try")
    n, a = await woke(), again(); e.cli.send_voice_assistant_event(Ev.VOICE_ASSISTANT_STT_END, {"text": "renunță"}); await asyncio.sleep(1)
    check("withdrawn" not in e.text()[-300:] and len(e.starts) == n, 'the request itself: "renunță" goes to Home Assistant as any request')
    await reply(NOT_UNDERSTOOD); await nothing_said()
    e.page.set(retry_tries="1")
    # muted: the Echo does not take requests, so it does not listen again either
    e.cli.switch_command(e.by["mute"].key, True); await asyncio.sleep(0.5)
    n, a = len(e.starts), again(); e.cli.switch_command(e.by["mute"].key, False); await asyncio.sleep(0.5)
    check(len(e.starts) == n and again() == a, "on: mute and back changes nothing by itself")
    # off again: as at the start
    e.page.set(retry_after_error="off")
    n, a = await woke(), again(); await reply(NOT_UNDERSTOOD)
    check(len(e.starts) == n and again() == a, "off again: nothing listens after the sentence")
    httpd.shutdown()


run(main, (e,))
