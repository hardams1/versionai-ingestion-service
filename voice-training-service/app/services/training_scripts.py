from __future__ import annotations

from app.models.schemas import SUPPORTED_LANGUAGES, ScriptSection, TrainingScript

SCRIPTS: dict[str, list[ScriptSection]] = {
    "en": [
        ScriptSection(
            title="Part 1 — Natural Introduction",
            instruction="Read slowly and naturally, as if talking to a close friend.",
            prompts=[
                "Hello, my name is [your name] and this is my natural speaking voice. "
                "I am recording this so that the artificial intelligence can learn exactly "
                "how I sound. I want it to capture my tone, my rhythm, and every subtle "
                "detail of the way I speak.",
            ],
        ),
        ScriptSection(
            title="Part 2 — Storytelling & Emotion",
            instruction="Let your emotions come through. Smile when it feels right. Slow down for serious parts.",
            prompts=[
                "One of my favorite memories is from when I was about seven years old. "
                "My grandmother used to tell me stories before bedtime, and her voice would "
                "rise and fall like music. I would lie there, completely captivated, hanging "
                "on every single word. Those moments shaped who I am today.",

                "Sometimes life throws unexpected challenges at you, and you have to decide "
                "whether to give up or push forward. I have learned that persistence is "
                "everything. Even when things seem impossible, taking one small step at a "
                "time eventually leads you somewhere amazing.",
            ],
        ),
        ScriptSection(
            title="Part 3 — Phonetic Coverage",
            instruction="Read clearly. These sentences are designed to capture every sound in your voice.",
            prompts=[
                "The quick brown fox jumps over the lazy dog, while a jovial crowd gathers "
                "by the buzzing beehive near the old oak tree. A gentle breeze carries the "
                "fragrance of jasmine and fresh thyme through the open kitchen window.",

                "She sells seashells by the seashore. Beneath the azure sky, a flock of "
                "geese flew southward over the village church. Judge my vow to fix the "
                "dozen broken zippers on those heavy jackets before Thursday morning.",
            ],
        ),
        ScriptSection(
            title="Part 4 — Questions & Exclamations",
            instruction="Express genuine surprise and curiosity. Vary your pitch naturally.",
            prompts=[
                "Wait, really? Are you absolutely sure about that? I never in a million "
                "years would have guessed! That is honestly one of the most surprising "
                "things I have heard all week. Tell me more about how you did it.",

                "Do you think we should take the highway or the scenic route? The highway "
                "is faster, but the scenic route has those beautiful mountain views. "
                "What do you think? I will leave it entirely up to you.",
            ],
        ),
        ScriptSection(
            title="Part 5 — Closing",
            instruction="Finish with your natural, relaxed speaking voice.",
            prompts=[
                "And that concludes my voice recording. I have tried to speak as naturally "
                "as possible throughout this entire session, using my real voice with all "
                "its unique characteristics. This is genuinely how I sound. Thank you.",
            ],
        ),
    ],
    "yo": [
        ScriptSection(
            title="Ìpín 1 — Ìfihàn àti Ọ̀rọ̀ Àdájọ́",
            instruction="Ka gbogbo ọ̀rọ̀ wọ̀nyí pẹ̀lú ohùn rẹ àdájọ́. Sọ̀rọ̀ bí ẹni pé o ń bá ọ̀rẹ́ rẹ sọ̀rọ̀.",
            prompts=[
                "Orúkọ mi ni [orúkọ rẹ], mo sì fẹ́ kí ẹ̀rọ yìí máa sọ̀rọ̀ bí ẹni pé èmi ni. "
                "Mo ń gbà ohùn mi sílẹ̀ kí ẹ̀rọ náà lè mọ ohùn mi dáadáa. "
                "Mo fẹ́ kí ó gbọ́ bí mo ṣe ń sọ̀rọ̀ ní gbogbo ìgbà.",

                "Mo dàgbà ní [ìlú rẹ], ibẹ̀ sì ni mo ti ń gbé títí di ìsinsìnyí. "
                "Ohùn mi jẹ́ àpẹẹrẹ ti ibi tí mo ti wá. Ẹni kọ̀ọ̀kan ní ohùn tí ó yàtọ̀ "
                "sí ti àwọn mìíràn, ohùn mi sì ń sọ ìtàn ìgbésí ayé mi.",

                "Ọjọ́ yìí, mo máa ka ọ̀pọ̀lọpọ̀ ọ̀rọ̀ tí ó ní ìmọ̀lára oríṣiríṣi. "
                "Èyí yóò ṣe ìrànlọ́wọ́ fún ẹ̀rọ náà láti mọ bí mo ṣe ń sọ̀rọ̀ "
                "nígbà tí inú mi dùn, tàbí nígbà tí mo ń ronú jìnnà.",
            ],
        ),
        ScriptSection(
            title="Ìpín 2 — Ìtàn, Ìrírí àti Ìmọ̀lára",
            instruction="Jẹ́ kí ìmọ̀lára rẹ hàn nínú ohùn rẹ. Sọ̀rọ̀ pẹ̀lú ìdùnnú àti ìtara.",
            prompts=[
                "Nígbà tí mo wà kékeré, ohun tí mo fẹ́ràn jùlọ ni láti ṣeré pẹ̀lú àwọn ọ̀rẹ́ mi "
                "ní àgbàlá ilé wa. A máa ń ṣeré títí tí oòrùn yóò fi wọ̀. "
                "Àwọn ìrántí wọ̀nyí ṣe pàtàkì fún mi gan-an.",

                "Ìrántí kan tí mo nífẹ̀ẹ́ sí ni nígbà tí ìdílé mi lọ sí irin-àjò papọ̀. "
                "A jẹun, a ṣeré, a sì kọrin papọ̀. Ó dára gan-an. "
                "Mo gbàgbọ́ pé ìfẹ́ ìdílé ni ohun tí ó ṣe pàtàkì jù lọ nínú ìgbésí ayé.",

                "Nígbà mìíràn, ìgbésí ayé lè ṣòro, ṣùgbọ́n mo ti kọ́ pé ìfaradà ni gbogbo rẹ̀. "
                "Bí a bá ń gbìyànjú lójoojúmọ́, a máa dé ibi tí a ń lọ nígbẹ̀yìngbẹ́yín. "
                "Ohùn mi yìí ni ohùn gidi mi. Ẹ ṣeun fún gbígbọ́.",
            ],
        ),
    ],
    "pcm": [
        ScriptSection(
            title="Part 1 — Introduction & Normal Gist",
            instruction="Talk am like say you dey yarn with your paddy for street. Make am natural.",
            prompts=[
                "My name na [your name], and na my voice be dis. I dey record am so that "
                "di AI fit learn how I dey talk. I wan make e sound exactly like me, "
                "with all my vibes and di way wey I dey express myself.",

                "I grow up for [your city], and di way wey I dey talk show where I come from. "
                "Everybody get im own voice wey dey different, and my own dey tell my story. "
                "I proud of di way wey I dey sound, and I wan make di technology capture am well well.",

                "Today, I go read plenty things wey go cover different emotions and sounds. "
                "Dis one go help di AI understand not just wetin I dey talk, "
                "but how I dey talk am, whether I dey happy, serious, or excited.",
            ],
        ),
        ScriptSection(
            title="Part 2 — Story Time & Emotion",
            instruction="Gist with passion. Make your voice show how you feel about wetin you dey talk.",
            prompts=[
                "When I be small pikin, the thing wey I like pass na to dey play with my friends "
                "for street until evening. My mama go dey call my name from far, and I go pretend "
                "say I no hear. Those times sweet me die, I no go ever forget am.",

                "I remember the first time wey I chop amala and ewedu with gbegiri soup. "
                "My guy, e sweet my belle die! Since that day, na my favorite food be that. "
                "Anytime I chop am, e dey remind me of home and all the good times.",

                "Life no be easy, but we dey push am. Na so life be for Naija, "
                "but di thing wey I don learn be say if you no give up, "
                "everything go eventually come together. Abeg make we just dey do our thing.",

                "And na so my voice recording don finish. I don try to talk as natural as possible "
                "throughout everything. Na my real voice be dis with all im unique style. "
                "I hope say di technology go capture everything well. Thank you for listening.",
            ],
        ),
    ],
}


def get_training_script(language: str) -> TrainingScript:
    lang_code = language if language in SCRIPTS else "en"
    sections = SCRIPTS.get(lang_code, SCRIPTS["en"])
    total_prompts = sum(len(s.prompts) for s in sections)
    est_minutes = round(total_prompts * 12 / 60)

    return TrainingScript(
        language=lang_code,
        language_name=SUPPORTED_LANGUAGES.get(lang_code, "English"),
        sections=sections,
        estimated_duration_minutes=max(2, est_minutes),
    )
