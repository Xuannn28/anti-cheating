
from pydub import AudioSegment

class AudioTracker: 
    def __init__(self):
        pass 

    def _convert_to_wav(self, input_path, output_path="processed_audio.wav"):
        """Standardizes input audio into 16kHz Mono WAV format."""
        sound = AudioSegment.from_file(input_path)
        sound = sound.set_frame_rate(16000).set_channels(1)
        sound.export(output_path, format="wav")
        return output_path
    
    def analyze_audio_chunk(self, raw_audio_path):
        pass
