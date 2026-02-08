#!/bin/bash

# Start virtual display
Xvfb :99 -screen 0 1920x1080x24 &
export DISPLAY=:99

# Start PulseAudio
rm -rf /var/run/pulse /var/lib/pulse /root/.config/pulse

# Fix PulseAudio "Access denied" by allowing anonymous auth
# This is safe in a container
if ! grep -q "auth-anonymous=1" /etc/pulse/system.pa; then
    echo "load-module module-native-protocol-unix auth-anonymous=1" >> /etc/pulse/system.pa
fi

pulseaudio -D --exit-idle-time=-1 --system --disallow-exit

# Wait for PulseAudio to be ready
echo "Waiting for PulseAudio..."
for i in {1..10}; do
    if pactl info > /dev/null 2>&1; then
        echo "PulseAudio is ready."
        break
    fi
    sleep 1
done

# Create a dummy sink to capture audio if no hardware device is present
pactl load-module module-null-sink sink_name=virtual_sink sink_properties=device.description=Virtual_Sink
pactl set-default-sink virtual_sink
pactl set-default-source virtual_sink.monitor

# Small wait to ensure Xvfb starts
sleep 2

# Run your app
exec python -u -m src.main "$@"
