#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import speech_recognition as sr
from pydub import AudioSegment
import json
from datetime import datetime
import glob
import math


class BulgarianAudioTranscriber:
    def __init__(self, audio_folder="audio_segments", output_folder="transcripts"):
        self.audio_folder = audio_folder
        self.output_folder = output_folder
        self.recognizer = sr.Recognizer()

        # Създаване на папките за изходни файлове
        if not os.path.exists(output_folder):
            os.makedirs(output_folder)

        # Папка за генерираните сегменти
        self.segments_folder = os.path.join(output_folder, "generated_segments")
        if not os.path.exists(self.segments_folder):
            os.makedirs(self.segments_folder)

    def split_audio_file(self, input_file, segment_duration_minutes=3.07):
        """Разбива голям аудио файл на сегменти от ~3:04 минути"""
        try:
            print(f"🔪 Зареждане на аудио файл: {os.path.basename(input_file)}")
            audio = AudioSegment.from_file(input_file)

            # Конвертиране на минутите в милисекунди
            segment_duration_ms = segment_duration_minutes * 60 * 1000

            # Изчисляване на броя сегменти
            total_duration_ms = len(audio)
            total_segments = math.ceil(total_duration_ms / segment_duration_ms)

            print(f"📊 Обща продължителност: {total_duration_ms // 60000:.1f} минути")
            print(f"📊 Ще се създадат {total_segments} сегмента от ~{segment_duration_minutes:.1f} минути")
            print(f"🔄 Започва разбиването...\n")

            segment_files = []

            for i in range(total_segments):
                # Изчисляване на началото и края на сегмента
                start_ms = i * segment_duration_ms
                end_ms = min((i + 1) * segment_duration_ms, total_duration_ms)

                # Извличане на сегмента
                segment = audio[start_ms:end_ms]

                # Име на файла
                base_name = os.path.splitext(os.path.basename(input_file))[0]
                segment_filename = f"{base_name}_segment_{i + 1:03d}.wav"
                segment_path = os.path.join(self.segments_folder, segment_filename)

                # Експортиране на сегмента
                segment.export(segment_path, format="wav", parameters=["-ar", "16000", "-ac", "1"])
                segment_files.append(segment_path)

                # Показване на прогреса
                actual_duration = (end_ms - start_ms) / 1000 / 60
                print(f"✓ Създаден сегмент {i + 1}/{total_segments}: {segment_filename} ({actual_duration:.2f} мин)")

            print(f"\n✅ Успешно създадени {len(segment_files)} сегмента!")
            return segment_files

        except Exception as e:
            print(f"❌ Грешка при разбиване на файла: {e}")
            return []

    def convert_to_wav(self, input_file):
        """Конвертира аудио файл в WAV формат за по-добро разпознаване"""
        try:
            audio = AudioSegment.from_file(input_file)
            # Конвертиране в 16kHz mono WAV за оптимално разпознаване
            audio = audio.set_frame_rate(16000).set_channels(1)

            wav_file = input_file.rsplit('.', 1)[0] + '_converted.wav'
            audio.export(wav_file, format="wav")
            return wav_file
        except Exception as e:
            print(f"Грешка при конвертиране на {input_file}: {e}")
            return None

    def transcribe_audio_segment(self, audio_file, segment_number):
        """Транскрибира един аудио сегмент на български език - продължава при грешки"""
        try:
            # Конвертиране в WAV ако е необходимо
            if not audio_file.lower().endswith('.wav'):
                wav_file = self.convert_to_wav(audio_file)
                if not wav_file:
                    print(f"⚠ Сегмент {segment_number}: Пропуснат - грешка при конвертиране")
                    return ""  # Връща празен текст вместо None
            else:
                wav_file = audio_file

            # Зареждане на аудио файла
            with sr.AudioFile(wav_file) as source:
                # Премахване на фонов шум (намалено време за по-бърза обработка)
                self.recognizer.adjust_for_ambient_noise(source, duration=0.2)
                audio_data = self.recognizer.record(source)

            # Разпознаване с Google Speech Recognition (поддържа български)
            try:
                text = self.recognizer.recognize_google(
                    audio_data,
                    language='bg-BG'  # Български език
                )
                print(f"✓ Сегмент {segment_number}: Успешно транскрибиран ({len(text.split())} думи)")
                return text

            except sr.UnknownValueError:
                print(f"⚠ Сегмент {segment_number}: Пропуснат - няма разпознаваема реч")
                return ""  # Празен текст вместо маркер

            except sr.RequestError as e:
                print(f"⚠ Сегмент {segment_number}: Пропуснат - грешка в услугата")
                return ""  # Празен текст вместо маркер

        except Exception as e:
            print(f"⚠ Сегмент {segment_number}: Пропуснат - {str(e)[:50]}...")
            return ""  # Връща празен текст при всякаква грешка

        finally:
            # Изтриване на временния WAV файл
            try:
                if 'wav_file' in locals() and wav_file != audio_file and os.path.exists(wav_file):
                    os.remove(wav_file)
            except:
                pass  # Игнорира грешки при изтриване

    def process_large_file(self, input_file, segment_duration_minutes=3.07):
        """Обработва голям аудио файл - разбива го и транскрибира"""
        print(f"📁 Обработка на голям файл: {os.path.basename(input_file)}")

        # Разбиване на сегменти
        segment_files = self.split_audio_file(input_file, segment_duration_minutes)

        if not segment_files:
            print("❌ Неуспешно разбиване на файла")
            return

        # Транскрибиране на сегментите
        print(f"\n🎯 Започва транскрипцията на {len(segment_files)} сегмента...\n")

        transcripts = []
        full_text = []

        for i, segment_file in enumerate(segment_files, 1):
            print(f"🎵 Транскрипция на сегмент {i}/{len(segment_files)}: {os.path.basename(segment_file)}")

            # Транскрипция на сегмента
            text = self.transcribe_audio_segment(segment_file, i)

            # Запазване на резултата
            segment_data = {
                "segment": i,
                "file": os.path.basename(segment_file),
                "original_file": os.path.basename(input_file),
                "text": text
            }

            transcripts.append(segment_data)

            # Добавяне към пълния текст (само ако има текст)
            if text.strip():  # Проверява дали има реален текст
                full_text.append(text)

            print(f"💬 Текст: {text if text else '[Пропуснат сегмент]'}\n")

        # Запазване на резултатите
        self.save_results(transcripts, full_text, os.path.basename(input_file))

        # Запитване дали да се изтрият генерираните сегменти
        self.cleanup_segments(segment_files)

    def process_segments_folder(self):
        """Обработва готови аудио сегменти в папката"""

        # Търсене на всички аудио файлове
        audio_extensions = ['*.mp3', '*.wav', '*.m4a', '*.flac', '*.aac', '*.ogg']
        audio_files = []

        for extension in audio_extensions:
            audio_files.extend(glob.glob(os.path.join(self.audio_folder, extension)))

        if not audio_files:
            print(f"❌ Не са намерени аудио файлове в папка '{self.audio_folder}'")
            return

        # Сортиране на файловете по име
        audio_files.sort()

        print(f"📁 Намерени {len(audio_files)} аудио файла за обработка")
        print("🎯 Започва транскрипцията на български език...\n")

        transcripts = []
        full_text = []

        for i, audio_file in enumerate(audio_files, 1):
            print(f"🎵 Обработка на файл {i}/{len(audio_files)}: {os.path.basename(audio_file)}")

            # Транскрипция на сегмента
            text = self.transcribe_audio_segment(audio_file, i)

            # Запазване на резултата
            segment_data = {
                "segment": i,
                "file": os.path.basename(audio_file),
                "text": text
            }

            transcripts.append(segment_data)

            # Добавяне към пълния текст (само ако има текст)
            if text.strip():  # Проверява дали има реален текст
                full_text.append(text)

            print(f"💬 Текст: {text if text else '[Пропуснат сегмент]'}\n")

        # Запазване на резултатите
        self.save_results(transcripts, full_text)

    def cleanup_segments(self, segment_files):
        """Пита дали да се изтрият генерираните сегменти"""
        try:
            response = input(f"\n🗑️ Да се изтрият {len(segment_files)} генерирани сегмента? (y/N): ").strip().lower()
            if response in ['y', 'yes', 'да']:
                for segment_file in segment_files:
                    if os.path.exists(segment_file):
                        os.remove(segment_file)
                print("✅ Генерираните сегменти са изтрити")

                # Изтриване на папката ако е празна
                try:
                    os.rmdir(self.segments_folder)
                    print("✅ Папката с генерираните сегменти е изтрита")
                except:
                    pass
            else:
                print(f"📁 Генерираните сегменти са запазени в: {self.segments_folder}")
        except:
            print(f"📁 Генерираните сегменти са запазени в: {self.segments_folder}")

    def save_results(self, transcripts, full_text, original_filename=None):
        """Запазва резултатите в различни формати"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Добавяне на името на оригиналния файл в имената на изходните файлове
        file_prefix = f"{os.path.splitext(original_filename)[0]}_" if original_filename else ""

        # 1. JSON файл с подробните данни
        json_file = os.path.join(self.output_folder, f"{file_prefix}transcripts_{timestamp}.json")
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(transcripts, f, ensure_ascii=False, indent=2)

        # 2. Файл с извлечения текст по сегменти
        segments_file = os.path.join(self.output_folder, f"{file_prefix}segments_text_{timestamp}.txt")
        with open(segments_file, 'w', encoding='utf-8') as f:
            f.write("ИЗВЛЕЧЕН ТЕКСТ ПО СЕГМЕНТИ\n")
            f.write("=" * 40 + "\n")
            if original_filename:
                f.write(f"Оригинален файл: {original_filename}\n")
            f.write(f"Дата: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}\n\n")

            for t in transcripts:
                f.write(f"Сегмент {t['segment']} ({t['file']}):\n")
                f.write(f"{t['text']}\n\n")

        # 3. Пълният текст като един документ
        full_text_file = os.path.join(self.output_folder, f"{file_prefix}full_text_{timestamp}.txt")
        with open(full_text_file, 'w', encoding='utf-8') as f:
            f.write("ПЪЛЕН ИЗВЛЕЧЕН ТЕКСТ\n")
            f.write("=" * 30 + "\n")
            if original_filename:
                f.write(f"Оригинален файл: {original_filename}\n")
            f.write(f"Дата: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}\n\n")
            combined_text = " ".join(full_text)
            f.write(combined_text)

        print("✅ Завършено! Създадени файлове:")
        print(f"📄 JSON данни: {json_file}")
        print(f"📄 Текст по сегменти: {segments_file}")
        print(f"📄 Пълен текст: {full_text_file}")
        print(f"\n📊 Статистика:")
        print(f"   • Общо сегменти: {len(transcripts)}")
        print(f"   • Успешно транскрибирани: {len(full_text)}")
        print(f"   • Пропуснати сегменти: {len(transcripts) - len(full_text)}")
        print(f"   • Процент успех: {len(full_text) / len(transcripts) * 100:.1f}%")
        print(f"   • Общо думи: {len(' '.join(full_text).split())}")


def main():
    print("🎙️ Извличане на текст от аудио файлове (Български език)")
    print("=" * 58)

    # Избор на режим на работа
    print("\n📋 Режими на работа:")
    print("1. Обработка на готови сегменти в папка")
    print("2. Разбиване на голям файл на сегменти и транскрипция")

    mode = input("\n🔢 Изберете режим (1 или 2): ").strip()

    if mode == "2":
        # Режим за голям файл
        input_file = input("📁 Път до големия аудио файл: ").strip()

        if not os.path.exists(input_file):
            print("❌ Файлът не съществува!")
            return

        segment_duration = input("⏱️ Продължителност на сегмент в минути (Enter за 3.07): ").strip()
        if not segment_duration:
            segment_duration = 3.07
        else:
            segment_duration = float(segment_duration)

        # Създаване на транскрибера
        transcriber = BulgarianAudioTranscriber()

        # Обработка на големия файл
        transcriber.process_large_file(input_file, segment_duration)

    else:
        # Режим за готови сегменти
        audio_folder = input("📁 Папка с аудио сегменти (Enter за 'audio_segments'): ").strip()
        if not audio_folder:
            audio_folder = "audio_segments"

        # Създаване на транскрибера
        transcriber = BulgarianAudioTranscriber(audio_folder)

        # Обработка на готовите сегменти
        transcriber.process_segments_folder()


if __name__ == "__main__":
    main()
