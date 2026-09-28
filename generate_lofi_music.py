import math
import numpy as np
import scipy.io.wavfile as wav

def generate_upbeat_lofi_track(filename="/config/.gemini/antigravity/brain/08d2929c-d1d5-4ee0-85a0-9038a785abd7/lofi_music.wav", duration=36.0, sample_rate=44100):
    num_samples = int(duration * sample_rate)
    audio = np.zeros(num_samples, dtype=np.float32)
    t = np.linspace(0, duration, num_samples, endpoint=False)

    bpm = 84.0
    beat_dur = 60.0 / bpm
    bar_dur = beat_dur * 4.0

    # Frequencies for jazzy lo-fi chords
    # Cmaj7, Am7, Dm7, G13
    chords = [
        [261.63, 329.63, 392.00, 493.88],  # C4, E4, G4, B4
        [220.00, 261.63, 329.63, 392.00],  # A3, C4, E4, G4
        [293.66, 349.23, 440.00, 523.25],  # D4, F4, A4, C5
        [196.00, 246.94, 349.23, 440.00],  # G3, B3, F4, A4
    ]

    total_bars = int(np.ceil(duration / bar_dur))

    # 1. Synthesize Warm Electric Piano Chords
    for b in range(total_bars):
        bar_start_t = b * bar_dur
        chord = chords[b % len(chords)]

        for note_idx, freq in enumerate(chord):
            note_start_t = bar_start_t + (note_idx % 2) * 0.05
            if note_start_t >= duration:
                continue

            start_idx = int(note_start_t * sample_rate)
            end_idx = min(int((bar_start_t + bar_dur) * sample_rate), num_samples)
            note_len = end_idx - start_idx
            if note_len <= 0:
                continue

            tn = t[start_idx:end_idx] - note_start_t
            # Warm lo-fi Rhodes/synth tone: fundamental + subtle harmonics + smooth decay
            fundamental = np.sin(2 * np.pi * freq * tn)
            h2 = 0.3 * np.sin(2 * np.pi * freq * 2 * tn)
            h3 = 0.1 * np.sin(2 * np.pi * freq * 3 * tn)
            synth = fundamental + h2 + h3

            # Exponential decay envelope
            envelope = np.exp(-tn * 1.5)
            # Soft attack
            attack_len = int(0.02 * sample_rate)
            if len(envelope) > attack_len:
                envelope[:attack_len] *= np.linspace(0, 1, attack_len)

            audio[start_idx:end_idx] += synth * envelope * 0.12

    # 2. Add Upbeat Drum Beat (Kick, Snare, Hi-Hats)
    eight_note_dur = beat_dur / 2.0
    total_eighths = int(duration / eight_note_dur)

    for step in range(total_eighths):
        step_time = step * eight_note_dur
        start_idx = int(step_time * sample_rate)
        beat_in_bar = step % 8

        # Kick on 0, 3, 4
        if beat_in_bar in [0, 3, 4]:
            kick_len = int(0.18 * sample_rate)
            end_idx = min(start_idx + kick_len, num_samples)
            l = end_idx - start_idx
            if l > 0:
                tk = t[start_idx:end_idx] - step_time
                # Pitch sweep kick (130 Hz down to 45 Hz)
                freq_sweep = 45.0 + 85.0 * np.exp(-tk * 35.0)
                phase = 2 * np.pi * np.cumsum(freq_sweep) / sample_rate
                kick = np.sin(phase) * np.exp(-tk * 14.0)
                audio[start_idx:end_idx] += kick * 0.35

        # Snare on beats 2 and 6 (i.e. quarters 2 & 4)
        if beat_in_bar in [2, 6]:
            snare_len = int(0.15 * sample_rate)
            end_idx = min(start_idx + snare_len, num_samples)
            l = end_idx - start_idx
            if l > 0:
                ts = t[start_idx:end_idx] - step_time
                # Noise + body tone
                noise = np.random.uniform(-1, 1, l)
                body = np.sin(2 * np.pi * 180 * ts) * np.exp(-ts * 30.0)
                snare = (noise * 0.7 + body * 0.3) * np.exp(-ts * 20.0)
                audio[start_idx:end_idx] += snare * 0.22

        # Hi-Hat on every 8th note
        hat_len = int(0.04 * sample_rate)
        end_idx = min(start_idx + hat_len, num_samples)
        l = end_idx - start_idx
        if l > 0:
            th = t[start_idx:end_idx] - step_time
            noise = np.random.uniform(-1, 1, l)
            hat = noise * np.exp(-th * 80.0)
            audio[start_idx:end_idx] += hat * (0.08 if beat_in_bar % 2 == 1 else 0.05)

    # 3. Add Gentle Vinyl Crackle
    crackle = np.random.normal(0, 0.008, num_samples)
    pop_indices = np.random.choice(num_samples, size=int(duration * 6), replace=False)
    crackle[pop_indices] += np.random.uniform(0.03, 0.08, len(pop_indices))
    audio += crackle * 0.3

    # Normalize audio cleanly
    max_val = np.max(np.abs(audio))
    if max_val > 0:
        audio = (audio / max_val) * 0.85

    # Convert to 16-bit PCM WAV
    audio_int16 = (audio * 32767).astype(np.int16)
    wav.write(filename, sample_rate, audio_int16)
    print(f"Generated lo-fi music track: {filename}")

if __name__ == "__main__":
    generate_upbeat_lofi_track()
