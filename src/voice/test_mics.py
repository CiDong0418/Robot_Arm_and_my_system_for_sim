import pyaudio
p = pyaudio.PyAudio()
for i in range(p.get_device_count()):
    info = p.get_device_info_by_index(i)
    if info['maxInputChannels'] > 0:
        try:
            s = p.open(rate=16000, channels=1, format=pyaudio.paInt16, input=True, frames_per_buffer=1280, input_device_index=i)
            print(f"Device {i} ({info['name']}) OK")
            s.close()
        except Exception as e:
            print(f"Device {i} ({info['name']}) FAILED: {e}")
try:
    s = p.open(rate=16000, channels=1, format=pyaudio.paInt16, input=True, frames_per_buffer=1280)
    print("Default OK")
    s.close()
except:
    pass
p.terminate()
