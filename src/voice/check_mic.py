import pyaudio
p = pyaudio.PyAudio()
print("\n🎤 系統偵測到的錄音設備有：")
for i in range(p.get_device_count()):
    info = p.get_device_info_by_index(i)
    if info['maxInputChannels'] > 0:
        print(f"設備 ID [{i}]: {info['name']}")