"""End-of-speech detection from microphone levels.

Pure Python so the timing rules can be tested without Qt, a microphone or a
running voice service. Callers feed one RMS amplitude per audio frame, then
act on the single ``True`` that marks the end of the utterance.
"""
import math


class EndOfSpeech:
    """Reports when the user has stopped talking.

    A fixed amplitude threshold misreads a noisy room as endless speech and a
    quiet one as instant silence, so the noise floor is taken from the early
    frames and then tracks the ambient level while nobody is speaking. Two
    durations keep a cough from sending and a short breath from cutting a
    sentence: ``minimum_speech`` must accumulate before a pause counts, and
    ``silence`` must be sustained before the end is reported.
    """

    def __init__(self, silence=0.9, minimum_speech=0.35, calibration=0.4,
                 noise_ratio=3.0, absolute=0.012, max_floor=0.03):
        if not silence > 0:
            raise ValueError('end-of-speech pause must be positive')
        if minimum_speech < 0 or calibration < 0:
            raise ValueError('durations must not be negative')
        if noise_ratio <= 1:
            raise ValueError('noise ratio must exceed 1')
        self.silence = float(silence)
        self.minimum_speech = float(minimum_speech)
        self.calibration = float(calibration)
        self.noise_ratio = float(noise_ratio)
        self.absolute = float(absolute)
        self.max_floor = float(max_floor)
        self.reset()

    def reset(self):
        """Forget the current utterance; the detector is reusable afterwards."""
        self.floor = None
        self.elapsed = 0.0
        self.heard = 0.0
        self.quiet = 0.0
        self.finished = False

    def threshold(self):
        floor = self.floor if self.floor is not None else 0.0
        return max(self.absolute, floor * self.noise_ratio)

    def feed(self, level, seconds=0.05):
        """Consume one frame and report whether speech just ended.

        Returns ``True`` at most once per utterance. Unusable samples (NaN,
        infinities, negative values) are ignored instead of ending a recording.
        """
        if self.finished:
            return False
        try:
            level = float(level)
            seconds = float(seconds)
        except (TypeError, ValueError):
            return False
        if not math.isfinite(level) or not math.isfinite(seconds):
            return False
        if level < 0 or not seconds > 0:
            return False
        if self.floor is None:
            # A loud first frame must not set an unreachable threshold, so the
            # estimate starts capped instead of at the observed level.
            self.floor = min(level, self.max_floor)
        limit = self.threshold()
        if level > limit:
            self.heard += seconds
            self.quiet = 0.0
        else:
            if self.elapsed < self.calibration:
                self.floor = min(self.floor, level)
            else:
                # Ambient tracking: follow a quieter room, never chase speech.
                self.floor = min(self.max_floor, .98 * self.floor + .02 * level)
            if self.heard > 0:
                self.quiet += seconds
        self.elapsed += seconds
        if self.heard >= self.minimum_speech and self.quiet >= self.silence:
            self.finished = True
            return True
        return False
