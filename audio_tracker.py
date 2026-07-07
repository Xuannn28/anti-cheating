
import os 
import torch 
import numpy as np
from config import APP_CONFIG
from pydub import AudioSegment
from faster_whisper import WhisperModel  # OpenAI speech2text model
from transformers import GPT2LMHeadModel, GPT2Tokenizer # OpenAI GPT-2 language model

class AudioTracker: 
    def __init__(self, config):
        # initialize speech2text model 
        self.stt_model = WhisperModel("base", device="cpu", compute_type="float32")

        # initialize local perplexity tokenizer and model 
        self.tokenizer = GPT2Tokenizer.from_pretrained("gpt2")
        self.perplexity_model = GPT2LMHeadModel.from_pretrained("gpt2")
        self.perplexity_model.eval()

        # load configuration details
        self.config = config 
        self.ppl_threshold = config['detection']['audio']['perplexity_threshold']
        self.min_w_count = config['detection']['audio']['min_word_count']

    def _convert_to_wav(self, input_path, output_path="processed_audio.wav"):
        """Standardizes input audio into 16kHz Mono WAV format for AI model later."""
        sound = AudioSegment.from_file(input_path)

        # strip out background noise and cut data size by dropping extra stereo (left&right) channel
        sound = sound.set_frame_rate(16000).set_channels(1)
        sound.export(output_path, format="wav")
        return output_path
    
    def analyze_audio_chunk(self, raw_audio_path):
        """Processes audio chunk: convert , transcribe, and scores perplexity"""
        temp_wav = "processed_chunk.wav"
        try: 
            # convert format 
            self._convert_to_wav(raw_audio_path, temp_wav)

            # extract transcript string 
            # segments = list of dict where each indicates a short chunk of audio 
            #            with own start/end time and text
            segments, _ = self.stt_model.transcribe(temp_wav, beam_size=5, vad_filter=True)
            transcript = " ".join([segment.text for segment in segments]).strip()

            if not transcript or len(transcript.split()) < self.min_w_count: 
                return {
                    "transcript": transcript, 
                    "perplexity": 0.0, 
                    "is_ai_generated": False
                }
            
            # calculate perplexity score 
            # return_tensors = pt format output as PyTorch tensor for transformer model later
            inputs = self.tokenizer(transcript, return_tensors="pt")
            input_ids = inputs["input_ids"]

            # run model inference process by disabling gradient tracking for optimization
            with torch.no_grad():
                outputs = self.perplexity_model(input_ids, labels=input_ids)
                
                # CE loss for guessing wrong on next token based on labels as answer sheets
                loss = outputs.loss.item()
            
            perplexity = float(np.exp(loss))

            # Determine if text patterns match predictable AI generation structures
            # low value = model easily predict the token, less surprised
            is_ai = perplexity < self.ppl_threshold
            
            return {
                "transcript": transcript,
                "perplexity": round(perplexity, 2),
                "is_ai_generated": is_ai
            }
        
        except Exception as e:
            return {"error": f"Audio processing failed: {str(e)}"}
        finally:
            # Clean up the temporary file from disk cache
            if os.path.exists(temp_wav):
                os.remove(temp_wav)

if __name__ == "__main__":
    # Create a quick test audio recording of yourself (10-15 seconds)
    # Save it in this exact folder and put the filename below
    TEST_FILE = "my_interview_sample.mp3" 
    
    print("Initializing AudioTracker class...")
    tracker = AudioTracker()
    print("Models loaded successfully!\n")
    
    if not os.path.exists(TEST_FILE):
        print(f"❌ ERROR: Could not find '{TEST_FILE}' in this folder.")
        print("Please drop a short test audio file here to check your pipeline.")
    else:
        print(f"🔄 Starting analysis on: {TEST_FILE}...")
        results = tracker.analyze_audio_chunk(TEST_FILE)
        
        print("\n================ TEST RESULTS ================")
        if "error" in results:
            print(f"💥 Pipeline Failed: {results['error']}")
        else:
            print(f"📝 Captured Transcript:\n   \"{results['transcript']}\"\n")
            print(f"📊 Calculated Perplexity: {results['perplexity']}")
            print(f"🚨 Flagged as AI Script?:  {results['is_ai_generated']}")
        print("==============================================")