import mido

# Replace with the detected MIDI output port name
midi_port_name = "CASIO USB-MIDI 0"

# Open the MIDI input port to listen for messages
with mido.open_input(midi_port_name) as port:
    print(f"Listening for MIDI messages from {midi_port_name}... Press keys on your keyboard.")

    # Print incoming messages in real-time
    for msg in port:
        print(msg)
