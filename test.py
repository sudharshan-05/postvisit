from transformers import AutoModel
import torchaudio
import torch

model = AutoModel.from_pretrained(
    "ai4bharat/indic-conformer-600m-multilingual",
    trust_remote_code=True
)

audio, sample_rate = torchaudio.load("test.wav")

# Convert to mono
audio = torch.mean(audio, dim=0, keepdim=True)

# Model expects 16 kHz
if sample_rate != 16000:
    resampler = torchaudio.transforms.Resample(
        sample_rate,
        16000
    )
    audio = resampler(audio)

result = model(audio, "ta", "ctc")

print(result)